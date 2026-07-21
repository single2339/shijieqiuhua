"""OSINT Weibo MCP Server — 微博搜索、用户信息、时间线。

需要设置环境变量:
  WEIBO_COOKIE      — 浏览器登录后的 Cookie 字符串 (必需)
  WEIBO_COOKIE_FILE — 或指定 Cookie 文件路径 (每行一个 Cookie: name=value)

Run:  python backend/mcp_servers/osint_weibo/server.py
Stdio transport.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "osint-weibo",
    instructions="OSINT微博情报工具 — 搜索、用户信息、时间线。需要微博Cookie认证。",
)

_REQUEST_TIMEOUT = 20.0
_RETRY_COUNT = 3
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
_WEIBO_SEARCH = "https://s.weibo.com/weibo"
_WEIBO_USER_INFO = "https://weibo.com/ajax/profile/info"
_WEIBO_USER_TIMELINE = "https://weibo.com/ajax/statuses/mymblog"


# ── Cookie management ────────────────────────────────────────────

def _load_cookies() -> str:
    """Load Weibo cookies from env or file."""
    cookie = os.getenv("WEIBO_COOKIE", "")
    if cookie:
        return cookie

    cookie_file = os.getenv("WEIBO_COOKIE_FILE", "")
    if cookie_file and Path(cookie_file).exists():
        lines = Path(cookie_file).read_text().strip().splitlines()
        pairs = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                pairs.append(line)
        return "; ".join(pairs)

    return ""


def _cookie_header() -> dict[str, str]:
    cookie = _load_cookies()
    if cookie:
        return {"Cookie": cookie}
    return {}


# ── Retry helper ─────────────────────────────────────────────────

async def _retry_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = _REQUEST_TIMEOUT,
    max_retries: int = _RETRY_COUNT,
) -> httpx.Response | None:
    base_headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/",
    }
    cookie_h = _cookie_header()
    all_headers = {**base_headers, **cookie_h, **(headers or {})}

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                r = await client.get(url, params=params, headers=all_headers)
                return r
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                await asyncio.sleep(delay)

    return None


# ── Tool: 微博搜索 ───────────────────────────────────────────────

@mcp.tool()
async def weibo_search(query: str, max_results: int = 20) -> dict:
    """搜索微博内容（实时搜索）。

    需要设置环境变量 WEIBO_COOKIE（从浏览器开发者工具复制 Cookie）。

    Args:
        query: 搜索关键词
        max_results: 最大结果数，默认20
    """
    if not _load_cookies():
        return _fallback_search(query, max_results)

    params = {
        "q": query,
        "typeall": "1",
        "suball": "1",
        "timescope": "custom:最近7天:2026-05-18-0:2026-05-25-23",
        "Refer": "g",
        "page": "1",
    }

    resp = await _retry_get(_WEIBO_SEARCH, params=params)
    if resp is None or resp.status_code != 200:
        return _fallback_search(query, max_results)

    html = resp.text
    posts = _parse_weibo_search_results(html, max_results)

    return {
        "query": query,
        "platform": "微博",
        "results": posts,
        "count": len(posts),
        "method": "direct",
    }


def _parse_weibo_search_results(html: str, max_results: int) -> list[dict]:
    """Parse Weibo search results from HTML."""
    posts: list[dict] = []
    card_pattern = re.compile(
        r'<div class="card-wrap".*?</div>\s*</div>\s*</div>\s*</div>',
        re.DOTALL,
    )
    cards = card_pattern.findall(html)

    for card in cards[:max_results]:
        post = _parse_weibo_card(card)
        if post:
            posts.append(post)
    return posts


def _parse_weibo_card(card: str) -> dict | None:
    """Parse a single Weibo card HTML."""
    mid_match = re.search(r'mid="(\d+)"', card)
    if not mid_match:
        return None

    text = ""
    text_match = re.search(r'<p[^>]*class="[^"]*txt[^"]*"[^>]*>(.*?)</p>', card, re.DOTALL)
    if text_match:
        text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip()
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    user = ""
    user_match = re.search(r'nick-name="([^"]+)"', card)
    if user_match:
        user = user_match.group(1)

    uid = ""
    uid_match = re.search(r'href="/([^"]+)"', card)
    if uid_match:
        uid = uid_match.group(1)

    post_time = ""
    time_match = re.search(r'<a[^>]*href="[^"]*\d{4}-\d{2}-\d{2}[^"]*"[^>]*>(.*?)</a>', card)
    if time_match:
        post_time = time_match.group(1).strip()

    stats = {"reposts": 0, "comments": 0, "likes": 0}
    for key, pattern in [
        ("reposts", r'转发[:\s]*(\d+)'),
        ("comments", r'评论[:\s]*(\d+)'),
        ("likes", r'赞[:\s]*(\d+)'),
    ]:
        m = re.search(pattern, card)
        if m:
            stats[key] = int(m.group(1)) if m.group(1).isdigit() else _parse_count(m.group(1))

    return {
        "mid": mid_match.group(1),
        "text": text[:500],
        "user": user,
        "user_url": f"https://weibo.com/{uid}" if uid else "",
        "time": post_time,
        "url": f"https://weibo.com/{mid_match.group(1)}",
        "stats": stats,
    }


def _parse_count(s: str) -> int:
    """Parse Weibo count strings like '1.2万' or '1234'."""
    s = s.strip()
    if "万" in s:
        try:
            return int(float(s.replace("万", "")) * 10000)
        except ValueError:
            return 0
    try:
        return int(s)
    except ValueError:
        return 0


# ── Tool: 微博用户信息 ───────────────────────────────────────────

@mcp.tool()
async def weibo_user(uid_or_url: str) -> dict:
    """获取微博用户信息（昵称、简介、粉丝数、关注数、认证信息）。

    需要设置环境变量 WEIBO_COOKIE。

    Args:
        uid_or_url: 微博用户ID（数字）或用户主页URL
    """
    uid = _extract_uid(uid_or_url)
    if not uid:
        return {"error": "无法提取用户ID", "input": uid_or_url}

    if not _load_cookies():
        return {"error": "未设置WEIBO_COOKIE环境变量", "uid": uid}

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://weibo.com/u/{uid}",
    }
    resp = await _retry_get(
        _WEIBO_USER_INFO,
        params={"uid": uid},
        headers=headers,
    )

    if resp is None or resp.status_code != 200:
        return {"error": f"获取用户信息失败 (HTTP {resp.status_code if resp else 'timeout'})", "uid": uid}

    try:
        data = resp.json()
        user_data = data.get("data", {}).get("user", {})
    except Exception:
        return {"error": "JSON解析失败", "uid": uid, "raw": resp.text[:500]}

    return {
        "uid": uid,
        "screen_name": user_data.get("screen_name", ""),
        "description": user_data.get("description", ""),
        "followers_count": user_data.get("followers_count", 0),
        "follow_count": user_data.get("follow_count", 0),
        "statuses_count": user_data.get("statuses_count", 0),
        "verified": user_data.get("verified", False),
        "verified_reason": user_data.get("verified_reason", ""),
        "location": user_data.get("location", ""),
        "gender": user_data.get("gender", ""),
        "profile_url": f"https://weibo.com/u/{uid}",
        "avatar": user_data.get("avatar_hd", user_data.get("profile_image_url", "")),
        "created_at": user_data.get("created_at", ""),
    }


# ── Tool: 微博用户时间线 ─────────────────────────────────────────

@mcp.tool()
async def weibo_timeline(uid_or_url: str, page: int = 1, count: int = 20) -> dict:
    """获取微博用户的最新帖子时间线。

    需要设置环境变量 WEIBO_COOKIE。

    Args:
        uid_or_url: 微博用户ID（数字）或用户主页URL
        page: 页码，从1开始
        count: 每页帖子数，默认20
    """
    uid = _extract_uid(uid_or_url)
    if not uid:
        return {"error": "无法提取用户ID", "input": uid_or_url}

    if not _load_cookies():
        return {"error": "未设置WEIBO_COOKIE环境变量", "uid": uid}

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://weibo.com/u/{uid}",
    }
    resp = await _retry_get(
        _WEIBO_USER_TIMELINE,
        params={"uid": uid, "page": str(page), "feature": "0"},
        headers=headers,
    )

    if resp is None or resp.status_code != 200:
        return {"error": f"获取时间线失败 (HTTP {resp.status_code if resp else 'timeout'})", "uid": uid}

    try:
        data = resp.json()
        posts_data = data.get("data", {}).get("list", [])
    except Exception:
        return {"error": "JSON解析失败", "uid": uid}

    posts: list[dict] = []
    for post in posts_data[:count]:
        posts.append({
            "mid": post.get("mid", post.get("id", "")),
            "text": re.sub(r'<[^>]+>', '', post.get("text_raw", post.get("text", "")))[:500],
            "created_at": post.get("created_at", ""),
            "source": post.get("source", ""),
            "reposts_count": post.get("reposts_count", 0),
            "comments_count": post.get("comments_count", 0),
            "attitudes_count": post.get("attitudes_count", 0),
            "url": f"https://weibo.com/{uid}/{post.get('mid', '')}" if post.get("mid") else "",
        })

    return {
        "uid": uid,
        "page": page,
        "posts": posts,
        "count": len(posts),
    }


def _extract_uid(uid_or_url: str) -> str:
    """Extract numeric Weibo UID from various input formats."""
    s = uid_or_url.strip()
    if re.match(r"^\d+$", s):
        return s
    m = re.search(r'/u/(\d+)', s)
    if m:
        return m.group(1)
    m = re.search(r'weibo\.com/(\d+)', s)
    if m:
        return m.group(1)
    return ""


# ── Fallback ─────────────────────────────────────────────────────

def _fallback_search(query: str, max_results: int) -> dict:
    return {
        "query": query,
        "platform": "微博",
        "results": [],
        "count": 0,
        "method": "fallback",
        "error": "未配置WEIBO_COOKIE环境变量，无法直接搜索微博",
        "suggestions": [
            "1. 从浏览器开发者工具复制微博Cookie，设置 export WEIBO_COOKIE='...'",
            f"2. 使用搜索引擎代替: 在百度/Bing搜索 'site:weibo.com {query}'",
            "3. 将Cookie保存到文件并设置 export WEIBO_COOKIE_FILE=/path/to/cookies.txt",
        ],
        "search_url": f"https://s.weibo.com/weibo?q={quote(query)}",
    }


# ── Entry Point ──────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

"""Web search adapter.

Primary backend: Sogou (www.sogou.com) HTML scraping — free, no API key, no
quota, no captcha wall, and (unlike Bing/DDG from a mainland China server)
returns relevant un-tampered results for both English and Chinese queries.
Bing from a China-region IP was tested and rejected: the GFW silently swaps
in unrelated decoy results (e.g. "Hobby Lobby") instead of erroring, which is
worse than returning nothing. DDG is blocked outright from China.

Fallback: DuckDuckGo HTML scraping — only matters for non-China deployments;
returns nothing when run from a mainland IP, so the pipeline degrades to "no
search evidence" rather than serving wrong results.

Both return the same shape: [{title, url, snippet}, ...].
"""
from __future__ import annotations

import logging
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
SOGOU_SEARCH_URL = "https://www.sogou.com/web"
BING_SEARCH_URL = "https://www.bing.com/search"
MAX_RESULTS = 5
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# High-signal football preview/stats domains, applied as a site: filter.
PREVIEW_DOMAINS = [
    "theanalyst.com",
    "sportsmole.co.uk",
    "rotowire.com",
    "si.com",
    "goal.com",
    "espn.com",
]


def search(
    query: str,
    *,
    max_results: int = MAX_RESULTS,
    include_domains: list[str] | None = None,
    prefer: str = "auto",
) -> list[dict[str, str]]:
    """Return [{title, url, snippet}, ...].

    prefer="auto": Bing first, Sogou fallback, DDG last resort.
    prefer="ddg": DDG only.
    prefer="sogou": Sogou only without domain filters.
    prefer="bing": Bing only.
    """
    if prefer == "ddg":
        return _ddg_search(query, max_results)
    if prefer == "sogou":
        return _sogou_search(query, max_results, include_domains=None)
    if prefer == "bing":
        return _bing_search(query, max_results)

    # auto: Bing first (Sogou anti-spider blocks our server IP), then
    # Sogou, then DDG.
    results = _bing_search(query, max_results)
    if results:
        return results
    results = _sogou_search(query, max_results, include_domains)
    if results:
        return results
    return _ddg_search(query, max_results)


def _scoped_query(query: str, include_domains: list[str] | None) -> str:
    if not include_domains:
        return query
    sites = " OR ".join(f"site:{d}" for d in include_domains)
    return f"{query} ({sites})"


def _sogou_search(
    query: str,
    max_results: int,
    include_domains: list[str] | None,
) -> list[dict[str, str]]:
    try:
        resp = httpx.get(
            SOGOU_SEARCH_URL,
            params={"query": _scoped_query(query, include_domains)},
            headers=_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("sogou search %r failed: %s", query, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict[str, str]] = []
    for item in soup.select(".vrwrap")[:max_results]:
        title_el = item.select_one("h3 a") or item.select_one("a")
        if title_el is None or not title_el.get_text(strip=True):
            continue
        snippet_el = item.select_one(".str_info") or item.select_one(".space-txt")
        results.append({
            "title": title_el.get_text(strip=True),
            "url": _resolve_sogou_url(title_el.get("href") or ""),
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


def _resolve_sogou_url(href: str) -> str:
    """Sogou wraps most results in /link?url=<opaque token>, a JS-redirect
    landing page (works fine in a real browser). Follow it once to get the
    real article URL so evidence citations point somewhere useful.
    """
    if not href:
        return href
    full = href if href.startswith("http") else f"https://www.sogou.com{href}"
    if "sogou.com/link" not in full:
        return full
    try:
        resp = httpx.get(full, headers=_HEADERS, timeout=8, follow_redirects=True)
        match = re.search(r"location\.replace\(\"([^\"]+)\"\)", resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        log.warning("sogou link resolve %r failed: %s", href, e)
    return full


def _ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    try:
        resp = httpx.get(
            DDG_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("ddg search %r failed: %s", query, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict[str, str]] = []
    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__a")
        snippet_el = result.select_one(".result__snippet")
        if title_el is None:
            continue
        results.append({
            "title": title_el.get_text(strip=True),
            "url": _resolve_ddg_url(title_el.get("href") or ""),
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


def _resolve_ddg_url(href: str) -> str:
    """DDG HTML results link through /l/?uddg=<encoded target>; unwrap it."""
    parsed = urllib.parse.urlparse(href)
    if parsed.path == "/l/":
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        return target or href
    return href


def _bing_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Scrape Bing search results. Works from mainland China."""
    try:
        resp = httpx.get(
            BING_SEARCH_URL,
            params={"q": query, "count": max_results},
            headers=_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("bing search %r failed: %s", query, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict[str, str]] = []
    for item in soup.select("li.b_algo")[:max_results]:
        title_el = item.select_one("h2 a")
        if title_el is None:
            continue
        snippet_el = item.select_one(".b_caption p") or item.select_one("p")
        results.append({
            "title": title_el.get_text(strip=True),
            "url": title_el.get("href") or "",
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results

"""LLM synthesis layer — turn multi-source collected evidence into a
structured OSINT-style match prediction (the format a human analyst produces).

Input is the evidence already gathered by the pipeline (web search previews,
dongqiudi fundamentals, weather). Output is a Chinese report:
方向研判 → 置信度(L1-L5) → 确认事实(带来源) → 替代解释 → 数据缺口.

Returns "" when there's no usable evidence or no LLM key, so the caller can
fall back to the template/osint_qa path.
"""
from __future__ import annotations

import logging
import os

import httpx

from ..models import FootballOsintJob

log = logging.getLogger(__name__)

_TIMEOUT = 45.0
# Topics worth feeding the synthesizer (skip the bare fixture row).
_USEFUL_PREFIXES = ("search.", "fundamental.", "weather.", "user.note")

_SYSTEM = (
    "你是足球情报分析师。基于下面提供的【多源赛前情报】，产出一份结构化中文研判报告。\n"
    "严格按以下结构输出（用这些小标题）：\n"
    "【方向研判】给出一个明确的方向性结论（主胜/客胜/平局倾向/主队不败 等），不要回避。\n"
    "【置信度】给 L1-L5 并说明依据：L1=≥3个独立来源交叉确认，L2=2个来源，L3=1个来源，L4=仅间接证据/实力先验，L5=来源矛盾。\n"
    "【确认事实】逐条列出，每条结尾标注来源（用情报里给的来源名/域名）。只写情报里出现的事实。\n"
    "【替代解释】列出 1-3 条可能推翻结论的变数（伤停、轮换、裁判、爆冷先例等）。\n"
    "【数据缺口】列出还缺什么关键数据。\n\n"
    "硬性规则：\n"
    "- 即使数据不足也要给出方向性结论，但要在置信度里诚实标注偏低。\n"
    "- 不得编造情报中没有的具体数字、比分、引述（可给方向和大致区间）。\n"
    "- 不要给出投注建议。"
)


def synthesize(job: FootballOsintJob, question: str = "") -> str:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    if not api_key:
        return ""

    evidence_lines = _format_evidence(job)
    if not evidence_lines:
        return ""  # nothing collected → let caller fall back

    match_ctx = (
        f"{job.match.home_team} vs {job.match.away_team}，"
        f"{job.match.competition or '赛事未指定'}，开球：{job.match.kickoff_at or '未知'}"
    )
    user = (
        f"比赛：{match_ctx}\n"
        f"用户关注的问题：{question or '总体研判'}\n\n"
        f"多源赛前情报（每条：[来源] 正文）：\n{evidence_lines}"
    )

    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("match_report synthesis failed: %s", e)
        return ""


def _format_evidence(job: FootballOsintJob, limit: int = 20) -> str:
    lines: list[str] = []
    for ev in job.evidence:
        if not ev.topic.startswith(_USEFUL_PREFIXES):
            continue
        body = (ev.raw_excerpt or ev.claim or "").strip()
        if not body:
            continue
        src = ev.source or ev.topic
        tag = f"{src}" + (f" | {ev.url}" if ev.url else "")
        lines.append(f"[{tag}] {body[:500]}")
        if len(lines) >= limit:
            break
    return "\n".join(lines)

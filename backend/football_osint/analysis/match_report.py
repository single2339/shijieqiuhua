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
    "你是足球情报分析师。你的任务是**直接回答用户的具体问题**，而不是每次都套用固定模板。\n\n"
    "回答规范：\n"
    "1. 首先用 1-2 句话直接、明确地回答用户的问题（给出方向、倾向或判断），这是最重要的。\n"
    "2. 然后根据问题类型，选择性地提供以下内容（只写相关的，不必全写）：\n"
    "   - 支持你判断的关键事实（每条标注来源）\n"
    "   - 置信度判断（L1-L5）：L1=≥3个独立来源交叉确认，L2=2个来源，L3=1个来源，L4=间接证据，L5=来源矛盾\n"
    "   - 可能推翻结论的替代解释（1-2条）\n"
    "   - 还缺什么关键数据（1-2条）\n\n"
    "关键原则：\n"
    "- 回答要**针对问题**。问\"谁赢\"就重点分析胜负；问\"角球\"就重点分析角球趋势；问\"红黄牌\"就重点分析纪律风险。\n"
    "- 即使数据不足也要给出明确倾向，但标注可靠性低。\n"
    "- 涉及半场、角球、红黄牌、进球数等可量化的问题时，必须给出具体的预测数值或区间"
    "（例如\"全场角球预计9-11个\"\"黄牌预计3-5张\"），不能只给方向性描述而不给数字。\n"
    "- 问题如果要求预测比分（如\"全场比分预测是多少\"\"上半场比分预计是多少\"），必须直接给出一个具体的预测比分"
    "（例如\"预测全场2:1\"\"预测上半场1:0\"），不能只说\"小比分\"\"略占优势\"之类模糊描述，"
    "也不能用\"大约\"\"可能\"回避给出确切数字。\n"
    "- 这些数值是你结合情报和球队近期数据做出的预测判断，不是在引用情报原文，"
    "因此即使情报里没有现成数字也要给出你的预测值或预测区间。\n"
    "- 但不得把情报中不存在的内容包装成\"已确认的事实\"，也不得编造具体的历史比赛比分或引述来源。\n"
    "- 不要给出投注建议。\n"
    "- 回答像人类分析师在对话中回复，不要写\"情报摘要\"等公文标题。"
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
                "temperature": 0.5,  # moderate randomness so answers feel distinct
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

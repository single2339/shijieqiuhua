"""LLM-driven structured fact extraction from multi-source OSINT evidence.

factor_registry.py's scoring formulas (_form_score_from_records etc.) need
home/away recent-form W/D/L, H2H counts, absence counts, and standings rank
as plain numbers. Today those numbers only ever come from a handful of
regexes matched against dongqiudi's own structured text — search snippets,
RSS news, and user notes carry the same facts in free-text form that the
regexes never match. This module reads ALL of it in one LLM call and
extracts the same fields the regexes were trying to find, so the scoring
formulas get fed regardless of which source happened to phrase it.

Returns ``None`` on any failure (no key, network error, bad JSON, timeout)
so the caller can fall back to the existing regex path unchanged.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx

from ..models import FootballOsintJobRequest, OsintEvidence

log = logging.getLogger(__name__)

_TIMEOUT = 45.0
_USEFUL_PREFIXES = ("fundamental.", "search.", "news.rss.", "user.note")

_SYSTEM = (
    "你是足球数据抽取助手。给定一场比赛的多条赛前情报文本，抽取以下结构化字段，"
    "只返回一个 JSON 对象，不要任何额外文字：\n"
    '{"home_form": {"wins": int, "draws": int, "losses": int} 或 null,\n'
    ' "away_form": {"wins": int, "draws": int, "losses": int} 或 null,\n'
    ' "h2h_home_wins": int 或 null, "h2h_draws": int 或 null, "h2h_home_losses": int 或 null,\n'
    ' "home_absences": int 或 null, "away_absences": int 或 null,\n'
    ' "home_rank": int 或 null, "away_rank": int 或 null}\n'
    "home_form/away_form 是该队近期比赛的胜/平/负场次。h2h_* 是双方历史交锋中主队的胜/平/负场次。"
    "home_absences/away_absences 是因伤/停赛缺席的人数。home_rank/away_rank 是当前联赛或赛事积分榜排名。\n"
    "严格规则：只抽取证据文本中明确出现的数字，绝不推测或编造。某个字段在任何一条证据里都没有明确数字，"
    "就填 null。"
)


@dataclass
class ExtractedFacts:
    home_form: tuple[int, int, int] | None
    away_form: tuple[int, int, int] | None
    h2h_home_wins: int | None
    h2h_draws: int | None
    h2h_home_losses: int | None
    home_absences: int | None
    away_absences: int | None
    home_rank: int | None
    away_rank: int | None


def extract(
    evidence: list[OsintEvidence],
    request: FootballOsintJobRequest,
) -> ExtractedFacts | None:
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None

    body = _format_evidence(evidence)
    if not body:
        return None

    return _call_llm(api_key, body, request)


def _format_evidence(evidence: list[OsintEvidence], limit: int = 30) -> str:
    lines = []
    for ev in evidence:
        if not ev.topic.startswith(_USEFUL_PREFIXES):
            continue
        text = (ev.raw_excerpt or ev.claim or "").strip()
        if not text:
            continue
        lines.append(f"[{ev.source}] {text[:400]}")
    return "\n".join(lines[:limit])


def _call_llm(api_key: str, body: str, request: FootballOsintJobRequest) -> ExtractedFacts | None:
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    user = (
        f"主队：{request.home_team}，客队：{request.away_team}\n\n"
        f"赛前情报（每条：[来源] 正文）：\n{body}"
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
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return _parse(data)
    except Exception as e:
        log.warning("evidence extraction failed: %s", e)
        return None


def _parse(data: dict) -> ExtractedFacts:
    def _form(key: str) -> tuple[int, int, int] | None:
        v = data.get(key)
        if not isinstance(v, dict):
            return None
        try:
            return (int(v["wins"]), int(v["draws"]), int(v["losses"]))
        except (KeyError, TypeError, ValueError):
            return None

    def _int(key: str) -> int | None:
        v = data.get(key)
        return int(v) if isinstance(v, (int, float)) else None

    return ExtractedFacts(
        home_form=_form("home_form"),
        away_form=_form("away_form"),
        h2h_home_wins=_int("h2h_home_wins"),
        h2h_draws=_int("h2h_draws"),
        h2h_home_losses=_int("h2h_home_losses"),
        home_absences=_int("home_absences"),
        away_absences=_int("away_absences"),
        home_rank=_int("home_rank"),
        away_rank=_int("away_rank"),
    )

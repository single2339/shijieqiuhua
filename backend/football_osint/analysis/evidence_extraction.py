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
    ' "home_rank": int 或 null, "away_rank": int 或 null,\n'
    ' "_qualitative_inference": true 或 false}\n'
    "home_form/away_form 是该队近期比赛的胜/平/负场次。h2h_* 是双方历史交锋中主队的胜/平/负场次。"
    "home_absences/away_absences 是因伤/停赛缺席的人数。home_rank/away_rank 是当前联赛或赛事积分榜排名。\n\n"
    "抽取策略（按优先级）：\n"
    "1. 如果证据中有\"X胜Y平Z负\"等明确数字，直接抽取，_qualitative_inference 设为 false。\n"
    "2. 如果某个字段没有明确数字，但证据中有任何关于球队近期表现、实力、状态的描述\n"
    "   （包括但不限于：首轮结果、攻防表现、排名对比、实力优劣、球队士气等），\n"
    "   请根据上下文推断最合理的数字，并将 _qualitative_inference 设为 true。\n"
    "   推断参考：\n"
    "   - 表现强/优势明显/大胜/实力碾压 → 近期约 4胜1平0负\n"
    "   - 表现不错/占优/状态良好 → 近期约 3胜1平1负\n"
    "   - 表现一般/互有优劣 → 近期约 2胜2平1负\n"
    "   - 首轮惨败/表现不佳/实力不济/防线漏洞 → 近期约 1胜1平3负\n"
    "   - 有伤病/缺席报道但未明确人数 → 约 2 人缺席\n"
    "   - 排名靠前/FIFA排名明显优于对手 → 排名约 2-4 位或低于对手30位以上\n"
    "   - 排名靠后/FIFA排名明显低于对手 → 排名约 15-18 位或高于对手30位以上\n"
    "⚠️ 重要：home_form 和 away_form 是必须字段，即使证据只提到其中一队，两队都要给出估计：\n"
    "   - 证据充分的一方给出精确推断，证据稀疏的一方根据实力定位推断\n"
    "   - \"世界杯新军/实力一般/亚洲球队\" → 近期约 2胜1平2负 或更差\n"
    "   - \"欧洲劲旅/夺冠热门/强队\" → 近期约 4胜1平0负 或 3胜2平0负\n"
    "   - 只要有最基本的球队定位描述（强队/弱队/新军/劲旅），就必须给出估计值\n"
    "3. 如果所有证据中完全没有任何关于两队的信息，对应字段才填 null。"
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
    qualitative_inference: bool = False


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
        qualitative_inference=bool(data.get("_qualitative_inference", False)),
    )

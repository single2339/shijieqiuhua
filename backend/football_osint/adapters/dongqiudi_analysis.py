"""Dongqiudi (懂球帝) match analysis adapter — replaces win007_baseface.

The mobile match-analysis page embeds a React SSR state blob
(``window.__INITIAL_STATE__=<JSON>``) containing battle history, recent
form, standings and sideline (missing-player) data for both teams.

Odds fields (``has_odds``, ``asia_companys``, ``euro_companys``) are
intentionally never read here — they must not leak into evidence text.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from ..analysis import report as report_module
from ..evidence import append_evidence
from ..models import FootballOsintJobRequest, OsintEvidence
from .url_safety import valid_urls
from .. import cache

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}

_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*")
_MATCH_ID_RE = re.compile(r"/matchDetail/(\d+)/")


def analysis_url(match_id: str) -> str:
    return f"https://m.dongqiudi.com/matchDetail/{match_id}/analysis"


def fetch_text(url: str) -> str | None:
    """Fetch a URL with mobile UA headers, return decoded text or None."""
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=DEFAULT_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        log.warning("dongqiudi_analysis fetch %s failed: %s", url, e)
        return None
    return resp.text


def fetch_url(
    url: str,
    *,
    source_type: str,
    topic: str,
    source_label: str,
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
) -> tuple[str, str]:
    """Fetch the analysis page, mint an evidence row. Cached per match_id.

    Extracts dongqiudi match_id from the URL.
    """
    match_id = _MATCH_ID_RE.search(url)
    ck = cache.analysis_key(match_id.group(1)) if match_id else cache.analysis_key(url)
    excerpt = cache.analysis_cache.get(ck)
    if excerpt is None:
        if not valid_urls([url]):
            return "", f"{url}: blocked by url allowlist/DNS check"
        html = fetch_text(url)
        if html is None:
            return "", f"{url}: fetch failed"
        state = _extract_initial_state(html)
        if state is None:
            return "", f"{url}: failed to parse __INITIAL_STATE__"
        summary = summarize_analysis(state)
        if not summary:
            return "", f"{url}: empty analysis"
        excerpt = report_module.compact_markdown(summary)
        cache.analysis_cache.set(ck, excerpt)
    evidence_id = append_evidence(
        evidence,
        source=source_label,
        source_type=source_type,
        claim=report_module.claim_from_markdown(request, excerpt, source_label),
        topic=topic,
        side="neutral",
        confidence=0.45,
        raw_excerpt=excerpt,
        url=url,
    )
    return evidence_id, ""


def _extract_initial_state(html: str) -> dict | None:
    match = _STATE_RE.search(html)
    if not match:
        return None
    start = match.end()
    depth = 0
    for i in range(start, len(html)):
        char = html[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def summarize_analysis(state: dict) -> str:
    """Plain-text summary of battle history / recent form / standings / sideline.

    Deliberately does not read has_odds / asia_companys / euro_companys.
    """
    info = state.get("matchContentStore", {}).get("matchAnalysisData", {}).get("info") or {}
    team_a = info.get("team_A", "")
    team_b = info.get("team_B", "")
    lines: list[str] = []

    battle = info.get("battle_history") or {}
    a_record, b_record = battle.get("team_A"), battle.get("team_B")
    if a_record and b_record:
        lines.append(
            f"历史交锋：{team_a} {a_record.get('win', 0)}胜{a_record.get('draw', 0)}平{a_record.get('lose', 0)}负，"
            f"{team_b} {b_record.get('win', 0)}胜{b_record.get('draw', 0)}平{b_record.get('lose', 0)}负"
        )

    recent = info.get("recent_record") or {}
    for team_name, key in ((team_a, "team_A"), (team_b, "team_B")):
        records = recent.get(key) or []
        if not records:
            continue
        counts = {"win": 0, "draw": 0, "lose": 0}
        for rec in records:
            color = rec.get("color")
            if color in counts:
                counts[color] += 1
        lines.append(f"{team_name}近期战绩：{counts['win']}胜{counts['draw']}平{counts['lose']}负（近{len(records)}场）")

    cup_table = info.get("cup_table") or {}
    rows = [
        f"{row.get('name')} 第{row.get('rank')}名 {row.get('points')}分"
        for row in (cup_table.get("list") or [])
        if row.get("name") in (team_a, team_b)
    ]
    if rows:
        lines.append(f"{cup_table.get('name', '积分榜')}：" + "；".join(rows))
    else:
        lines.append("积分榜：无排名数据")

    sideline = info.get("sideline") or {}
    side_a = len(sideline.get("team_A") or [])
    side_b = len(sideline.get("team_B") or [])
    lines.append(f"伤停信息：{team_a} {side_a} 人缺席，{team_b} {side_b} 人缺席")

    return "\n".join(lines)

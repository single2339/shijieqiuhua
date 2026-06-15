"""Dongqiudi (懂球帝) schedule adapter — replaces win007_schedule.

``https://api.dongqiudi.com/data/tab/new/soccer`` is a public, unauthenticated
JSON endpoint returning a rolling ~6 day window of soccer fixtures with
true UTC kickoff times.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx

from .. import cache

if TYPE_CHECKING:
    from ..evidence import OsintEvidence
    from ..models import FootballOsintJobRequest

log = logging.getLogger(__name__)

DONGQIUDI_SCHEDULE_URL = "https://api.dongqiudi.com/data/tab/new/soccer"

DEFAULT_TIMEOUT_SECONDS = 15.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}

# The "今日赛事" sidebar frames its 3-day window in Beijing time.
CST = timezone(timedelta(hours=8))

_STATUS_MAP = {
    "Fixture": "scheduled",
    "Played": "finished",
}


@dataclass(frozen=True)
class Fixture:
    match_id: str
    league: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    status: str
    home_score: int | None
    away_score: int | None


def fetch_fixtures() -> list[Fixture]:
    cached = cache.schedule_cache.get("fixtures")
    if cached is not None:
        return cached
    try:
        resp = httpx.get(DONGQIUDI_SCHEDULE_URL, headers=_HEADERS, timeout=DEFAULT_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        log.warning("dongqiudi_schedule fetch failed: %s", e)
        return cached if cached is not None else []
    fixtures = parse_schedule(payload)
    cache.schedule_cache.set("fixtures", fixtures)
    return fixtures


def parse_schedule(payload: dict) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for item in payload.get("list", []):
        if item.get("cmp_type") != "soccer":
            continue
        try:
            kickoff_at = datetime.strptime(
                f"{item['date_utc']} {item['time_utc']}", "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        fixtures.append(Fixture(
            match_id=item.get("match_id", ""),
            league=item.get("competition_name", ""),
            kickoff_at=kickoff_at,
            home_team=item.get("team_A_name", ""),
            away_team=item.get("team_B_name", ""),
            status=_STATUS_MAP.get(item.get("status", ""), "live"),
            home_score=_safe_int(item.get("fs_A")),
            away_score=_safe_int(item.get("fs_B")),
        ))
    return fixtures


def fixtures_in_range(fixtures: list[Fixture], days_ahead: int = 3) -> list[Fixture]:
    """Fixtures from yesterday (Beijing time) through `days_ahead` days from now.

    Includes the trailing 24 h so the sidebar never renders empty when the
    dongqiudi rolling window hasn't yet picked up the next matchday.  Status is
    derived from kickoff time because the dongqiudi tab API always returns
    ``"Fixture"`` regardless of whether the match is live or finished.
    """
    now = datetime.now(CST)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days_ahead + 2)
    return sorted(
        (_with_derived_status(f, now) for f in fixtures if start <= f.kickoff_at.astimezone(CST) < end),
        key=lambda f: f.kickoff_at,
    )


def _with_derived_status(fixture: Fixture, now: datetime) -> Fixture:
    """Derive live/finished from kickoff time when the API only says 'Fixture'.

    Heuristic: a match is live if kickoff ≤ now < kickoff + 2h30m, finished
    if now ≥ kickoff + 2h30m. Scores are preserved from the API when present.
    """
    kickoff_cst = fixture.kickoff_at.astimezone(CST)
    match_end = kickoff_cst + timedelta(minutes=150)

    if now < kickoff_cst:
        return fixture

    # API might have updated scores after full-time
    if fixture.home_score is not None and fixture.away_score is not None:
        return replace(fixture, status="finished")

    if now < match_end:
        return replace(fixture, status="live")

    return replace(fixture, status="finished")


def find_fixture(fixtures: list[Fixture], home_team: str, away_team: str) -> Fixture | None:
    """Resolve a fixture by (normalized) home/away team names."""
    home_norm, away_norm = _norm(home_team), _norm(away_team)
    if not home_norm or not away_norm:
        return None
    for f in fixtures:
        if _norm(f.home_team) == home_norm and _norm(f.away_team) == away_norm:
            return f
    return None


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", name).strip().lower()


def fetch_url(
    url: str,
    *,
    source_type: str,
    topic: str,
    source_label: str,
    request: "FootballOsintJobRequest",
    evidence: "list[OsintEvidence]",
) -> "tuple[str, str]":
    """Fetch schedule, find matching fixture, mint an evidence row.

    Mirrors win007_http.fetch_url's (evidence_id, failure_reason) signature.
    """
    from ..analysis import report as report_module
    from ..evidence import append_evidence

    fixtures = fetch_fixtures()
    fixture = find_fixture(fixtures, request.home_team, request.away_team)
    if not fixture:
        return "", f"dongqiudi schedule: no fixture for {request.home_team} vs {request.away_team}"

    summary = (
        f"懂球帝赛程确认：{fixture.league} {fixture.home_team} vs {fixture.away_team}，"
        f"{fixture.kickoff_at.strftime('%Y-%m-%d %H:%M UTC')}，状态{fixture.status}"
        + (f"，比分{fixture.home_score}-{fixture.away_score}" if fixture.home_score is not None else "")
    )
    excerpt = report_module.compact_markdown(summary)
    evidence_id = append_evidence(
        evidence,
        source=source_label,
        source_type=source_type,
        claim=report_module.claim_from_markdown(request, excerpt, source_label),
        topic=topic,
        side="neutral",
        confidence=0.55,
        raw_excerpt=excerpt,
        url=url,
    )
    return evidence_id, ""


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

"""football-data.org schedule adapter — upcoming fixtures for the sidebar.

Unlike the dongqiudi feed (which only carries recently-finished matches), the
football-data.org free tier returns real *future* fixtures, and its free
competition set is exactly the "important" leagues we want to surface
(五大联赛 / 欧冠 / 世界杯 / 欧洲杯 等). English names are translated to Chinese
via :mod:`name_translation`.

Requires ``FOOTBALL_DATA_API_KEY`` in the environment (free key from
https://www.football-data.org/). Without it, :func:`fetch_fixtures` returns an
empty list and logs a warning.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .. import cache
from . import name_translation

log = logging.getLogger(__name__)

FOOTBALL_DATA_URL = "https://api.football-data.org/v4/matches"
DEFAULT_TIMEOUT_SECONDS = 15.0

# The sidebar renders kickoff times in Beijing time.
CST = timezone(timedelta(hours=8))

_STATUS_MAP = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "SUSPENDED": "live",
    "FINISHED": "finished",
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
    provider: str = "football-data"
    provider_match_id: str = ""
    home_provider_id: str = ""
    away_provider_id: str = ""


def fetch_fixtures(days_ahead: int = 3) -> list[Fixture]:
    """Fetch fixtures from today through ``days_ahead`` days (UTC), cached 5 min."""
    today = datetime.now(timezone.utc).date()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=max(days_ahead, 0))).isoformat()
    return fetch_fixtures_for_range(date_from, date_to)


def fetch_fixtures_for_range(date_from: str, date_to: str) -> list[Fixture]:
    """Fetch fixtures for an explicit ``YYYY-MM-DD`` UTC date range, cached 5 min.

    Unlike ``fetch_fixtures`` (always "today + N days forward"), this accepts
    past dates too — used by track-record backfill to look up finished matches.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not api_key:
        log.warning("FOOTBALL_DATA_API_KEY not set; fixtures unavailable")
        return []

    cache_key = f"fd:{date_from}:{date_to}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            FOOTBALL_DATA_URL,
            params={"dateFrom": date_from, "dateTo": date_to},
            headers={"X-Auth-Token": api_key},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        log.warning("football-data fetch failed: %s", e)
        return cached if cached is not None else []

    fixtures = parse_matches(payload)
    cache.schedule_cache.set(cache_key, fixtures)
    return fixtures


def parse_matches(payload: dict) -> list[Fixture]:
    raw = payload.get("matches", [])

    # Collect every name up front so translation is a single batched call.
    names: list[str] = []
    for m in raw:
        names.append(_competition(m))
        names.append(_team(m, "homeTeam"))
        names.append(_team(m, "awayTeam"))
    name_map = name_translation.translate(names)

    fixtures: list[Fixture] = []
    for m in raw:
        kickoff = _parse_utc(m.get("utcDate"))
        if kickoff is None:
            continue
        full_time = (m.get("score") or {}).get("fullTime") or {}
        league_en = _competition(m)
        home_en = _team(m, "homeTeam")
        away_en = _team(m, "awayTeam")
        match_id = _payload_id(m.get("id"))
        home_provider_id = _payload_id((m.get("homeTeam") or {}).get("id"))
        away_provider_id = _payload_id((m.get("awayTeam") or {}).get("id"))
        fixtures.append(Fixture(
            match_id=match_id,
            league=name_map.get(league_en, league_en),
            kickoff_at=kickoff,
            home_team=name_map.get(home_en, home_en),
            away_team=name_map.get(away_en, away_en),
            status=_STATUS_MAP.get(m.get("status", ""), "scheduled"),
            home_score=full_time.get("home"),
            away_score=full_time.get("away"),
            provider_match_id=match_id,
            home_provider_id=home_provider_id,
            away_provider_id=away_provider_id,
        ))
    return fixtures


def upcoming(fixtures: list[Fixture]) -> list[Fixture]:
    """Fixtures kicking off now or later (plus any in-play), sorted by kickoff."""
    now = datetime.now(timezone.utc)
    return sorted(
        (f for f in fixtures if f.status == "live" or f.kickoff_at >= now),
        key=lambda f: f.kickoff_at,
    )


def _competition(match: dict) -> str:
    return (match.get("competition") or {}).get("name", "")


def _team(match: dict, side: str) -> str:
    return (match.get(side) or {}).get("name", "")


def _payload_id(value: object) -> str:
    return "" if value is None else str(value)


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

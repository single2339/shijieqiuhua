"""football-data.org stats adapter — structured form/H2H data.

Fetches recent match results and head-to-head records from football-data.org
to feed factor_registry with reliable structured data, bypassing regex/LLM
extraction entirely for form and H2H factors.

Requires ``FOOTBALL_DATA_API_KEY`` in the environment. Without it, all public
functions return None and log a warning once.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from .. import cache
from . import name_translation

log = logging.getLogger(__name__)

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
DEFAULT_TIMEOUT = 12.0
_LOGGED_KEY_MISSING = False

# Cache team ID lookups for 1 hour.
_team_id_cache: dict[str, int | None] = {}


def _headers() -> dict[str, str]:
    return {"X-Auth-Token": os.getenv("FOOTBALL_DATA_API_KEY", "")}


def _check_key() -> bool:
    global _LOGGED_KEY_MISSING
    if not os.getenv("FOOTBALL_DATA_API_KEY", ""):
        if not _LOGGED_KEY_MISSING:
            log.warning("FOOTBALL_DATA_API_KEY not set; football-data stats unavailable")
            _LOGGED_KEY_MISSING = True
        return False
    return True


@dataclass(frozen=True)
class TeamFormRecord:
    team_name: str          # Chinese name
    wins: int
    draws: int
    losses: int
    recent_count: int       # how many matches this is based on


@dataclass(frozen=True)
class H2HRecord:
    home_team: str
    away_team: str
    home_wins: int
    draws: int
    away_wins: int
    total_matches: int


def _find_team_id(team_name_cn: str) -> int | None:
    """Resolve a Chinese team name to a football-data.org team ID.

    Uses the name_translation cache for EN→CN reverse lookup, then searches
    the API. Result is cached in memory for 1 hour.
    """
    name_cn = team_name_cn.strip()
    if name_cn in _team_id_cache:
        return _team_id_cache[name_cn]

    en_name = name_translation.to_english(name_cn)
    # Try the English name from cache first; fall back to the Chinese name
    # if the cache doesn't have a mapping (e.g. already-English input).
    search_names = [en_name] if en_name != name_cn else [name_cn]
    # Also try without common suffixes
    for name in list(search_names):
        for suffix in (" FC", " CF", " SC", " United", " City"):
            if name.endswith(suffix):
                search_names.append(name[:-len(suffix)])

    for search in search_names:
        team_id = _search_team_api(search)
        if team_id is not None:
            _team_id_cache[name_cn] = team_id
            return team_id

    _team_id_cache[name_cn] = None
    return None


def _search_team_api(name: str) -> int | None:
    """Search /v4/teams?name=... and return the first matching ID."""
    try:
        resp = httpx.get(
            f"{FOOTBALL_DATA_URL}/teams",
            params={"name": name, "limit": 5},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        teams = resp.json().get("teams", [])
        if teams:
            return teams[0]["id"]
    except Exception as e:
        log.debug("team search %r failed: %s", name, e)
    return None


def fetch_team_form(team_name_cn: str, limit: int = 5) -> TeamFormRecord | None:
    """Fetch recent finished matches for a team and return W/D/L counts."""
    if not _check_key():
        return None

    team_id = _find_team_id(team_name_cn)
    if team_id is None:
        return None

    cache_key = f"fd_form:{team_id}:{limit}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            f"{FOOTBALL_DATA_URL}/teams/{team_id}/matches",
            params={"status": "FINISHED", "limit": limit},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
    except Exception as e:
        log.warning("team %d form fetch failed: %s", team_id, e)
        return None

    wins = draws = losses = 0
    for m in matches:
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        score = (m.get("score") or {}).get("fullTime") or {}
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue
        is_home = home.get("id") == team_id
        if home_goals > away_goals:
            wins += 1 if is_home else 0
            losses += 0 if is_home else 1
        elif home_goals < away_goals:
            losses += 1 if is_home else 0
            wins += 0 if is_home else 1
        else:
            draws += 1

    record = TeamFormRecord(
        team_name=team_name_cn,
        wins=wins,
        draws=draws,
        losses=losses,
        recent_count=len(matches),
    )
    cache.schedule_cache.set(cache_key, record)
    return record


def fetch_h2h(home_cn: str, away_cn: str) -> H2HRecord | None:
    """Return head-to-head record between two teams.

    Fetches recent finished matches for the home team and filters to matches
    against the away team. Uses the same team ID cache.
    """
    if not _check_key():
        return None

    home_id = _find_team_id(home_cn)
    away_id = _find_team_id(away_cn)
    if home_id is None or away_id is None:
        return None

    cache_key = f"fd_h2h:{home_id}:{away_id}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            f"{FOOTBALL_DATA_URL}/teams/{home_id}/matches",
            params={"status": "FINISHED", "limit": 30},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
    except Exception as e:
        log.warning("h2h fetch for teams %d/%d failed: %s", home_id, away_id, e)
        return None

    home_wins = draws = away_wins = 0
    for m in matches:
        h = m.get("homeTeam", {})
        a = m.get("awayTeam", {})
        if h.get("id") != home_id or a.get("id") != away_id:
            continue
        score = (m.get("score") or {}).get("fullTime") or {}
        hg = score.get("home")
        ag = score.get("away")
        if hg is None or ag is None:
            continue
        if hg > ag:
            home_wins += 1
        elif hg < ag:
            away_wins += 1
        else:
            draws += 1

    record = H2HRecord(
        home_team=home_cn,
        away_team=away_cn,
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
        total_matches=home_wins + draws + away_wins,
    )
    cache.schedule_cache.set(cache_key, record)
    return record

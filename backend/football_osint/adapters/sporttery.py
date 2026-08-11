"""中国体育彩票 API adapter — free, no key, real fixture + odds data.

Fetches match fixtures with HAD (胜平负) / HHAD (让球胜平负) odds from the
官方 sporttery.cn API.  This replaces football-data.org for fixture discovery
and provides market-consensus odds as a new prediction signal.

Data flow:
  sporttery.cn → fixture list + odds → pipeline evidence (market odds factor)
  sporttery.cn → finished matches → track_record settlement fallback

API docs: https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .. import cache
from ..analysis.market import normalize_decimal_odds, parse_home_handicap
from ..evidence import append_evidence
from ..models import FootballOsintJobRequest, OsintEvidence, OutcomeOdds, SportteryMarket

log = logging.getLogger(__name__)

URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry"
DEFAULT_TIMEOUT = 12.0
CST = timezone(timedelta(hours=8))

# API status → our status mapping
_STATUS_MAP = {
    "Selling": "scheduled",
    "Wait": "scheduled",
    "Live": "live",
    "End": "finished",
    "Stop": "finished",
}


@dataclass(frozen=True)
class SportteryFixture:
    """A single match from the sporttery API, normalised."""
    match_id: str               # sporttery internal ID (e.g. "2040327")
    home_team: str              # Chinese full name
    away_team: str              # Chinese full name
    league: str                 # Chinese league name
    kickoff_at: datetime        # CST datetime
    status: str                 # "scheduled" / "live" / "finished"
    home_score: int | None = None
    away_score: int | None = None
    had_odds: dict[str, float] = field(default_factory=dict)   # {"h": 2.10, "d": 3.50, "a": 2.80}
    hhad_odds: dict[str, float] = field(default_factory=dict)
    venue_hint: str = ""


@dataclass(frozen=True)
class SportteryOdds:
    """Extracted odds for evidence attachment."""
    home_team: str
    away_team: str
    kickoff_at: str
    had_h: float
    had_d: float
    had_a: float
    hhad_h: float | None = None
    hhad_d: float | None = None
    hhad_a: float | None = None
    hhad_goal_line: str = ""
    league: str = ""


def market_snapshot(odds: SportteryOdds, *, observed_at: str) -> SportteryMarket | None:
    """Build a typed, de-margined market snapshot from Sporttery odds."""
    if min(odds.had_h, odds.had_d, odds.had_a) <= 0:
        return None

    had_odds = OutcomeOdds(
        home_win=odds.had_h,
        draw=odds.had_d,
        away_win=odds.had_a,
    )
    home_handicap = parse_home_handicap(odds.hhad_goal_line)
    hhad_values = (odds.hhad_h, odds.hhad_d, odds.hhad_a)
    has_valid_hhad = home_handicap is not None and all(
        value is not None and value > 0 for value in hhad_values
    )
    hhad_odds = None
    hhad_probabilities = None
    if has_valid_hhad:
        hhad_odds = OutcomeOdds(
            home_win=odds.hhad_h,
            draw=odds.hhad_d,
            away_win=odds.hhad_a,
        )
        hhad_probabilities = normalize_decimal_odds(hhad_odds)

    return SportteryMarket(
        provider="sporttery",
        had_odds=had_odds,
        had_implied_probabilities=normalize_decimal_odds(had_odds),
        home_handicap=home_handicap if has_valid_hhad else None,
        hhad_odds=hhad_odds,
        hhad_implied_probabilities=hhad_probabilities,
        observed_at=observed_at,
    )


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.lottery.gov.cn/",
        "Origin": "https://www.lottery.gov.cn",
        "Connection": "keep-alive",
    }


def _fetch_raw(pool_code: str = "had") -> dict[str, Any] | None:
    """Fetch raw JSON from the sporttery API. Returns None on failure."""
    params = {"poolCode": pool_code, "channel": "c"}
    try:
        resp = httpx.get(
            URL, params=params, headers=_headers(),
            timeout=float(os.getenv("FOOTBALL_OSINT_SPORTTERY_TIMEOUT", str(DEFAULT_TIMEOUT))),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if not data.get("success"):
            log.warning("sporttery API returned success=false: %s", data.get("errorMessage"))
            return None
        return data
    except Exception as e:
        log.warning("sporttery fetch failed (pool=%s): %s", pool_code, e)
        return None


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse CST date+time from the API into a timezone-aware datetime."""
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=CST)
    except (ValueError, TypeError):
        return None


def _parse_odds(odds_dict: dict) -> dict[str, float]:
    """Convert API odds strings to float values."""
    result: dict[str, float] = {}
    for key in ("h", "d", "a"):
        try:
            result[key] = float(odds_dict.get(key, 0) or 0)
        except (ValueError, TypeError):
            result[key] = 0.0
    return result


def _extract_score(match: dict) -> tuple[int | None, int | None]:
    """Try to extract final score from API response.

    The sporttery API does NOT always include final scores in the match list
    endpoint.  When available they live in nested odds objects;
    we try multiple paths and return (None, None) when unavailable.
    """
    # Path 1: direct score fields
    home_score = match.get("homeScore")
    away_score = match.get("awayScore")
    if home_score is not None and away_score is not None:
        try:
            return int(home_score), int(away_score)
        except (ValueError, TypeError):
            pass

    # Path 2: from had.goalLine (contains score context for finished matches)
    had = match.get("had") or {}
    goal_line = had.get("goalLine", "")
    if goal_line and ":" in goal_line:
        parts = goal_line.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except (ValueError, TypeError):
                pass

    return None, None


def parse_matches(raw_data: dict) -> list[SportteryFixture]:
    """Parse raw API JSON into a list of SportteryFixture objects."""
    fixtures: list[SportteryFixture] = []
    match_info_list = (raw_data.get("value") or {}).get("matchInfoList") or []

    for date_info in match_info_list:
        for m in date_info.get("subMatchList") or []:
            kickoff = _parse_datetime(
                m.get("matchDate", ""),
                m.get("matchTime", "00:00:00"),
            )
            if kickoff is None:
                continue

            home_score, away_score = _extract_score(m)

            fixtures.append(SportteryFixture(
                match_id=str(m.get("matchId", "")),
                home_team=m.get("homeTeamAllName") or m.get("homeTeamAbbName", ""),
                away_team=m.get("awayTeamAllName") or m.get("awayTeamAbbName", ""),
                league=m.get("leagueAllName") or m.get("leagueAbbName", ""),
                kickoff_at=kickoff,
                status=_STATUS_MAP.get(m.get("matchStatus", ""), "scheduled"),
                home_score=home_score,
                away_score=away_score,
                had_odds=_parse_odds(m.get("had") or {}),
                hhad_odds=_parse_odds(m.get("hhad") or {}),
                venue_hint=(m.get("remark") or ""),
            ))

    return fixtures


# ── public API ──

def fetch_fixtures(days_ahead: int = 7) -> list[SportteryFixture]:
    """Fetch upcoming fixtures from today through ``days_ahead`` days.

    Results are cached for 5 minutes.
    """
    cache_key = f"st_fixtures:{days_ahead}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    data = _fetch_raw("had")
    if data is None:
        return []

    all_fixtures = parse_matches(data)
    now = datetime.now(CST)
    cutoff = now + timedelta(days=max(days_ahead, 0))
    upcoming = [
        f for f in all_fixtures
        if now <= f.kickoff_at <= cutoff
    ]
    upcoming.sort(key=lambda f: f.kickoff_at)
    cache.schedule_cache.set(cache_key, upcoming)
    return upcoming


def fetch_fixtures_for_range(date_from: str, date_to: str) -> list[SportteryFixture]:
    """Fetch fixtures for an explicit ``YYYY-MM-DD`` CST date range.

    Used by track-record backfill to look up finished match results.
    Results are cached for 5 minutes.
    """
    cache_key = f"st_range:{date_from}:{date_to}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    data = _fetch_raw("had")
    if data is None:
        return []

    all_fixtures = parse_matches(data)
    try:
        d_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=CST)
        d_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=CST) + timedelta(days=1)
    except ValueError:
        return []

    in_range = [
        f for f in all_fixtures
        if d_from <= f.kickoff_at < d_to
    ]
    cache.schedule_cache.set(cache_key, in_range)
    return in_range


def _normalise_team_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _kickoff_date(kickoff_at: str) -> str | None:
    """Return the CST calendar date for a parseable kickoff string."""
    value = kickoff_at.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, fmt).replace(tzinfo=CST)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CST)
    return parsed.astimezone(CST).date().isoformat()


def _find_match(raw_data: dict, match_id: str) -> dict | None:
    for date_info in (raw_data.get("value") or {}).get("matchInfoList") or []:
        for match in date_info.get("subMatchList") or []:
            if str(match.get("matchId", "")) == match_id:
                return match
    return None


def get_odds(
    home_team: str,
    away_team: str,
    kickoff_at: str = "",
    *,
    provider_match_id: str = "",
) -> SportteryOdds | None:
    """Look up odds for a specific match by team names.

    Returns None if the match is not found in the current sporttery data.
    """
    data = _fetch_raw("had")
    if data is None:
        return None

    # Also try HHAD for handicap data
    hhad_data = _fetch_raw("hhad")

    home_n = _normalise_team_name(home_team)
    away_n = _normalise_team_name(away_team)
    kickoff_date = _kickoff_date(kickoff_at)

    match_info_list = (data.get("value") or {}).get("matchInfoList") or []
    selected = _find_match(data, provider_match_id.strip()) if provider_match_id.strip() else None
    if selected is None:
        for date_info in match_info_list:
            for match in date_info.get("subMatchList") or []:
                match_home = _normalise_team_name(match.get("homeTeamAllName") or match.get("homeTeamAbbName") or "")
                match_away = _normalise_team_name(match.get("awayTeamAllName") or match.get("awayTeamAbbName") or "")
                if match_home != home_n or match_away != away_n:
                    continue
                if kickoff_date is not None and match.get("matchDate") != kickoff_date:
                    continue
                selected = match
                break
            if selected is not None:
                break

    if selected is None:
        return None

    had = _parse_odds(selected.get("had") or {})
    hhad: dict[str, float] = {}
    hhad_goal_line = ""
    if hhad_data:
        hhad_match = _find_match(hhad_data, str(selected.get("matchId", "")))
        if hhad_match is not None:
            hhad = _parse_odds(hhad_match.get("hhad") or {})
            hhad_goal_line = (hhad_match.get("hhad") or {}).get("goalLine", "")

    return SportteryOdds(
        home_team=home_team.strip(),
        away_team=away_team.strip(),
        kickoff_at=f"{selected.get('matchDate', '')} {selected.get('matchTime', '')}",
        had_h=had.get("h", 0.0),
        had_d=had.get("d", 0.0),
        had_a=had.get("a", 0.0),
        hhad_h=hhad.get("h") if hhad else None,
        hhad_d=hhad.get("d") if hhad else None,
        hhad_a=hhad.get("a") if hhad else None,
        hhad_goal_line=hhad_goal_line,
        league=selected.get("leagueAllName") or selected.get("leagueAbbName", ""),
    )


def collect(request: FootballOsintJobRequest, evidence: list[OsintEvidence]) -> tuple[str, str]:
    """Pipeline adapter entry point — add sporttery odds as market-consensus evidence.

    Returns (evidence_id, error_reason) compatible with the pipeline collector
    pattern (same signature as open_meteo.collect).
    """
    odds = get_odds(
        request.home_team,
        request.away_team,
        request.kickoff_at,
        provider_match_id=request.provider_match_id,
    )
    if odds is None:
        return "", "体彩未覆盖该场比赛"

    # Build HAD claim
    had_parts = [f"主胜{odds.had_h:.2f}", f"平{odds.had_d:.2f}", f"客胜{odds.had_a:.2f}"]
    claim_parts = [f"体彩胜平负赔率: {' / '.join(had_parts)}"]

    if odds.hhad_h is not None:
        hhad_parts = [f"主胜{odds.hhad_h:.2f}", f"平{odds.hhad_d:.2f}", f"客胜{odds.hhad_a:.2f}"]
        if odds.hhad_goal_line:
            claim_parts.append(f"让球({odds.hhad_goal_line})赔率: {' / '.join(hhad_parts)}")
        else:
            claim_parts.append(f"让球赔率: {' / '.join(hhad_parts)}")

    claim = "；".join(claim_parts)

    # Compute implied probabilities from HAD odds (overround-removed)
    implied = _implied_probabilities(odds.had_h, odds.had_d, odds.had_a)

    raw = json.dumps({
        "had": {"h": odds.had_h, "d": odds.had_d, "a": odds.had_a},
        "hhad": {"h": odds.hhad_h, "d": odds.hhad_d, "a": odds.hhad_a, "goal_line": odds.hhad_goal_line} if odds.hhad_h else None,
        "implied": implied,
    }, ensure_ascii=False)

    # Market odds are strong signals — confidence 0.60 (higher than weather's 0.55,
    # lower than structured fundamental data at 0.65+)
    eid = append_evidence(
        evidence,
        source=f"中国体育彩票 ({odds.league})",
        source_type="odds",
        claim=claim,
        topic="odds.sporttery.market",
        side="neutral",
        confidence=0.60,
        raw_excerpt=raw,
    )
    return eid, ""


def _implied_probabilities(h: float, d: float, a: float) -> dict[str, float]:
    """Convert decimal odds to implied probabilities (overround-removed)."""
    if h <= 0 or d <= 0 or a <= 0:
        return {"home": 0.0, "draw": 0.0, "away": 0.0}
    total = 1.0 / h + 1.0 / d + 1.0 / a
    if total == 0:
        return {"home": 0.0, "draw": 0.0, "away": 0.0}
    return {
        "home": round((1.0 / h) / total, 4),
        "draw": round((1.0 / d) / total, 4),
        "away": round((1.0 / a) / total, 4),
    }

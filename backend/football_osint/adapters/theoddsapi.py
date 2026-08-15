"""Licensed multi-bookmaker 1X2 quotes from The Odds API.

This module deliberately has no pipeline dependency.  It is disabled unless a
licensed API key is configured, and it returns only validated generic market
snapshots so callers never have to handle provider payloads directly.
"""
from __future__ import annotations

import math
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..analysis.market import normalize_decimal_odds
from ..models import FootballOsintJobRequest, MarketSourceSnapshot, OutcomeOdds

DEFAULT_BASE_URL = "https://api.the-odds-api.com"
DEFAULT_BOOKMAKERS = "pinnacle,bet365,williamhill"
REQUEST_TIMEOUT_SECONDS = 8.0
_CST = timezone(timedelta(hours=8))

# The provider uses these stable sport keys.  We only request competitions
# whose identity can be expressed without guessing.
_SPORT_KEYS = {
    "英超": "soccer_epl",
    "englishpremierleague": "soccer_epl",
    "premierleague": "soccer_epl",
    "西甲": "soccer_spain_la_liga",
    "laliga": "soccer_spain_la_liga",
    "西班牙甲级联赛": "soccer_spain_la_liga",
    "德甲": "soccer_germany_bundesliga",
    "bundesliga": "soccer_germany_bundesliga",
    "意甲": "soccer_italy_serie_a",
    "seriea": "soccer_italy_serie_a",
    "法甲": "soccer_france_ligue_one",
    "ligue1": "soccer_france_ligue_one",
    "欧冠": "soccer_uefa_champs_league",
    "uefachampionsleague": "soccer_uefa_champs_league",
    "championsleague": "soccer_uefa_champs_league",
    "欧联": "soccer_uefa_europa_league",
    "uefaeuropaleague": "soccer_uefa_europa_league",
    "europaleague": "soccer_uefa_europa_league",
}


def collect(request: FootballOsintJobRequest) -> tuple[list[MarketSourceSnapshot], str]:
    """Collect complete, identity-safe 1X2 snapshots for one football match."""
    api_key = os.getenv("THEODDS_API_KEY", "").strip()
    if not api_key:
        return [], "未配置授权赔率数据服务"

    sport_key = _sport_key(request.competition)
    if sport_key is None:
        return [], "该赛事不受授权赔率数据服务支持"

    requested_kickoff = _parse_kickoff(request.kickoff_at)
    if requested_kickoff is None:
        return [], "比赛开赛时间不完整，无法安全匹配授权赔率数据"

    base_url = os.getenv("THEODDS_API_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    bookmakers = os.getenv("THEODDS_API_BOOKMAKERS", DEFAULT_BOOKMAKERS).strip() or DEFAULT_BOOKMAKERS
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/v4/sports/{sport_key}/odds/",
            params={
                "apiKey": api_key,
                "regions": "uk",
                "markets": "h2h",
                "oddsFormat": "decimal",
                "bookmakers": bookmakers,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException:
        return [], "授权赔率数据服务请求超时"
    except httpx.HTTPStatusError:
        return [], "授权赔率数据服务请求失败"
    except (httpx.HTTPError, ValueError, TypeError):
        return [], "授权赔率数据服务响应无效"

    if not isinstance(payload, list):
        return [], "授权赔率数据服务响应无效"

    matches = [
        event for event in payload
        if isinstance(event, dict) and _event_matches(event, request, requested_kickoff)
    ]
    if len(matches) != 1:
        return [], "未找到唯一匹配的授权赔率赛事"

    try:
        snapshots = _snapshots_from_event(matches[0])
    except ValueError:
        return [], "授权赔率数据服务响应无效"
    if not snapshots:
        return [], "授权赔率数据服务未提供完整有效的胜平负赔率"
    return snapshots, ""


def _sport_key(competition: str) -> str | None:
    return _SPORT_KEYS.get(_normalise(competition))


def _normalise(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]", "", normalized, flags=re.UNICODE)


def _parse_kickoff(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?", raw):
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(raw, fmt).replace(tzinfo=_CST)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_CST)
    return parsed.astimezone(timezone.utc)


def _event_matches(
    event: dict[str, Any],
    request: FootballOsintJobRequest,
    requested_kickoff: datetime,
) -> bool:
    if _normalise(event.get("home_team")) != _normalise(request.home_team):
        return False
    if _normalise(event.get("away_team")) != _normalise(request.away_team):
        return False
    event_kickoff = _parse_kickoff(event.get("commence_time", ""))
    return event_kickoff == requested_kickoff


def _snapshots_from_event(event: dict[str, Any]) -> list[MarketSourceSnapshot]:
    event_id = str(event.get("id", "")).strip()
    home = _normalise(event.get("home_team"))
    away = _normalise(event.get("away_team"))
    if not event_id or not home or not away:
        return []

    observed_at = datetime.now(timezone.utc)
    snapshots: list[MarketSourceSnapshot] = []
    seen_source_ids: set[str] = set()
    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        raise ValueError("bookmakers must be a list")
    for bookmaker in bookmakers:
        snapshot = _snapshot_from_bookmaker(bookmaker, home, away, event_id, observed_at)
        if snapshot is not None and snapshot.source_id not in seen_source_ids:
            snapshots.append(snapshot)
            seen_source_ids.add(snapshot.source_id)
    return snapshots


def _snapshot_from_bookmaker(
    bookmaker: object,
    home: str,
    away: str,
    event_id: str,
    observed_at: datetime,
) -> MarketSourceSnapshot | None:
    if not isinstance(bookmaker, dict):
        return None
    source_id = str(bookmaker.get("key", "")).strip()
    if not source_id:
        return None

    odds_by_outcome: dict[str, float] = {}
    markets = bookmaker.get("markets")
    if not isinstance(markets, list):
        raise ValueError("markets must be a list")
    for market in markets:
        if not isinstance(market, dict):
            raise ValueError("market must be an object")
        if market.get("key") != "h2h":
            continue
        outcomes = market.get("outcomes")
        if not isinstance(outcomes, list):
            raise ValueError("outcomes must be a list")
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                raise ValueError("outcome must be an object")
            name = _normalise(outcome.get("name"))
            if name == home:
                outcome_key = "home"
            elif name == away:
                outcome_key = "away"
            elif name == "draw":
                outcome_key = "draw"
            else:
                continue
            price = _decimal_price(outcome.get("price"))
            if price is None or outcome_key in odds_by_outcome:
                return None
            odds_by_outcome[outcome_key] = price
        break

    if set(odds_by_outcome) != {"home", "draw", "away"}:
        return None
    odds = OutcomeOdds(
        home_win=odds_by_outcome["home"],
        draw=odds_by_outcome["draw"],
        away_win=odds_by_outcome["away"],
    )
    title = str(bookmaker.get("title", "")).strip() or source_id
    return MarketSourceSnapshot(
        source_id=source_id,
        display_name=f"The Odds API · {title}",
        market="1x2",
        odds=odds,
        implied_probabilities=normalize_decimal_odds(odds),
        observed_at=observed_at,
        provider_event_id=event_id,
    )


def _decimal_price(value: object) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None

from __future__ import annotations

import pytest

from backend.football_osint.adapters import sporttery
from backend.football_osint.adapters.sporttery import SportteryOdds
from backend.football_osint.analysis.market import (
    handicap_probabilities,
    normalize_decimal_odds,
    parse_home_handicap,
    score_matrix_probabilities,
    settle_handicap,
)
from backend.football_osint.models import FootballOsintJobRequest, OutcomeOdds


def _raw(matches: list[dict]) -> dict:
    return {"success": True, "value": {"matchInfoList": [{"subMatchList": matches}]}}


def _match(
    match_id: str,
    date: str,
    home: str = "同名主队",
    away: str = "同名客队",
    *,
    had: dict | None = None,
    hhad: dict | None = None,
) -> dict:
    return {
        "matchId": match_id,
        "matchDate": date,
        "matchTime": "19:30:00",
        "homeTeamAllName": home,
        "awayTeamAllName": away,
        "leagueAllName": "测试联赛",
        "had": had or {"h": "2.00", "d": "3.50", "a": "4.00"},
        "hhad": hhad or {},
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("+1", 1), ("(-1)", -1), ("", None), ("+1.5", None), ("主队+1", None)],
)
def test_parse_home_handicap_accepts_only_official_integer_forms(raw, expected):
    assert parse_home_handicap(raw) == expected


def test_normalize_decimal_odds_removes_margin_and_preserves_probability_total():
    probabilities = normalize_decimal_odds(OutcomeOdds(home_win=2.0, draw=3.5, away_win=4.0))

    assert probabilities.home_win > probabilities.draw > probabilities.away_win
    assert probabilities.home_win + probabilities.draw + probabilities.away_win == pytest.approx(1.0, abs=1e-9)


def test_score_matrix_probabilities_normalizes_all_score_mass():
    probabilities = score_matrix_probabilities({(1, 0): 2.0, (1, 1): 1.0, (0, 2): 1.0})

    assert probabilities.model_dump() == pytest.approx({"home_win": 0.5, "draw": 0.25, "away_win": 0.25})


def test_handicap_probabilities_aggregates_each_score_once():
    probabilities = handicap_probabilities({(1, 1): 0.2, (1, 2): 0.3, (1, 3): 0.5}, 1)

    assert probabilities.model_dump() == pytest.approx({"home_win": 0.2, "draw": 0.3, "away_win": 0.5})


@pytest.mark.parametrize(
    "matrix",
    [
        {(1, 0): -0.1, (0, 0): 1.1},
        {(1, 0): float("nan")},
        {(1, 0): float("inf")},
        {(1, 0): 0.0, (0, 0): 0.0},
    ],
)
def test_score_matrix_helpers_reject_invalid_probability_mass(matrix):
    with pytest.raises(ValueError):
        score_matrix_probabilities(matrix)
    with pytest.raises(ValueError):
        handicap_probabilities(matrix, 1)


@pytest.mark.parametrize(
    ("home_score", "away_score", "handicap", "outcome"),
    [(1, 1, 1, "home"), (1, 2, 1, "draw"), (1, 3, 1, "away")],
)
def test_settle_handicap_uses_adjusted_home_score(home_score, away_score, handicap, outcome):
    assert settle_handicap(home_score, away_score, handicap) == outcome


def test_market_snapshot_attaches_had_and_valid_hhad_with_normalized_probabilities():
    odds = SportteryOdds(
        home_team="主队",
        away_team="客队",
        kickoff_at="2026-08-15 19:30:00",
        had_h=2.0,
        had_d=3.5,
        had_a=4.0,
        hhad_h=1.8,
        hhad_d=3.6,
        hhad_a=4.5,
        hhad_goal_line="+1",
    )

    market = sporttery.market_snapshot(odds, observed_at="2026-08-11T12:00:00+00:00")

    assert market is not None
    assert market.provider == "sporttery"
    assert market.home_handicap == 1
    assert market.had_odds.model_dump() == {"home_win": 2.0, "draw": 3.5, "away_win": 4.0}
    assert market.hhad_odds.model_dump() == {"home_win": 1.8, "draw": 3.6, "away_win": 4.5}
    assert market.had_implied_probabilities.home_win + market.had_implied_probabilities.draw + market.had_implied_probabilities.away_win == pytest.approx(1.0, abs=1e-9)


def test_market_snapshot_parses_parenthesized_handicap_and_suppresses_malformed_hhad():
    valid = SportteryOdds("主队", "客队", "", 2.0, 3.5, 4.0, 1.8, 3.6, 4.5, "(-1)")
    malformed = SportteryOdds("主队", "客队", "", 2.0, 3.5, 4.0, 1.8, 3.6, 4.5, "+1.5")

    assert sporttery.market_snapshot(valid, observed_at="now").home_handicap == -1
    market = sporttery.market_snapshot(malformed, observed_at="now")
    assert market is not None
    assert market.home_handicap is None
    assert market.hhad_odds is None
    assert market.hhad_implied_probabilities is None


def test_market_snapshot_rejects_non_positive_had_odds():
    odds = SportteryOdds("主队", "客队", "", 2.0, 0.0, 4.0)

    assert sporttery.market_snapshot(odds, observed_at="now") is None


@pytest.mark.parametrize("bad_odds", [float("nan"), float("inf")])
def test_market_snapshot_rejects_non_finite_had_odds(bad_odds):
    odds = SportteryOdds("主队", "客队", "", bad_odds, 3.5, 4.0)

    assert sporttery.market_snapshot(odds, observed_at="now") is None


@pytest.mark.parametrize("bad_odds", [float("nan"), float("inf")])
def test_market_snapshot_suppresses_non_finite_hhad_odds(bad_odds):
    odds = SportteryOdds("主队", "客队", "", 2.0, 3.5, 4.0, bad_odds, 3.6, 4.5, "+1")

    market = sporttery.market_snapshot(odds, observed_at="now")

    assert market is not None
    assert market.home_handicap is None
    assert market.hhad_odds is None
    assert market.hhad_implied_probabilities is None


def test_parse_odds_converts_non_finite_values_to_zero():
    assert sporttery._parse_odds({"h": "NaN", "d": "inf", "a": "2.0"}) == {
        "h": 0.0,
        "d": 0.0,
        "a": 2.0,
    }


def test_get_odds_uses_kickoff_date_to_disambiguate_duplicate_team_names(monkeypatch):
    had = _raw([_match("old", "2026-08-14"), _match("right", "2026-08-15")])
    hhad = _raw([_match("right", "2026-08-15", hhad={"h": "1.8", "d": "3.6", "a": "4.5", "goalLine": "+1"})])
    monkeypatch.setattr(sporttery, "_fetch_raw", lambda pool: had if pool == "had" else hhad)

    odds = sporttery.get_odds("同名主队", "同名客队", "2026-08-15T19:30:00+08:00")

    assert odds is not None
    assert odds.kickoff_at.startswith("2026-08-15")


def test_get_odds_prefers_official_provider_match_id(monkeypatch):
    had = _raw([_match("first", "2026-08-15"), _match("official", "2026-08-16")])
    hhad = _raw([])
    monkeypatch.setattr(sporttery, "_fetch_raw", lambda pool: had if pool == "had" else hhad)

    odds = sporttery.get_odds(
        "同名主队",
        "同名客队",
        "2026-08-15T19:30:00+08:00",
        provider="sporttery",
        provider_match_id="official",
    )

    assert odds is not None
    assert odds.kickoff_at.startswith("2026-08-16")


def test_get_odds_ignores_foreign_provider_match_id_collision(monkeypatch):
    had = _raw([
        _match("football-data-id", "2026-08-16", "无关主队", "无关客队"),
        _match("sporttery-id", "2026-08-15"),
    ])
    monkeypatch.setattr(sporttery, "_fetch_raw", lambda pool: had if pool == "had" else _raw([]))

    odds = sporttery.get_odds(
        "同名主队",
        "同名客队",
        "2026-08-15T19:30:00+08:00",
        provider="football-data",
        provider_match_id="football-data-id",
    )

    assert odds is not None
    assert odds.kickoff_at.startswith("2026-08-15")


def test_collect_passes_request_provider_to_odds_lookup(monkeypatch):
    received = {}

    def fake_get_odds(*args, **kwargs):
        received.update(kwargs)
        return None

    monkeypatch.setattr(sporttery, "get_odds", fake_get_odds)

    evidence = []
    sporttery.collect(
        FootballOsintJobRequest(
            home_team="主队",
            away_team="客队",
            provider="football-data",
            provider_match_id="foreign-id",
        ),
        evidence,
    )

    assert received == {"provider": "football-data", "provider_match_id": "foreign-id"}
    assert evidence == []


def test_collect_keeps_successful_market_quotes_out_of_osint_evidence(monkeypatch):
    monkeypatch.setattr(
        sporttery,
        "get_odds",
        lambda *args, **kwargs: SportteryOdds(
            home_team="主队", away_team="客队", kickoff_at="2026-08-15 19:30",
            had_h=2.0, had_d=3.5, had_a=4.0, league="测试联赛",
        ),
    )
    evidence = []

    evidence_id, reason = sporttery.collect(
        FootballOsintJobRequest(home_team="主队", away_team="客队"),
        evidence,
    )

    assert (evidence_id, reason) == ("", "")
    assert evidence == []

"""Tests for the football match analysis core."""

from __future__ import annotations

from backend.football import (
    FootballAnalysisRequest,
    MatchOdds,
    TeamForm,
    analyze_football_match,
)


def test_football_analysis_combines_market_poisson_and_value_edges():
    request = FootballAnalysisRequest(
        match_id="fixture-2026-001",
        league="World Cup",
        home_team="Japan",
        away_team="Wales",
        home=TeamForm(goals_for=2.0, goals_against=0.9),
        away=TeamForm(goals_for=1.0, goals_against=1.7),
        market=MatchOdds(
            home_win=2.30,
            draw=3.40,
            away_win=3.40,
            over_25=2.20,
            under_25=1.72,
            opening_home_win=2.55,
            opening_away_win=3.10,
        ),
        intel=[
            {
                "title": "Japan full squad in training",
                "source": "team-news",
                "confidence": 0.82,
                "polarity": "support_home",
            },
            {
                "title": "Heavy rain expected",
                "source": "weather",
                "confidence": 0.7,
                "polarity": "risk",
            },
        ],
    )

    result = analyze_football_match(request)

    assert result.market_probabilities["home_win"] > result.market_probabilities["away_win"]
    assert result.model_probabilities["home_win"] > result.model_probabilities["away_win"]
    assert any(score["score"] in {"2:1", "1:0", "2:0"} for score in result.poisson.top_scores[:3])
    assert any(edge.selection == "home_win" and edge.expected_value > 0 for edge in result.value_edges)
    assert any(flag.code == "odds_movement" for flag in result.risk_flags)
    assert any(flag.code == "external_risk" for flag in result.risk_flags)


def test_football_analysis_handles_missing_optional_market_data():
    request = FootballAnalysisRequest(
        home_team="Home",
        away_team="Away",
        home=TeamForm(goals_for=1.2, goals_against=1.0),
        away=TeamForm(goals_for=1.1, goals_against=1.1),
        market=MatchOdds(home_win=2.70, draw=3.10, away_win=2.80),
    )

    result = analyze_football_match(request)

    assert round(sum(result.market_probabilities.values()), 3) == 1.0
    assert result.total_goals_expectation > 0
    assert result.recommendation in {"home_win", "draw", "away_win", "no_bet"}


def test_football_analysis_api_is_public_readonly(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("OSINT_ROLE", "api")

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/football/analyze",
        json={
            "home_team": "Home",
            "away_team": "Away",
            "home": {"goals_for": 1.5, "goals_against": 1.0},
            "away": {"goals_for": 1.1, "goals_against": 1.4},
            "market": {"home_win": 2.4, "draw": 3.2, "away_win": 3.0},
        },
    )

    assert response.status_code == 200
    assert response.json()["recommendation"] in {"home_win", "draw", "away_win", "no_bet"}

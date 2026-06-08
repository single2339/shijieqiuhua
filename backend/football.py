from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TeamForm(BaseModel):
    goals_for: float = Field(ge=0.0)
    goals_against: float = Field(ge=0.0)
    matches: int = Field(default=6, ge=1)


class MatchOdds(BaseModel):
    home_win: float = Field(gt=1.0)
    draw: float = Field(gt=1.0)
    away_win: float = Field(gt=1.0)
    over_25: float | None = Field(default=None, gt=1.0)
    under_25: float | None = Field(default=None, gt=1.0)
    opening_home_win: float | None = Field(default=None, gt=1.0)
    opening_away_win: float | None = Field(default=None, gt=1.0)


class IntelSignal(BaseModel):
    title: str = ""
    source: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    polarity: str = "neutral"


class FootballAnalysisRequest(BaseModel):
    match_id: str = ""
    league: str = ""
    home_team: str
    away_team: str
    kickoff_at: str = ""
    home: TeamForm
    away: TeamForm
    market: MatchOdds
    league_avg_goals: float = Field(default=2.6, gt=0.1)
    intel: list[IntelSignal] = Field(default_factory=list)


class PoissonProjection(BaseModel):
    lambda_home: float
    lambda_away: float
    top_scores: list[dict[str, Any]]
    over_25_probability: float
    method: str


class ValueEdge(BaseModel):
    selection: str
    model_probability: float
    market_probability: float
    decimal_odds: float
    expected_value: float
    kelly_fraction: float


class RiskFlag(BaseModel):
    code: str
    severity: str
    message: str


class FootballAnalysisResponse(BaseModel):
    match_id: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    market_probabilities: dict[str, float]
    model_probabilities: dict[str, float]
    poisson: PoissonProjection
    total_goals_expectation: float
    value_edges: list[ValueEdge] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    recommendation: str = "no_bet"
    disclaimer: str = "For research and risk analysis only; not betting advice."


def analyze_football_match(request: FootballAnalysisRequest) -> FootballAnalysisResponse:
    market_probabilities = _de_margin(
        {
            "home_win": request.market.home_win,
            "draw": request.market.draw,
            "away_win": request.market.away_win,
        }
    )
    lambda_home, lambda_away = _estimate_lambdas(request)
    poisson = _poisson_projection(lambda_home, lambda_away)
    model_probabilities = {
        "home_win": poisson["outcomes"]["home_win"],
        "draw": poisson["outcomes"]["draw"],
        "away_win": poisson["outcomes"]["away_win"],
        "over_25": poisson["over_25_probability"],
        "under_25": 1.0 - poisson["over_25_probability"],
    }

    value_edges = _value_edges(request.market, market_probabilities, model_probabilities)
    risk_flags = _risk_flags(request)
    recommendation = value_edges[0].selection if value_edges else "no_bet"

    return FootballAnalysisResponse(
        match_id=request.match_id,
        market_probabilities=market_probabilities,
        model_probabilities={k: _round(v) for k, v in model_probabilities.items()},
        poisson=PoissonProjection(
            lambda_home=_round(lambda_home),
            lambda_away=_round(lambda_away),
            top_scores=poisson["top_scores"],
            over_25_probability=_round(poisson["over_25_probability"]),
            method="Independent Poisson score matrix using recent scoring/conceding rates with a small home-field adjustment.",
        ),
        total_goals_expectation=_round(lambda_home + lambda_away),
        value_edges=value_edges,
        risk_flags=risk_flags,
        recommendation=recommendation,
    )


def _de_margin(odds: dict[str, float]) -> dict[str, float]:
    raw = {key: 1.0 / value for key, value in odds.items()}
    total = sum(raw.values())
    return {key: _round(value / total) for key, value in raw.items()}


def _estimate_lambdas(request: FootballAnalysisRequest) -> tuple[float, float]:
    per_team_baseline = request.league_avg_goals / 2.0
    home = ((request.home.goals_for + request.away.goals_against + per_team_baseline) / 3.0) * 1.1
    away = (request.away.goals_for + request.home.goals_against + per_team_baseline) / 3.0

    for signal in request.intel:
        impact = 0.04 * signal.confidence
        if signal.polarity == "support_home":
            home += impact
        elif signal.polarity == "support_away":
            away += impact
        elif signal.polarity == "risk":
            home -= impact / 2
            away -= impact / 2

    return max(0.05, min(home, 6.0)), max(0.05, min(away, 6.0))


def _poisson_projection(lambda_home: float, lambda_away: float) -> dict[str, Any]:
    max_goals = 8
    score_probs: list[tuple[int, int, float]] = []
    outcomes = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    over_25 = 0.0
    mass = 0.0

    for home_goals in range(max_goals + 1):
        hp = _poisson(home_goals, lambda_home)
        for away_goals in range(max_goals + 1):
            probability = hp * _poisson(away_goals, lambda_away)
            mass += probability
            score_probs.append((home_goals, away_goals, probability))
            if home_goals > away_goals:
                outcomes["home_win"] += probability
            elif home_goals == away_goals:
                outcomes["draw"] += probability
            else:
                outcomes["away_win"] += probability
            if home_goals + away_goals > 2.5:
                over_25 += probability

    if mass > 0:
        outcomes = {key: value / mass for key, value in outcomes.items()}
        over_25 /= mass
        score_probs = [(h, a, p / mass) for h, a, p in score_probs]

    score_probs.sort(key=lambda item: item[2], reverse=True)
    top_scores = [
        {"score": f"{home}:{away}", "probability": _round(probability)}
        for home, away, probability in score_probs[:5]
    ]
    return {
        "outcomes": {key: _round(value) for key, value in outcomes.items()},
        "over_25_probability": _round(over_25),
        "top_scores": top_scores,
    }


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _value_edges(
    market: MatchOdds,
    market_probabilities: dict[str, float],
    model_probabilities: dict[str, float],
) -> list[ValueEdge]:
    odds = {
        "home_win": market.home_win,
        "draw": market.draw,
        "away_win": market.away_win,
        "over_25": market.over_25,
        "under_25": market.under_25,
    }
    edges: list[ValueEdge] = []
    for selection, decimal_odds in odds.items():
        if decimal_odds is None or selection not in model_probabilities:
            continue
        model_probability = model_probabilities[selection]
        expected_value = (model_probability * decimal_odds) - 1.0
        if expected_value <= 0:
            continue
        market_probability = market_probabilities.get(selection, 1.0 / decimal_odds)
        edges.append(
            ValueEdge(
                selection=selection,
                model_probability=_round(model_probability),
                market_probability=_round(market_probability),
                decimal_odds=decimal_odds,
                expected_value=_round(expected_value),
                kelly_fraction=_round(min(_kelly_fraction(model_probability, decimal_odds), 0.05)),
            )
        )
    return sorted(edges, key=lambda edge: edge.expected_value, reverse=True)


def _kelly_fraction(probability: float, odds: float) -> float:
    net_odds = odds - 1.0
    if net_odds <= 0:
        return 0.0
    fraction = ((net_odds * probability) - (1.0 - probability)) / net_odds
    return max(0.0, fraction)


def _risk_flags(request: FootballAnalysisRequest) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    movements = []
    if request.market.opening_home_win:
        movements.append(("home_win", request.market.opening_home_win, request.market.home_win))
    if request.market.opening_away_win:
        movements.append(("away_win", request.market.opening_away_win, request.market.away_win))
    if any(abs(current - opening) / opening >= 0.05 for _, opening, current in movements):
        flags.append(
            RiskFlag(
                code="odds_movement",
                severity="medium",
                message="Opening-to-current odds moved by at least 5%; verify cause before acting.",
            )
        )
    if any(signal.polarity == "risk" for signal in request.intel):
        flags.append(
            RiskFlag(
                code="external_risk",
                severity="medium",
                message="External football intelligence includes at least one risk signal.",
            )
        )
    if len(request.intel) < 2:
        flags.append(
            RiskFlag(
                code="thin_intel",
                severity="low",
                message="Few independent intelligence signals were supplied.",
            )
        )
    return flags


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)

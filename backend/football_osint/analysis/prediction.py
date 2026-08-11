"""Deterministic score-matrix prediction and official market fusion."""
from __future__ import annotations

from math import exp, factorial

from ..models import (
    FactorImpact,
    FootballOsintJobRequest,
    HandicapConclusion,
    OutcomeProbabilities,
    PredictionResult,
    SportteryMarket,
)
from .market import handicap_probabilities, score_matrix_probabilities

_DRAW_PRESSURE_LEAN_THRESHOLD = 0.012
_OUTCOME_TO_LEAN = {"home_win": "home", "draw": "draw", "away_win": "away"}
_HANDICAP_TO_OUTCOME = {"home_win": "home", "draw": "draw", "away_win": "away"}


def predict(
    request: FootballOsintJobRequest,
    factors: list[FactorImpact],
    factor_min: int = 1,
    *,
    market: SportteryMarket | None = None,
) -> PredictionResult:
    """Turn scored factors into exact outcomes, optionally blending official HAD."""
    active_fundamentals = [
        factor for factor in factors
        if factor.group in ("form", "h2h", "squad") and factor.enabled
    ]
    fundamental_count = len(active_fundamentals)
    has_fundamental_signal = fundamental_count >= factor_min
    home_impact = sum(
        factor.impact * factor.weight
        for factor in factors
        if factor.enabled and factor.group != "market" and factor.direction == "home"
    )
    away_impact = sum(
        abs(factor.impact) * factor.weight
        for factor in factors
        if factor.enabled and factor.group != "market" and factor.direction == "away"
    )
    draw_pressure = sum(
        factor.impact * factor.weight
        for factor in factors
        if factor.enabled and factor.factor_id == "uncertainty.draw_risk" and factor.direction == "draw"
    )
    edge = home_impact - away_impact
    model_lean = _model_lean(edge, draw_pressure)
    matrix = _score_matrix(model_lean, edge, factors, draw_pressure)
    model_probabilities = score_matrix_probabilities(matrix)
    coverage = fundamental_count
    outcome_probabilities = _blend_probabilities(
        model_probabilities,
        market.had_implied_probabilities if market and market.had_odds is not None and coverage else None,
        coverage,
    )
    primary_key, primary_probability, margin = _top_two(outcome_probabilities)

    if not has_fundamental_signal:
        lean = "info_insufficient"
        summary = "市场仅作参考，无基本面方向。" if market else "无基本面数据，暂不作方向判断。"
        drivers: list[str] = []
        scoreline_band: list[str] = []
    else:
        # Cautious double-chance language only remains for an explicit draw-risk rule.
        lean = _cautious_lean(edge, draw_pressure) or _OUTCOME_TO_LEAN[primary_key]
        clarity = "clear" if margin >= 0.05 else "close"
        summary = _summary(primary_key, primary_probability, margin, clarity)
        drivers = [
            factor.label
            for factor in sorted(factors, key=lambda item: abs(item.impact) * item.weight, reverse=True)
            if factor.enabled and abs(factor.impact) > 0.005
        ][:4]
        if not drivers:
            drivers = [factor.label for factor in factors if factor.enabled and factor.factor_id == "fixture.existence"][:1]
        scoreline_band = _rank_scorelines(matrix)

    uncertainties = [factor.label for factor in factors if factor.group == "uncertainty" and factor.enabled]
    uncertainties.extend(factor.missing_reason for factor in factors if factor.missing_reason)
    handicap_conclusion = _handicap_conclusion(matrix, market, coverage) if has_fundamental_signal else None

    return PredictionResult(
        lean=lean,  # type: ignore[arg-type]
        summary=summary,
        outcome_probabilities=outcome_probabilities,
        primary_probability=primary_probability,
        margin_to_runner_up=margin,
        clarity="insufficient" if not has_fundamental_signal else ("clear" if margin >= 0.05 else "close"),
        scoreline_band=scoreline_band,
        drivers=drivers,
        uncertainties=uncertainties[:4],
        sporttery_market=market,
        handicap_conclusion=handicap_conclusion,
    )


def _model_lean(edge: float, draw_pressure: float) -> str:
    cautious = _cautious_lean(edge, draw_pressure)
    if cautious:
        return cautious
    if abs(edge) < 0.015:
        return "draw"
    return "home" if edge > 0 else "away"


def _cautious_lean(edge: float, draw_pressure: float) -> str | None:
    if draw_pressure < _DRAW_PRESSURE_LEAN_THRESHOLD:
        return None
    if abs(edge) <= 0.025:
        return "draw"
    if 0 < edge <= 0.055:
        return "home_or_draw"
    if -0.055 <= edge < 0:
        return "away_or_draw"
    return None


def _score_matrix(
    lean: str,
    edge: float,
    factors: list[FactorImpact],
    draw_pressure: float,
) -> dict[tuple[int, int], float]:
    """Return one normalized 0--6 Poisson score matrix for every derivation."""
    youth_volatility = any(
        factor.enabled and factor.factor_id == "uncertainty.youth_volatility" for factor in factors
    )
    weather_drag = sum(
        abs(factor.impact) * factor.weight
        for factor in factors
        if factor.enabled and factor.factor_id == "weather.exposure" and factor.impact < 0
    )
    total_goals = 2.45
    if youth_volatility:
        total_goals += 0.55
    if weather_drag:
        total_goals -= 0.35
    if draw_pressure > 0:
        total_goals -= min(0.15, draw_pressure * 12.5)
    if lean == "draw":
        total_goals -= 0.10
    total_goals = max(1.65, min(3.25, total_goals))

    spread = min(1.15, abs(edge) * 8.0)
    if lean in {"home_or_draw", "away_or_draw"}:
        spread *= 0.65
    if lean == "draw":
        spread = 0.0
    home_lambda = total_goals / 2.0 + (spread / 2.0 if edge >= 0 else -spread / 2.0)
    away_lambda = total_goals / 2.0 - (spread / 2.0 if edge >= 0 else -spread / 2.0)

    matrix: dict[tuple[int, int], float] = {}
    for home_goals in range(7):
        for away_goals in range(7):
            probability = _poisson_probability(home_lambda, home_goals) * _poisson_probability(away_lambda, away_goals)
            probability *= _lean_score_multiplier(lean, edge, home_goals, away_goals)
            if draw_pressure > 0:
                if home_goals == away_goals:
                    probability *= 1.0 + min(1.8, draw_pressure * 130.0)
                elif abs(home_goals - away_goals) >= 2:
                    probability *= 0.80
            if youth_volatility and home_goals + away_goals >= 3:
                probability *= 1.18
            if youth_volatility and home_goals == away_goals == 2:
                probability *= 1.20
            if weather_drag:
                if home_goals + away_goals <= 1:
                    probability *= 1.25
                if home_goals + away_goals >= 3:
                    probability *= 0.70
            matrix[(home_goals, away_goals)] = probability
    total = sum(matrix.values())
    return {score: mass / total for score, mass in matrix.items()}


def _blend_probabilities(
    model: OutcomeProbabilities,
    market: OutcomeProbabilities | None,
    coverage: int,
) -> OutcomeProbabilities:
    if market is None:
        return model
    model_weight, market_weight = (0.65, 0.35) if coverage >= 2 else (0.45, 0.55)
    return OutcomeProbabilities(
        home_win=model.home_win * model_weight + market.home_win * market_weight,
        draw=model.draw * model_weight + market.draw * market_weight,
        away_win=model.away_win * model_weight + market.away_win * market_weight,
    )


def _handicap_conclusion(
    matrix: dict[tuple[int, int], float],
    market: SportteryMarket | None,
    coverage: int,
) -> HandicapConclusion | None:
    if (
        market is None
        or market.home_handicap is None
        or market.hhad_implied_probabilities is None
        or market.hhad_odds is None
    ):
        return None
    probabilities = _blend_probabilities(
        handicap_probabilities(matrix, market.home_handicap),
        market.hhad_implied_probabilities,
        coverage,
    )
    key, probability, margin = _top_two(probabilities)
    return HandicapConclusion(
        home_handicap=market.home_handicap,
        outcome=_HANDICAP_TO_OUTCOME[key],
        handicap_probabilities=probabilities,
        probability=probability,
        margin_to_runner_up=margin,
        clarity="clear" if margin >= 0.05 else "close",
    )


def _top_two(probabilities: OutcomeProbabilities) -> tuple[str, float, float]:
    ranked = sorted(probabilities.model_dump().items(), key=lambda item: item[1], reverse=True)
    return ranked[0][0], ranked[0][1], ranked[0][1] - ranked[1][1]


def _rank_scorelines(matrix: dict[tuple[int, int], float]) -> list[str]:
    return [f"{home}-{away}" for (home, away), _ in sorted(matrix.items(), key=lambda item: item[1], reverse=True)[:4]]


def _summary(primary_key: str, probability: float, margin: float, clarity: str) -> str:
    outcome = {"home_win": "主胜", "draw": "平局", "away_win": "客胜"}[primary_key]
    if clarity == "clear":
        return f"{outcome}概率{probability:.0%}，领先{margin * 100:.0f}个百分点。"
    return f"{outcome}优势不足，概率{probability:.0%}。"


def _poisson_probability(expected_goals: float, goals: int) -> float:
    return exp(-expected_goals) * expected_goals**goals / factorial(goals)


def _lean_score_multiplier(lean: str, edge: float, home_goals: int, away_goals: int) -> float:
    goal_diff = home_goals - away_goals
    strength = abs(edge)
    if lean == "draw":
        return 1.12 if goal_diff == 0 else (0.98 if abs(goal_diff) == 1 else 0.86)
    if lean == "home":
        if goal_diff > 0:
            return 1.30 if strength >= 0.12 and goal_diff >= 2 else 1.18
        return 0.96 if goal_diff == 0 else 0.80
    if lean == "away":
        if goal_diff < 0:
            return 1.30 if strength >= 0.12 and goal_diff <= -2 else 1.18
        return 0.96 if goal_diff == 0 else 0.80
    if lean == "home_or_draw":
        return 1.12 if goal_diff == 0 else (1.10 if goal_diff > 0 else 0.75)
    if lean == "away_or_draw":
        return 1.12 if goal_diff == 0 else (1.10 if goal_diff < 0 else 0.75)
    return 1.0

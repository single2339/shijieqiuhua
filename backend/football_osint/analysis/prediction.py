"""Prediction model (W2.4 — extracted from pipeline.py).

Owns the deterministic mapping from FactorImpact list → PredictionResult.
The maths here are intentionally simple (linear edge calc + clamped midpoint
bands); the contract that matters is:

- when uncertainty group dominates OR the edge is tiny → lean = *_or_draw
- bands always sum to roughly 1.0 with ±0.04 width
- drivers list factor_ids by |impact*weight| desc, capped at 4
- uncertainties merge enabled uncertainty.* labels with any missing_reason text

PRD §4.1 contract; do not break PredictionResult shape.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import exp, factorial

from ..models import (
    FactorImpact,
    FootballOsintJobRequest,
    PredictionResult,
)

# kickoff_at is a free-form string from different callers — frontend fixture
# clicks send "%Y-%m-%d %H:%M", warm_cache's synthetic requests send "%m-%d %H:%M"
# (no year). Both are Beijing time by convention elsewhere in this package.
_CST = timezone(timedelta(hours=8))
_KICKOFF_FORMATS = ("%Y-%m-%d %H:%M", "%m-%d %H:%M")
_DRAW_PRESSURE_LEAN_THRESHOLD = 0.012


def _hours_until_kickoff(kickoff_at: str) -> float | None:
    """Best-effort parse; returns None rather than raising on unknown formats."""
    kickoff_at = kickoff_at.strip()
    if not kickoff_at:
        return None
    for fmt in _KICKOFF_FORMATS:
        try:
            parsed = datetime.strptime(kickoff_at, fmt)
        except ValueError:
            continue
        if fmt == "%m-%d %H:%M":
            parsed = parsed.replace(year=datetime.now(_CST).year)
        parsed = parsed.replace(tzinfo=_CST)
        return (parsed - datetime.now(_CST)).total_seconds() / 3600
    return None


_LEAN_CN: dict[str, str] = {
    "home": "主队占优",
    "away": "客队占优",
    "draw": "平局倾向",
    "home_or_draw": "主队不败",
    "away_or_draw": "客队不败",
    "info_insufficient": "信息不足",
}


def predict(
    request: FootballOsintJobRequest,
    factors: list[FactorImpact],
    factor_min: int = 1,
) -> PredictionResult:
    # A factor is "active" when it's enabled — evidence was found and scored.
    # impact=0 with enabled=True means the teams are evenly matched on that
    # dimension, which IS a real signal (not a data gap).
    active_factors = [f for f in factors if f.group in ("form", "h2h", "squad") and f.enabled]
    # ponytail: factor_min read from system_config by caller; default=1 preserves prior behaviour
    has_fundamental_signal = len(active_factors) >= factor_min

    home_impact = sum(f.impact * f.weight for f in factors if f.enabled and f.direction == "home")
    away_impact = sum(abs(f.impact) * f.weight for f in factors if f.enabled and f.direction == "away")
    draw_pressure = sum(
        f.impact * f.weight
        for f in factors
        if f.enabled and f.factor_id == "uncertainty.draw_risk" and f.direction == "draw"
    )
    uncertainty = sum(
        abs(f.impact) * f.weight
        for f in factors
        if f.group == "uncertainty" and f.factor_id != "uncertainty.draw_risk"
    )
    edge = home_impact - away_impact

    if not has_fundamental_signal:
        lean = "info_insufficient"
    elif draw_pressure >= _DRAW_PRESSURE_LEAN_THRESHOLD and abs(edge) <= 0.025:
        lean = "draw"
    elif draw_pressure >= _DRAW_PRESSURE_LEAN_THRESHOLD and 0 < edge <= 0.055:
        lean = "home_or_draw"
    elif draw_pressure >= _DRAW_PRESSURE_LEAN_THRESHOLD and -0.055 <= edge < 0:
        lean = "away_or_draw"
    elif abs(edge) < 0.01 and home_impact > 0 and away_impact > 0:
        # Both sides have signals and the edge is near zero — this is a
        # genuinely balanced match, not a "we don't know" scenario.
        lean = "draw"
    elif abs(edge) < 0.015 or uncertainty > 0.015:
        lean = "home_or_draw" if edge >= 0 else "away_or_draw"
    else:
        lean = "home" if edge > 0 else "away"

    home_mid = max(0.24, min(0.52, 0.36 + edge))
    away_mid = max(0.20, min(0.50, 0.32 - edge))
    draw_mid = max(0.20, min(0.34, 1.0 - home_mid - away_mid))

    if lean == "info_insufficient":
        drivers: list[str] = []
        hours_to_kickoff = _hours_until_kickoff(request.kickoff_at)
        if hours_to_kickoff is None or hours_to_kickoff > 48:
            # Far from kickoff: dongqiudi/国内媒体 typically only publish
            # match-specific analysis in the final 1-2 days, so a miss here
            # usually just means "too early", not "this match has no coverage".
            summary = (
                f"{request.home_team} vs {request.away_team}：赛前分析暂未发布，现有证据不足以支撑方向判断，"
                "如实标记为信息不足。这类大赛通常临开赛前 1-2 天才会放出近期状态、历史交锋、阵容等数据，"
                "建议开赛前 1-2 天再来看。"
            )
        else:
            summary = (
                f"{request.home_team} vs {request.away_team}：未取得近期状态、历史交锋或阵容等结构化基本面数据"
                "（懂球帝赛前分析未命中该场比赛），现有证据不足以支撑方向判断，如实标记为信息不足，"
                "建议临近开赛前复扫。"
            )
    else:
        # drivers use Chinese factor labels, not internal factor_ids
        drivers = [
            f.label
            for f in sorted(factors, key=lambda item: abs(item.impact) * item.weight, reverse=True)
            if f.enabled and abs(f.impact) > 0.005
        ][:4]
        if not drivers:
            drivers = [f.label for f in factors if f.enabled and f.factor_id == "fixture.existence"][:1]
        lean_cn = _LEAN_CN.get(lean, lean)
        summary = f"{request.home_team} vs {request.away_team}，判断为「{lean_cn}」，置信度受数据覆盖度约束。"

    uncertainties = [f.label for f in factors if f.group == "uncertainty" and f.enabled]
    uncertainties.extend(f.missing_reason for f in factors if f.missing_reason)

    return PredictionResult(
        lean=lean,  # type: ignore[arg-type]
        summary=summary,
        probability_band={
            "home_win": band(home_mid),
            "draw": band(draw_mid),
            "away_win": band(away_mid),
        },
        scoreline_band=[] if lean == "info_insufficient" else _scoreline_band(lean, edge, factors, draw_pressure),
        drivers=drivers,
        uncertainties=uncertainties[:4],
    )


def band(mid: float) -> tuple[float, float]:
    """Symmetric ±0.04 probability band, clamped to [0, 1]."""
    return (round(max(0.0, mid - 0.04), 2), round(min(1.0, mid + 0.04), 2))


def _scoreline_band(
    lean: str,
    edge: float,
    factors: list[FactorImpact],
    draw_pressure: float,
) -> list[str]:
    """Rank likely scorelines with a small Poisson grid.

    The pipeline does not yet have reliable per-team xG. Use a conservative
    baseline total, then adjust it with signals already present in the factor
    set: youth volatility raises tempo/variance, bad weather and draw pressure
    lower tempo, and the directional edge splits expected goals between teams.
    """
    youth_volatility = any(
        f.enabled and f.factor_id == "uncertainty.youth_volatility" for f in factors
    )
    weather_drag = sum(
        abs(f.impact) * f.weight
        for f in factors
        if f.enabled and f.factor_id == "weather.exposure" and f.impact < 0
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

    home_lambda = total_goals / 2.0
    away_lambda = total_goals / 2.0
    if edge >= 0:
        home_lambda += spread / 2.0
        away_lambda -= spread / 2.0
    else:
        home_lambda -= spread / 2.0
        away_lambda += spread / 2.0

    ranked: list[tuple[float, str]] = []
    for home_goals in range(5):
        for away_goals in range(5):
            probability = _poisson_probability(home_lambda, home_goals) * _poisson_probability(
                away_lambda, away_goals
            )
            probability *= _lean_score_multiplier(lean, edge, home_goals, away_goals)
            if draw_pressure > 0:
                if home_goals == away_goals:
                    probability *= 1.0 + min(1.8, draw_pressure * 130.0)
                elif abs(home_goals - away_goals) >= 2:
                    probability *= 0.80
            if youth_volatility and home_goals + away_goals >= 3:
                probability *= 1.18
            if youth_volatility and home_goals == 2 and away_goals == 2:
                probability *= 1.20
            if weather_drag:
                if home_goals + away_goals <= 1:
                    probability *= 1.25
                if home_goals + away_goals >= 3:
                    probability *= 0.70
            ranked.append((probability, f"{home_goals}-{away_goals}"))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [score for _, score in ranked[:4]]


def _poisson_probability(expected_goals: float, goals: int) -> float:
    return exp(-expected_goals) * expected_goals**goals / factorial(goals)


def _lean_score_multiplier(lean: str, edge: float, home_goals: int, away_goals: int) -> float:
    goal_diff = home_goals - away_goals
    strength = abs(edge)

    if lean == "draw":
        if goal_diff == 0:
            return 1.90
        return 0.55 if abs(goal_diff) == 1 else 0.25

    if lean == "home":
        if goal_diff > 0:
            return 1.74 if strength >= 0.12 and goal_diff >= 2 else 1.45
        return 0.55 if goal_diff == 0 else 0.25

    if lean == "away":
        if goal_diff < 0:
            return 1.74 if strength >= 0.12 and goal_diff <= -2 else 1.45
        return 0.55 if goal_diff == 0 else 0.25

    if lean == "home_or_draw":
        if goal_diff == 0:
            return 1.44
        return 1.25 if goal_diff > 0 else 0.35

    if lean == "away_or_draw":
        if goal_diff == 0:
            return 1.44
        return 1.25 if goal_diff < 0 else 0.35

    return 1.0

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

from ..models import (
    FactorImpact,
    FootballOsintJobRequest,
    PredictionResult,
)


def predict(request: FootballOsintJobRequest, factors: list[FactorImpact]) -> PredictionResult:
    home_impact = sum(f.impact * f.weight for f in factors if f.enabled and f.direction == "home")
    away_impact = sum(abs(f.impact) * f.weight for f in factors if f.enabled and f.direction == "away")
    uncertainty = sum(abs(f.impact) * f.weight for f in factors if f.group == "uncertainty")
    edge = home_impact - away_impact

    if abs(edge) < 0.015 or uncertainty > 0.015:
        lean = "home_or_draw" if edge >= 0 else "away_or_draw"
    else:
        lean = "home" if edge > 0 else "away"

    home_mid = max(0.24, min(0.52, 0.36 + edge))
    away_mid = max(0.20, min(0.50, 0.32 - edge))
    draw_mid = max(0.20, min(0.34, 1.0 - home_mid - away_mid))
    drivers = [
        f.factor_id
        for f in sorted(factors, key=lambda item: abs(item.impact) * item.weight, reverse=True)
        if f.enabled
    ][:4]
    uncertainties = [f.label for f in factors if f.group == "uncertainty" and f.enabled]
    uncertainties.extend(f.missing_reason for f in factors if f.missing_reason)

    return PredictionResult(
        lean=lean,  # type: ignore[arg-type]
        summary=f"{request.home_team} vs {request.away_team} 当前为 {lean} 倾向，置信受数据覆盖度约束。",
        probability_band={
            "home_win": band(home_mid),
            "draw": band(draw_mid),
            "away_win": band(away_mid),
        },
        scoreline_band=["1-1", "1-0", "2-1"] if edge >= 0 else ["1-1", "0-1", "1-2"],
        drivers=drivers,
        uncertainties=uncertainties[:4],
    )


def band(mid: float) -> tuple[float, float]:
    """Symmetric ±0.04 probability band, clamped to [0, 1]."""
    return (round(max(0.0, mid - 0.04), 2), round(min(1.0, mid + 0.04), 2))

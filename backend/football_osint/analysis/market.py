"""Pure market probability and handicap settlement helpers."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Literal

from ..models import OutcomeOdds, OutcomeProbabilities

_HANDICAP_PATTERN = re.compile(r"[+-]?\d+")


def _probabilities(home: float, draw: float, away: float) -> OutcomeProbabilities:
    if any(not math.isfinite(weight) or weight < 0 for weight in (home, draw, away)):
        raise ValueError("probability weights must be finite and non-negative")
    total = home + draw + away
    if total <= 0:
        raise ValueError("probability weights must have positive total")
    home_probability = home / total
    draw_probability = draw / total
    away_probability = 1.0 - home_probability - draw_probability
    return OutcomeProbabilities(
        home_win=home_probability,
        draw=draw_probability,
        away_win=away_probability,
    )


def normalize_decimal_odds(odds: OutcomeOdds) -> OutcomeProbabilities:
    """Convert decimal odds into a de-margin three-way distribution."""
    return _probabilities(1.0 / odds.home_win, 1.0 / odds.draw, 1.0 / odds.away_win)


def parse_home_handicap(raw: str) -> int | None:
    """Parse only an official integer home-handicap representation."""
    value = raw.strip() if isinstance(raw, str) else ""
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    if not _HANDICAP_PATTERN.fullmatch(value):
        return None
    return int(value)


def score_matrix_probabilities(
    matrix: Mapping[tuple[int, int], float],
) -> OutcomeProbabilities:
    """Aggregate a score-probability matrix into ordinary 1X2 outcomes."""
    home = draw = away = 0.0
    for (home_score, away_score), mass in matrix.items():
        if not math.isfinite(mass) or mass < 0:
            raise ValueError("score matrix mass must be finite and non-negative")
        if home_score > away_score:
            home += mass
        elif home_score == away_score:
            draw += mass
        else:
            away += mass
    return _probabilities(home, draw, away)


def settle_handicap(
    home_score: int,
    away_score: int,
    home_handicap: int,
) -> Literal["home", "draw", "away"]:
    """Settle a home-side handicap after applying it to the final score."""
    adjusted_home_score = home_score + home_handicap
    if adjusted_home_score > away_score:
        return "home"
    if adjusted_home_score == away_score:
        return "draw"
    return "away"


def handicap_probabilities(
    matrix: Mapping[tuple[int, int], float],
    home_handicap: int,
) -> OutcomeProbabilities:
    """Aggregate a score matrix under the supplied home handicap."""
    outcomes = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for (home_score, away_score), mass in matrix.items():
        if not math.isfinite(mass) or mass < 0:
            raise ValueError("score matrix mass must be finite and non-negative")
        outcomes[settle_handicap(home_score, away_score, home_handicap)] += mass
    return _probabilities(outcomes["home"], outcomes["draw"], outcomes["away"])

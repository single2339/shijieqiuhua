"""Pure market probability and handicap settlement helpers."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Literal

from ..models import (
    MarketComparison,
    MarketConsensus,
    MarketSourceSnapshot,
    MatchDecision,
    OutcomeOdds,
    OutcomeProbabilities,
)

_HANDICAP_PATTERN = re.compile(r"[+-]?\d+")
MARKET_SNAPSHOT_MAX_AGE = timedelta(minutes=30)


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


def de_vig_snapshot(snapshot: MarketSourceSnapshot) -> OutcomeProbabilities:
    """Convert one source snapshot's decimal odds into fair probabilities."""
    return normalize_decimal_odds(snapshot.odds)


def is_market_snapshot_fresh(
    snapshot: MarketSourceSnapshot,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a snapshot is no more than thirty minutes old."""
    reference = now or datetime.now(timezone.utc)
    observed_at = snapshot.observed_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    return reference - observed_at <= MARKET_SNAPSHOT_MAX_AGE


def fresh_market_sources(
    snapshots: list[MarketSourceSnapshot],
    *,
    now: datetime | None = None,
) -> list[MarketSourceSnapshot]:
    """Filter a source list to snapshots within the market freshness window."""
    return [snapshot for snapshot in snapshots if is_market_snapshot_fresh(snapshot, now=now)]


def build_market_consensus(
    snapshots: list[MarketSourceSnapshot],
    *,
    now: datetime | None = None,
) -> MarketConsensus:
    """Build a median probability consensus only when three sources are fresh."""
    fresh_sources = fresh_market_sources(snapshots, now=now)
    source_names = [snapshot.source for snapshot in fresh_sources]
    source_count = len(fresh_sources)
    if source_count < 3:
        return MarketConsensus(
            status="single_source" if source_count == 1 else "insufficient_sources",
            fresh_source_count=source_count,
            source_names=source_names,
        )

    probabilities = [de_vig_snapshot(snapshot) for snapshot in fresh_sources]
    return MarketConsensus(
        status="consensus",
        fresh_source_count=source_count,
        source_names=source_names,
        probabilities=_probabilities(
            median(probability.home_win for probability in probabilities),
            median(probability.draw for probability in probabilities),
            median(probability.away_win for probability in probabilities),
        ),
    )


def compare_market_consensus(
    model: MatchDecision | None,
    consensus: MarketConsensus | None,
) -> MarketComparison:
    """Compare the model's leading outcome with a validated market consensus."""
    if (
        model is None
        or model.outcome == "info_insufficient"
        or model.outcome_probabilities is None
        or consensus is None
        or consensus.status != "consensus"
        or consensus.probabilities is None
    ):
        return MarketComparison(status="limited")

    model_leader = _probability_leader(model.outcome_probabilities)
    market_leader = _probability_leader(consensus.probabilities)
    leader_delta = abs(
        model.outcome_probabilities.model_dump()[model_leader]
        - consensus.probabilities.model_dump()[market_leader]
    )
    status = (
        "aligned"
        if model_leader == market_leader and leader_delta <= 0.07
        else "divergent"
    )
    return MarketComparison(
        status=status,
        model_leader=model_leader,
        market_leader=market_leader,
        leader_delta=leader_delta,
    )


def _probability_leader(
    probabilities: OutcomeProbabilities,
) -> Literal["home_win", "draw", "away_win"]:
    values = probabilities.model_dump()
    return max(values, key=values.__getitem__)


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

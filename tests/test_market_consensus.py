from datetime import datetime, timedelta, timezone

import pytest

from backend.football_osint.analysis.market import (
    build_market_consensus,
    compare_market_consensus,
    de_vig_snapshot,
)
from backend.football_osint.models import (
    MarketSourceSnapshot,
    MatchDecision,
    OutcomeOdds,
    OutcomeProbabilities,
)


NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def snapshot(source: str, odds: tuple[float, float, float], observed_at: datetime = NOW) -> MarketSourceSnapshot:
    return MarketSourceSnapshot(
        source=source,
        odds=OutcomeOdds(home_win=odds[0], draw=odds[1], away_win=odds[2]),
        observed_at=observed_at,
    )


def test_three_fresh_sources_create_median_consensus():
    consensus = build_market_consensus(
        [
            snapshot("a", (2.0, 4.0, 4.0)),
            snapshot("b", (2.5, 10 / 3, 10 / 3)),
            snapshot("c", (20 / 9, 10 / 3, 4.0)),
        ],
        now=NOW,
    )

    assert consensus.status == "consensus"
    assert consensus.fresh_source_count == 3
    assert consensus.probabilities is not None
    assert consensus.probabilities.home_win == pytest.approx(0.45)
    assert consensus.probabilities.draw == pytest.approx(0.30)
    assert consensus.probabilities.away_win == pytest.approx(0.25)


def test_two_fresh_sources_do_not_create_probabilities():
    consensus = build_market_consensus(
        [snapshot("a", (2.0, 4.0, 4.0)), snapshot("b", (2.5, 10 / 3, 10 / 3))],
        now=NOW,
    )

    assert consensus.status == "insufficient_sources"
    assert consensus.fresh_source_count == 2
    assert consensus.probabilities is None


def test_stale_snapshot_is_excluded_from_consensus():
    consensus = build_market_consensus(
        [
            snapshot("a", (2.0, 4.0, 4.0)),
            snapshot("b", (2.5, 10 / 3, 10 / 3)),
            snapshot("stale", (20 / 9, 10 / 3, 4.0), NOW - timedelta(minutes=31)),
        ],
        now=NOW,
    )

    assert consensus.status == "insufficient_sources"
    assert consensus.fresh_source_count == 2
    assert consensus.source_names == ["a", "b"]
    assert consensus.probabilities is None


def test_de_vig_snapshot_normalizes_implied_probabilities_to_one():
    probabilities = de_vig_snapshot(snapshot("a", (2.0, 3.5, 4.0)))

    assert probabilities.home_win + probabilities.draw + probabilities.away_win == pytest.approx(1.0)


def test_comparison_is_aligned_for_same_leader_within_seven_points():
    consensus = build_market_consensus(
        [
            snapshot("a", (2.0, 4.0, 4.0)),
            snapshot("b", (2.5, 10 / 3, 10 / 3)),
            snapshot("c", (20 / 9, 10 / 3, 4.0)),
        ],
        now=NOW,
    )

    comparison = compare_market_consensus(
        MatchDecision(
            outcome="home_win",
            outcome_probabilities=OutcomeProbabilities(home_win=0.50, draw=0.28, away_win=0.22),
        ),
        consensus,
    )

    assert comparison.status == "aligned"
    assert comparison.model_leader == "home_win"
    assert comparison.market_leader == "home_win"
    assert comparison.leader_delta == pytest.approx(0.05)


def test_comparison_is_divergent_for_different_leaders():
    consensus = build_market_consensus(
        [
            snapshot("a", (2.0, 4.0, 4.0)),
            snapshot("b", (2.5, 10 / 3, 10 / 3)),
            snapshot("c", (20 / 9, 10 / 3, 4.0)),
        ],
        now=NOW,
    )

    comparison = compare_market_consensus(
        MatchDecision(
            outcome="away_win",
            outcome_probabilities=OutcomeProbabilities(home_win=0.25, draw=0.25, away_win=0.50),
        ),
        consensus,
    )

    assert comparison.status == "divergent"


def test_comparison_is_limited_without_consensus_or_model_information():
    unavailable = build_market_consensus([], now=NOW)

    comparison = compare_market_consensus(
        MatchDecision(outcome="info_insufficient"),
        unavailable,
    )

    assert comparison.status == "limited"
    assert comparison.model_leader is None
    assert comparison.market_leader is None
    assert comparison.leader_delta is None

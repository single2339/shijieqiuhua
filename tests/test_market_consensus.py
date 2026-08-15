from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.football_osint.analysis.market import (
    build_market_consensus,
    compare_market_consensus,
    de_vig_snapshot,
    is_market_snapshot_fresh,
)
from backend.football_osint.models import (
    MarketComparison,
    MarketConsensus,
    MarketSourceSnapshot,
    MatchDecision,
    OutcomeOdds,
    OutcomeProbabilities,
)


NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def snapshot(source_id: str, odds: tuple[float, float, float], observed_at: datetime = NOW) -> MarketSourceSnapshot:
    return MarketSourceSnapshot(
        source_id=source_id,
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


def test_duplicate_snapshots_do_not_count_as_independent_sources():
    consensus = build_market_consensus(
        [
            snapshot("a", (2.0, 4.0, 4.0), NOW - timedelta(minutes=5)),
            snapshot("a", (2.5, 10 / 3, 10 / 3), NOW - timedelta(minutes=1)),
            snapshot("a", (20 / 9, 10 / 3, 4.0), NOW - timedelta(minutes=3)),
            snapshot("b", (2.0, 4.0, 4.0), NOW - timedelta(minutes=4)),
            snapshot("b", (2.5, 10 / 3, 10 / 3), NOW - timedelta(minutes=2)),
        ],
        now=NOW,
    )

    assert consensus.status == "insufficient_sources"
    assert consensus.fresh_source_count == 2
    assert consensus.source_ids == ["a", "b"]
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
    assert consensus.source_ids == ["a", "b"]
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


def test_snapshot_rejects_naive_timestamp():
    with pytest.raises(ValidationError, match="timezone-aware"):
        snapshot("a", (2.0, 4.0, 4.0), NOW.replace(tzinfo=None))


def test_snapshot_normalizes_aware_timestamp_to_utc():
    observed_at = NOW.astimezone(timezone(timedelta(hours=8)))

    market_snapshot = snapshot("a", (2.0, 4.0, 4.0), observed_at)

    assert market_snapshot.observed_at == NOW
    assert market_snapshot.observed_at.tzinfo == timezone.utc


def test_freshness_rejects_future_snapshot_beyond_clock_skew():
    assert is_market_snapshot_fresh(
        snapshot("a", (2.0, 4.0, 4.0), NOW + timedelta(seconds=60)),
        now=NOW,
    )
    assert not is_market_snapshot_fresh(
        snapshot("a", (2.0, 4.0, 4.0), NOW + timedelta(seconds=61)),
        now=NOW,
    )


def test_freshness_rejects_naive_reference_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        is_market_snapshot_fresh(snapshot("a", (2.0, 4.0, 4.0)), now=NOW.replace(tzinfo=None))


def test_consensus_is_input_order_invariant_for_same_timestamp_duplicates():
    snapshots = [
        snapshot("a", (2.0, 4.0, 4.0)),
        snapshot("a", (4.0, 4.0, 2.0)),
        snapshot("b", (5 / 3, 5.0, 5.0)),
        snapshot("c", (5.0, 5 / 3, 5.0)),
    ]

    forward = build_market_consensus(snapshots, now=NOW)
    reverse = build_market_consensus(list(reversed(snapshots)), now=NOW)

    assert forward == reverse
    assert forward.source_ids == ["a", "b", "c"]
    assert forward.probabilities is not None
    assert forward.probabilities.home_win > 0.5


@pytest.mark.parametrize(
    ("status", "fresh_source_count", "source_ids", "probabilities"),
    [
        ("consensus", 2, ["a", "b"], OutcomeProbabilities(home_win=0.4, draw=0.3, away_win=0.3)),
        ("consensus", 3, ["a", "b", "c"], None),
        ("single_source", 2, ["a", "b"], None),
        ("single_source", 1, ["a"], OutcomeProbabilities(home_win=0.4, draw=0.3, away_win=0.3)),
        ("insufficient_sources", 2, ["a", "b"], OutcomeProbabilities(home_win=0.4, draw=0.3, away_win=0.3)),
        ("insufficient_sources", 3, ["a", "b", "c"], None),
        ("consensus", 3, ["a", "a", "b"], OutcomeProbabilities(home_win=0.4, draw=0.3, away_win=0.3)),
    ],
)
def test_consensus_contract_rejects_invalid_coverage(
    status: str,
    fresh_source_count: int,
    source_ids: list[str],
    probabilities: OutcomeProbabilities | None,
):
    with pytest.raises(ValidationError):
        MarketConsensus(
            status=status,
            fresh_source_count=fresh_source_count,
            source_ids=source_ids,
            probabilities=probabilities,
        )


@pytest.mark.parametrize(
    "comparison",
    [
        {"status": "aligned"},
        {"status": "divergent", "model_leader": "home_win", "market_leader": "away_win"},
        {"status": "limited", "model_leader": "home_win"},
    ],
)
def test_market_comparison_contract_rejects_invalid_states(comparison: dict[str, object]):
    with pytest.raises(ValidationError):
        MarketComparison(**comparison)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_outcome_odds_reject_non_finite_values(value: float):
    with pytest.raises(ValidationError):
        OutcomeOdds(home_win=value, draw=3.0, away_win=4.0)

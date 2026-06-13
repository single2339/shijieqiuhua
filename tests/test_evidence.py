"""Smoke tests for backend.football_osint.evidence (W1 skeleton).

These lock the strong/weak/insufficient thresholds (PRD §4.5). W2 will
add real adapters that produce evidence; thresholds must keep this contract.
"""
from __future__ import annotations

from backend.football_osint.evidence import (
    STRONG_THRESHOLD,
    WEAK_THRESHOLD,
    by_strength,
    classify_strength,
)
from backend.football_osint.models import OsintEvidence


def _ev(confidence: float, eid: str = "ev_001") -> OsintEvidence:
    return OsintEvidence(
        id=eid,
        source="test",
        source_type="test",
        claim="x",
        topic="test",
        side="neutral",
        confidence=confidence,
        freshness=1.0,
    )


def test_classify_strength_strong():
    assert classify_strength(0.50) == "strong"
    assert classify_strength(0.99) == "strong"


def test_classify_strength_weak():
    assert classify_strength(0.49) == "weak"
    assert classify_strength(0.25) == "weak"


def test_classify_strength_insufficient():
    assert classify_strength(0.24) == "insufficient"
    assert classify_strength(0.0) == "insufficient"


def test_thresholds_match_prd():
    """Lock the thresholds at module level so a future PR cannot quietly drift."""
    assert STRONG_THRESHOLD == 0.50
    assert WEAK_THRESHOLD == 0.25


def test_by_strength_buckets_all_three():
    items = [_ev(0.6, "a"), _ev(0.3, "b"), _ev(0.1, "c"), _ev(0.5, "d")]
    buckets = by_strength(items)
    assert {ev.id for ev in buckets["strong"]} == {"a", "d"}
    assert {ev.id for ev in buckets["weak"]} == {"b"}
    assert {ev.id for ev in buckets["insufficient"]} == {"c"}

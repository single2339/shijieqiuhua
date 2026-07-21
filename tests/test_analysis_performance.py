from __future__ import annotations

from types import SimpleNamespace

from backend.models import IntelLayer, Verdict
from backend.processors import analysis


def _unique_item(index: int):
    return SimpleNamespace(
        id=str(index),
        title=f"uniqueevent{index}",
        summary="",
        country=f"country-{index}",
        layer=IntelLayer.POLITICS,
        captured_at="2026-07-21",
        confidence=0.5,
        evidence_count=1,
        sources=[f"source-{index}"],
        source_system=f"source-{index}",
        url="",
        verdict=Verdict.UNCERTAIN,
    )


def test_event_clustering_does_not_compare_every_unrelated_cluster(monkeypatch):
    comparisons = 0
    original = analysis._cluster_match_score

    def count_comparison(*args):
        nonlocal comparisons
        comparisons += 1
        return original(*args)

    monkeypatch.setattr(analysis, "_cluster_match_score", count_comparison)

    result = analysis.generate_event_clusters([_unique_item(index) for index in range(500)])

    assert result["total_clusters"] == 500
    assert comparisons < 1000

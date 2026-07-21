"""Tests for the situation brief MVP."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import GeoPoint, IntelItem, IntelLayer, Verdict
import backend.processors.analysis as analysis
from backend.processors.analysis import (
    compute_corroboration,
    generate_event_clusters,
    generate_situation_brief,
    generate_warning_indicators,
)


def _item(
    item_id: str,
    title: str,
    layer: IntelLayer,
    country: str,
    confidence: float,
    sources: list[str],
) -> IntelItem:
    return IntelItem(
        id=item_id,
        title=title,
        summary=f"Summary for {title}",
        layer=layer,
        location=GeoPoint(lat=0, lng=0),
        location_name=country,
        country=country,
        confidence=confidence,
        verdict=Verdict.UNCERTAIN,
        bayesian_trace=[0.5, confidence],
        evidence_count=1,
        sources=sources,
        source_system=sources[0],
        captured_at="2026-06-01T08:00:00Z",
        url=f"https://example.com/{item_id}",
    )


def test_situation_brief_outputs_judgments_evidence_and_gaps():
    items = [
        _item("a", "Military deployment reported near border", IntelLayer.MILITARY, "Ukraine", 0.82, ["Reuters", "BBC"]),
        _item("b", "Cyber incident affects energy provider", IntelLayer.CYBER, "Ukraine", 0.62, ["CISA"]),
        _item("c", "Market reaction follows policy signal", IntelLayer.FINANCE, "United States", 0.51, ["Bloomberg"]),
    ]

    brief = generate_situation_brief(
        items,
        scope={"date": "2026-06-01"},
        requested_layers=["military", "cyber", "finance", "health"],
    )

    assert brief["total_items"] == 3
    assert brief["intelligence_level"]["level"] in {"L1", "L2", "L3", "L4"}
    assert brief["core_findings"]
    assert brief["confirmed_facts"]
    assert brief["assessments"]
    assert brief["pending_verification"]
    assert brief["key_judgments"]
    assert brief["evidence"][0]["id"] == "E01"
    assert brief["evidence"][0]["confidence_level"] in {"L1", "L2", "L3", "L4"}
    assert any("公共卫生" in gap["description"] for gap in brief["collection_gaps"])
    assert any(task["priority"] == "高" for task in brief["recommended_tasks"])


def test_event_clusters_group_related_claims_with_confidence():
    items = [
        _item("a", "Military deployment reported near border", IntelLayer.MILITARY, "Ukraine", 0.82, ["Reuters"]),
        _item("b", "BBC reports military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.78, ["BBC"]),
        _item("c", "Market reaction follows policy signal", IntelLayer.FINANCE, "United States", 0.51, ["Bloomberg"]),
    ]

    result = generate_event_clusters(items, scope={"date": "2026-06-01"})

    assert result["total_items"] == 3
    assert result["total_clusters"] >= 2
    top = result["clusters"][0]
    assert top["item_count"] == 2
    assert top["confidence"]["level"] == "L2"
    assert top["claims"][0]["verification_status"] == "双源支撑"
    assert top["evidence"][0]["id"] == "E01"


def test_corroboration_uses_event_level_overlap():
    items = [
        _item("a", "Military deployment reported near border", IntelLayer.MILITARY, "Ukraine", 0.82, ["Reuters"]),
        _item("b", "BBC reports military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.78, ["BBC"]),
        _item("c", "Market reaction follows policy signal", IntelLayer.FINANCE, "United States", 0.51, ["Bloomberg"]),
    ]

    result = compute_corroboration(items)

    assert result["event_count"] >= 2
    pair = next(
        p for p in result["top_pairs"]
        if {p["source_a"], p["source_b"]} == {"Reuters", "BBC"}
    )
    assert pair["shared_events"] == 1
    assert pair["high_confidence_events"] == 1
    assert pair["shared_event_ids"]


def test_warning_indicators_trigger_on_high_impact_verified_event():
    items = [
        _item("a", "Military deployment reported near border", IntelLayer.MILITARY, "Ukraine", 0.82, ["Reuters"]),
        _item("b", "BBC reports military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.78, ["BBC"]),
        _item("c", "AP confirms military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.8, ["AP"]),
    ]

    result = generate_warning_indicators(items, scope={"date": "2026-06-01"}, requested_layers=["military"])

    assert result["overall_level"] in {"critical", "high"}
    assert result["active_indicator_count"] >= 1
    assert result["indicators"][0]["confidence"]["level"] == "L1"
    assert result["indicators"][0]["related_event_ids"]
    assert result["collection_requirements"]


def test_warning_indicators_can_reuse_precomputed_event_clusters(monkeypatch):
    items = [
        _item("a", "Military deployment reported near border", IntelLayer.MILITARY, "Ukraine", 0.82, ["Reuters"]),
        _item("b", "BBC reports military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.78, ["BBC"]),
        _item("c", "AP confirms military deployment near Ukraine border", IntelLayer.MILITARY, "Ukraine", 0.8, ["AP"]),
    ]
    clusters = generate_event_clusters(items, scope={"date": "2026-06-01"})

    def fail_if_recomputed(*_args, **_kwargs):
        raise AssertionError("warning indicators should reuse the event cluster snapshot")

    monkeypatch.setattr(analysis, "generate_event_clusters", fail_if_recomputed)

    result = analysis.generate_warning_indicators(
        items,
        scope={"date": "2026-06-01"},
        requested_layers=["military"],
        clusters_result=clusters,
    )

    assert result["active_indicator_count"] >= 1

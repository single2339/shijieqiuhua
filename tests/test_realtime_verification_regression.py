from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend import main


def _event_result(scope: dict) -> dict:
    return {
        "scope": scope,
        "total_items": 1,
        "total_clusters": 0,
        "unclustered_count": 0,
        "clusters": [],
    }


def _warning_result(scope: dict) -> dict:
    return {
        "scope": scope,
        "total_items": 1,
        "overall_level": "normal",
        "active_indicator_count": 0,
        "indicators": [],
        "collection_requirements": [],
    }


def _brief_result(scope: dict) -> dict:
    return {
        "scope": scope,
        "summary": "测试态势研判",
        "total_items": 1,
        "source_count": 1,
        "core_findings": [],
        "confirmed_facts": [],
        "assessments": [],
        "alternative_explanations": [],
        "pending_verification": [],
        "key_judgments": [],
        "evidence": [],
        "contradictions": [],
        "collection_gaps": [],
        "recommended_tasks": [],
        "recommended_next_steps": [],
    }


class _FakeAnalysisResult:
    def __init__(self, data: dict):
        self.data = data


@pytest.mark.asyncio
async def test_realtime_verification_events_and_warnings_share_cluster_snapshot(monkeypatch):
    cluster_calls = 0
    build_calls = []
    main._dashboard_cache.clear()

    async def fake_build_items_async(*_args, **kwargs):
        build_calls.append(kwargs)
        return [SimpleNamespace(layer=SimpleNamespace(value="military"))]

    def fake_generate_event_clusters(items, scope, limit=20):
        nonlocal cluster_calls
        cluster_calls += 1
        return _event_result(scope)

    def fake_generate_warning_indicators(items, scope, requested_layers, clusters_result=None):
        assert clusters_result is not None
        assert clusters_result["scope"] == scope
        return _warning_result(scope)

    monkeypatch.setattr(main, "_build_items_async", fake_build_items_async)
    monkeypatch.setattr(main, "generate_event_clusters", fake_generate_event_clusters)
    monkeypatch.setattr(main, "generate_warning_indicators", fake_generate_warning_indicators)

    events, warnings = await asyncio.gather(
        main.analysis_events(start_date="2026-05-20", end_date="2026-06-02", layers="military,cyber"),
        main.analysis_warnings(start_date="2026-05-20", end_date="2026-06-02", layers="military,cyber"),
    )

    assert events.total_items == 1
    assert warnings.total_items == 1
    assert cluster_calls == 1
    assert build_calls[0]["limit"] > 0
    assert build_calls[0]["use_merge_groups"] is False


@pytest.mark.asyncio
async def test_corroboration_uses_scoped_lightweight_window(monkeypatch):
    build_calls = []
    agent_items = []

    items = [
        SimpleNamespace(layer=SimpleNamespace(value="military")),
        SimpleNamespace(layer=SimpleNamespace(value="finance")),
    ]

    async def fake_build_items_async(*_args, **kwargs):
        build_calls.append(kwargs)
        return items

    class FakeAgent:
        async def run(self, task):
            agent_items.extend(task.params["items"])
            return _FakeAnalysisResult({
                "sources": [],
                "matrix": [],
                "top_pairs": [],
                "event_count": 0,
                "claim_count": 0,
            })

    monkeypatch.setattr(main, "_build_items_async", fake_build_items_async)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_args, **_kwargs: FakeAgent())

    result = await main.analysis_corroboration(
        start_date="2026-05-20",
        end_date="2026-06-02",
        layers="military",
        country="Ukraine",
    )

    assert result.event_count == 0
    assert [item.layer.value for item in agent_items] == ["military"]
    assert build_calls[0]["limit"] > 0
    assert build_calls[0]["use_merge_groups"] is False
    assert build_calls[0]["start_date"] == "2026-05-20"
    assert build_calls[0]["end_date"] == "2026-06-02"
    assert build_calls[0]["country_filter"] == "Ukraine"


@pytest.mark.asyncio
async def test_gap_analysis_uses_scoped_lightweight_window(monkeypatch):
    build_calls = []
    agent_items = []

    items = [
        SimpleNamespace(layer=SimpleNamespace(value="military")),
        SimpleNamespace(layer=SimpleNamespace(value="finance")),
    ]

    async def fake_build_items_async(*_args, **kwargs):
        build_calls.append(kwargs)
        return items

    class FakeAgent:
        async def run(self, task):
            agent_items.extend(task.params["items"])
            return _FakeAnalysisResult({"gaps": [], "coverage_stats": {"total_items": len(task.params["items"])}})

    monkeypatch.setattr(main, "_build_items_async", fake_build_items_async)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_args, **_kwargs: FakeAgent())

    result = await main.analysis_gaps(
        start_date="2026-05-20",
        end_date="2026-06-02",
        layers="military",
        country="Ukraine",
    )

    assert result.coverage_stats["total_items"] == 1
    assert [item.layer.value for item in agent_items] == ["military"]
    assert build_calls[0]["limit"] > 0
    assert build_calls[0]["use_merge_groups"] is False
    assert build_calls[0]["start_date"] == "2026-05-20"
    assert build_calls[0]["end_date"] == "2026-06-02"
    assert build_calls[0]["country_filter"] == "Ukraine"


@pytest.mark.asyncio
async def test_situation_brief_uses_lightweight_cached_window(monkeypatch):
    brief_calls = 0
    build_calls = []
    main._dashboard_cache.clear()

    async def fake_build_items_async(*_args, **kwargs):
        build_calls.append(kwargs)
        return [
            SimpleNamespace(layer=SimpleNamespace(value="military")),
            SimpleNamespace(layer=SimpleNamespace(value="finance")),
        ]

    def fake_generate_situation_brief(items, scope, requested_layers):
        nonlocal brief_calls
        brief_calls += 1
        assert [item.layer.value for item in items] == ["military"]
        assert requested_layers == ["military"]
        return _brief_result(scope)

    monkeypatch.setattr(main, "_build_items_async", fake_build_items_async)
    monkeypatch.setattr(main, "generate_situation_brief", fake_generate_situation_brief)

    first = await main.analysis_brief(
        start_date="2026-05-20",
        end_date="2026-06-02",
        layers="military",
        country="Ukraine",
    )
    second = await main.analysis_brief(
        start_date="2026-05-20",
        end_date="2026-06-02",
        layers="military",
        country="Ukraine",
    )

    assert first.total_items == 1
    assert second.total_items == 1
    assert brief_calls == 1
    assert len(build_calls) == 1
    assert build_calls[0]["limit"] > 0
    assert build_calls[0]["use_merge_groups"] is False

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI

from backend import main


class _FakeIndexer:
    def incremental_update(self) -> int:
        return 0

    def close(self) -> None:
        pass


def _prepare_lifespan(monkeypatch, tmp_path):
    (tmp_path / "seed.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setattr(main, "_init_indexer", lambda: None)
    monkeypatch.setattr(main, "_get_indexer", lambda: _FakeIndexer())
    monkeypatch.setattr(main, "_indexer", _FakeIndexer())
    monkeypatch.setattr(main, "_build_items", lambda *args, **kwargs: [])


def test_api_role_opens_index_without_building_or_updating(monkeypatch):
    calls: list[str] = []

    class FakeIndexer:
        def count(self):
            calls.append("count")
            return 10

        def build_index(self):
            calls.append("build")
            return 10

        def incremental_update(self):
            calls.append("incremental")
            return 1

    monkeypatch.setenv("OSINT_ROLE", "api")
    monkeypatch.setattr(main, "_get_indexer", lambda: FakeIndexer())

    main._init_indexer()

    assert calls == ["count"]


@pytest.mark.asyncio
async def test_api_role_does_not_start_background_orchestrator(monkeypatch, tmp_path):
    _prepare_lifespan(monkeypatch, tmp_path)
    monkeypatch.setenv("OSINT_ROLE", "api")

    calls: list[str] = []

    class FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            calls.append("init")

        async def start_collection_loop(self):
            calls.append("collection")

        async def start_merge_loop(self):
            calls.append("merge")

        async def stop(self):
            calls.append("stop")

    import backend.agents.system.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "OrchestratorAgent", FakeOrchestrator)

    async with main.lifespan(FastAPI()):
        pass

    assert calls == []


@pytest.mark.asyncio
async def test_all_role_starts_background_orchestrator(monkeypatch, tmp_path):
    _prepare_lifespan(monkeypatch, tmp_path)
    monkeypatch.setenv("OSINT_ROLE", "all")

    calls: list[str] = []

    class FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            calls.append("init")

        async def start_collection_loop(self):
            calls.append("collection")

        async def start_merge_loop(self):
            calls.append("merge")

        async def stop(self):
            calls.append("stop")

    import backend.agents.system.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "OrchestratorAgent", FakeOrchestrator)

    async with main.lifespan(FastAPI()):
        pass

    assert calls == ["init", "collection", "merge", "stop"]


@pytest.mark.asyncio
async def test_stats_without_dates_uses_default_recent_window(monkeypatch):
    captured: dict[str, str] = {}
    main._dashboard_cache.clear()

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 7, tzinfo=timezone.utc)

    def fake_build_stats(start_date: str, end_date: str):
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        return main.DashboardStats(
            total_items=0,
            total_sources=0,
            by_layer=[],
            daily_trend=[],
            source_matrix=[],
            geo_distribution=[],
            top_keywords=[],
        )

    def fail_build_items(*_args, **_kwargs):
        raise AssertionError("stats should not build full IntelItem objects")

    monkeypatch.setattr(main, "datetime", _FakeDateTime)
    monkeypatch.setattr(main, "_build_dashboard_stats_fast", fake_build_stats)
    monkeypatch.setattr(main, "_build_items", fail_build_items)
    monkeypatch.setattr(main, "STATS_DEFAULT_DAYS", 14, raising=False)

    await main.dashboard_stats()

    assert captured == {
        "start_date": "2026-05-25",
        "end_date": "2026-06-07",
    }

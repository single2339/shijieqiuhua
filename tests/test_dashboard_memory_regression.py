from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend import main
from backend.bronze_reader import BronzeDocument
from backend.models import IntelLayer


def test_build_items_pushes_date_filter_into_index_query(monkeypatch):
    calls: list[dict] = []

    class FakeIndexer:
        def get_all(self):
            pytest.fail("dashboard item building must not load every document before filtering")

        def query(self, **kwargs):
            calls.append(kwargs)
            return []

    monkeypatch.setattr(main, "_get_indexer", lambda: FakeIndexer())

    assert main._build_items(start_date="2026-07-21", end_date="2026-07-21") == []
    assert calls == [{
        "start_date": "2026-07-21",
        "end_date": "2026-07-21",
        "layer": "",
        "country": "",
        "limit": 0,
    }]


def test_nonmerged_analysis_does_not_load_merge_index(monkeypatch):
    doc = BronzeDocument({
        "raw_document_id": "doc-1",
        "body_inline": "港口运行正常",
        "source_system": "test-source",
        "captured_at": "2026-07-21T00:00:00Z",
        "extensions": {"summary": "港口运行正常"},
    })

    class FakeIndexer:
        def query(self, **_kwargs):
            return [doc]

    monkeypatch.setattr(main, "_get_indexer", lambda: FakeIndexer())
    monkeypatch.setattr(
        main,
        "load_merge_index",
        lambda *_args: pytest.fail("non-merged analysis must not parse the merge index"),
    )
    monkeypatch.setattr(main, "extract_location_with_fallback", lambda *_args: ("", "", 0.0, 0.0))
    monkeypatch.setattr(main, "_get_layer", lambda _doc: IntelLayer.LOGISTICS if hasattr(IntelLayer, "LOGISTICS") else IntelLayer.ECONOMY)

    items = main._build_items(use_merge_groups=False)

    assert [item.id for item in items] == ["doc-1"]


def test_dashboard_excludes_quarantined_and_unclassified_documents(monkeypatch):
    quarantined = BronzeDocument({
        "raw_document_id": "doc-quarantined",
        "body_inline": "A long generic tutorial with no warning indicator or intelligence value.",
        "source_system": "generic-blog",
        "captured_at": "2026-07-21T00:00:00Z",
        "extensions": {"intelligence_admission": {"status": "quarantined"}},
    })
    unclassified = BronzeDocument({
        "raw_document_id": "doc-unclassified",
        "body_inline": "A practical CSS layout guide.",
        "source_system": "legacy-blog",
        "captured_at": "2026-07-21T00:00:00Z",
        "extensions": {},
    })

    class FakeIndexer:
        def query(self, **_kwargs):
            return [quarantined, unclassified]

    monkeypatch.setattr(main, "_get_indexer", lambda: FakeIndexer())
    monkeypatch.setattr(main, "extract_location_with_fallback", lambda *_args: ("", "", 0.0, 0.0))
    monkeypatch.setattr(main, "_get_layer", lambda _doc: IntelLayer.UNCLASSIFIED)

    assert main._build_items(use_merge_groups=False) == []


def test_dashboard_layer_summary_does_not_expose_internal_unclassified_bucket(monkeypatch):
    class FakeIndexer:
        def get_available_dates(self):
            return []

    monkeypatch.setattr(main, "_get_indexer", lambda: FakeIndexer())

    dashboard = main._build_dashboard_data([], page=1, page_size=100)

    assert IntelLayer.UNCLASSIFIED not in {summary.layer for summary in dashboard.layers}


def test_master_item_cache_has_a_small_independent_bound(monkeypatch):
    main._master_list_cache.clear()
    monkeypatch.setattr(main, "MASTER_LIST_CACHE_MAX_SIZE", 2, raising=False)
    monkeypatch.setattr(main, "_build_items", lambda **kwargs: [kwargs.get("start_date")])

    main._get_or_build_items("2026-07-19", "2026-07-19", "")
    main._get_or_build_items("2026-07-20", "2026-07-20", "")
    main._get_or_build_items("2026-07-21", "2026-07-21", "")

    assert len(main._master_list_cache) == 2


@pytest.mark.asyncio
async def test_unscoped_dashboard_uses_a_bounded_recent_window(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 21, tzinfo=timezone.utc)

    monkeypatch.setattr(main, "datetime", FakeDateTime)
    monkeypatch.setattr(main, "DASHBOARD_DEFAULT_DAYS", 1, raising=False)
    monkeypatch.setattr(
        main,
        "_get_or_build_items",
        lambda start_date, end_date, date: calls.append((start_date, end_date, date)) or [],
    )
    monkeypatch.setattr(main, "_build_dashboard_data", lambda items, page, page_size: "dashboard")
    main._dashboard_cache.clear()

    assert await main.get_dashboard() == "dashboard"
    assert calls == [("2026-07-21", "2026-07-21", "")]


def test_prewarm_uses_the_bounded_recent_window(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 21, tzinfo=timezone.utc)

    monkeypatch.setattr(main, "datetime", FakeDateTime)
    monkeypatch.setattr(main, "DASHBOARD_DEFAULT_DAYS", 1, raising=False)
    monkeypatch.setattr(
        main,
        "_get_or_build_items",
        lambda start_date, end_date, date: calls.append((start_date, end_date, date)) or [],
    )
    monkeypatch.setattr(main, "_build_dashboard_data", lambda items, page, page_size: object())
    main._dashboard_cache.clear()

    main._prewarm_dashboard_cache()

    assert calls == [("2026-07-21", "2026-07-21", "")]


def test_api_cache_prewarm_also_warms_super_analysis(monkeypatch, tmp_path):
    calls: list[object] = []
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setattr(main, "_prewarm_dashboard_cache", lambda: calls.append("dashboard"))

    from backend.agents.intelligence import super_analyst
    monkeypatch.setattr(
        super_analyst,
        "prewarm_super_analysis",
        lambda storage: calls.append(("super", storage)) or {"catalog": "ready", "embedding": "ready"},
        raising=False,
    )

    main._prewarm_api_caches()

    assert calls == ["dashboard", ("super", tmp_path)]

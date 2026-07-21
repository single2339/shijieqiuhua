from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend import main


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

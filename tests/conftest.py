import os

import pytest


def pytest_configure(config):
    os.environ.setdefault("JWT_SECRET", "pytest-test-secret")


@pytest.fixture(autouse=True)
def _isolate_caches():
    """Clear shared module-level TTL caches between tests.

    search_cache/schedule_cache are process-global; without this, deterministic
    query keys (same teams) leak cached results across tests.
    """
    from backend.football_osint import cache

    for c in (cache.search_cache, cache.schedule_cache, cache.analysis_cache, cache.weather_cache):
        with c._lock:
            c._store.clear()
    yield


@pytest.fixture(autouse=True)
def _no_real_web_search(monkeypatch):
    """Prevent tests from making real DuckDuckGo HTTP calls by default."""
    from backend.football_osint.adapters import web_search

    monkeypatch.setattr(web_search, "search", lambda query, **kwargs: [])


@pytest.fixture(autouse=True)
def _no_real_dongqiudi_schedule(monkeypatch):
    """Prevent tests from making real dongqiudi schedule API calls by default."""
    from backend.football_osint.adapters import dongqiudi_schedule

    monkeypatch.setattr(dongqiudi_schedule, "fetch_fixtures", lambda: [])


@pytest.fixture(autouse=True)
def _no_real_dongqiudi_analysis(monkeypatch):
    """Prevent tests from making real dongqiudi analysis HTTP calls by default."""
    from backend.football_osint.adapters import dongqiudi_analysis

    monkeypatch.setattr(dongqiudi_analysis, "fetch_text", lambda url: None)

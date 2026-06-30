"""Tests for football_data_schedule.fetch_fixtures_for_range."""
from __future__ import annotations

import httpx
import pytest

from backend.football_osint import cache
from backend.football_osint.adapters import football_data_schedule


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.schedule_cache._store.clear()
    yield
    cache.schedule_cache._store.clear()


def test_fetch_fixtures_for_range_queries_explicit_dates(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "matches": [
                        {
                            "id": 1,
                            "utcDate": "2026-05-01T19:00:00Z",
                            "status": "FINISHED",
                            "competition": {"name": "Premier League"},
                            "homeTeam": {"name": "Man City"},
                            "awayTeam": {"name": "Liverpool"},
                            "score": {"fullTime": {"home": 2, "away": 1}},
                        }
                    ]
                }
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(
        football_data_schedule.name_translation, "translate",
        lambda names: {n: n for n in names},
    )

    fixtures = football_data_schedule.fetch_fixtures_for_range("2026-05-01", "2026-05-02")

    assert captured["params"] == {"dateFrom": "2026-05-01", "dateTo": "2026-05-02"}
    assert len(fixtures) == 1
    assert fixtures[0].home_team == "Man City"
    assert fixtures[0].status == "finished"
    assert fixtures[0].home_score == 2
    assert fixtures[0].away_score == 1



def test_parse_matches_preserves_provider_identity(monkeypatch):
    from backend.football_osint.adapters import football_data_schedule as fds

    monkeypatch.setattr(
        fds.name_translation, "translate",
        lambda names: {n: n for n in names},
    )
    payload = {
        "matches": [{
            "id": 537424,
            "utcDate": "2026-06-30T17:00:00Z",
            "status": "TIMED",
            "competition": {"name": "FIFA World Cup"},
            "homeTeam": {"id": 808, "name": "Côte d'Ivoire"},
            "awayTeam": {"id": 816, "name": "Norway"},
            "score": {"fullTime": {"home": None, "away": None}},
        }]
    }

    fixture = fds.parse_matches(payload)[0]

    assert fixture.provider == "football-data"
    assert fixture.provider_match_id == "537424"
    assert fixture.home_provider_id == "808"
    assert fixture.away_provider_id == "816"

def test_fetch_fixtures_for_range_without_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    assert football_data_schedule.fetch_fixtures_for_range("2026-05-01", "2026-05-02") == []

"""Tests for GET /api/football/osint/track-record."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app_football import app
from backend.football_osint import track_record


def test_track_record_route_returns_settled_only_below_threshold(monkeypatch):
    monkeypatch.setattr(track_record, "get_stats", lambda **kw: {"settled": 5})
    client = TestClient(app)

    res = client.get("/api/football/osint/track-record")

    assert res.status_code == 200
    assert res.json() == {"settled": 5}


def test_track_record_route_returns_full_stats_above_threshold(monkeypatch):
    fake_stats = {"settled": 30, "lean_accuracy": 0.6, "scoreline_accuracy": 0.2, "recent": []}
    monkeypatch.setattr(track_record, "get_stats", lambda **kw: fake_stats)
    client = TestClient(app)

    res = client.get("/api/football/osint/track-record")

    assert res.status_code == 200
    assert res.json() == fake_stats

"""Paid access and immutable bronze-history coverage."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient


def _paid_user():
    return {"id": 1, "role": "user", "is_active": 1}


def test_history_review_compare_and_job_routes_require_login():
    from backend.app_football import app

    client = TestClient(app)
    assert client.get("/api/football/osint/history").status_code == 401
    assert client.get("/api/football/osint/history/fo_20260630_abcdef1234").status_code == 401
    assert client.get("/api/football/osint/jobs/fo_20260630_abcdef1234").status_code == 401
    assert client.get("/api/football/osint/jobs/fo_20260630_abcdef1234/report.md").status_code == 401
    assert client.post("/api/football/osint/compare", json={"job_ids": ["fo_20260630_abcdef1234"]}).status_code == 401


def test_history_review_compare_and_job_routes_require_paid_entitlement(monkeypatch):
    from backend.app_football import app
    from backend.auth import routes as auth_routes
    import backend.billing as billing

    monkeypatch.setattr(auth_routes, "get_current_user", lambda request: _paid_user())
    monkeypatch.setattr(billing, "has_entitlement", lambda user_id: False)

    client = TestClient(app)
    assert client.get("/api/football/osint/history").status_code == 403
    assert client.get("/api/football/osint/history/fo_20260630_abcdef1234").status_code == 403
    assert client.get("/api/football/osint/jobs/fo_20260630_abcdef1234").status_code == 403
    assert client.get("/api/football/osint/jobs/fo_20260630_abcdef1234/report.md").status_code == 403
    assert client.post("/api/football/osint/compare", json={"job_ids": ["fo_20260630_abcdef1234"]}).status_code == 403


def test_paid_history_route_returns_history_payload(monkeypatch):
    from backend.app_football import app
    from backend.auth import routes as auth_routes
    import backend.billing as billing
    from backend.football_osint import routes

    monkeypatch.setattr(auth_routes, "get_current_user", lambda request: _paid_user())
    monkeypatch.setattr(billing, "has_entitlement", lambda user_id: True)
    monkeypatch.setattr(routes.history_module, "get_history_list", lambda *, days, paid: [])

    response = TestClient(app).get("/api/football/osint/history")

    assert response.status_code == 200
    assert response.json() == []


def test_paid_job_replay_uses_persisted_market_snapshot_not_current_cache(monkeypatch, tmp_path):
    from backend.football_osint import history as history_module, routes, warm_cache
    from backend.football_osint.models import (
        FootballOsintJob,
        FootballOsintJobStatus,
        MarketContext,
        MarketSourceSnapshot,
        OsintMatch,
        OutcomeOdds,
    )

    job_id = "fo_20260630_abcdef1234"
    bronze_root = tmp_path / "football_osint"
    job_dir = bronze_root / job_id
    job_dir.mkdir(parents=True)

    persisted = FootballOsintJob(
        job_id=job_id,
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="巴西", away_team="日本", kickoff_at="2026-06-30T01:00:00+08:00"),
        market_context=MarketContext(snapshots=[MarketSourceSnapshot(
            source_id="persisted-book", display_name="历史快照", odds=OutcomeOdds(home_win=2.0, draw=3.0, away_win=4.0),
            observed_at="2026-06-29T10:00:00+08:00",
        )]),
    )
    current = persisted.model_copy(deep=True)
    current.market_context.snapshots[0].source_id = "current-book"
    (job_dir / "status.json").write_text(persisted.model_dump_json(), encoding="utf-8")

    monkeypatch.setattr(history_module, "DEFAULT_STORAGE_ROOT", bronze_root)
    monkeypatch.setattr(warm_cache, "get_cached_by_job_id", lambda _job_id: current)
    monkeypatch.setattr(routes, "_require_paid", lambda request: _paid_user())

    replayed = asyncio.run(routes.get_job(job_id, object()))

    assert replayed.market_context.snapshots[0].source_id == "persisted-book"

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app_football import app
from backend.football_osint.models import FootballOsintJobRequest


def test_compare_route_rejects_non_list_job_ids(monkeypatch):
    from backend.auth import routes as auth_routes
    import backend.billing as billing

    monkeypatch.setattr(auth_routes, "get_current_user", lambda request: {"id": 1, "role": "user", "is_active": 1})
    monkeypatch.setattr(billing, "has_entitlement", lambda user_id: True)

    res = TestClient(app).post("/api/football/osint/compare", json={"job_ids": "abc"})

    assert res.status_code == 422


def test_pipeline_job_id_changes_with_question_and_user_notes():
    from backend.football_osint import pipeline

    base = FootballOsintJobRequest(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00", competition="英超", question="角球？")
    other_question = base.model_copy(update={"question": "红黄牌？"})
    with_note = base.model_copy(update={"user_supplied": {"notes": ["private note"]}})

    assert pipeline._job_id(base) != pipeline._job_id(other_question)
    assert pipeline._job_id(base) != pipeline._job_id(with_note)


def test_zero_config_collection_does_not_attach_sporttery_odds(monkeypatch):
    from backend.football_osint import pipeline
    from backend.football_osint.models import OsintEvidence, OsintSourceStatus

    called = {"sporttery": False}
    request = FootballOsintJobRequest(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00", competition="英超")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda request, evidence: ("", "无天气"))
    monkeypatch.setattr(pipeline, "_collect_search_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda request, evidence: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda request, evidence, sources: None)

    def fake_sporttery(request, evidence):
        called["sporttery"] = True
        return "ev_sporttery", ""
    monkeypatch.setattr(pipeline, "_collect_sporttery", fake_sporttery, raising=False)

    pipeline._collect_zero_config_sources(request, evidence, sources)

    assert called["sporttery"] is False
    assert all("体彩" not in ev.claim and ev.source_type != "odds" for ev in evidence)
    assert all(src.adapter != "sporttery" for src in sources)

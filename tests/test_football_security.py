from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_model_copy_normalizes_user_supplied_dict():
    request = FootballOsintJobRequest(home_team="曼城", away_team="利物浦")

    copied = request.model_copy(update={"user_supplied": {"notes": ["private note"]}})

    assert copied.user_supplied.notes == ["private note"]


def test_concurrent_evidence_append_mints_unique_ids_referenced_by_sources():
    from backend.football_osint import evidence as evidence_module
    from backend.football_osint.models import OsintSourceStatus

    class CoordinatedEvidence(list):
        def __init__(self) -> None:
            super().__init__()
            self.barrier = Barrier(4)

        def __len__(self) -> int:
            length = super().__len__()
            append_lock = getattr(evidence_module, "_EVIDENCE_APPEND_LOCK", None)
            if append_lock is None or not append_lock.locked():
                self.barrier.wait(timeout=2)
            return length

    evidence = CoordinatedEvidence()

    def collect(index: int) -> OsintSourceStatus:
        evidence_id = evidence_module.append_evidence(
            evidence,
            source=f"collector-{index}", source_type="test", claim="concurrent evidence",
            topic="test.concurrent", side="neutral", confidence=0.5,
        )
        return OsintSourceStatus(
            adapter=f"collector-{index}", label="并发采集", status="ok", evidence_ids=[evidence_id],
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(collect, range(4)))

    evidence_ids = [item.id for item in evidence]
    assert len(evidence_ids) == len(set(evidence_ids)) == 4
    assert {reference for source in sources for reference in source.evidence_ids} == set(evidence_ids)


def test_zero_config_collection_attaches_official_sporttery_market_once(monkeypatch):
    from backend.football_osint import pipeline
    from backend.football_osint.models import OsintEvidence, OsintSourceStatus

    from backend.football_osint.models import OutcomeOdds, OutcomeProbabilities, SportteryMarket

    called = {"sporttery": 0}
    request = FootballOsintJobRequest(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00", competition="英超")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda request, evidence: ("", "无天气"))
    monkeypatch.setattr(pipeline, "_collect_search_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda request, evidence: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda request, evidence, sources: None)

    market = SportteryMarket(
        had_odds=OutcomeOdds(home_win=2.0, draw=3.5, away_win=4.0),
        had_implied_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.28, away_win=0.24),
        observed_at="2026-08-11T12:00:00+00:00",
    )

    def fake_sporttery(request, evidence):
        called["sporttery"] += 1
        evidence.append(OsintEvidence(
            id="ev_sporttery", source="中国体育彩票", source_type="odds",
            claim="体彩胜平负", topic="odds.sporttery.market", confidence=0.6,
        ))
        return market, "ev_sporttery", ""
    monkeypatch.setattr(pipeline, "_collect_sporttery", fake_sporttery, raising=False)

    _, collected_market = pipeline._collect_zero_config_sources(request, evidence, sources)

    assert called["sporttery"] == 1
    assert [ev.topic for ev in evidence].count("odds.sporttery.market") == 1
    assert next(src for src in sources if src.adapter == "sporttery").status == "ok"
    assert collected_market == market


def test_zero_config_collection_marks_uncovered_sporttery_as_skipped(monkeypatch):
    from backend.football_osint import pipeline
    from backend.football_osint.models import OsintEvidence, OsintSourceStatus

    request = FootballOsintJobRequest(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00", competition="英超")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda request, evidence: ("", "无天气"))
    monkeypatch.setattr(pipeline, "_collect_search_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda request, evidence: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_sporttery", lambda request, evidence: (None, "", "体彩未覆盖该场比赛"), raising=False)

    pipeline._collect_zero_config_sources(request, evidence, sources)

    sporttery_source = next(src for src in sources if src.adapter == "sporttery")
    assert sporttery_source.status == "skipped"
    assert not [ev for ev in evidence if ev.topic == "odds.sporttery.market"]

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.football_osint import decision_service
from backend.football_osint.models import (
    ConfidenceRating,
    FootballOsintJob,
    FootballOsintJobRequest,
    FootballOsintJobStatus,
    IntelligenceFinding,
    MarketConsensus,
    MarketContext,
    MarketSourceSnapshot,
    OsintMatch,
    OutcomeOdds,
    OutcomeProbabilities,
    PredictionResult,
    SportteryMarket,
)


NOW = datetime(2026, 8, 15, 12, tzinfo=timezone.utc)
REQUEST = FootballOsintJobRequest(
    home_team="主队",
    away_team="客队",
    kickoff_at="2026-08-16T20:00:00+08:00",
    competition="英超",
    question="全场角球数预测是多少？",
)


def _snapshot(source_id: str) -> MarketSourceSnapshot:
    return MarketSourceSnapshot(
        source_id=source_id,
        display_name=source_id,
        odds=OutcomeOdds(home_win=2.0, draw=4.0, away_win=4.0),
        observed_at=NOW,
    )


def _job() -> FootballOsintJob:
    probabilities = OutcomeProbabilities(home_win=0.50, draw=0.28, away_win=0.22)
    prediction = PredictionResult(
        lean="home",
        summary="主队占优。",
        outcome_probabilities=probabilities,
        primary_probability=0.50,
        margin_to_runner_up=0.22,
        clarity="clear",
        scoreline_band=["2-1"],
        drivers=["近期状态"],
        sporttery_market=SportteryMarket(
            had_odds=OutcomeOdds(home_win=2.0, draw=4.0, away_win=4.0),
            had_implied_probabilities=probabilities,
            observed_at=NOW.isoformat(),
        ),
    )
    return FootballOsintJob(
        job_id="fo_20260815_abcdef1234",
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="主队", away_team="客队", kickoff_at=REQUEST.kickoff_at, competition="英超"),
        prediction=prediction,
        confidence=ConfidenceRating(level="L2", reason="证据较充分"),
        market_context=MarketContext(
            snapshots=[_snapshot("sporttery"), _snapshot("pinnacle"), _snapshot("bet365")],
            consensus=MarketConsensus(
                status="consensus",
                fresh_source_count=3,
                source_ids=["bet365", "pinnacle", "sporttery"],
                probabilities=probabilities,
            ),
        ),
        confirmed_findings=[
            IntelligenceFinding(
                id="finding_1", statement="状态支持主队", finding_type="assessment",
                confidence_level="L2", source_summary="公开来源",
            )
        ],
        updated_at=NOW.isoformat(),
    )


async def test_decision_uses_fulltime_cache_key_and_compares_after_prediction(monkeypatch):
    job = _job()
    received: list[FootballOsintJobRequest] = []

    async def fake_cache_or_compute(request):
        received.append(request)
        return SimpleNamespace(job=job)

    async def fake_state(request, resolved_job):
        assert resolved_job is job
        return "scheduled", None

    monkeypatch.setattr(decision_service.warm_cache, "cache_or_compute", fake_cache_or_compute)
    monkeypatch.setattr(decision_service, "_resolve_fixture_state", fake_state)

    decision = await decision_service.resolve(REQUEST)

    assert received[0].question == decision_service.FULLTIME_QUESTION
    assert decision.model_prediction == job.prediction
    assert decision.market_comparison.status == "aligned"
    assert decision.market_consensus == job.market_context.consensus
    assert decision.market_sources == job.market_context.snapshots
    assert decision.evidence_summary == job.confirmed_findings


def test_compose_degrades_cleanly_when_market_consensus_is_unavailable():
    job = _job()
    job.market_context = MarketContext(snapshots=[_snapshot("sporttery")])

    decision = decision_service.compose(job, fixture_status="scheduled")

    assert decision.market_consensus is None
    assert decision.market_comparison.status == "limited"
    assert decision.model_prediction == job.prediction
    assert "sporttery_market" not in decision.model_dump()["model_prediction"]
    assert "handicap_conclusion" not in decision.model_dump()["model_prediction"]
    assert "不构成投注" in decision.disclaimer


async def test_finished_fixture_uses_provider_settlement_time_not_job_update(monkeypatch):
    job = _job()
    job.updated_at = "2026-08-10T00:00:00+00:00"
    fixture = SimpleNamespace(
        status="finished",
        home_score=2,
        away_score=1,
        settled_at=NOW,
    )
    monkeypatch.setattr(decision_service, "_find_fixture", lambda _request: fixture)

    status, actual = await decision_service._resolve_fixture_state(REQUEST, job)

    assert status == "finished"
    assert actual is not None
    assert actual.settled_at == NOW
    assert actual.settled_at != decision_service._as_utc(job.updated_at)


async def test_dongqiudi_raw_fixture_with_score_becomes_finished_with_review(monkeypatch):
    from backend.football_osint.adapters import dongqiudi_schedule, football_data_schedule

    job = _job()
    raw_fixture = dongqiudi_schedule.Fixture(
        match_id="dqd_1",
        league="英超",
        kickoff_at=datetime.now(timezone.utc) - timedelta(hours=1),
        home_team="主队",
        away_team="客队",
        status="scheduled",
        home_score=2,
        away_score=1,
    )
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures", lambda **_kwargs: [])
    monkeypatch.setattr(dongqiudi_schedule, "fetch_fixtures", lambda: [raw_fixture])

    request = REQUEST.model_copy(update={"kickoff_at": raw_fixture.kickoff_at.isoformat()})
    status, actual = await decision_service._resolve_fixture_state(request, job)
    decision = decision_service.compose(job, fixture_status=status, actual_result=actual)

    assert status == "finished"
    assert actual is not None
    assert actual.home_score == 2
    assert actual.away_score == 1
    assert decision.review is not None
    assert decision.review.lean_correct is True


def test_decision_endpoint_requires_login_and_paid_entitlement(monkeypatch):
    from backend.auth import routes as auth_routes
    from backend import billing
    from backend.app_football import app

    def anonymous(_request):
        raise HTTPException(status_code=401, detail="未登录")

    monkeypatch.setattr(auth_routes, "get_current_user", anonymous)
    response = TestClient(app).post("/api/football/osint/decisions", json=REQUEST.model_dump())
    assert response.status_code == 401

    monkeypatch.setattr(auth_routes, "get_current_user", lambda _request: {"id": 1})
    monkeypatch.setattr(billing, "has_entitlement", lambda _user_id: False)
    response = TestClient(app).post("/api/football/osint/decisions", json=REQUEST.model_dump())
    assert response.status_code == 403


def test_decision_endpoint_returns_paid_fulltime_decision(monkeypatch):
    from backend.auth import routes as auth_routes
    from backend import billing
    from backend.app_football import app

    job = _job()
    decision = decision_service.compose(job, fixture_status="scheduled")

    async def fake_resolve(request):
        assert request.question == REQUEST.question
        return decision

    monkeypatch.setattr(auth_routes, "get_current_user", lambda _request: {"id": 1})
    monkeypatch.setattr(billing, "has_entitlement", lambda _user_id: True)
    monkeypatch.setattr(decision_service, "resolve", fake_resolve)

    response = TestClient(app).post("/api/football/osint/decisions", json=REQUEST.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["fixture_status"] == "scheduled"
    assert data["model_prediction"]["scoreline_band"] == ["2-1"]
    assert data["market_comparison"]["status"] == "aligned"
    assert "sporttery_market" not in data["model_prediction"]
    assert "handicap_conclusion" not in data["model_prediction"]
    assert "不构成投注" in data["disclaimer"]

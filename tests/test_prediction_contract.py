"""Contract tests for exact outcome probabilities and Sporttery settlement storage."""
from __future__ import annotations

import sqlite3
import threading

import pytest
from pydantic import ValidationError

from backend.auth import db as auth_db
from backend.football_osint.models import (
    FactorImpact,
    FootballOsintJob,
    FootballOsintJobStatus,
    FootballOsintJobRequest,
    HandicapConclusion,
    MarketContext,
    MarketSourceSnapshot,
    OsintMatch,
    OutcomeOdds,
    OutcomeProbabilities,
    PredictionResult,
    SportteryMarket,
)


def test_prediction_result_serializes_exact_outcomes_and_sporttery_fields():
    prediction = PredictionResult(
        lean="home",
        summary="主队略占优",
        outcome_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
        primary_probability=0.48,
        margin_to_runner_up=0.19,
        clarity="clear",
        scoreline_band=["2-1"],
        sporttery_market=SportteryMarket(
            had_odds=OutcomeOdds(home_win=1.9, draw=3.1, away_win=3.8),
            had_implied_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
            home_handicap=-1,
            hhad_odds=OutcomeOdds(home_win=2.1, draw=3.4, away_win=3.0),
            hhad_implied_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
            observed_at="2026-08-11T12:00:00+00:00",
        ),
        handicap_conclusion=HandicapConclusion(
            home_handicap=-1,
            outcome="away",
            handicap_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
            probability=0.40,
            margin_to_runner_up=0.08,
            clarity="clear",
        ),
    )
    job = FootballOsintJob(
        job_id="contract_1",
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="主队", away_team="客队"),
        prediction=prediction,
    )

    payload = job.model_dump(mode="json")

    assert payload["prediction"] == {
        "lean": "home",
        "summary": "主队略占优",
        "outcome_probabilities": {"home_win": 0.48, "draw": 0.29, "away_win": 0.23},
        "primary_probability": 0.48,
        "margin_to_runner_up": 0.19,
        "clarity": "clear",
        "scoreline_band": ["2-1"],
        "drivers": [],
        "uncertainties": [],
        "sporttery_market": {
            "provider": "sporttery",
            "had_odds": {"home_win": 1.9, "draw": 3.1, "away_win": 3.8},
            "had_implied_probabilities": {"home_win": 0.48, "draw": 0.29, "away_win": 0.23},
            "home_handicap": -1,
            "hhad_odds": {"home_win": 2.1, "draw": 3.4, "away_win": 3.0},
            "hhad_implied_probabilities": {"home_win": 0.32, "draw": 0.28, "away_win": 0.40},
            "observed_at": "2026-08-11T12:00:00+00:00",
        },
        "handicap_conclusion": {
            "home_handicap": -1,
            "outcome": "away",
            "handicap_probabilities": {"home_win": 0.32, "draw": 0.28, "away_win": 0.40},
            "probability": 0.40,
            "margin_to_runner_up": 0.08,
            "clarity": "clear",
        },
    }


def test_sporttery_market_serializes_had_without_hhad():
    market = SportteryMarket(
        had_implied_probabilities=OutcomeProbabilities(home_win=0.50, draw=0.28, away_win=0.22),
        observed_at="2026-08-11T12:00:00+00:00",
    )

    assert market.model_dump(mode="json") == {
        "provider": "sporttery",
        "had_odds": None,
        "had_implied_probabilities": {"home_win": 0.5, "draw": 0.28, "away_win": 0.22},
        "home_handicap": None,
        "hhad_odds": None,
        "hhad_implied_probabilities": None,
        "observed_at": "2026-08-11T12:00:00+00:00",
    }


def test_sporttery_market_rejects_incomplete_hhad_group():
    with pytest.raises(ValidationError):
        SportteryMarket(
            had_implied_probabilities=OutcomeProbabilities(home_win=0.50, draw=0.28, away_win=0.22),
            home_handicap=-1,
            observed_at="2026-08-11T12:00:00+00:00",
        )


def test_prediction_result_rejects_handicap_conclusion_without_complete_hhad_market():
    with pytest.raises(ValidationError):
        PredictionResult(
            lean="home",
            summary="主队略占优",
            outcome_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
            primary_probability=0.48,
            margin_to_runner_up=0.19,
            clarity="clear",
            scoreline_band=[],
            sporttery_market=SportteryMarket(
                had_implied_probabilities=OutcomeProbabilities(home_win=0.50, draw=0.28, away_win=0.22),
                observed_at="2026-08-11T12:00:00+00:00",
            ),
            handicap_conclusion=HandicapConclusion(
                home_handicap=-1,
                outcome="away",
                handicap_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
                probability=0.40,
                margin_to_runner_up=0.08,
                clarity="clear",
            ),
        )


def test_prediction_result_rejects_handicap_conclusion_with_different_handicap():
    with pytest.raises(ValidationError):
        PredictionResult(
            lean="home",
            summary="主队略占优",
            outcome_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
            primary_probability=0.48,
            margin_to_runner_up=0.19,
            clarity="clear",
            scoreline_band=[],
            sporttery_market=SportteryMarket(
                had_implied_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
                home_handicap=-1,
                hhad_odds=OutcomeOdds(home_win=2.1, draw=3.4, away_win=3.0),
                hhad_implied_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
                observed_at="2026-08-11T12:00:00+00:00",
            ),
            handicap_conclusion=HandicapConclusion(
                home_handicap=-2,
                outcome="away",
                handicap_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
                probability=0.40,
                margin_to_runner_up=0.08,
                clarity="clear",
            ),
        )


def test_handicap_conclusion_rejects_inconsistent_probability_metrics():
    with pytest.raises(ValidationError):
        HandicapConclusion(
            home_handicap=-1,
            outcome="away",
            handicap_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
            probability=0.40,
            margin_to_runner_up=0.04,
            clarity="close",
        )


def test_handicap_conclusion_rejects_outcome_not_matching_highest_probability():
    with pytest.raises(ValidationError):
        HandicapConclusion(
            home_handicap=-1,
            outcome="home",
            handicap_probabilities=OutcomeProbabilities(home_win=0.32, draw=0.28, away_win=0.40),
            probability=0.40,
            margin_to_runner_up=0.08,
            clarity="clear",
        )


def test_outcome_probabilities_reject_values_above_one():
    with pytest.raises(ValidationError):
        OutcomeProbabilities(home_win=1.01, draw=0.0, away_win=0.0)


def test_outcome_probabilities_reject_total_other_than_one():
    with pytest.raises(ValidationError):
        OutcomeProbabilities(home_win=0.5, draw=0.3, away_win=0.3)


def test_prediction_result_rejects_inconsistent_derived_fields():
    with pytest.raises(ValidationError):
        PredictionResult(
            lean="home",
            summary="主队略占优",
            outcome_probabilities=OutcomeProbabilities(home_win=0.48, draw=0.29, away_win=0.23),
            primary_probability=0.48,
            margin_to_runner_up=0.10,
            clarity="close",
            scoreline_band=["2-1"],
        )


def test_legacy_probability_band_is_converted_to_normalized_exact_probabilities():
    prediction = PredictionResult.model_validate({
        "lean": "home",
        "summary": "历史结果",
        "probability_band": {
            "home_win": [0.40, 0.48],
            "draw": [0.24, 0.32],
            "away_win": [0.20, 0.28],
        },
        "scoreline_band": ["2-1"],
    })

    assert prediction.outcome_probabilities.model_dump() == pytest.approx({
        "home_win": 0.458333,
        "draw": 0.291667,
        "away_win": 0.25,
    })
    assert prediction.primary_probability == pytest.approx(0.458333)
    assert prediction.margin_to_runner_up == pytest.approx(0.166666)
    assert prediction.clarity == "clear"
    assert prediction.sporttery_market is None
    assert prediction.handicap_conclusion is None
    assert "probability_band" not in prediction.model_dump()


def test_prediction_record_exposes_sporttery_handicap_settlement_columns(tmp_path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())

    conn = auth_db.get_db()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(prediction_record)")}

    assert {
        "sporttery_home_handicap",
        "predicted_hhad_outcome",
        "predicted_hhad_probability",
        "actual_hhad_outcome",
        "hhad_correct",
    } <= columns


def test_partly_applied_sporttery_migration_adds_remaining_columns(tmp_path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir()
    db_path = storage / "_auth.db"
    seeded = sqlite3.connect(db_path)
    seeded.executescript(
        (auth_db._MIGRATIONS_DIR / "004_prediction_track_record.sql").read_text(encoding="utf-8")
    )
    seeded.execute("ALTER TABLE prediction_record ADD COLUMN sporttery_home_handicap INTEGER")
    seeded.close()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", db_path)
    monkeypatch.setattr(auth_db, "_local", threading.local())

    conn = auth_db.get_db()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(prediction_record)")}

    assert {
        "sporttery_home_handicap",
        "predicted_hhad_outcome",
        "predicted_hhad_probability",
        "actual_hhad_outcome",
        "hhad_correct",
    } <= columns


def test_market_sources_stay_outside_osint_prediction(tmp_path, monkeypatch):
    """Market context may be retained separately without altering OSINT prediction."""
    from datetime import datetime, timezone

    from backend.football_osint import pipeline
    from backend.football_osint.analysis.prediction import predict
    from backend.football_osint.adapters.sporttery import SportteryOdds

    storage = tmp_path / "bronze_storage"
    storage.mkdir()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    conn = auth_db.get_db()

    odds = SportteryOdds(
        home_team="主队", away_team="客队", kickoff_at="2026-05-01 19:00",
        had_h=2.10, had_d=3.40, had_a=3.60,
        hhad_h=2.00, hhad_d=3.20, hhad_a=3.80, hhad_goal_line="+1", league="测试联赛",
    )
    market_context = MarketContext(
        snapshots=[
            MarketSourceSnapshot(
                source_id="sporttery",
                odds=OutcomeOdds(home_win=odds.had_h, draw=odds.had_d, away_win=odds.had_a),
                observed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        ]
    )
    factors = [
        FactorImpact(
            factor_id="form.recent_signal", label="主队近期状态", group="form",
            direction="home", weight=0.30, impact=0.18, confidence=0.80, enabled=True,
        ),
        FactorImpact(
            factor_id="h2h.relevance", label="主队交锋优势", group="h2h",
            direction="home", weight=0.20, impact=0.12, confidence=0.75, enabled=True,
        ),
    ]

    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda request, evidence: ("", "disabled"))
    monkeypatch.setattr(
        pipeline, "_collect_search_sources",
        lambda request, evidence, sources: pipeline.data_quality_module.SearchQualityStats(),
    )
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda request, evidence: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline.factor_registry_module, "build_factors", lambda *args, **kwargs: factors)
    monkeypatch.setattr(pipeline.sporttery_adapter, "get_odds", lambda *args, **kwargs: odds)

    job = pipeline.run_prediction_sync(
        {
            "home_team": "主队",
            "away_team": "客队",
            "kickoff_at": "2026-05-01 19:00",
            "competition": "测试联赛",
        },
        storage_root=storage / "football_osint",
    )

    assert job.prediction is not None
    assert job.prediction.summary
    assert len(set(job.prediction.outcome_probabilities.model_dump().values())) == 3
    assert sum(job.prediction.outcome_probabilities.model_dump().values()) == pytest.approx(1.0)
    prediction_payload = job.prediction.model_dump(exclude_none=True)
    assert "sporttery_market" not in prediction_payload
    assert "handicap_conclusion" not in prediction_payload
    assert next(source for source in job.sources if source.adapter == "sporttery").status == "ok"
    assert market_context.snapshots[0].source_id == "sporttery"
    expected_prediction = predict(
        FootballOsintJobRequest(
            home_team="主队",
            away_team="客队",
            kickoff_at="2026-05-01 19:00",
            competition="测试联赛",
        ),
        factors,
    )
    assert job.prediction.model_dump(exclude_none=True) == expected_prediction.model_dump(exclude_none=True)

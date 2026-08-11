"""Contract tests for exact outcome probabilities and Sporttery settlement storage."""
from __future__ import annotations

import sqlite3
import threading

import pytest
from pydantic import ValidationError

from backend.auth import db as auth_db
from backend.football_osint.models import (
    FootballOsintJob,
    FootballOsintJobStatus,
    HandicapConclusion,
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
            home_handicap=-1,
            hhad_odds=OutcomeOdds(home_win=2.1, draw=3.4, away_win=3.0),
        ),
        handicap_conclusion=HandicapConclusion(outcome="away", probability=0.45),
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
            "home_handicap": -1,
            "hhad_odds": {"home_win": 2.1, "draw": 3.4, "away_win": 3.0},
        },
        "handicap_conclusion": {"outcome": "away", "probability": 0.45},
    }


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

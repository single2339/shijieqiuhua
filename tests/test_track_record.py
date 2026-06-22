"""Tests for backend.football_osint.track_record."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.auth import db as auth_db


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir(parents=True)
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    return auth_db.get_db()


def test_prediction_record_table_exists(tmp_db):
    row = tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prediction_record'"
    ).fetchone()
    assert row is not None


import json
from datetime import datetime, timedelta, timezone

from backend.football_osint import track_record
from backend.football_osint.adapters import football_data_schedule
from backend.football_osint.models import (
    FootballOsintJob, FootballOsintJobStatus, OsintMatch, PredictionResult,
)


def _job(lean="home", status=FootballOsintJobStatus.COMPLETED, job_id="job1",
         home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00",
         created_at="2026-05-01T10:00:00+00:00", scoreline_band=("1-1", "2-1")):
    return FootballOsintJob(
        job_id=job_id,
        status=status,
        progress=100,
        match=OsintMatch(home_team=home_team, away_team=away_team, kickoff_at=kickoff_at),
        prediction=PredictionResult(
            lean=lean, summary="", probability_band={}, scoreline_band=list(scoreline_band),
        ),
        created_at=created_at,
        updated_at=created_at,
    )


def test_record_if_definite_inserts_row_for_definite_lean(tmp_db):
    inserted = track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    assert inserted is True
    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job1'").fetchone()
    assert row["predicted_lean"] == "home"
    assert json.loads(row["predicted_scoreline_band"]) == ["1-1", "2-1"]
    assert row["settled_at"] is None


def test_record_if_definite_skips_ambiguous_lean(tmp_db):
    inserted = track_record.record_if_definite(_job(lean="home_or_draw"), conn=tmp_db)
    assert inserted is False
    assert tmp_db.execute("SELECT COUNT(*) c FROM prediction_record").fetchone()["c"] == 0


def test_record_if_definite_is_idempotent(tmp_db):
    track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    inserted_again = track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    assert inserted_again is False
    assert tmp_db.execute("SELECT COUNT(*) c FROM prediction_record").fetchone()["c"] == 1


def test_settle_pending_resolves_match_and_computes_correctness(tmp_db, monkeypatch):
    track_record.record_if_definite(_job(lean="home", scoreline_band=("1-1", "2-1")), conn=tmp_db)

    fake_fixture = football_data_schedule.Fixture(
        match_id="1", league="EPL",
        kickoff_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
        home_team="曼城", away_team="利物浦", status="finished",
        home_score=2, away_score=1,
    )
    monkeypatch.setattr(
        football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [fake_fixture]
    )

    settled = track_record.settle_pending(conn=tmp_db)

    assert settled == 1
    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job1'").fetchone()
    assert row["actual_home_score"] == 2
    assert row["actual_away_score"] == 1
    assert row["actual_outcome"] == "home"
    assert row["lean_correct"] == 1
    assert row["scoreline_hit"] == 1
    assert row["settled_at"] is not None


def test_settle_pending_leaves_unmatched_rows_pending(tmp_db, monkeypatch):
    track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [])

    settled = track_record.settle_pending(conn=tmp_db)

    assert settled == 0
    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job1'").fetchone()
    assert row["settled_at"] is None


def test_get_stats_below_min_sample_omits_accuracy(tmp_db):
    track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    tmp_db.execute(
        "UPDATE prediction_record SET actual_outcome='home', lean_correct=1, "
        "scoreline_hit=1, settled_at=datetime('now') WHERE job_id='job1'"
    )
    tmp_db.commit()

    stats = track_record.get_stats(conn=tmp_db, min_sample=20)

    assert stats == {"settled": 1}


def test_get_stats_at_or_above_min_sample_includes_accuracy_and_recent(tmp_db):
    for i in range(3):
        job = _job(lean="home", job_id=f"job{i}", home_team=f"队{i}", away_team="对手")
        track_record.record_if_definite(job, conn=tmp_db)
        tmp_db.execute(
            "UPDATE prediction_record SET actual_home_score=2, actual_away_score=1, "
            "actual_outcome='home', lean_correct=1, scoreline_hit=1, "
            "settled_at=datetime('now') WHERE job_id=?",
            (f"job{i}",),
        )
    tmp_db.commit()

    stats = track_record.get_stats(conn=tmp_db, min_sample=3, recent_limit=2)

    assert stats["settled"] == 3
    assert stats["lean_accuracy"] == 1.0
    assert stats["scoreline_accuracy"] == 1.0
    assert len(stats["recent"]) == 2
    assert stats["recent"][0]["lean_correct"] is True


def test_backfill_due_scans_storage_records_and_settles(tmp_db, tmp_path, monkeypatch):
    job_dir = tmp_path / "football_osint" / "job_old"
    job_dir.mkdir(parents=True)
    job = _job(lean="away", job_id="job_old", home_team="切尔西", away_team="阿森纳",
               kickoff_at="04-01 12:00", created_at="2026-04-01T08:00:00+00:00",
               scoreline_band=("0-1", "1-2"))
    (job_dir / "status.json").write_text(job.model_dump_json(), encoding="utf-8")

    fake_fixture = football_data_schedule.Fixture(
        match_id="2", league="EPL",
        kickoff_at=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
        home_team="切尔西", away_team="阿森纳", status="finished",
        home_score=0, away_score=2,
    )
    monkeypatch.setattr(
        football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [fake_fixture]
    )

    result = track_record.backfill_due(storage_root=tmp_path / "football_osint")

    assert result == {"recorded": 1, "settled": 1}
    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job_old'").fetchone()
    assert row["actual_outcome"] == "away"
    assert row["lean_correct"] == 1
    assert row["scoreline_hit"] == 0  # band was 0-1/1-2, actual was 0-2


def test_backfill_due_skips_jobs_too_close_to_kickoff(tmp_db, tmp_path, monkeypatch):
    job_dir = tmp_path / "football_osint" / "job_recent"
    job_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    job = _job(lean="home", job_id="job_recent",
               kickoff_at=now.strftime("%m-%d %H:%M"), created_at=now.isoformat())
    (job_dir / "status.json").write_text(job.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [])

    result = track_record.backfill_due(storage_root=tmp_path / "football_osint")

    assert result == {"recorded": 0, "settled": 0}
    assert tmp_db.execute("SELECT COUNT(*) c FROM prediction_record").fetchone()["c"] == 0

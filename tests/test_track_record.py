"""Tests for backend.football_osint.track_record."""
from __future__ import annotations

import sqlite3
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


def test_prediction_record_metadata_columns_and_warm_cache_run_exist(tmp_db):
    cols = {
        row["name"]
        for row in tmp_db.execute("PRAGMA table_info(prediction_record)").fetchall()
    }
    assert {
        "match_key",
        "question_kind",
        "question_id",
        "question_hash",
        "warm_window",
        "cache_source",
        "record_role",
        "stats_primary",
        "excluded_reason",
        "created_from_job_id",
    } <= cols

    table = tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='warm_cache_run'"
    ).fetchone()
    assert table is not None

    partial_indexes = {
        row["name"]
        for row in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prediction_record'"
        ).fetchall()
    }
    assert "idx_prediction_record_one_stats_primary" in partial_indexes


def test_existing_prediction_record_table_is_upgraded_before_new_indexes(tmp_path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir(parents=True)
    db_path = storage / "_auth.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE prediction_record (
            job_id TEXT PRIMARY KEY,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_at TEXT NOT NULL DEFAULT '',
            competition TEXT NOT NULL DEFAULT '',
            predicted_lean TEXT NOT NULL,
            predicted_scoreline_band TEXT NOT NULL DEFAULT '[]',
            actual_home_score INTEGER,
            actual_away_score INTEGER,
            actual_outcome TEXT,
            lean_correct INTEGER,
            scoreline_hit INTEGER,
            settled_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.close()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", db_path)
    monkeypatch.setattr(auth_db, "_local", threading.local())

    upgraded = auth_db.get_db()

    cols = {row["name"] for row in upgraded.execute("PRAGMA table_info(prediction_record)").fetchall()}
    assert {"match_key", "stats_primary", "record_role"} <= cols
    assert upgraded.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_prediction_record_one_stats_primary'"
    ).fetchone() is not None


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


def test_record_if_definite_records_info_insufficient_for_history(tmp_db):
    inserted = track_record.record_if_definite(_job(lean="info_insufficient"), conn=tmp_db)
    assert inserted is True
    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job1'").fetchone()
    assert row["predicted_lean"] == "info_insufficient"
    assert row["lean_correct"] is None
    assert row["scoreline_hit"] is None


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


def test_settle_pending_scores_double_chance_predictions(tmp_db, monkeypatch):
    track_record.record_if_definite(_job(lean="home_or_draw", scoreline_band=("1-1",)), conn=tmp_db)
    fake_fixture = football_data_schedule.Fixture(
        match_id="dc1", league="EPL",
        kickoff_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
        home_team="曼城", away_team="利物浦", status="finished",
        home_score=1, away_score=1,
    )
    monkeypatch.setattr(
        football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [fake_fixture]
    )

    assert track_record.settle_pending(conn=tmp_db) == 1
    row = tmp_db.execute("SELECT actual_outcome, lean_correct, scoreline_hit FROM prediction_record WHERE job_id='job1'").fetchone()
    assert row["actual_outcome"] == "draw"
    assert row["lean_correct"] == 1
    assert row["scoreline_hit"] == 1


def test_football_data_parse_prefers_regular_time_score_for_settlement(monkeypatch):
    monkeypatch.setattr(
        football_data_schedule.name_translation,
        "translate",
        lambda names: {name: name for name in names},
    )
    fixtures = football_data_schedule.parse_matches({
        "matches": [{
            "id": 10,
            "utcDate": "2026-07-01T19:00:00Z",
            "status": "FINISHED",
            "competition": {"name": "Cup"},
            "homeTeam": {"id": 1, "name": "Home"},
            "awayTeam": {"id": 2, "name": "Away"},
            "score": {
                "duration": "PENALTY_SHOOTOUT",
                "regularTime": {"home": 1, "away": 1},
                "fullTime": {"home": 2, "away": 2},
            },
        }],
    })

    assert len(fixtures) == 1
    assert (fixtures[0].home_score, fixtures[0].away_score) == (1, 1)


def test_football_data_parse_ignores_extra_time_final_without_regular_time(monkeypatch):
    monkeypatch.setattr(
        football_data_schedule.name_translation,
        "translate",
        lambda names: {name: name for name in names},
    )
    fixtures = football_data_schedule.parse_matches({
        "matches": [{
            "id": 11,
            "utcDate": "2026-07-01T19:00:00Z",
            "status": "FINISHED",
            "competition": {"name": "Cup"},
            "homeTeam": {"id": 1, "name": "Home"},
            "awayTeam": {"id": 2, "name": "Away"},
            "score": {
                "duration": "EXTRA_TIME",
                "fullTime": {"home": 2, "away": 1},
            },
        }],
    })

    assert len(fixtures) == 1
    assert (fixtures[0].home_score, fixtures[0].away_score) == (None, None)

def test_settle_pending_parses_full_year_kickoff(tmp_db, monkeypatch):
    track_record.record_if_definite(
        _job(kickoff_at="2026-05-01 19:00", created_at="2026-04-25T10:00:00+00:00"),
        conn=tmp_db,
    )
    captured = {}
    fake_fixture = football_data_schedule.Fixture(
        match_id="fy1", league="EPL",
        kickoff_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
        home_team="曼城", away_team="利物浦", status="finished",
        home_score=2, away_score=1,
    )
    def fake_fetch(date_from, date_to):
        captured["range"] = (date_from, date_to)
        return [fake_fixture]
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures_for_range", fake_fetch)

    assert track_record.settle_pending(conn=tmp_db) == 1
    assert captured["range"] == ("2026-04-29", "2026-05-03")


def test_settle_pending_continues_after_bad_scoreline_band(tmp_db, monkeypatch):
    track_record.record_if_definite(_job(job_id="bad", home_team="坏队"), conn=tmp_db)
    tmp_db.execute("UPDATE prediction_record SET predicted_scoreline_band='not-json' WHERE job_id='bad'")
    track_record.record_if_definite(_job(job_id="good", home_team="好队"), conn=tmp_db)
    tmp_db.commit()
    fixtures = [
        football_data_schedule.Fixture(
            match_id="bad", league="EPL",
            kickoff_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
            home_team="坏队", away_team="利物浦", status="finished",
            home_score=2, away_score=1,
        ),
        football_data_schedule.Fixture(
            match_id="good", league="EPL",
            kickoff_at=datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc),
            home_team="好队", away_team="利物浦", status="finished",
            home_score=2, away_score=1,
        ),
    ]
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: fixtures)

    assert track_record.settle_pending(conn=tmp_db) == 2
    bad = tmp_db.execute("SELECT scoreline_hit FROM prediction_record WHERE job_id='bad'").fetchone()
    good = tmp_db.execute("SELECT scoreline_hit FROM prediction_record WHERE job_id='good'").fetchone()
    assert bad["scoreline_hit"] == 0
    assert good["scoreline_hit"] == 1

def test_settle_pending_leaves_unmatched_rows_pending(tmp_db, monkeypatch):
    track_record.record_if_definite(_job(lean="home"), conn=tmp_db)
    monkeypatch.setattr(football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [])
    monkeypatch.setattr(track_record.sporttery_adapter, "fetch_fixtures_for_range", lambda date_from, date_to: [])

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


def test_get_stats_includes_double_chance_in_public_accuracy_and_best_lean(tmp_db):
    cases = (
        ("home", "definite", "曼城", "利物浦", "05-01 19:00"),
        ("home_or_draw", "double", "阿森纳", "切尔西", "05-02 19:00"),
        ("away", "miss", "巴西", "日本", "05-03 19:00"),
        ("info_insufficient", "abstain", "德国", "法国", "05-04 19:00"),
    )
    for lean, job_id, home_team, away_team, kickoff_at in cases:
        track_record.record_if_definite(
            _job(lean=lean, job_id=job_id, home_team=home_team, away_team=away_team, kickoff_at=kickoff_at),
            conn=tmp_db,
        )
    tmp_db.execute(
        "UPDATE prediction_record SET actual_home_score=1, actual_away_score=0, actual_outcome='home', "
        "lean_correct=1, scoreline_hit=1, settled_at=datetime('now') WHERE job_id='definite'"
    )
    tmp_db.execute(
        "UPDATE prediction_record SET actual_home_score=1, actual_away_score=1, actual_outcome='draw', "
        "lean_correct=1, scoreline_hit=0, settled_at=datetime('now') WHERE job_id='double'"
    )
    tmp_db.execute(
        "UPDATE prediction_record SET actual_home_score=1, actual_away_score=0, actual_outcome='home', "
        "lean_correct=0, scoreline_hit=0, settled_at=datetime('now') WHERE job_id='miss'"
    )
    tmp_db.execute(
        "UPDATE prediction_record SET actual_home_score=0, actual_away_score=0, actual_outcome='draw', "
        "lean_correct=NULL, scoreline_hit=NULL, settled_at=datetime('now') WHERE job_id='abstain'"
    )
    tmp_db.commit()

    stats = track_record.get_stats(conn=tmp_db, min_sample=1, recent_limit=10)

    assert stats["settled"] == 3
    assert stats["lean_accuracy"] == 0.6667
    assert {r["predicted_lean"] for r in stats["recent"]} == {"home", "home_or_draw", "away"}
    assert stats["by_lean"] == [
        {"lean": "home", "settled": 1, "accuracy": 1.0},
        {"lean": "home_or_draw", "settled": 1, "accuracy": 1.0},
        {"lean": "away", "settled": 1, "accuracy": 0.0},
    ]
    assert stats["best_lean"] == {"lean": "home", "settled": 1, "accuracy": 1.0}


def test_record_if_definite_selects_one_stats_primary_per_match(tmp_db):
    from backend.football_osint import job_metadata, warm_cache
    from backend.football_osint.models import FootballOsintJobRequest

    for i, question in enumerate(warm_cache.PRESET_QUESTIONS):
        request = FootballOsintJobRequest(
            home_team="巴西",
            away_team="日本",
            kickoff_at="06-30 01:00",
            competition="世界杯",
            question=question,
        )
        track_record.record_if_definite(
            _job(job_id=f"job{i}", home_team="巴西", away_team="日本", kickoff_at="06-30 01:00"),
            conn=tmp_db,
            metadata=job_metadata.record_request_metadata(request, warm_window="t-2h", cache_source="t-2h"),
        )

    rows = tmp_db.execute(
        "SELECT job_id, question_id, record_role, stats_primary, excluded_reason "
        "FROM prediction_record ORDER BY job_id"
    ).fetchall()
    assert sum(row["stats_primary"] for row in rows) == 1
    primary = [row for row in rows if row["stats_primary"] == 1][0]
    assert primary["question_id"] == "fulltime_score"
    assert primary["record_role"] == "stats_primary"
    assert all(row["record_role"] in {"stats_primary", "history_detail"} for row in rows)


def test_migrate_prediction_record_metadata_selects_one_legacy_primary_idempotently(tmp_db):
    for job_id, lean, created_at in (
        ("old_double", "home_or_draw", "2026-06-29T10:00:00+00:00"),
        ("old_home", "home", "2026-06-29T09:00:00+00:00"),
        ("old_away_latest", "away", "2026-06-29T11:00:00+00:00"),
    ):
        tmp_db.execute(
            """
            INSERT INTO prediction_record(
                job_id, home_team, away_team, kickoff_at, competition,
                predicted_lean, predicted_scoreline_band, created_at
            )
            VALUES (?, '巴西', '日本', '06-30 01:00', '世界杯', ?, '[]', ?)
            """,
            (job_id, lean, created_at),
        )
    tmp_db.commit()

    first = track_record.migrate_prediction_record_metadata(conn=tmp_db)
    second = track_record.migrate_prediction_record_metadata(conn=tmp_db)

    rows = tmp_db.execute(
        "SELECT job_id, question_kind, question_id, record_role, stats_primary, excluded_reason "
        "FROM prediction_record ORDER BY job_id"
    ).fetchall()
    assert first["matches_total"] == 1
    assert second["changed_rows"] == 0
    assert sum(row["stats_primary"] for row in rows) == 1
    assert [row["job_id"] for row in rows if row["stats_primary"] == 1] == ["old_away_latest"]
    assert all(row["question_kind"] == "legacy" for row in rows)
    assert all(row["question_id"] == "legacy_unknown" for row in rows)
    assert all(row["excluded_reason"] for row in rows if row["stats_primary"] == 0)



def test_migrate_prediction_record_metadata_preserves_new_request_metadata(tmp_db):
    from backend.football_osint import job_metadata
    from backend.football_osint.models import FootballOsintJobRequest

    request = FootballOsintJobRequest(
        home_team="巴西",
        away_team="日本",
        kickoff_at="06-30 01:00",
        competition="世界杯",
        question="全场比分预测是多少？",
    )
    track_record.record_if_definite(
        _job(job_id="new_fulltime", home_team="巴西", away_team="日本", kickoff_at="06-30 01:00"),
        conn=tmp_db,
        metadata=job_metadata.record_request_metadata(request, warm_window="t-2h", cache_source="t-2h"),
    )

    first = track_record.migrate_prediction_record_metadata(conn=tmp_db)
    second = track_record.migrate_prediction_record_metadata(conn=tmp_db)

    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='new_fulltime'").fetchone()
    assert first["changed_rows"] == 0
    assert second["changed_rows"] == 0
    assert row["question_kind"] == "preset"
    assert row["question_id"] == "fulltime_score"
    assert row["warm_window"] == "t-2h"
    assert row["cache_source"] == "t-2h"


def test_record_if_definite_keeps_non_fulltime_questions_out_of_public_stats(tmp_db):
    from backend.football_osint import job_metadata
    from backend.football_osint.models import FootballOsintJobRequest

    request = FootballOsintJobRequest(
        home_team="巴西",
        away_team="日本",
        kickoff_at="06-30 01:00",
        competition="世界杯",
        question="全场角球数预测是多少？",
    )
    track_record.record_if_definite(
        _job(job_id="corners", home_team="巴西", away_team="日本", kickoff_at="06-30 01:00"),
        conn=tmp_db,
        metadata=job_metadata.record_request_metadata(request, warm_window="t-2h", cache_source="t-2h"),
    )

    row = tmp_db.execute("SELECT question_id, record_role, stats_primary, excluded_reason FROM prediction_record").fetchone()
    assert row["question_id"] == "corners_total"
    assert row["record_role"] == "history_detail"
    assert row["stats_primary"] == 0
    assert row["excluded_reason"] == "non_public_question"

def test_get_stats_uses_only_stats_primary_rows_and_reports_policy(tmp_db):
    from backend.football_osint import job_metadata
    from backend.football_osint.models import FootballOsintJobRequest

    for i, question in enumerate(("全场比分预测是多少？", "全场角球数预测是多少？")):
        request = FootballOsintJobRequest(
            home_team="巴西",
            away_team="日本",
            kickoff_at="06-30 01:00",
            question=question,
        )
        track_record.record_if_definite(
            _job(job_id=f"job{i}", home_team="巴西", away_team="日本", kickoff_at="06-30 01:00"),
            conn=tmp_db,
            metadata=job_metadata.record_request_metadata(request),
        )
    tmp_db.execute(
        "UPDATE prediction_record SET actual_outcome='home', lean_correct=1, scoreline_hit=1, settled_at=datetime('now')"
    )
    tmp_db.commit()

    stats = track_record.get_stats(conn=tmp_db, min_sample=1, recent_limit=10)

    assert stats["settled"] == 1
    assert stats["sample_policy"] == "one_stats_primary_per_match"
    assert stats["excluded_duplicates"] == 1
    assert len(stats["recent"]) == 1

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



def test_backfill_due_preserves_request_metadata_from_bronze_request_json(tmp_db, tmp_path, monkeypatch):
    from backend.football_osint import job_metadata
    from backend.football_osint.models import FootballOsintJobRequest

    job_dir = tmp_path / "football_osint" / "job_with_request"
    job_dir.mkdir(parents=True)
    job = _job(lean="home", job_id="job_with_request", home_team="巴西", away_team="日本",
               kickoff_at="04-01 12:00", created_at="2026-04-01T08:00:00+00:00")
    request = FootballOsintJobRequest(
        home_team="巴西",
        away_team="日本",
        kickoff_at="04-01 12:00",
        competition="世界杯",
        question="全场比分预测是多少？",
    )
    (job_dir / "status.json").write_text(job.model_dump_json(), encoding="utf-8")
    (job_dir / "request.json").write_text(
        json.dumps(
            job_metadata.record_request_metadata(request, warm_window="t-2h", cache_source="t-2h"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fake_fixture = football_data_schedule.Fixture(
        match_id="4", league="世界杯",
        kickoff_at=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
        home_team="巴西", away_team="日本", status="finished",
        home_score=2, away_score=0,
    )
    monkeypatch.setattr(
        football_data_schedule, "fetch_fixtures_for_range", lambda date_from, date_to: [fake_fixture]
    )

    result = track_record.backfill_due(storage_root=tmp_path / "football_osint")

    row = tmp_db.execute("SELECT * FROM prediction_record WHERE job_id='job_with_request'").fetchone()
    assert result == {"recorded": 1, "settled": 1}
    assert row["question_id"] == "fulltime_score"
    assert row["question_kind"] == "preset"
    assert row["warm_window"] == "t-2h"
    assert row["cache_source"] == "t-2h"
    assert row["stats_primary"] == 1

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

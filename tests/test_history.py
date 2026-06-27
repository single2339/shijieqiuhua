"""Tests for backend.football_osint.history (v2 post-match review & compare)."""
from __future__ import annotations

import json
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


def _insert_record(conn, *, job_id="job1", home="曼城", away="利物浦",
                   kickoff="2026-06-25 19:00", competition="英超",
                   lean="home", actual_outcome="home",
                   home_score=2, away_score=1,
                   lean_correct=1, scoreline_hit=0,
                   settled_at="2026-06-25 21:05"):
    conn.execute(
        """INSERT INTO prediction_record
           (job_id, home_team, away_team, kickoff_at, competition,
            predicted_lean, predicted_scoreline_band,
            actual_home_score, actual_away_score, actual_outcome,
            lean_correct, scoreline_hit, settled_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, home, away, kickoff, competition,
         lean, json.dumps(["1-0", "2-1"]),
         home_score, away_score, actual_outcome,
         lean_correct, scoreline_hit, settled_at),
    )
    conn.commit()


# ── get_history_list ──────────────────────────────────────────────────────────

def test_history_list_returns_settled_records(tmp_db):
    _insert_record(tmp_db)
    from backend.football_osint.history import get_history_list
    rows = get_history_list(days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r["job_id"] == "job1"
    assert r["predicted_lean"] == "home"
    assert r["actual_outcome"] == "home"
    assert r["lean_correct"] is True


def test_history_list_excludes_unsettled(tmp_db):
    _insert_record(tmp_db, settled_at=None)
    from backend.football_osint.history import get_history_list
    assert get_history_list(days=30) == []


def test_history_list_respects_days_filter(tmp_db, monkeypatch):
    # Insert a record settled 60 days ago — should be excluded with days=30
    _insert_record(tmp_db, settled_at="2020-01-01 10:00")
    from backend.football_osint.history import get_history_list
    assert get_history_list(days=30) == []


# ── get_history_detail ────────────────────────────────────────────────────────

def test_history_detail_returns_none_for_missing(tmp_db):
    from backend.football_osint.history import get_history_detail
    assert get_history_detail("no_such_job", paid=False) is None


def test_history_detail_base_fields_for_free_user(tmp_db):
    _insert_record(tmp_db)
    from backend.football_osint.history import get_history_detail
    result = get_history_detail("job1", paid=False)
    assert result is not None
    rec = result["record"]
    assert rec["lean_correct"] is True
    assert "factors" not in result
    assert "retrospective" not in result


def test_history_detail_paid_gets_factors_expired_when_no_bronze(tmp_db):
    _insert_record(tmp_db)
    from backend.football_osint.history import get_history_detail
    result = get_history_detail("job1", paid=True)
    assert result["factors_expired"] is True
    assert "factors" not in result


def test_history_detail_paid_gets_factors_and_retrospective(tmp_db, tmp_path, monkeypatch):
    _insert_record(tmp_db, lean="home", actual_outcome="home")

    # Write a minimal bronze_storage status.json
    from backend.football_osint.models import (
        FactorImpact, FootballOsintJob, FootballOsintJobStatus, OsintMatch,
    )
    from backend.football_osint import storage as st_mod
    job_dir = tmp_path / "bronze_storage" / "football_osint" / "job1"
    job_dir.mkdir(parents=True)
    job = FootballOsintJob(
        job_id="job1",
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00"),
        factors=[
            FactorImpact(factor_id="f1", label="近期状态", group="form", direction="home", weight=0.3, impact=0.3, confidence=0.8, enabled=True),
            FactorImpact(factor_id="f2", label="历史交锋", group="h2h", direction="home", weight=0.2, impact=0.2, confidence=0.7, enabled=True),
            FactorImpact(factor_id="f3", label="客队缺阵", group="squad", direction="away", weight=0.2, impact=0.2, confidence=0.6, enabled=True),
        ],
    )
    (job_dir / "status.json").write_text(job.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(st_mod, "DEFAULT_STORAGE_ROOT", tmp_path / "bronze_storage" / "football_osint")

    # Patch history module's DEFAULT_STORAGE_ROOT too
    from backend.football_osint import history as h_mod
    monkeypatch.setattr(h_mod, "DEFAULT_STORAGE_ROOT", tmp_path / "bronze_storage" / "football_osint")

    from backend.football_osint.history import get_history_detail
    result = get_history_detail("job1", paid=True)
    assert "factors_expired" not in result
    assert len(result["factors"]) == 3
    retro = result["retrospective"]
    assert "近期状态" in retro["hit_factors"]
    assert "历史交锋" in retro["hit_factors"]
    assert "客队缺阵" in retro["miss_factors"]


# ── _build_retrospective ──────────────────────────────────────────────────────

def test_build_retrospective_hit_and_miss():
    from backend.football_osint.history import _build_retrospective
    from backend.football_osint.models import FactorImpact
    factors = [
        FactorImpact(factor_id="a", label="A", group="g", direction="home", weight=0.3, impact=0.3, confidence=0.8, enabled=True),
        FactorImpact(factor_id="b", label="B", group="g", direction="away", weight=0.2, impact=0.2, confidence=0.7, enabled=True),
        FactorImpact(factor_id="c", label="C", group="g", direction="neutral", weight=0.1, impact=0.1, confidence=0.5, enabled=True),
        FactorImpact(factor_id="d", label="D", group="g", direction="home", weight=0.1, impact=0.1, confidence=0.5, enabled=False),
    ]
    retro = _build_retrospective(factors, actual_outcome="home")
    assert retro["hit_factors"] == ["A"]
    assert retro["miss_factors"] == ["B"]
    assert "1 个方向与实际结果吻合" in retro["note"]


def test_build_retrospective_no_factors():
    from backend.football_osint.history import _build_retrospective
    retro = _build_retrospective([], actual_outcome="draw")
    assert retro["hit_factors"] == []
    assert retro["miss_factors"] == []
    assert "缺乏足够因子" in retro["note"]


# ── compare_jobs ──────────────────────────────────────────────────────────────

def test_compare_jobs_returns_error_for_missing(tmp_path, monkeypatch):
    from backend.football_osint import history as h_mod
    monkeypatch.setattr(h_mod, "DEFAULT_STORAGE_ROOT", tmp_path)
    results = h_mod.compare_jobs(["no_such_job"])
    assert results[0]["error"] == "数据不可用"


def test_compare_jobs_from_warm_cache(monkeypatch):
    from backend.football_osint.models import (
        FootballOsintJob, FootballOsintJobStatus, OsintMatch, PredictionResult, ConfidenceRating,
    )
    from backend.football_osint import history as h_mod, warm_cache

    job = FootballOsintJob(
        job_id="job_cached",
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="曼城", away_team="利物浦", kickoff_at="05-01 19:00"),
        prediction=PredictionResult(lean="home", summary="", probability_band={}, scoreline_band=[]),
        confidence=ConfidenceRating(level="L2", reason="主队近期状态稳定"),
    )
    monkeypatch.setattr(warm_cache, "get_cached_by_job_id", lambda jid: job if jid == "job_cached" else None)

    results = h_mod.compare_jobs(["job_cached"])
    assert len(results) == 1
    r = results[0]
    assert r["predicted_lean"] == "home"
    assert r["confidence_level"] == "L2"
    assert r["factor_completeness"] == "0/0"


def test_compare_jobs_caps_at_three(monkeypatch, tmp_path):
    from backend.football_osint import history as h_mod
    monkeypatch.setattr(h_mod, "DEFAULT_STORAGE_ROOT", tmp_path)
    # 5 jobs requested, only 3 processed
    results = h_mod.compare_jobs(["a", "b", "c", "d", "e"])
    assert len(results) == 3

"""Prediction track record — records definite-lean predictions and settles
them against actual results, for the public hit-rate stat on the landing page.

See docs/superpowers/specs/2026-06-22-prediction-track-record-design.md.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.auth.db import get_db
from backend.football_osint.adapters import football_data_schedule
from backend.football_osint.models import FootballOsintJob, FootballOsintJobStatus
from backend.football_osint.storage import DEFAULT_STORAGE_ROOT

log = logging.getLogger(__name__)

_DEFINITE_LEANS = {"home", "away", "draw"}
_SETTLE_AFTER_HOURS = 3  # only attempt to record once kickoff is clearly in the past


def _norm(name: str) -> str:
    return name.strip().lower()


def record_if_definite(job: FootballOsintJob, *, conn: sqlite3.Connection | None = None) -> bool:
    """Insert a prediction_record row if the job has a definite lean and isn't already tracked.

    Returns True if a row was inserted, False if skipped (ambiguous lean,
    not completed, or already recorded).
    """
    if job.status != FootballOsintJobStatus.COMPLETED:
        return False
    if job.prediction is None or job.prediction.lean not in _DEFINITE_LEANS:
        return False

    c = conn or get_db()
    try:
        c.execute(
            """
            INSERT INTO prediction_record
              (job_id, home_team, away_team, kickoff_at, competition,
               predicted_lean, predicted_scoreline_band, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id, job.match.home_team, job.match.away_team,
                job.match.kickoff_at, job.match.competition,
                job.prediction.lean, json.dumps(job.prediction.scoreline_band, ensure_ascii=False),
                job.created_at,
            ),
        )
        c.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already recorded


def _approx_kickoff(kickoff_at: str, created_at_iso: str) -> datetime:
    """Best-effort reconstruction of a full kickoff datetime.

    job.match.kickoff_at is stored as "%m-%d %H:%M" (no year, see warm_cache.py
    cache_key format) or empty. We anchor the missing year to created_at's
    year, correcting for year-wrap when the reconstructed date would land
    more than 30 days before the job was created.
    """
    created_at = datetime.fromisoformat(created_at_iso)
    if not kickoff_at:
        return created_at
    try:
        parsed = datetime.strptime(kickoff_at, "%m-%d %H:%M")
    except ValueError:
        return created_at
    candidate = parsed.replace(year=created_at.year, tzinfo=timezone.utc)
    if candidate < created_at - timedelta(days=30):
        candidate = candidate.replace(year=created_at.year + 1)
    return candidate


def _resolve_one(home_team: str, away_team: str, kickoff_guess: datetime) -> tuple[int, int] | None:
    """Look up the actual final score for one match via football_data_schedule.

    ponytail: ±2 day window + exact normalized name match. No fuzzy name
    matching — if it doesn't find a hit, the row just stays unsettled
    (best-effort backfill, see design doc). Upgrade to fuzzy matching only
    if unmatched-row rate turns out to matter in practice.
    """
    date_from = (kickoff_guess - timedelta(days=2)).date().isoformat()
    date_to = (kickoff_guess + timedelta(days=2)).date().isoformat()
    fixtures = football_data_schedule.fetch_fixtures_for_range(date_from, date_to)

    home_n, away_n = _norm(home_team), _norm(away_team)
    for f in fixtures:
        if f.status != "finished":
            continue
        if _norm(f.home_team) == home_n and _norm(f.away_team) == away_n:
            if f.home_score is None or f.away_score is None:
                continue
            return f.home_score, f.away_score
    return None


def settle_pending(*, conn: sqlite3.Connection | None = None) -> int:
    """Try to resolve actual results for all unsettled rows. Returns count settled."""
    c = conn or get_db()
    rows = c.execute(
        "SELECT job_id, home_team, away_team, kickoff_at, predicted_lean, "
        "predicted_scoreline_band, created_at FROM prediction_record WHERE settled_at IS NULL"
    ).fetchall()

    settled = 0
    for row in rows:
        kickoff_guess = _approx_kickoff(row["kickoff_at"], row["created_at"])
        result = _resolve_one(row["home_team"], row["away_team"], kickoff_guess)
        if result is None:
            continue
        home_score, away_score = result
        actual_outcome = "draw" if home_score == away_score else ("home" if home_score > away_score else "away")
        lean_correct = 1 if row["predicted_lean"] == actual_outcome else 0
        band = json.loads(row["predicted_scoreline_band"])
        scoreline_hit = 1 if f"{home_score}-{away_score}" in band else 0

        c.execute(
            """
            UPDATE prediction_record
            SET actual_home_score=?, actual_away_score=?, actual_outcome=?,
                lean_correct=?, scoreline_hit=?, settled_at=datetime('now')
            WHERE job_id=?
            """,
            (home_score, away_score, actual_outcome, lean_correct, scoreline_hit, row["job_id"]),
        )
        settled += 1
    c.commit()
    return settled


def backfill_due(storage_root: str | Path | None = None) -> dict:
    """Scan bronze_storage for newly-completed definite-lean jobs, record them,
    then attempt to settle every still-pending row.

    ponytail: rescans every job_id on each call (bounded by checking against
    already-recorded job_ids first, not by file mtime). Fine at current job
    volumes; switch to a created_at high-water-mark cursor if the bronze_storage
    job count grows large enough to make the glob itself slow.
    """
    root = Path(storage_root) if storage_root else DEFAULT_STORAGE_ROOT
    conn = get_db()

    already_recorded = {
        r["job_id"] for r in conn.execute("SELECT job_id FROM prediction_record").fetchall()
    }

    recorded = 0
    now = datetime.now(timezone.utc)
    for status_path in root.glob("*/status.json"):
        job_id = status_path.parent.name
        if job_id in already_recorded:
            continue
        try:
            job = FootballOsintJob.model_validate_json(status_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("track_record: failed to parse %s", status_path)
            continue

        kickoff_guess = _approx_kickoff(job.match.kickoff_at, job.created_at)
        if kickoff_guess > now - timedelta(hours=_SETTLE_AFTER_HOURS):
            continue  # too early — match likely hasn't finished yet

        if record_if_definite(job, conn=conn):
            recorded += 1

    settled = settle_pending(conn=conn)
    return {"recorded": recorded, "settled": settled}


def get_stats(*, conn: sqlite3.Connection | None = None, min_sample: int = 20, recent_limit: int = 20) -> dict:
    c = conn or get_db()
    agg = c.execute(
        "SELECT COUNT(*) n, SUM(lean_correct) lc, SUM(scoreline_hit) sh "
        "FROM prediction_record WHERE settled_at IS NOT NULL"
    ).fetchone()
    settled = agg["n"] or 0
    if settled < min_sample:
        return {"settled": settled}

    recent_rows = c.execute(
        "SELECT home_team, away_team, kickoff_at, predicted_lean, predicted_scoreline_band, "
        "actual_home_score, actual_away_score, lean_correct, scoreline_hit "
        "FROM prediction_record WHERE settled_at IS NOT NULL "
        "ORDER BY settled_at DESC LIMIT ?",
        (recent_limit,),
    ).fetchall()

    return {
        "settled": settled,
        "lean_accuracy": round((agg["lc"] or 0) / settled, 4),
        "scoreline_accuracy": round((agg["sh"] or 0) / settled, 4),
        "recent": [
            {
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "kickoff_at": r["kickoff_at"],
                "predicted_lean": r["predicted_lean"],
                "predicted_scoreline_band": json.loads(r["predicted_scoreline_band"]),
                "actual_home_score": r["actual_home_score"],
                "actual_away_score": r["actual_away_score"],
                "lean_correct": bool(r["lean_correct"]),
                "scoreline_hit": bool(r["scoreline_hit"]),
            }
            for r in recent_rows
        ],
    }

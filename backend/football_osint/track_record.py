"""Prediction track record — records definite-lean predictions and settles
them against actual results, for the public hit-rate stat on the landing page.

See docs/superpowers/specs/2026-06-22-prediction-track-record-design.md.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.auth.db import get_db
from backend.football_osint.adapters import football_data_schedule
from backend.football_osint.adapters import sporttery as sporttery_adapter
from backend.football_osint.analysis.market import settle_handicap
from backend.football_osint.models import FootballOsintJob, FootballOsintJobStatus
from backend.football_osint.storage import DEFAULT_STORAGE_ROOT

log = logging.getLogger(__name__)

_TRACKABLE_LEANS = {"home", "away", "draw", "home_or_draw", "away_or_draw", "info_insufficient"}
_STATS_LEANS = {"home", "away", "draw", "home_or_draw", "away_or_draw"}
_LEAN_ORDER = {lean: i for i, lean in enumerate(("home", "away", "draw", "home_or_draw", "away_or_draw"))}
_MIN_SAMPLE_DEFAULT = 20
_SETTLE_AFTER_HOURS = 3  # only attempt to record once kickoff is clearly in the past


def _norm(name: str) -> str:
    return name.strip().lower()


def record_if_definite(
    job: FootballOsintJob,
    *,
    conn: sqlite3.Connection | None = None,
    metadata: dict | None = None,
) -> bool:
    """Insert a prediction_record row if the completed job should appear in history."""
    if job.status != FootballOsintJobStatus.COMPLETED:
        return False
    if job.prediction is None or job.prediction.lean not in _TRACKABLE_LEANS:
        return False

    c = conn or get_db()
    meta = _record_metadata(job, metadata)
    handicap_values = _market_handicap_values(job)
    try:
        c.execute(
            """
            INSERT INTO prediction_record
              (job_id, home_team, away_team, kickoff_at, competition,
               predicted_lean, predicted_scoreline_band, created_at,
               sporttery_home_handicap, predicted_hhad_outcome, predicted_hhad_probability,
               match_key, question_kind, question_id, question_hash,
               warm_window, cache_source, record_role, stats_primary,
               excluded_reason, created_from_job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id, job.match.home_team, job.match.away_team,
                job.match.kickoff_at, job.match.competition,
                job.prediction.lean, json.dumps(job.prediction.scoreline_band, ensure_ascii=False),
                job.created_at, *handicap_values,
                meta["match_key"], meta["question_kind"], meta["question_id"],
                meta["question_hash"], meta["warm_window"], meta["cache_source"],
                "history_detail", 0, "", job.job_id,
            ),
        )
        select_stats_primary(c, meta["match_key"])
        c.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already recorded


def _market_handicap_values(job: FootballOsintJob) -> tuple[int | None, str | None, float | None]:
    context = job.market_context
    if context is None or not context.handicap_snapshots:
        return None, None, None

    snapshot = context.handicap_snapshots[0]
    probabilities = snapshot.implied_probabilities.model_dump()
    outcome_key = max(probabilities, key=probabilities.__getitem__)
    outcome = {"home_win": "home", "draw": "draw", "away_win": "away"}[outcome_key]
    return snapshot.home_handicap, outcome, probabilities[outcome_key]


def _record_metadata(job: FootballOsintJob, metadata: dict | None) -> dict:
    from backend.football_osint import job_metadata

    if metadata is None:
        return {
            "match_key": job_metadata.match_key(job.match.home_team, job.match.away_team, job.match.kickoff_at),
            "question_kind": "legacy",
            "question_id": "legacy_unknown",
            "question_hash": None,
            "warm_window": "legacy_unknown",
            "cache_source": "migration",
        }
    return {
        "match_key": metadata.get("match_key") or job_metadata.match_key(job.match.home_team, job.match.away_team, job.match.kickoff_at),
        "question_kind": metadata.get("question_kind") or "legacy",
        "question_id": metadata.get("question_id") or "legacy_unknown",
        "question_hash": metadata.get("question_hash"),
        "warm_window": metadata.get("warm_window") or "legacy_unknown",
        "cache_source": metadata.get("cache_source") or "migration",
    }


def _load_request_metadata(job_dir: Path) -> dict | None:
    path = job_dir / "request.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("track_record: failed to parse %s", path)
        return None
    return data if isinstance(data, dict) else None



def select_stats_primary(conn: sqlite3.Connection, match_key_value: str) -> None:
    rows = conn.execute(
        """
        SELECT job_id, predicted_lean, question_id, warm_window, created_at
        FROM prediction_record
        WHERE match_key=?
        """,
        (match_key_value,),
    ).fetchall()
    primary = _choose_stats_primary(rows)
    stats_placeholders = ",".join("?" for _ in _STATS_LEANS)
    conn.execute(
        f"""
        UPDATE prediction_record
        SET stats_primary=0,
            record_role='history_detail',
            excluded_reason=CASE
                WHEN predicted_lean NOT IN ({stats_placeholders}) THEN 'non_public_lean'
                WHEN question_id NOT IN ('fulltime_score','legacy_unknown') THEN 'non_public_question'
                ELSE 'duplicate_match'
            END
        WHERE match_key=?
        """,
        (*sorted(_STATS_LEANS), match_key_value),
    )
    if primary is not None:
        conn.execute(
            """
            UPDATE prediction_record
            SET stats_primary=1, record_role='stats_primary', excluded_reason=''
            WHERE job_id=?
            """,
            (primary["job_id"],),
        )


def _choose_stats_primary(rows) -> sqlite3.Row | None:
    candidates = [
        row for row in rows
        if row["predicted_lean"] in _STATS_LEANS
        and row["question_id"] in {"fulltime_score", "legacy_unknown"}
    ]
    if not candidates:
        return None

    def rank(row) -> tuple[int, int, str]:
        window_rank = {"t-2h": 3, "t-5h": 2, "on-demand": 1}.get(row["warm_window"], 0)
        return (1 if row["question_id"] == "fulltime_score" else 0, window_rank, row["created_at"] or "")

    return max(candidates, key=rank)


def migrate_prediction_record_metadata(*, conn: sqlite3.Connection | None = None) -> dict[str, int]:
    c = conn or get_db()
    rows = c.execute("SELECT * FROM prediction_record").fetchall()
    if not rows:
        return {"matches_total": 0, "changed_rows": 0}

    from backend.football_osint import job_metadata

    changed_rows = 0
    match_keys: set[str] = set()
    for row in rows:
        mk = row["match_key"] or job_metadata.match_key(row["home_team"], row["away_team"], row["kickoff_at"])
        match_keys.add(mk)
        needs_legacy_update = not row["match_key"] or row["record_role"] == "legacy_pending"
        needs_created_from_update = row["created_from_job_id"] is None
        if not needs_legacy_update and not needs_created_from_update:
            continue
        if not needs_legacy_update:
            c.execute(
                "UPDATE prediction_record SET created_from_job_id=COALESCE(created_from_job_id, job_id) WHERE job_id=?",
                (row["job_id"],),
            )
            changed_rows += 1
            continue
        c.execute(
            """
            UPDATE prediction_record
            SET match_key=?,
                question_kind='legacy',
                question_id='legacy_unknown',
                warm_window='legacy_unknown',
                cache_source='migration',
                created_from_job_id=COALESCE(created_from_job_id, job_id)
            WHERE job_id=?
            """,
            (mk, row["job_id"]),
        )
        changed_rows += 1

    for mk in match_keys:
        select_stats_primary(c, mk)
    c.commit()
    return {"matches_total": len(match_keys), "changed_rows": changed_rows}


def _approx_kickoff(kickoff_at: str, created_at_iso: str) -> datetime:
    """Best-effort reconstruction of a full kickoff datetime."""
    created_at = datetime.fromisoformat(created_at_iso)
    if not kickoff_at:
        return created_at
    try:
        parsed = datetime.strptime(kickoff_at, "%Y-%m-%d %H:%M")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = datetime.strptime(f"{created_at.year}-{kickoff_at}", "%Y-%m-%d %H:%M")
    except ValueError:
        parsed = None
    if parsed is not None:
        candidate = parsed.replace(tzinfo=timezone.utc)
        if candidate < created_at - timedelta(days=30):
            candidate = candidate.replace(year=created_at.year + 1)
        return candidate
    try:
        return datetime.fromisoformat(kickoff_at)
    except ValueError:
        return created_at


def _resolve_one(home_team: str, away_team: str, kickoff_guess: datetime) -> tuple[int, int] | None:
    """Look up the actual 90-minute score for one match.

    Tries football-data.org first, then falls back to the 体彩 API (free, no
    key needed).  ±2 day window + exact normalized name match.
    """
    date_from = (kickoff_guess - timedelta(days=2)).date().isoformat()
    date_to = (kickoff_guess + timedelta(days=2)).date().isoformat()

    home_n, away_n = _norm(home_team), _norm(away_team)

    # Primary: football-data.org
    fixtures = football_data_schedule.fetch_fixtures_for_range(date_from, date_to)
    for f in fixtures:
        if f.status != "finished":
            continue
        if _norm(f.home_team) == home_n and _norm(f.away_team) == away_n:
            if f.home_score is None or f.away_score is None:
                continue
            return f.home_score, f.away_score

    # Fallback: sporttery.cn (free API, no key — works even when
    # football-data.org key is expired/revoked)
    st_fixtures = sporttery_adapter.fetch_fixtures_for_range(date_from, date_to)
    for f in st_fixtures:
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
        "predicted_scoreline_band, created_at, sporttery_home_handicap, "
        "predicted_hhad_outcome FROM prediction_record WHERE settled_at IS NULL"
    ).fetchall()

    settled = 0
    for row in rows:
        kickoff_guess = _approx_kickoff(row["kickoff_at"], row["created_at"])
        result = _resolve_one(row["home_team"], row["away_team"], kickoff_guess)
        if result is None:
            continue
        home_score, away_score = result
        actual_outcome = "draw" if home_score == away_score else ("home" if home_score > away_score else "away")
        predicted_lean = row["predicted_lean"]
        if predicted_lean == "info_insufficient":
            lean_correct = None
        elif predicted_lean == "home_or_draw":
            lean_correct = 1 if actual_outcome in {"home", "draw"} else 0
        elif predicted_lean == "away_or_draw":
            lean_correct = 1 if actual_outcome in {"away", "draw"} else 0
        else:
            lean_correct = 1 if predicted_lean == actual_outcome else 0
        try:
            band = json.loads(row["predicted_scoreline_band"])
        except (TypeError, json.JSONDecodeError):
            log.warning("prediction_record %s has malformed scoreline band", row["job_id"])
            band = []
        scoreline_hit = None if predicted_lean == "info_insufficient" else (1 if f"{home_score}-{away_score}" in band else 0)
        home_handicap = row["sporttery_home_handicap"]
        predicted_hhad_outcome = row["predicted_hhad_outcome"]
        actual_hhad_outcome = (
            settle_handicap(home_score, away_score, home_handicap)
            if home_handicap is not None
            else None
        )
        hhad_correct = (
            (1 if actual_hhad_outcome == predicted_hhad_outcome else 0)
            if actual_hhad_outcome is not None and predicted_hhad_outcome is not None
            else None
        )

        c.execute(
            """
            UPDATE prediction_record
            SET actual_home_score=?, actual_away_score=?, actual_outcome=?,
                lean_correct=?, scoreline_hit=?, actual_hhad_outcome=?, hhad_correct=?,
                settled_at=datetime('now')
            WHERE job_id=?
            """,
            (
                home_score, away_score, actual_outcome, lean_correct, scoreline_hit,
                actual_hhad_outcome, hhad_correct, row["job_id"],
            ),
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
    migrate_prediction_record_metadata(conn=conn)

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

        metadata = _load_request_metadata(status_path.parent)
        if record_if_definite(job, conn=conn, metadata=metadata):
            recorded += 1

    settled = settle_pending(conn=conn)
    return {"recorded": recorded, "settled": settled}


def get_stats(*, conn: sqlite3.Connection | None = None, min_sample: int | None = None, recent_limit: int = 20) -> dict:
    c = conn or get_db()
    if min_sample is None:
        min_sample = int(os.getenv("TRACK_RECORD_MIN_SAMPLE", str(_MIN_SAMPLE_DEFAULT)))
    stats_placeholders = ",".join("?" for _ in _STATS_LEANS)
    stats_params = tuple(sorted(_STATS_LEANS))
    agg = c.execute(
        "SELECT COUNT(*) n, SUM(lean_correct) lc, SUM(scoreline_hit) sh "
        f"FROM prediction_record WHERE stats_primary=1 AND settled_at IS NOT NULL "
        f"AND predicted_lean IN ({stats_placeholders})",
        stats_params,
    ).fetchone()
    settled = agg["n"] or 0
    if settled < min_sample:
        return {"settled": settled}

    recent_rows = c.execute(
        "SELECT home_team, away_team, kickoff_at, predicted_lean, predicted_scoreline_band, "
        "actual_home_score, actual_away_score, lean_correct, scoreline_hit "
        f"FROM prediction_record WHERE stats_primary=1 AND settled_at IS NOT NULL "
        f"AND predicted_lean IN ({stats_placeholders}) "
        "ORDER BY settled_at DESC LIMIT ?",
        (*stats_params, recent_limit),
    ).fetchall()

    by_lean_rows = c.execute(
        "SELECT predicted_lean, COUNT(*) n, SUM(lean_correct) lc "
        f"FROM prediction_record WHERE stats_primary=1 AND settled_at IS NOT NULL "
        f"AND predicted_lean IN ({stats_placeholders}) "
        "GROUP BY predicted_lean",
        stats_params,
    ).fetchall()
    by_lean = sorted(
        (
            {
                "lean": r["predicted_lean"],
                "settled": r["n"],
                "accuracy": round((r["lc"] or 0) / r["n"], 4),
            }
            for r in by_lean_rows
            if r["n"]
        ),
        key=lambda item: (-item["accuracy"], -item["settled"], _LEAN_ORDER.get(item["lean"], 99)),
    )

    return {
        "settled": settled,
        "lean_accuracy": round((agg["lc"] or 0) / settled, 4),
        "scoreline_accuracy": round((agg["sh"] or 0) / settled, 4),
        "sample_policy": "one_stats_primary_per_match",
        "excluded_duplicates": c.execute(
            "SELECT COUNT(*) c FROM prediction_record WHERE stats_primary=0 AND settled_at IS NOT NULL"
        ).fetchone()["c"],
        "by_lean": by_lean,
        "best_lean": by_lean[0] if by_lean else None,
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


_BACKFILL_INTERVAL_SECONDS = 60 * 60  # hourly


async def backfill_loop() -> None:
    """Run forever: backfill_due() once per hour."""
    import asyncio

    while True:
        try:
            result = await asyncio.to_thread(backfill_due)
            log.info("track_record backfill: recorded=%d settled=%d", result["recorded"], result["settled"])
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("track_record backfill_loop iteration failed")
        await asyncio.sleep(_BACKFILL_INTERVAL_SECONDS)


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    result = backfill_due()
    print(f"recorded={result['recorded']} settled={result['settled']}")

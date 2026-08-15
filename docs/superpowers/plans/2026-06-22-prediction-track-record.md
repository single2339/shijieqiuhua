# Prediction Track Record Implementation Plan

> **已被 2026-06-30 PRD 修订补丁 supersede**：本文保留为历史 implementation plan，不再直接作为开工依据。新的实现入口是 `docs/superpowers/specs/2026-06-30-football-cache-track-record-prd-addendum.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public "prediction vs actual result" track record — storage, auto-backfill, a stats API, and a landing-page stat strip — so the product can advertise a verifiable hit-rate.

**Architecture:** A new SQLite table `prediction_record` (in the existing shared `_auth.db`) holds one row per job with a definite predicted lean (home/away/draw). An hourly background loop (mirroring the existing `warm_cache.warm_loop` pattern) inserts new rows from completed jobs and resolves pending rows against `football_data_schedule` (extended to accept an explicit date range instead of only "today + N days"). A `GET /api/football/osint/track-record` endpoint aggregates settled rows into a hit-rate summary + recent-20 list, gated by a minimum sample size of 20. The landing page fetches this once and renders a stat strip + collapsible detail table.

**Tech Stack:** Python 3.11 / FastAPI / sqlite3 (stdlib) / pytest. React 19 / TypeScript / vitest.

## Global Constraints

- Only jobs with `prediction.lean` in `{home, away, draw}` are tracked — `home_or_draw`, `away_or_draw`, and `info_insufficient` are excluded from the sample (spec: "范围").
- `settled` count below 20 → the stats endpoint omits `lean_accuracy`, `scoreline_accuracy`, and `recent`; the frontend renders nothing in that case (spec: "范围", "前端展示").
- Historical backfill is best-effort — `football_data_schedule`'s free-tier historical depth is unverified; unmatched rows simply stay unsettled (spec: "数据来源与已知限制"). Do not add retry/alerting logic for unmatched rows.
- New SQL lives in `sql/004_prediction_track_record.sql`, loaded via the existing `_EXTRA_MIGRATIONS` tuple in `backend/auth/db.py` — do not create a second database file.
- No caching layer on the stats endpoint — it's a single cheap aggregate query (spec: "统计接口").

---

### Task 1: SQL migration for `prediction_record`

**Files:**
- Create: `sql/004_prediction_track_record.sql`
- Modify: `backend/auth/db.py:14` (`_EXTRA_MIGRATIONS` tuple)
- Test: `tests/test_track_record.py` (new file)

**Interfaces:**
- Produces: table `prediction_record` with columns `job_id TEXT PRIMARY KEY, home_team TEXT, away_team TEXT, kickoff_at TEXT, competition TEXT, predicted_lean TEXT, predicted_scoreline_band TEXT, actual_home_score INTEGER, actual_away_score INTEGER, actual_outcome TEXT, lean_correct INTEGER, scoreline_hit INTEGER, settled_at TEXT, created_at TEXT`. Later tasks read/write this table via `backend.auth.db.get_db()`.

- [ ] **Step 1: Write the migration file**

```sql
-- sql/004_prediction_track_record.sql
CREATE TABLE IF NOT EXISTS prediction_record (
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

CREATE INDEX IF NOT EXISTS idx_prediction_record_settled ON prediction_record(settled_at);
```

- [ ] **Step 2: Wire it into the migration loader**

In `backend/auth/db.py`, change line 14 from:
```python
_EXTRA_MIGRATIONS = ("003_billing_and_entitlements.sql",)
```
to:
```python
_EXTRA_MIGRATIONS = ("003_billing_and_entitlements.sql", "004_prediction_track_record.sql")
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_track_record.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_track_record.py -v`
Expected: FAIL (table doesn't exist yet, or import error if file didn't exist before this step — should pass once Steps 1-2 are done, so run this *before* Steps 1-2 to confirm RED, then re-run after)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_track_record.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add sql/004_prediction_track_record.sql backend/auth/db.py tests/test_track_record.py
git commit -m "feat: add prediction_record table for track-record stats"
```

---

### Task 2: `football_data_schedule` — arbitrary date-range fetch

**Files:**
- Modify: `backend/football_osint/adapters/football_data_schedule.py:55-83`
- Test: `tests/test_football_data_schedule_range.py` (new file)

**Interfaces:**
- Consumes: nothing new (refactors existing `fetch_fixtures`).
- Produces: `fetch_fixtures_for_range(date_from: str, date_to: str) -> list[Fixture]` — `date_from`/`date_to` are `YYYY-MM-DD` strings (UTC), inclusive. Used by Task 3.

- [ ] **Step 1: Write the failing test**

Create `tests/test_football_data_schedule_range.py`:

```python
"""Tests for football_data_schedule.fetch_fixtures_for_range."""
from __future__ import annotations

import httpx
import pytest

from backend.football_osint import cache
from backend.football_osint.adapters import football_data_schedule


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.schedule_cache._store.clear()
    yield
    cache.schedule_cache._store.clear()


def test_fetch_fixtures_for_range_queries_explicit_dates(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "matches": [
                        {
                            "id": 1,
                            "utcDate": "2026-05-01T19:00:00Z",
                            "status": "FINISHED",
                            "competition": {"name": "Premier League"},
                            "homeTeam": {"name": "Man City"},
                            "awayTeam": {"name": "Liverpool"},
                            "score": {"fullTime": {"home": 2, "away": 1}},
                        }
                    ]
                }
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(
        football_data_schedule.name_translation, "translate",
        lambda names: {n: n for n in names},
    )

    fixtures = football_data_schedule.fetch_fixtures_for_range("2026-05-01", "2026-05-02")

    assert captured["params"] == {"dateFrom": "2026-05-01", "dateTo": "2026-05-02"}
    assert len(fixtures) == 1
    assert fixtures[0].home_team == "Man City"
    assert fixtures[0].status == "finished"
    assert fixtures[0].home_score == 2
    assert fixtures[0].away_score == 1


def test_fetch_fixtures_for_range_without_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    assert football_data_schedule.fetch_fixtures_for_range("2026-05-01", "2026-05-02") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_football_data_schedule_range.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'fetch_fixtures_for_range'`

- [ ] **Step 3: Implement — extract a shared range helper**

In `backend/football_osint/adapters/football_data_schedule.py`, replace the body of `fetch_fixtures` (lines 55-83) with:

```python
def fetch_fixtures(days_ahead: int = 3) -> list[Fixture]:
    """Fetch fixtures from today through ``days_ahead`` days (UTC), cached 5 min."""
    today = datetime.now(timezone.utc).date()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=max(days_ahead, 0))).isoformat()
    return fetch_fixtures_for_range(date_from, date_to)


def fetch_fixtures_for_range(date_from: str, date_to: str) -> list[Fixture]:
    """Fetch fixtures for an explicit ``YYYY-MM-DD`` UTC date range, cached 5 min.

    Unlike ``fetch_fixtures`` (always "today + N days forward"), this accepts
    past dates too — used by track-record backfill to look up finished matches.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not api_key:
        log.warning("FOOTBALL_DATA_API_KEY not set; fixtures unavailable")
        return []

    cache_key = f"fd:{date_from}:{date_to}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            FOOTBALL_DATA_URL,
            params={"dateFrom": date_from, "dateTo": date_to},
            headers={"X-Auth-Token": api_key},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        log.warning("football-data fetch failed: %s", e)
        return cached if cached is not None else []

    fixtures = parse_matches(payload)
    cache.schedule_cache.set(cache_key, fixtures)
    return fixtures
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_football_data_schedule_range.py -v`
Expected: PASS

- [ ] **Step 5: Run the existing adapter's callers to confirm no regression**

Run: `pytest tests/test_football_osint.py -v`
Expected: PASS (no behavior change to `fetch_fixtures`'s public signature or return value)

- [ ] **Step 6: Commit**

```bash
git add backend/football_osint/adapters/football_data_schedule.py tests/test_football_data_schedule_range.py
git commit -m "refactor: extract fetch_fixtures_for_range from football_data_schedule"
```

---

### Task 3: `track_record.py` — record + settle + matching

**Files:**
- Create: `backend/football_osint/track_record.py`
- Test: `tests/test_track_record.py` (extend from Task 1)

**Interfaces:**
- Consumes: `backend.auth.db.get_db()`, `backend.football_osint.models.FootballOsintJob`, `backend.football_osint.models.FootballOsintJobStatus`, `backend.football_osint.adapters.football_data_schedule.fetch_fixtures_for_range(date_from: str, date_to: str) -> list[Fixture]` (Task 2). `Fixture` has fields `home_team: str, away_team: str, status: str, home_score: int | None, away_score: int | None`.
- Produces: `record_if_definite(job: FootballOsintJob, conn=None) -> bool` (True if a row was inserted), `settle_pending(conn=None) -> int` (count of rows settled), `backfill_due(storage_root: str | Path | None = None) -> dict` (returns `{"recorded": int, "settled": int}`), `get_stats(conn=None, min_sample: int = 20, recent_limit: int = 20) -> dict`. Used by Task 4 (CLI), Task 5 (loop), Task 6 (route).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_track_record.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_track_record.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.football_osint.track_record'`

- [ ] **Step 3: Implement `track_record.py`**

Create `backend/football_osint/track_record.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_track_record.py -v`
Expected: PASS (all tests from Task 1 and Task 3)

- [ ] **Step 5: Commit**

```bash
git add backend/football_osint/track_record.py tests/test_track_record.py
git commit -m "feat: add track_record record/settle/stats logic"
```

---

### Task 4: One-off historical seed CLI

**Files:**
- Modify: `backend/football_osint/track_record.py` (append `__main__` block)
- Test: manual verification only (thin CLI wrapper over already-tested `backfill_due`)

**Interfaces:**
- Consumes: `backfill_due()` (Task 3).
- Produces: `python -m backend.football_osint.track_record` runnable from repo root.

- [ ] **Step 1: Append the CLI entry point**

Append to `backend/football_osint/track_record.py`:

```python
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    result = backfill_due()
    print(f"recorded={result['recorded']} settled={result['settled']}")
```

- [ ] **Step 2: Verify manually**

Run: `python -m backend.football_osint.track_record`
Expected: prints `recorded=N settled=M` (N/M depend on what's in your local `bronze_storage/football_osint/`; 0/0 is fine on a fresh checkout — this confirms the script runs without error, not a specific count)

- [ ] **Step 3: Commit**

```bash
git add backend/football_osint/track_record.py
git commit -m "feat: add CLI entry point for one-off track-record backfill"
```

---

### Task 5: Stats endpoint

**Files:**
- Modify: `backend/football_osint/routes.py` (add import + route near `list_fixtures`, after line 161's blank line / before line 162's `@router.get("/fixtures")`)
- Test: `tests/test_track_record_route.py` (new file)

**Interfaces:**
- Consumes: `track_record.get_stats()` (Task 3).
- Produces: `GET /api/football/osint/track-record` → JSON body matching `get_stats()`'s return shape. No auth required (public marketing stat).

- [ ] **Step 1: Write the failing test**

Create `tests/test_track_record_route.py`:

```python
"""Tests for GET /api/football/osint/track-record."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app_football import app
from backend.football_osint import track_record


def test_track_record_route_returns_settled_only_below_threshold(monkeypatch):
    monkeypatch.setattr(track_record, "get_stats", lambda **kw: {"settled": 5})
    client = TestClient(app)

    res = client.get("/api/football/osint/track-record")

    assert res.status_code == 200
    assert res.json() == {"settled": 5}


def test_track_record_route_returns_full_stats_above_threshold(monkeypatch):
    fake_stats = {"settled": 30, "lean_accuracy": 0.6, "scoreline_accuracy": 0.2, "recent": []}
    monkeypatch.setattr(track_record, "get_stats", lambda **kw: fake_stats)
    client = TestClient(app)

    res = client.get("/api/football/osint/track-record")

    assert res.status_code == 200
    assert res.json() == fake_stats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_track_record_route.py -v`
Expected: FAIL with 404 (route doesn't exist)

- [ ] **Step 3: Implement the route**

In `backend/football_osint/routes.py`, add to the imports near the top (after the existing `from . import warm_cache` line):

```python
from . import track_record
```

Then add the route, placed right before the existing `@router.get("/fixtures")` (around line 161):

```python
@router.get("/track-record")
async def get_track_record():
    return await asyncio.to_thread(track_record.get_stats)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_track_record_route.py -v`
Expected: PASS

- [ ] **Step 5: Run full backend suite to confirm no regression**

Run: `pytest tests/ -v`
Expected: PASS (all pre-existing tests plus the new ones)

- [ ] **Step 6: Commit**

```bash
git add backend/football_osint/routes.py tests/test_track_record_route.py
git commit -m "feat: add GET /api/football/osint/track-record endpoint"
```

---

### Task 6: Hourly backfill loop wired into app startup

**Files:**
- Modify: `backend/football_osint/track_record.py` (append `backfill_loop`)
- Modify: `backend/app_football.py:19-26` (lifespan)

**Interfaces:**
- Consumes: `backfill_due()` (Task 3).
- Produces: `backfill_loop() -> None` (runs forever, `asyncio.create_task`-able, mirrors `warm_cache.warm_loop`'s shape).

- [ ] **Step 1: Implement the loop**

Append to `backend/football_osint/track_record.py` (before the `if __name__` block from Task 4):

```python
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
```

- [ ] **Step 2: Wire it into app startup**

In `backend/app_football.py`, change the `lifespan` function (lines 19-26) from:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.football_osint import warm_cache

    task = asyncio.create_task(warm_cache.warm_loop())
    try:
        yield
    finally:
        task.cancel()
```

to:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.football_osint import track_record, warm_cache

    warm_task = asyncio.create_task(warm_cache.warm_loop())
    backfill_task = asyncio.create_task(track_record.backfill_loop())
    try:
        yield
    finally:
        warm_task.cancel()
        backfill_task.cancel()
```

- [ ] **Step 3: Verify the app still starts**

Run: `uvicorn backend.app_football:app --port 8001 &` then `curl -s http://127.0.0.1:8001/api/football/osint/track-record` then kill the server.
Expected: curl returns `{"settled":0}` (or similar), server starts without exceptions in the log.

- [ ] **Step 4: Commit**

```bash
git add backend/football_osint/track_record.py backend/app_football.py
git commit -m "feat: start hourly track-record backfill loop on app startup"
```

---

### Task 7: Frontend — types + API client

**Files:**
- Modify: `frontend/src/shijieqiuhua/types.ts` (append after `FootballOsintJob`, i.e. after line 157)
- Modify: `frontend/src/shijieqiuhua/api.ts` (append after `fetchFixtures`, around line 54)
- Test: `frontend/__tests__/shijieqiuhua-osint-api.test.ts` (extend)

**Interfaces:**
- Produces: `TrackRecordEntry` and `TrackRecordStats` types; `fetchTrackRecord(): Promise<TrackRecordStats>`. Used by Task 8.

- [ ] **Step 1: Write the failing test**

Append to `frontend/__tests__/shijieqiuhua-osint-api.test.ts`:

```ts
import { fetchTrackRecord } from '../src/shijieqiuhua/api'

// ... (inside the existing describe block, add a new test)
test('fetches track record stats', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ settled: 30, lean_accuracy: 0.6, scoreline_accuracy: 0.2, recent: [] }),
  }))

  const stats = await fetchTrackRecord()

  expect(stats.settled).toBe(30)
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/football/osint/track-record')
})
```

(Add the `fetchTrackRecord` import to the existing top-of-file import line rather than a second `import` statement: `import { askFootballQuestion, createFootballOsintJob, fetchFootballOsintJob, fetchTrackRecord } from '../src/shijieqiuhua/api'`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/shijieqiuhua-osint-api.test.ts`
Expected: FAIL — `fetchTrackRecord` is not exported

- [ ] **Step 3: Add the type**

Append to `frontend/src/shijieqiuhua/types.ts` (after the `FootballOsintJob` interface, line 157):

```ts
export interface TrackRecordEntry {
  home_team: string
  away_team: string
  kickoff_at: string
  predicted_lean: string
  predicted_scoreline_band: string[]
  actual_home_score: number
  actual_away_score: number
  lean_correct: boolean
  scoreline_hit: boolean
}

export interface TrackRecordStats {
  settled: number
  lean_accuracy?: number
  scoreline_accuracy?: number
  recent?: TrackRecordEntry[]
}
```

- [ ] **Step 4: Add the API client function**

Append to `frontend/src/shijieqiuhua/api.ts` (after `fetchFixtures`, line 54), and add `TrackRecordStats` to the existing `import type { ... } from './types'` line at the top of the file:

```ts
export async function fetchTrackRecord(): Promise<TrackRecordStats> {
  const res = await fetch('/api/football/osint/track-record')
  return readJson<TrackRecordStats>(res)
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/shijieqiuhua-osint-api.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shijieqiuhua/types.ts frontend/src/shijieqiuhua/api.ts frontend/__tests__/shijieqiuhua-osint-api.test.ts
git commit -m "feat: add fetchTrackRecord API client and TrackRecordStats type"
```

---

### Task 8: Frontend — landing page stat strip + detail table

**Files:**
- Modify: `frontend/src/shijieqiuhua/components/LandingPage.tsx`
- Test: `frontend/__tests__/shijieqiuhua-app.test.tsx` (extend) + `frontend/__tests__/shijieqiuhua-track-record-format.test.ts` (new file, for the pure formatting function)

**Interfaces:**
- Consumes: `fetchTrackRecord()`, `TrackRecordStats`, `TrackRecordEntry` (Task 7).
- Produces: named export `formatTrackRecordSummary(stats: TrackRecordStats): string | null` from `LandingPage.tsx` (testable without rendering, since the existing test suite uses `renderToString` and doesn't execute `useEffect`).

- [ ] **Step 1: Write the failing test for the pure formatter**

Create `frontend/__tests__/shijieqiuhua-track-record-format.test.ts`:

```ts
import { describe, expect, test } from 'vitest'
import { formatTrackRecordSummary } from '../src/shijieqiuhua/components/LandingPage'
import type { TrackRecordStats } from '../src/shijieqiuhua/types'

describe('formatTrackRecordSummary', () => {
  test('returns null when sample is below threshold (no recent field)', () => {
    const stats: TrackRecordStats = { settled: 5 }
    expect(formatTrackRecordSummary(stats)).toBeNull()
  })

  test('formats a summary string once accuracy fields are present', () => {
    const stats: TrackRecordStats = {
      settled: 124, lean_accuracy: 0.68, scoreline_accuracy: 0.21, recent: [],
    }
    expect(formatTrackRecordSummary(stats)).toBe('近 124 场比赛 · 方向命中率 68% · 比分命中率 21%')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/shijieqiuhua-track-record-format.test.ts`
Expected: FAIL — `formatTrackRecordSummary` is not exported

- [ ] **Step 3: Implement the formatter + component**

In `frontend/src/shijieqiuhua/components/LandingPage.tsx`:

Add to the top imports (alongside the existing `@phosphor-icons/react` import line), add `CaretDown` to the icon import list, and add a new import line:

```ts
import { useEffect, useState } from 'react'
import { fetchTrackRecord } from '../api'
import type { TrackRecordStats } from '../types'
```

After the `TRUST` constant (line 18), add:

```ts
export function formatTrackRecordSummary(stats: TrackRecordStats): string | null {
  if (stats.lean_accuracy === undefined || stats.scoreline_accuracy === undefined) return null
  const leanPct = Math.round(stats.lean_accuracy * 100)
  const scorePct = Math.round(stats.scoreline_accuracy * 100)
  return `近 ${stats.settled} 场比赛 · 方向命中率 ${leanPct}% · 比分命中率 ${scorePct}%`
}

function TrackRecordStrip() {
  const [stats, setStats] = useState<TrackRecordStats | null>(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    fetchTrackRecord().then(setStats).catch(() => {})
  }, [])

  if (!stats) return null
  const summary = formatTrackRecordSummary(stats)
  if (!summary || !stats.recent) return null

  return (
    <div className="sqh-land-track-record">
      <button className="sqh-land-track-record-summary" onClick={() => setExpanded(e => !e)}>
        {summary}
        <CaretDown size={14} weight="bold" style={{ transform: expanded ? 'rotate(180deg)' : undefined }} />
      </button>
      {expanded && (
        <table className="sqh-land-track-record-table">
          <thead>
            <tr><th>对阵</th><th>预测</th><th>实际比分</th><th>命中</th></tr>
          </thead>
          <tbody>
            {stats.recent.map((r, i) => (
              <tr key={i}>
                <td>{r.home_team} vs {r.away_team}</td>
                <td>{r.predicted_lean}（{r.predicted_scoreline_band.join('/')}）</td>
                <td>{r.actual_home_score}-{r.actual_away_score}</td>
                <td>{r.lean_correct ? '✓' : '✗'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

Then render `<TrackRecordStrip />` right after the closing `</div>` of `sqh-land-trust` (i.e. immediately after the `{TRUST.map(...)}` block's closing `</div>`, still inside `<header className="sqh-land-hero">`).

- [ ] **Step 4: Run formatter test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/shijieqiuhua-track-record-format.test.ts`
Expected: PASS

- [ ] **Step 5: Run the full frontend suite to confirm no regression**

Run: `cd frontend && npm test`
Expected: PASS — `shijieqiuhua-app.test.tsx`'s `renderToString` calls don't execute `useEffect`, so `TrackRecordStrip` renders as `null` (its initial `stats` state) and the existing assertions about static text are unaffected.

- [ ] **Step 6: Manual UI check**

Run: `cd frontend && npm run dev`, open `http://localhost:5173`, confirm the landing page loads with no console errors. Since the backend likely has `settled < 20` locally, no stat strip will render — this is the expected `< 20` path. To see the populated path, you can temporarily point `fetchTrackRecord` at a local mock by editing the dev-only override, or just trust the unit tests for the populated branch (rendering 20+ real settled rows isn't reproducible without seeded data).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shijieqiuhua/components/LandingPage.tsx frontend/__tests__/shijieqiuhua-track-record-format.test.ts
git commit -m "feat: show prediction track-record stat strip on landing page"
```

---

### Task 9: CSS for the new strip

**Files:**
- Modify: `frontend/src/shijieqiuhua.css` (append new rules near existing `.sqh-land-trust` / `.sqh-land-stat` rules)

**Interfaces:**
- Consumes: nothing.
- Produces: visual styling for `.sqh-land-track-record`, `.sqh-land-track-record-summary`, `.sqh-land-track-record-table` classes used in Task 8.

- [ ] **Step 1: Find the existing trust-strip styles**

Run: `grep -n "sqh-land-trust\|sqh-land-stat" frontend/src/shijieqiuhua.css`

- [ ] **Step 2: Append new rules directly after that block**

Add (use the file's existing literal hex palette — check the nearby `.sqh-land-stat` rule for the exact brand-green/beige hex values in use and reuse them rather than introducing new ones):

```css
.sqh-land-track-record { margin-top: 20px; }
.sqh-land-track-record-summary {
  display: inline-flex; align-items: center; gap: 6px;
  background: none; border: none; cursor: pointer;
  font-size: 14px; font-weight: 600; padding: 0;
}
.sqh-land-track-record-table { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }
.sqh-land-track-record-table th, .sqh-land-track-record-table td {
  padding: 6px 10px; text-align: left; border-bottom: 1px solid rgba(0,0,0,0.08);
}
```

- [ ] **Step 3: Manual visual check**

Run: `cd frontend && npm run dev`, confirm no CSS parse errors in the browser console (the rules apply even with no matching elements rendered, since `settled < 20` locally hides the strip — this just confirms the CSS itself is syntactically valid and loaded).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shijieqiuhua.css
git commit -m "style: add track-record stat strip styling"
```

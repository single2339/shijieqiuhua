# Football Cache Track Record Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 2026-06-30 PRD addendum so warm-cache windows, bronze job metadata, track-record stats, history grouping, and job/report fallback are match-level, durable, and test-covered.

**Architecture:** Keep the current single-node FastAPI + SQLite + bronze filesystem architecture. Add a small football schema/metadata layer, keep prediction algorithms unchanged, and make `prediction_record` a history/settlement index with exactly one public stats-primary row per `match_key`.

**Tech Stack:** Python 3.11+ / FastAPI / sqlite3 stdlib / pytest; no new runtime dependencies.

## Global Constraints

- Do not change prediction weights, search strategy, or UI visual design.
- Public stats only count `stats_primary=1 AND settled_at IS NOT NULL AND predicted_lean IN ('home','away','draw')`.
- Same `match_key` may have many history rows, but at most one `stats_primary=1` row.
- Warm-window completion must be durable in SQLite; the in-memory `_completed_windows` set may only be an acceleration cache.
- `request.json` must contain job provenance metadata while not exposing raw free-text in public history responses.
- Existing `/track-record` response fields must stay backward-compatible; added fields are optional.
- All behavior changes must be introduced test-first.

---

### Task 1: Schema and metadata helpers

**Files:**
- Modify: `sql/004_prediction_track_record.sql`
- Create: `backend/football_osint/schema.py`
- Create: `backend/football_osint/job_metadata.py`
- Modify: `backend/auth/db.py`
- Test: `tests/test_track_record.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Produces `ensure_schema(conn: sqlite3.Connection) -> None`.
- Produces `match_key(home_team: str, away_team: str, kickoff_at: str) -> str`.
- Produces `question_metadata(question: str, *, warm_window: str = "on-demand", cache_source: str = "on-demand") -> dict[str, str | None]`.
- Produces `record_request_metadata(request: FootballOsintJobRequest, *, warm_window: str, cache_source: str) -> dict`.

**Steps:**
- [x] Add failing schema tests that assert new `prediction_record` columns, `warm_cache_run`, and partial indexes exist after `auth_db.get_db()`.
- [x] Add failing metadata tests for `match_key`, preset `question_id`, free-text hashing, and no raw free-text in public-safe metadata.
- [x] Implement `schema.ensure_schema()` with idempotent `PRAGMA table_info` checks and `ALTER TABLE ... ADD COLUMN` only when missing.
- [x] Call `ensure_schema()` from `auth_db.get_db()` after SQL migrations.
- [x] Implement `job_metadata.py` with the six preset question IDs.
- [x] Re-run the focused schema/metadata tests until green.

### Task 2: Bronze request metadata and warm-cache durable runs

**Files:**
- Modify: `backend/football_osint/storage.py`
- Modify: `backend/football_osint/pipeline.py`
- Modify: `backend/football_osint/warm_cache.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- `run_prediction_sync(payload, storage_root=None, *, warm_window="on-demand", cache_source="on-demand")` passes metadata to storage.
- `storage.persist_job(job, storage_root=None, *, request=None, warm_window="on-demand", cache_source="on-demand")` writes enriched `request.json`.
- `warm_cache.mark_warm_run(...)` writes durable `warm_cache_run` rows.
- `_force_refresh(...) -> CacheEntry` raises on failure and returns the refreshed entry.

**Steps:**
- [x] Add failing test that `request.json` contains `match_key`, `question_kind`, `question_id`, `question_hash`, `warm_window`, `cache_source`, `locale`, and user-supplied counts.
- [x] Add failing async tests that a completed warm window is skipped after in-memory state is cleared, and a partial window records `successful_questions=5`.
- [x] Update `storage.persist_job()` and `pipeline.run_prediction_sync()` to write request metadata.
- [x] Update `_force_refresh()` to return `CacheEntry` and stop swallowing exceptions.
- [x] Update `_run_analysis_for_match()` to write `warm_cache_run` as `completed`, `partial`, or `failed` with job ids.
- [x] Update `_next_analysis_time()` / warm loop decision path to consult durable completed windows before scheduling work.
- [x] Re-run focused warm/storage tests until green.

### Task 3: Track-record stats-primary semantics and migration

**Files:**
- Modify: `backend/football_osint/track_record.py`
- Test: `tests/test_track_record.py`

**Interfaces:**
- `record_if_definite(job, conn=None, metadata=None) -> bool` writes all trackable rows with metadata.
- `select_stats_primary(conn, match_key_value: str) -> None` maintains one primary per match.
- `migrate_prediction_record_metadata(conn=None) -> dict[str, int]` fills legacy metadata and is idempotent.
- `get_stats()` filters on `stats_primary=1` plus explicit lean.

**Steps:**
- [x] Add failing tests for six jobs on the same match producing one `stats_primary=1` row and five `history_detail` rows.
- [x] Add failing tests for legacy duplicates migration: one primary selected, others excluded with reasons, second run unchanged.
- [x] Add failing test that `get_stats()` excludes non-primary explicit rows and reports `sample_policy` / `excluded_duplicates`.
- [x] Implement metadata insertion and stats-primary selection.
- [x] Implement idempotent legacy migration helper.
- [x] Update `backfill_due()` to call migration/schema helpers before record/settle.
- [x] Re-run `tests/test_track_record.py` until green.

### Task 4: Routes, history grouping, and report fallback

**Files:**
- Modify: `backend/football_osint/history.py`
- Modify: `backend/football_osint/routes.py`
- Test: `tests/test_history.py`
- Test: `tests/test_track_record_route.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- `/jobs/{job_id}` and `/jobs/{job_id}/report.md` read bronze files after cache miss.
- `history.get_history_list()` groups by `match_key` and exposes `detail_count` / `primary_job_id`.
- `history.get_history_detail()` includes record metadata and tolerates malformed `predicted_scoreline_band`.
- `/compare` rejects duplicate `match_key` selections with 422.

**Steps:**
- [x] Add failing route tests for bronze fallback after cache miss.
- [x] Add failing history tests for grouping, metadata in detail, malformed scoreline fallback, and no raw free-text in list output.
- [x] Add failing compare test for duplicate same-match jobs.
- [x] Implement bronze fallback helpers in routes.
- [x] Update history queries/read models.
- [x] Update compare duplicate guard.
- [x] Re-run focused route/history tests until green.

### Task 5: Full verification and review

**Files:**
- All touched backend files and tests.

**Steps:**
- [x] Run focused suites: `tests/test_track_record.py`, `tests/test_history.py`, `tests/test_track_record_route.py`, `tests/test_football_osint.py`.
- [x] Run full backend suite: `.venv/bin/pytest`.
- [x] Run `git diff --check` on touched files.
- [x] Dispatch final code review.
- [x] Fix any Critical/Important findings and re-run affected tests.

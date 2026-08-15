"""SQLite schema helpers for football OSINT metadata migrations."""
from __future__ import annotations

import sqlite3

_PREDICTION_RECORD_COLUMNS: dict[str, str] = {
    "match_key": "TEXT NOT NULL DEFAULT ''",
    "question_kind": "TEXT NOT NULL DEFAULT 'legacy'",
    "question_id": "TEXT NOT NULL DEFAULT 'legacy_unknown'",
    "question_hash": "TEXT",
    "warm_window": "TEXT NOT NULL DEFAULT 'legacy_unknown'",
    "cache_source": "TEXT NOT NULL DEFAULT 'migration'",
    "record_role": "TEXT NOT NULL DEFAULT 'legacy_pending'",
    "stats_primary": "INTEGER NOT NULL DEFAULT 0",
    "excluded_reason": "TEXT NOT NULL DEFAULT ''",
    "created_from_job_id": "TEXT",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure football-specific SQLite objects are present.

    The auth layer re-runs SQL migrations on each new connection. SQLite does
    not reliably support idempotent ``ALTER TABLE ADD COLUMN`` across target
    versions, so missing columns are added here by inspecting table metadata.
    """
    _ensure_prediction_record_columns(conn)
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_record_one_stats_primary
        ON prediction_record(match_key)
        WHERE stats_primary = 1;

        CREATE INDEX IF NOT EXISTS idx_prediction_record_match_key
        ON prediction_record(match_key);

        CREATE INDEX IF NOT EXISTS idx_prediction_record_role_settled
        ON prediction_record(record_role, settled_at);

        CREATE TABLE IF NOT EXISTS warm_cache_run (
            match_key TEXT NOT NULL,
            window TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff_at TEXT NOT NULL,
            competition TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            expected_questions INTEGER NOT NULL DEFAULT 6,
            successful_questions INTEGER NOT NULL DEFAULT 0,
            job_ids_json TEXT NOT NULL DEFAULT '[]',
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT,
            error TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (match_key, window)
        );
        """
    )
    conn.commit()


def _ensure_prediction_record_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(prediction_record)").fetchall()
    }
    for name, definition in _PREDICTION_RECORD_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE prediction_record ADD COLUMN {name} {definition}")

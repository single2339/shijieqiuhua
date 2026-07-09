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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    match_key TEXT NOT NULL DEFAULT '',
    question_kind TEXT NOT NULL DEFAULT 'legacy',
    question_id TEXT NOT NULL DEFAULT 'legacy_unknown',
    question_hash TEXT,
    warm_window TEXT NOT NULL DEFAULT 'legacy_unknown',
    cache_source TEXT NOT NULL DEFAULT 'migration',
    record_role TEXT NOT NULL DEFAULT 'legacy_pending',
    stats_primary INTEGER NOT NULL DEFAULT 0,
    excluded_reason TEXT NOT NULL DEFAULT '',
    created_from_job_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_prediction_record_settled ON prediction_record(settled_at);

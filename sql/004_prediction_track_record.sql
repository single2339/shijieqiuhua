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

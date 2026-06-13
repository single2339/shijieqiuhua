-- 002_telemetry.sql
-- v1 telemetry + alert tables. SQLite-flavored.
-- Idempotent: safe to re-run (uses IF NOT EXISTS).
-- Loaded automatically by backend/telemetry.py on first emit().

-- ── telemetry_event ──
-- Behavior + performance signals. NOT for compliance — see audit_log for that.
-- payload_json holds event-specific fields; queries use json_extract().
CREATE TABLE IF NOT EXISTS telemetry_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL UNIQUE,           -- ulid (26 chars)
    ts            TEXT NOT NULL,                  -- ISO8601 UTC, e.g. 2026-06-13T10:00:00Z
    event_name    TEXT NOT NULL,                  -- snake_case, e.g. research.dashboard_completed
    user_id       TEXT,                           -- nullable for anonymous
    session_id    TEXT,                           -- browser session cookie
    request_id    TEXT,                           -- ties multiple emits to one HTTP request
    duration_ms   INTEGER,                        -- only for *.completed events
    status        TEXT,                           -- ok | error | skipped | timeout
    error_code    TEXT,                           -- only when status=error
    payload_json  TEXT NOT NULL DEFAULT '{}',     -- event-specific fields
    ip_hash       TEXT,                           -- sha256(ip)[:12]
    ua_class      TEXT                            -- desktop | mobile | bot | unknown
);

CREATE INDEX IF NOT EXISTS idx_tel_event_ts ON telemetry_event(event_name, ts);
CREATE INDEX IF NOT EXISTS idx_tel_user_ts  ON telemetry_event(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_tel_request  ON telemetry_event(request_id);
CREATE INDEX IF NOT EXISTS idx_tel_ts       ON telemetry_event(ts);

-- ── alert_fired ──
-- Dedup table for alert_runner. Same rule_id within cooldown window
-- (default 15 min for P1, 24h for P2) won't re-send.
CREATE TABLE IF NOT EXISTS alert_fired (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id       TEXT NOT NULL,                  -- ALERT-1, ALERT-2, ...
    severity      TEXT NOT NULL,                  -- P1 | P2
    fired_at      TEXT NOT NULL,                  -- ISO8601 UTC
    payload_json  TEXT NOT NULL DEFAULT '{}',     -- diagnostic snapshot
    sent_to       TEXT,                           -- email address(es) joined by ','
    delivery_status TEXT NOT NULL DEFAULT 'pending'  -- pending | sent | failed | skipped_dryrun
);

CREATE INDEX IF NOT EXISTS idx_alert_recent ON alert_fired(rule_id, fired_at);

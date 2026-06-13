-- 003_billing_and_entitlements.sql
--
-- W1 schema additions for v1 billing + audit. Lives in the same SQLite file
-- as the existing auth tables (bronze_storage/_auth.db) so payment/entitlement
-- writes can share a transaction with the user row they affect.
--
-- Naming differs slightly from PRD §6.1 because the auth module already owns
-- `users` (INTEGER id, not TEXT). We reuse that primary key rather than
-- migrating to TEXT ulids, which would break the existing 71 tests.
--
-- Idempotent — safe to re-run on every backend boot.

-- ── activation_code (付费码) ──
CREATE TABLE IF NOT EXISTS activation_code (
    code                          TEXT PRIMARY KEY,           -- [A-Z2-9]{16}
    status                        TEXT NOT NULL,              -- unused | used
    granted_to_user_id            INTEGER REFERENCES users(id),
    redeemed_at                   TEXT,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at                    TEXT NOT NULL,              -- ISO8601; default 90d via app
    validity_days_after_redeem   INTEGER,                     -- NULL = permanent entitlement
    note                          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_activation_code_status ON activation_code(status);

-- ── entitlement (权益) ──
-- v1 only one type ('full_analysis'); UNIQUE(user_id, type) prevents
-- double-grant. expires_at NULL = permanent.
CREATE TABLE IF NOT EXISTS entitlement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    type        TEXT NOT NULL,
    granted_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,                                         -- NULL = permanent
    source      TEXT NOT NULL,                                -- code:<code> | admin:<admin_id>
    UNIQUE(user_id, type)
);
CREATE INDEX IF NOT EXISTS idx_entitlement_user ON entitlement(user_id);

-- ── audit_log ──
-- Compliance-relevant events. Separate from telemetry_event (different DB,
-- different retention: 6mo vs 90d). actor='user'|'admin'|'system'.
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL DEFAULT (datetime('now')),
    user_id       INTEGER REFERENCES users(id),
    actor         TEXT NOT NULL,
    event         TEXT NOT NULL,                              -- e.g. invitation.consumed
    payload_json  TEXT NOT NULL DEFAULT '{}',
    ip            TEXT,
    user_agent    TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_event_ts ON audit_log(event, ts);
CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_log(user_id, ts);

-- ── system_config ──
-- admin CLI writes here (e.g. info_insufficient threshold). Read by pipeline.
CREATE TABLE IF NOT EXISTS system_config (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by   TEXT
);

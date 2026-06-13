"""Audit log writer.

Compliance-relevant events (registration, code redemption, admin actions)
flow through this module. Distinct from backend.telemetry by design:

- audit_log lives in the auth DB so it shares transactions with users / billing
- payload retention is 6 months (vs 90 days for telemetry)
- write() takes the auth DB connection so callers can include it inside
  the surrounding transaction; if no conn passed, opens its own

Like telemetry.emit(), write() never raises — the calling event is more
important than the audit row.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from backend.auth.db import get_db

log = logging.getLogger(__name__)


def write(
    *,
    event: str,
    actor: str,
    user_id: int | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Append one audit row. Never raises.

    Caller may pass an existing connection to reuse the surrounding
    transaction (e.g. registration consuming an invite code). Otherwise
    a fresh autocommit insert.
    """
    if actor not in ("user", "admin", "system"):
        log.warning("audit.write: unknown actor=%s, coercing to 'system'", actor)
        actor = "system"
    payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
    try:
        c = conn or get_db()
        c.execute(
            """
            INSERT INTO audit_log (user_id, actor, event, payload_json, ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, actor, event, payload_json, ip, user_agent),
        )
        if conn is None:
            c.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("audit.write failed: %s (%s)", event, exc)


def recent(event: str | None = None, limit: int = 50, conn: sqlite3.Connection | None = None) -> list[sqlite3.Row]:
    """Read helper, mainly for admin CLI / tests."""
    c = conn or get_db()
    if event:
        rows = c.execute(
            "SELECT * FROM audit_log WHERE event=? ORDER BY id DESC LIMIT ?",
            (event, limit),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return list(rows)

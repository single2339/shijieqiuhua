"""Lightweight telemetry SDK for Shijieqiuhua v1.

Design rules:
- emit() MUST NOT raise. Telemetry failures must not break the main flow.
- Single SQLite table (telemetry_event). For v1 traffic (< 50 writes/s) a
  shared connection with WAL is enough; revisit if the load grows.
- PII never leaves the function: callers pass already-hashed values via
  hash_text() / host_of() / hash_ip().
- audit_log writes go through a separate path (see backend/audit.py, TBD)
  because they have different retention and are compliance-relevant.

See docs/superpowers/specs/2026-06-13-telemetry/01-events-and-model.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# ── DB location ──
# Lazy-init: the DB lives next to bronze_storage._index.db so the same backup
# job covers both. Override via FOOTBALL_OSINT_TELEMETRY_DB for tests.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "bronze_storage" / "_telemetry.db"
_SQL_MIGRATION_PATH = Path(__file__).resolve().parent.parent / "sql" / "002_telemetry.sql"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_db_path_cached: Path | None = None


def _db_path() -> Path:
    override = os.getenv("FOOTBALL_OSINT_TELEMETRY_DB", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def _get_conn() -> sqlite3.Connection:
    """Lazy-open the connection. WAL + small cache. Safe across threads."""
    global _conn, _db_path_cached
    target = _db_path()
    with _lock:
        if _conn is None or _db_path_cached != target:
            if _conn is not None:
                _conn.close()
            target.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(target), check_same_thread=False, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            if _SQL_MIGRATION_PATH.exists():
                conn.executescript(_SQL_MIGRATION_PATH.read_text(encoding="utf-8"))
            _conn = conn
            _db_path_cached = target
        return _conn


def reset_for_tests() -> None:
    """Tear down the cached connection so tests can swap DB paths cleanly."""
    global _conn, _db_path_cached
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _db_path_cached = None


# ── PII helpers ──

def hash_text(text: str | None, length: int = 12) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def hash_ip(ip: str | None) -> str:
    return hash_text(ip)


def host_of(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower()
    except (ValueError, AttributeError):
        return ""


# ── core ──

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_event_id() -> str:
    # Not strictly ulid, but uuid4 hex is uniformly unique and avoids a new dep.
    return uuid.uuid4().hex


def emit(
    event_name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    status: str | None = None,
    error_code: str | None = None,
    payload: dict[str, Any] | None = None,
    ip_hash: str | None = None,
    ua_class: str | None = None,
) -> None:
    """Persist one telemetry event.

    Never raises. Logs at warning level on failure so we can spot a broken
    pipeline without taking the request path down with us.
    """
    try:
        conn = _get_conn()
        payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
        with _lock:
            conn.execute(
                """
                INSERT INTO telemetry_event
                  (event_id, ts, event_name, user_id, session_id, request_id,
                   duration_ms, status, error_code, payload_json, ip_hash, ua_class)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_event_id(),
                    _now_iso(),
                    event_name,
                    user_id,
                    session_id,
                    request_id,
                    duration_ms,
                    status,
                    error_code,
                    payload_json,
                    ip_hash,
                    ua_class,
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — telemetry must never propagate
        log.warning("telemetry emit failed: %s (%s)", event_name, exc)


@contextmanager
def measure(
    event_name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip_hash: str | None = None,
    ua_class: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Time a block and emit the event when it finishes.

    Usage::

        with measure("research.dashboard_completed", user_id=u) as m:
            result = do_work()
            m["payload"]["cache_hit"] = result.cache_hit

    On exception the event is recorded with status='error' and re-raised.
    """
    state: dict[str, Any] = {
        "payload": dict(payload or {}),
        "status": "ok",
        "error_code": None,
    }
    started = time.monotonic()
    try:
        yield state
    except Exception as exc:  # noqa: BLE001
        state["status"] = "error"
        state["error_code"] = state.get("error_code") or exc.__class__.__name__
        raise
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        emit(
            event_name,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            duration_ms=duration_ms,
            status=state["status"],
            error_code=state["error_code"],
            payload=state["payload"],
            ip_hash=ip_hash,
            ua_class=ua_class,
        )

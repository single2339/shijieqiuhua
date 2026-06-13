"""Tests for backend.audit.

audit.write() must:
- never raise (similar to telemetry.emit)
- accept actor='user'|'admin'|'system' and coerce others to 'system'
- share the caller's transaction when conn is provided
- store payload as JSON
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from backend import audit
from backend.auth import db as auth_db


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir(parents=True)
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    conn = auth_db.get_db()
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, role) "
        "VALUES (1, 'u1', 'a@b.com', 'x', 'user')"
    )
    conn.commit()
    yield conn
    auth_db.close_db()


def test_write_persists_event(tmp_db):
    audit.write(
        event="invitation.consumed",
        actor="user",
        user_id=1,
        payload={"invite_code_prefix": "ABCD"},
        ip="1.2.3.4",
    )
    rows = audit.recent(event="invitation.consumed", conn=tmp_db)
    assert len(rows) == 1
    assert rows[0]["actor"] == "user"
    assert rows[0]["user_id"] == 1
    assert "ABCD" in rows[0]["payload_json"]


def test_write_unknown_actor_coerces_to_system(tmp_db):
    audit.write(event="x.test", actor="hacker", payload={})
    rows = audit.recent(event="x.test", conn=tmp_db)
    assert rows[0]["actor"] == "system"


def test_write_swallows_errors(monkeypatch, tmp_db):
    """If the DB layer fails, audit.write must not raise."""

    def boom(*_a, **_kw):
        raise sqlite3.OperationalError("simulated")

    monkeypatch.setattr(audit, "get_db", boom)
    audit.write(event="x.swallowed", actor="system", payload={})


def test_write_shares_caller_transaction(tmp_db):
    """When conn is passed, write does not commit; caller controls the txn."""
    tmp_db.execute("BEGIN IMMEDIATE")
    audit.write(event="txn.test", actor="user", user_id=1, payload={}, conn=tmp_db)
    # Before commit, another connection should not see the row
    other = sqlite3.connect(str(auth_db.DB_PATH))
    other.row_factory = sqlite3.Row
    rows = other.execute("SELECT * FROM audit_log WHERE event='txn.test'").fetchall()
    other.close()
    # WAL mode + uncommitted writes: the other reader sees nothing
    assert len(rows) == 0
    tmp_db.commit()


def test_recent_filters_by_event(tmp_db):
    audit.write(event="a.one", actor="system", payload={})
    audit.write(event="a.two", actor="system", payload={})
    audit.write(event="a.one", actor="system", payload={})
    rows = audit.recent(event="a.one", conn=tmp_db)
    assert len(rows) == 2

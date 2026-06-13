"""Tests for backend.admin CLI.

Smoke tests for each subcommand. Goal: verify the CLI dispatches correctly,
ADMIN_TOKEN gates writes, and audit rows are emitted. End-to-end command
contracts (option parsing, output format) are covered too.
"""
from __future__ import annotations

import io
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend import admin, audit, billing
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
        "VALUES (1, 'rootadmin', 'a@example.com', 'x', 'admin')"
    )
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, role) "
        "VALUES (2, 'normal', 'n@example.com', 'x', 'user')"
    )
    conn.commit()
    monkeypatch.setenv("ADMIN_TOKEN", "test-secret")
    yield conn
    auth_db.close_db()


# ── auth gate ──

def test_no_admin_token_returns_1(tmp_db, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    rc = admin.main(["invite_codes", "--count", "1"])
    assert rc == 1


def test_token_mismatch_returns_1(tmp_db, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN_INPUT", "wrong-token")
    rc = admin.main(["invite_codes", "--count", "1"])
    assert rc == 1


# ── invite_codes ──

def test_invite_codes_creates_rows_and_audit(tmp_db, capsys):
    rc = admin.main(["invite_codes", "--count", "3", "--max-uses", "1", "--validity-days", "30"])
    assert rc == 0
    rows = tmp_db.execute("SELECT code, max_uses, current_uses FROM registration_codes ORDER BY id").fetchall()
    assert len(rows) == 3
    assert all(r["max_uses"] == 1 and r["current_uses"] == 0 for r in rows)
    audit_rows = audit.recent(event="admin.bulk_create_invite", conn=tmp_db)
    assert len(audit_rows) == 1


def test_invite_codes_writes_csv_when_output_given(tmp_db, tmp_path):
    out = tmp_path / "codes.csv"
    rc = admin.main(["invite_codes", "--count", "2", "--output", str(out)])
    assert rc == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # header + 2 rows
    assert content.count("\n") == 3


def test_invite_codes_rejects_count_over_1000(tmp_db):
    rc = admin.main(["invite_codes", "--count", "1500"])
    assert rc == 2


# ── payment_codes ──

def test_payment_codes_creates_activation_rows_and_audit(tmp_db):
    rc = admin.main(["payment_codes", "--count", "5", "--validity-days", "60", "--note", "promo"])
    assert rc == 0
    rows = tmp_db.execute("SELECT status, note FROM activation_code").fetchall()
    assert len(rows) == 5
    assert all(r["status"] == "unused" and r["note"] == "promo" for r in rows)
    audit_rows = audit.recent(event="admin.bulk_create_payment", conn=tmp_db)
    assert len(audit_rows) == 1


def test_payment_codes_validity_after_redeem_propagates(tmp_db):
    rc = admin.main(["payment_codes", "--count", "1", "--validity-after-redeem", "365"])
    assert rc == 0
    row = tmp_db.execute("SELECT validity_days_after_redeem FROM activation_code LIMIT 1").fetchone()
    assert row["validity_days_after_redeem"] == 365


# ── list_users ──

def test_list_users_emits_rows(tmp_db, capsys):
    rc = admin.main(["list_users", "--limit", "10"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "rootadmin" in out
    assert "normal" in out


def test_list_users_paid_filter_excludes_unpaid(tmp_db, capsys):
    # Burn one entitlement onto user 2
    code = billing.generate_codes(count=1)[0]
    billing.redeem_code(code=code, user_id=2)
    rc = admin.main(["list_users", "--paid"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "normal" in out  # the paid user
    assert "rootadmin" not in out  # admin doesn't have entitlement


# ── list_codes ──

def test_list_codes_invite_returns_unused(tmp_db, capsys):
    admin.main(["invite_codes", "--count", "2"])
    capsys.readouterr()  # drop the bare codes printed by invite_codes
    rc = admin.main(["list_codes", "--type", "invite", "--status", "unused"])
    assert rc == 0
    out = capsys.readouterr().out
    # 2 rows of tab-separated columns (code, max_uses, current_uses, is_active, created_at, expires_at)
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) == 2
    assert all("\t" in l for l in lines)


def test_list_codes_payment_used_filter(tmp_db, capsys):
    # Create + redeem 1, leave 1 unused
    [code1, code2] = billing.generate_codes(count=2)
    billing.redeem_code(code=code1, user_id=2)
    rc = admin.main(["list_codes", "--type", "payment", "--status", "used"])
    assert rc == 0
    out = capsys.readouterr().out
    assert code1 in out
    assert code2 not in out


# ── set_threshold ──

def test_set_threshold_writes_system_config_and_upserts(tmp_db):
    rc = admin.main(["set_threshold", "--key", "info_insufficient_factor_min", "--value", "1"])
    assert rc == 0
    row = tmp_db.execute(
        "SELECT value FROM system_config WHERE key='info_insufficient_factor_min'"
    ).fetchone()
    assert row["value"] == "1"
    # Upsert: change it, expect overwrite (not duplicate)
    rc = admin.main(["set_threshold", "--key", "info_insufficient_factor_min", "--value", "2"])
    assert rc == 0
    rows = tmp_db.execute(
        "SELECT value FROM system_config WHERE key='info_insufficient_factor_min'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["value"] == "2"
    audit_rows = audit.recent(event="admin.set_threshold", conn=tmp_db)
    assert len(audit_rows) == 2


# ── ban_user ──

def test_ban_user_flips_is_active_and_audits(tmp_db):
    rc = admin.main(["ban_user", "--user-id", "2", "--reason", "abuse"])
    assert rc == 0
    row = tmp_db.execute("SELECT is_active FROM users WHERE id=2").fetchone()
    assert row["is_active"] == 0
    audit_rows = audit.recent(event="admin.ban_user", conn=tmp_db)
    assert len(audit_rows) == 1
    assert audit_rows[0]["user_id"] == 2


def test_ban_user_unknown_id_returns_5(tmp_db):
    rc = admin.main(["ban_user", "--user-id", "9999", "--reason", "x"])
    assert rc == 5

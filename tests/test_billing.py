"""Tests for backend.billing.

Covers UC-03 acceptance criteria AC-03-1 through AC-03-9 from
docs/superpowers/specs/2026-06-12-prd-redo/10-acceptance-criteria.md.

Each test creates an isolated _auth.db under tmp_path and monkeypatches
backend.auth.db so the module-level singleton uses the throwaway DB.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend import audit, billing
from backend.auth import db as auth_db
from backend.billing import service as billing_service


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
        "VALUES (1, 'tester', 't@example.com', 'x', 'user')"
    )
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, role) "
        "VALUES (2, 'tester2', 't2@example.com', 'x', 'user')"
    )
    conn.commit()
    yield conn
    auth_db.close_db()


def _make_code(conn, *, code="ABCD2345EFGH6789", status="unused", expires_in_days=90, validity_days_after_redeem=None):
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO activation_code (code, status, expires_at, validity_days_after_redeem) VALUES (?, ?, ?, ?)",
        (code, status, expires_at, validity_days_after_redeem),
    )
    conn.commit()
    return code


# ── happy path ──

def test_redeem_creates_entitlement_and_marks_code_used(tmp_db):
    code = _make_code(tmp_db)
    ent = billing.redeem_code(code=code, user_id=1)
    assert ent.user_id == 1
    assert ent.type == "full_analysis"
    assert ent.expires_at is None  # permanent (validity_days_after_redeem=None)

    row = tmp_db.execute("SELECT status, granted_to_user_id FROM activation_code WHERE code=?", (code,)).fetchone()
    assert row["status"] == "used"
    assert row["granted_to_user_id"] == 1


def test_redeem_with_validity_window_sets_expires_at(tmp_db):
    code = _make_code(tmp_db, validity_days_after_redeem=30)
    ent = billing.redeem_code(code=code, user_id=1)
    assert ent.expires_at is not None


def test_redeem_writes_audit_row(tmp_db):
    code = _make_code(tmp_db)
    billing.redeem_code(code=code, user_id=1, actor_ip="1.2.3.4")
    rows = audit.recent(event="billing.code_redeemed", conn=tmp_db)
    assert len(rows) == 1
    assert rows[0]["user_id"] == 1
    assert rows[0]["ip"] == "1.2.3.4"


# ── error paths (AC-03-2 .. AC-03-5) ──

def test_redeem_unknown_code_raises_invalid(tmp_db):
    with pytest.raises(billing.BillingError) as exc_info:
        billing.redeem_code(code="NOPENOPENOPENOPE", user_id=1)
    assert exc_info.value.error_code == "E_CODE_INVALID"


def test_redeem_used_code_raises_used(tmp_db):
    code = _make_code(tmp_db, status="used")
    with pytest.raises(billing.BillingError) as exc_info:
        billing.redeem_code(code=code, user_id=1)
    assert exc_info.value.error_code == "E_CODE_USED"


def test_redeem_expired_code_raises_expired(tmp_db):
    code = _make_code(tmp_db, expires_in_days=-1)
    with pytest.raises(billing.BillingError) as exc_info:
        billing.redeem_code(code=code, user_id=1)
    assert exc_info.value.error_code == "E_CODE_EXPIRED"


def test_redeem_when_user_already_entitled_does_not_consume_code(tmp_db):
    code = _make_code(tmp_db)
    billing.redeem_code(code=code, user_id=1)  # first burn
    second_code = _make_code(tmp_db, code="ZZZZZZZZZZZZZZZZ")
    with pytest.raises(billing.BillingError) as exc_info:
        billing.redeem_code(code=second_code, user_id=1)
    assert exc_info.value.error_code == "E_ENTITLEMENT_DUPLICATE"
    # AC-03-5: second code MUST stay unused
    row = tmp_db.execute("SELECT status FROM activation_code WHERE code=?", (second_code,)).fetchone()
    assert row["status"] == "unused"


def test_redeem_empty_code_raises_invalid(tmp_db):
    with pytest.raises(billing.BillingError) as exc_info:
        billing.redeem_code(code="   ", user_id=1)
    assert exc_info.value.error_code == "E_CODE_INVALID"


def test_redeem_normalizes_case(tmp_db):
    code = _make_code(tmp_db, code="ABCDEFGHJKMNPQRS")
    ent = billing.redeem_code(code="abcdefghjkmnpqrs", user_id=1)  # lowercase input
    assert ent.user_id == 1


# ── has_entitlement ──

def test_has_entitlement_false_initially(tmp_db):
    assert billing.has_entitlement(1) is False


def test_has_entitlement_true_after_redeem(tmp_db):
    code = _make_code(tmp_db)
    billing.redeem_code(code=code, user_id=1)
    assert billing.has_entitlement(1) is True
    assert billing.has_entitlement(2) is False  # different user


def test_has_entitlement_false_when_expired(tmp_db):
    # Manually insert an expired entitlement
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    tmp_db.execute(
        "INSERT INTO entitlement (user_id, type, granted_at, expires_at, source) "
        "VALUES (1, 'full_analysis', ?, ?, 'test')",
        (yesterday, yesterday),
    )
    tmp_db.commit()
    assert billing.has_entitlement(1) is False


# ── generate_codes (AC-10-3 cap, AC-10-4 validity) ──

def test_generate_codes_creates_n_unique_unused_rows(tmp_db):
    codes = billing.generate_codes(count=5)
    assert len(codes) == 5
    assert len(set(codes)) == 5
    rows = tmp_db.execute(
        "SELECT status FROM activation_code WHERE code IN ({})".format(",".join("?" * 5)),
        codes,
    ).fetchall()
    assert all(r["status"] == "unused" for r in rows)


def test_generate_codes_writes_audit(tmp_db):
    billing.generate_codes(count=3, note="W1 smoke")
    rows = audit.recent(event="admin.bulk_create_payment", conn=tmp_db)
    assert len(rows) == 1


def test_generate_codes_rejects_count_above_1000(tmp_db):
    with pytest.raises(billing.BillingError) as exc_info:
        billing.generate_codes(count=1500)
    assert exc_info.value.error_code == "E_BAD_COUNT"


def test_generate_codes_rejects_zero_or_negative(tmp_db):
    with pytest.raises(billing.BillingError):
        billing.generate_codes(count=0)
    with pytest.raises(billing.BillingError):
        billing.generate_codes(count=-1)


def test_redeem_renews_expired_entitlement(tmp_db):
    # User 1 already holds an EXPIRED full_analysis entitlement. Because the
    # table is UNIQUE(user_id, type), a plain INSERT on renewal would fail; the
    # UPSERT must refresh the existing row instead.
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    tmp_db.execute(
        "INSERT INTO entitlement (user_id, type, granted_at, expires_at, source) "
        "VALUES (1, 'full_analysis', ?, ?, 'old')",
        (past, past),
    )
    tmp_db.commit()
    assert billing.has_entitlement(1) is False  # expired

    code = _make_code(tmp_db, code="RENEW2345EFGH6789", validity_days_after_redeem=30)
    ent = billing.redeem_code(code=code, user_id=1)

    assert ent.type == "full_analysis"
    assert ent.expires_at is not None
    assert ent.expires_at > datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    # exactly one row — renewed in place, not duplicated
    count = tmp_db.execute(
        "SELECT COUNT(*) FROM entitlement WHERE user_id=1 AND type='full_analysis'"
    ).fetchone()[0]
    assert count == 1
    assert billing.has_entitlement(1) is True

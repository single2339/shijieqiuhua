"""Billing service — code generation, redemption, entitlement checks.

Stays small (~150 lines) on purpose. W2 will route callers through here from
FastAPI handlers; W1 just needs the domain logic and tests.

Concurrency model:
- redeem_code uses BEGIN IMMEDIATE so two simultaneous redemptions on the
  same code race-resolve at SQLite level (one wins, other gets E_CODE_USED).
- All three writes (activation_code update, entitlement insert, audit_log)
  share the transaction so a failure mid-flight rolls everything back.

PRD trace: §6.1 schema, §5.6 error codes, UC-03 acceptance criteria.
"""
from __future__ import annotations

import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from backend import audit
from backend.auth.db import get_db

log = logging.getLogger(__name__)

# ── domain ──

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # PRD §6.3: skip 0/O/1/I/L
ACTIVATION_CODE_LEN = 16
DEFAULT_EXPIRES_DAYS = 90


class EntitlementType(str, Enum):
    FULL_ANALYSIS = "full_analysis"


class BillingError(Exception):
    """Domain error with a stable error_code for the API layer to surface."""

    def __init__(self, error_code: str, message: str = "") -> None:
        super().__init__(message or error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class Entitlement:
    id: int
    user_id: int
    type: str
    granted_at: str
    expires_at: str | None
    source: str


# ── helpers ──

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _generate_one_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(ACTIVATION_CODE_LEN))


def _expires_in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# ── operations ──

def generate_codes(
    count: int,
    *,
    expires_days: int = DEFAULT_EXPIRES_DAYS,
    validity_days_after_redeem: int | None = None,
    note: str = "",
    admin_actor: str = "admin",
) -> list[str]:
    """Bulk-create activation codes. Used by admin CLI.

    Returns the generated codes in the order written. Carries an audit row
    'admin.bulk_create_payment'.
    """
    if count <= 0 or count > 1000:
        raise BillingError("E_BAD_COUNT", f"count must be in [1, 1000], got {count}")

    conn = get_db()
    expires_at = _expires_in(expires_days)
    created: list[str] = []
    with conn:  # autocommit on success, rollback on raise
        for _ in range(count):
            for _retry in range(3):  # collision retries
                code = _generate_one_code()
                try:
                    conn.execute(
                        """
                        INSERT INTO activation_code
                          (code, status, expires_at, validity_days_after_redeem, note)
                        VALUES (?, 'unused', ?, ?, ?)
                        """,
                        (code, expires_at, validity_days_after_redeem, note),
                    )
                    created.append(code)
                    break
                except sqlite3.IntegrityError:
                    continue  # collision → retry
            else:
                raise BillingError(
                    "E_CODE_COLLISION",
                    "Failed to generate unique code after 3 retries — alphabet exhausted?",
                )
        audit.write(
            event="admin.bulk_create_payment",
            actor=admin_actor,
            payload={"count": len(created), "expires_days": expires_days, "note": note},
            conn=conn,
        )
    return created


def has_entitlement(
    user_id: int,
    entitlement_type: str = EntitlementType.FULL_ANALYSIS.value,
    *,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """True iff user holds an active (non-expired) entitlement of that type."""
    c = conn or get_db()
    row = c.execute(
        """
        SELECT expires_at FROM entitlement
        WHERE user_id=? AND type=?
        """,
        (user_id, entitlement_type),
    ).fetchone()
    if row is None:
        return False
    expires_at = row["expires_at"] if hasattr(row, "keys") else row[0]
    if not expires_at:
        return True  # NULL = permanent
    return expires_at > _now_iso()


def redeem_code(
    *,
    code: str,
    user_id: int,
    actor_ip: str | None = None,
    actor_ua: str | None = None,
) -> Entitlement:
    """Redeem an activation code for the given user.

    Atomic: status flip + entitlement insert + audit row run inside one
    BEGIN IMMEDIATE transaction. Concurrent attempts on the same code
    serialize on SQLite's reserved lock; the loser sees status='used'.

    Raises BillingError with one of:
      E_CODE_INVALID          — code does not exist
      E_CODE_USED             — already redeemed
      E_CODE_EXPIRED          — past expires_at
      E_ENTITLEMENT_DUPLICATE — user already holds same type; code NOT consumed
    """
    code = code.strip().upper()
    if not code:
        raise BillingError("E_CODE_INVALID", "empty code")

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT code, status, expires_at, validity_days_after_redeem
            FROM activation_code WHERE code=?
            """,
            (code,),
        ).fetchone()
        if row is None:
            raise BillingError("E_CODE_INVALID", "unknown code")
        status = row["status"]
        if status == "used":
            raise BillingError("E_CODE_USED", "code already redeemed")
        if row["expires_at"] <= _now_iso():
            raise BillingError("E_CODE_EXPIRED", "code expired")

        # Refuse to consume a code if user already holds the entitlement.
        # Critical AC-03-5: code must remain unused on this path.
        if has_entitlement(user_id, EntitlementType.FULL_ANALYSIS.value, conn=conn):
            raise BillingError(
                "E_ENTITLEMENT_DUPLICATE",
                "user already holds full_analysis entitlement",
            )

        validity_days = row["validity_days_after_redeem"]
        if validity_days is None:
            entitlement_expires_at = None
        else:
            entitlement_expires_at = _expires_in(validity_days)

        now = _now_iso()
        conn.execute(
            "UPDATE activation_code SET status='used', granted_to_user_id=?, redeemed_at=? WHERE code=?",
            (user_id, now, code),
        )
        # UPSERT: a previously expired entitlement row still exists (UNIQUE on
        # user_id+type), so a plain INSERT would fail. Renew it in place.
        conn.execute(
            """
            INSERT INTO entitlement (user_id, type, granted_at, expires_at, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, type) DO UPDATE SET
                granted_at=excluded.granted_at,
                expires_at=excluded.expires_at,
                source=excluded.source
            """,
            (
                user_id,
                EntitlementType.FULL_ANALYSIS.value,
                now,
                entitlement_expires_at,
                f"code:{code}",
            ),
        )
        entitlement_id = conn.execute(
            "SELECT id FROM entitlement WHERE user_id=? AND type=?",
            (user_id, EntitlementType.FULL_ANALYSIS.value),
        ).fetchone()["id"]
        audit.write(
            event="billing.code_redeemed",
            actor="user",
            user_id=user_id,
            payload={"code_prefix": code[:4], "validity_days": validity_days},
            ip=actor_ip,
            user_agent=actor_ua,
            conn=conn,
        )
        conn.commit()
    except BillingError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        log.exception("redeem_code unexpected failure")
        raise BillingError("E_DB_TRANSIENT", "transient database error")

    return Entitlement(
        id=entitlement_id,
        user_id=user_id,
        type=EntitlementType.FULL_ANALYSIS.value,
        granted_at=now,
        expires_at=entitlement_expires_at,
        source=f"code:{code}",
    )

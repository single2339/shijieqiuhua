"""Admin CLI for v1 ops.

Usage:
    python -m backend.admin invite_codes  --count N [--max-uses 1] [--validity-days 30] [--note "..."] [--output path.csv]
    python -m backend.admin payment_codes --count N [--validity-days 90] [--validity-after-redeem 365] [--note "..."]
    python -m backend.admin list_users    [--paid] [--limit 100]
    python -m backend.admin list_codes    --type invite|payment [--status unused|used] [--limit 100]
    python -m backend.admin set_threshold --key info_insufficient_factor_min --value 1
    python -m backend.admin ban_user      --user-id N --reason "..."

Auth:
    ADMIN_TOKEN must be set in env. Token is checked literally — there is no
    user-tied admin auth in CLI; the assumption (PRD Q26 default) is that
    only operators with shell access to the box can run this. Token serves as
    a typo guard, not as a security boundary on its own.

Audit trail:
    Every state-changing command writes one audit_log row with actor='admin'.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from backend import audit, billing
from backend.auth.db import get_db

log = logging.getLogger("admin")

INVITE_CODE_ALPHABET = string.ascii_uppercase + string.digits  # match auth/admin_routes.py
INVITE_CODE_LEN = 16
MAX_BULK_COUNT = 1000


# ── auth ──

class AdminAuthError(Exception):
    pass


def _check_admin_token() -> None:
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected:
        raise AdminAuthError("ADMIN_TOKEN env var is not set")
    provided = os.getenv("ADMIN_TOKEN_INPUT", "").strip() or expected
    # If ADMIN_TOKEN_INPUT is set (e.g. piped from a wrapper), it must match
    # ADMIN_TOKEN. If absent, we assume the operator who set ADMIN_TOKEN is
    # running directly. This is the threat model from PRD Q26.
    if provided != expected:
        raise AdminAuthError("admin token mismatch")


# ── helpers ──

def _now_iso_seconds() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _expires_in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LEN))


def _write_csv(path: Path, header: Iterable[str], rows: Iterable[Iterable[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(list(header))
        for r in rows:
            writer.writerow(list(r))


# ── commands ──

def cmd_invite_codes(args: argparse.Namespace) -> int:
    if args.count > MAX_BULK_COUNT:
        log.error("count > %d not allowed", MAX_BULK_COUNT)
        return 2
    db = get_db()
    expires_at = _expires_in(args.validity_days)
    created_by = _resolve_admin_user_id(db)
    created: list[str] = []
    with db:
        for _ in range(args.count):
            for _retry in range(3):
                code = _generate_invite_code()
                try:
                    db.execute(
                        """
                        INSERT INTO registration_codes
                          (code, created_by, max_uses, current_uses, is_active, expires_at)
                        VALUES (?, ?, ?, 0, 1, ?)
                        """,
                        (code, created_by, args.max_uses, expires_at),
                    )
                    created.append(code)
                    break
                except Exception:  # noqa: BLE001 — collision retry
                    continue
            else:
                log.error("collision retries exhausted")
                return 3
        audit.write(
            event="admin.bulk_create_invite",
            actor="admin",
            payload={
                "count": len(created),
                "max_uses": args.max_uses,
                "expires_days": args.validity_days,
                "note": args.note,
            },
            conn=db,
        )

    _emit_codes(created, args.output, kind="invite")
    log.info("created %d invite codes (max_uses=%d, validity=%dd)", len(created), args.max_uses, args.validity_days)
    return 0


def cmd_payment_codes(args: argparse.Namespace) -> int:
    try:
        codes = billing.generate_codes(
            count=args.count,
            expires_days=args.validity_days,
            validity_days_after_redeem=args.validity_after_redeem,
            note=args.note,
        )
    except billing.BillingError as exc:
        log.error("billing error: %s — %s", exc.error_code, exc)
        return 4
    _emit_codes(codes, args.output, kind="payment")
    log.info("created %d payment codes (validity=%dd)", len(codes), args.validity_days)
    return 0


def cmd_list_users(args: argparse.Namespace) -> int:
    db = get_db()
    if args.paid:
        rows = db.execute(
            """
            SELECT u.id, u.username, u.email, u.created_at,
                   e.granted_at, e.expires_at
            FROM users u
            JOIN entitlement e ON e.user_id = u.id AND e.type = 'full_analysis'
            ORDER BY e.granted_at DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, username, email, role, is_active, created_at FROM users ORDER BY id DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print("\t".join(str(r[k]) for k in r.keys()))
    return 0


def cmd_list_codes(args: argparse.Namespace) -> int:
    db = get_db()
    if args.type == "invite":
        sql = "SELECT code, max_uses, current_uses, is_active, created_at, expires_at FROM registration_codes"
        params: tuple = ()
        if args.status == "unused":
            sql += " WHERE current_uses = 0 AND is_active = 1"
        elif args.status == "used":
            sql += " WHERE current_uses > 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params = (args.limit,)
    else:  # payment
        sql = "SELECT code, status, expires_at, redeemed_at, granted_to_user_id FROM activation_code"
        if args.status:
            sql += f" WHERE status='{args.status}'"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params = (args.limit,)
    rows = db.execute(sql, params).fetchall()
    for r in rows:
        print("\t".join(str(r[k]) for k in r.keys()))
    return 0


def cmd_set_threshold(args: argparse.Namespace) -> int:
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO system_config (key, value, updated_at, updated_by)
            VALUES (?, ?, ?, 'admin')
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                            updated_at=excluded.updated_at,
                                            updated_by='admin'
            """,
            (args.key, args.value, _now_iso_seconds()),
        )
        audit.write(
            event="admin.set_threshold",
            actor="admin",
            payload={"key": args.key, "value": args.value},
            conn=db,
        )
    log.info("set %s = %s", args.key, args.value)
    return 0


def cmd_ban_user(args: argparse.Namespace) -> int:
    db = get_db()
    with db:
        cur = db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (args.user_id,))
        if cur.rowcount == 0:
            log.error("user_id %d not found", args.user_id)
            return 5
        audit.write(
            event="admin.ban_user",
            actor="admin",
            user_id=args.user_id,
            payload={"reason": args.reason},
            conn=db,
        )
    log.info("banned user %d", args.user_id)
    return 0


# ── helpers ──

def _resolve_admin_user_id(db) -> int:
    """Pick *some* admin user to satisfy the registration_codes.created_by FK.

    PRD Q26 says CLI auth is via ADMIN_TOKEN, not a user account. To keep
    the existing FK happy we use the first admin row; if there is none
    yet, fall back to user_id=1 (which any bootstrap creates).
    """
    row = db.execute(
        "SELECT id FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if row is not None:
        return row["id"]
    row = db.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    return row["id"] if row else 0


def _emit_codes(codes: list[str], output: str | None, *, kind: str) -> None:
    if not codes:
        return
    if output:
        path = Path(output)
        _write_csv(path, ["code", "kind"], ((c, kind) for c in codes))
        log.info("wrote %d codes to %s", len(codes), path)
    else:
        for c in codes:
            print(c)


# ── main ──

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backend.admin", description="ShijieQiuhua admin CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("invite_codes", help="bulk-create registration codes")
    inv.add_argument("--count", type=int, required=True)
    inv.add_argument("--max-uses", type=int, default=1)
    inv.add_argument("--validity-days", type=int, default=30)
    inv.add_argument("--note", type=str, default="")
    inv.add_argument("--output", type=str, default=None, help="CSV path; if absent, print one per line")
    inv.set_defaults(func=cmd_invite_codes)

    pay = sub.add_parser("payment_codes", help="bulk-create activation codes")
    pay.add_argument("--count", type=int, required=True)
    pay.add_argument("--validity-days", type=int, default=90, help="redemption window")
    pay.add_argument(
        "--validity-after-redeem",
        type=int,
        default=None,
        help="entitlement validity after redeem in days; omit for permanent",
    )
    pay.add_argument("--note", type=str, default="")
    pay.add_argument("--output", type=str, default=None)
    pay.set_defaults(func=cmd_payment_codes)

    lu = sub.add_parser("list_users", help="list users")
    lu.add_argument("--paid", action="store_true", help="only users with full_analysis entitlement")
    lu.add_argument("--limit", type=int, default=100)
    lu.add_argument("--json", action="store_true")
    lu.set_defaults(func=cmd_list_users)

    lc = sub.add_parser("list_codes", help="list invite or payment codes")
    lc.add_argument("--type", choices=["invite", "payment"], required=True)
    lc.add_argument("--status", choices=["unused", "used"], default=None)
    lc.add_argument("--limit", type=int, default=100)
    lc.set_defaults(func=cmd_list_codes)

    st = sub.add_parser("set_threshold", help="write to system_config")
    st.add_argument("--key", type=str, required=True)
    st.add_argument("--value", type=str, required=True)
    st.set_defaults(func=cmd_set_threshold)

    bn = sub.add_parser("ban_user", help="set user.is_active=0 and audit")
    bn.add_argument("--user-id", type=int, required=True)
    bn.add_argument("--reason", type=str, required=True)
    bn.set_defaults(func=cmd_ban_user)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _check_admin_token()
    except AdminAuthError as exc:
        log.error("auth: %s", exc)
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

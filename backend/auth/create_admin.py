"""Create initial admin user and invite codes.

Usage:
    python backend/auth/create_admin.py --username admin --password <pwd>
    python backend/auth/create_admin.py --username admin --password <pwd> --codes 5
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.auth.db import get_db
from backend.auth.service import hash_password


def generate_code(length: int = 16) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Create initial admin user")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--codes", type=int, default=5, help="Number of invite codes to generate")
    args = parser.parse_args()

    db = get_db()

    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (args.username,)
    ).fetchone()
    if existing:
        print(f"User '{args.username}' already exists, skipping creation.")
        admin_id = existing["id"]
    else:
        pw_hash = hash_password(args.password)
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
            (args.username, "", pw_hash),
        )
        db.commit()
        admin_id = cursor.lastrowid
        print(f"Admin user '{args.username}' created (id={admin_id}).")

    expires_at = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")
    codes = []
    for _ in range(args.codes):
        code = generate_code()
        db.execute(
            "INSERT INTO registration_codes (code, created_by, max_uses, expires_at) VALUES (?, ?, 1, ?)",
            (code, admin_id, expires_at),
        )
        codes.append(code)
    db.commit()

    print(f"\nGenerated {len(codes)} invite codes (valid 365 days):")
    for c in codes:
        print(f"  {c}")


if __name__ == "__main__":
    main()

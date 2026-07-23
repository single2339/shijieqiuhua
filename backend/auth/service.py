"""Authentication service — password hashing, JWT, user CRUD."""

from __future__ import annotations

import os

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import jwt, JWTError

from backend.auth.db import get_db

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET 环境变量未设置。请设置一个持久化的密钥，避免每次重启后所有用户 token 失效。")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=1)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

# Brute-force protection: lock out an identifier after too many failed
# attempts within a sliding window. The global per-IP rate limiter is the
# coarse defense; this is the per-account one.
LOGIN_LOCKOUT_THRESHOLD = 10
LOGIN_LOCKOUT_WINDOW_MINUTES = 15


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + ACCESS_TOKEN_EXPIRE,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int, ip_address: str = "", user_agent: str = "") -> str:
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    expires_at = now + REFRESH_TOKEN_EXPIRE

    db = get_db()
    db.execute(
        "INSERT INTO sessions (user_id, token_jti, expires_at, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)",
        (user_id, jti, expires_at.strftime("%Y-%m-%dT%H:%M:%S"), ip_address, user_agent),
    )
    db.commit()

    return jwt.encode(
        {"sub": str(user_id), "jti": jti, "iat": now, "exp": expires_at},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def revoke_access_token(token: str) -> None:
    """Persist the revocation of an access token until its natural expiry."""
    payload = decode_token(token)
    if not payload or not payload.get("jti"):
        return
    exp = payload.get("exp")
    if isinstance(exp, datetime):
        expires_at = exp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        try:
            expires_at = datetime.fromtimestamp(float(exp), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError, OSError):
            return
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO revoked_access_tokens (jti, expires_at) VALUES (?, ?)",
        (payload["jti"], expires_at),
    )
    db.commit()


def is_access_token_revoked(jti: str) -> bool:
    if not jti:
        return False
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute("DELETE FROM revoked_access_tokens WHERE expires_at < ?", (now,))
    row = db.execute(
        "SELECT 1 FROM revoked_access_tokens WHERE jti = ?", (jti,)
    ).fetchone()
    db.commit()
    return row is not None


def _reserve_invite_code(db: sqlite3.Connection, code: str) -> bool:
    """Atomically consume one use of an invite code within the caller's
    transaction. The conditional UPDATE serializes concurrent registrations on
    the same code (SQLite allows one writer at a time), closing the TOCTOU gap
    that a separate check-then-increment would leave open. Returns False if the
    code is missing, inactive, exhausted, or expired."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cursor = db.execute(
        "UPDATE registration_codes SET current_uses = current_uses + 1 "
        "WHERE code = ? AND is_active = 1 AND current_uses < max_uses "
        "AND (expires_at = '' OR expires_at >= ?)",
        (code.upper().strip(), now),
    )
    return cursor.rowcount == 1

def _registration_duplicate_error(db: sqlite3.Connection, username: str, email: str) -> str | None:
    if db.execute(
        "SELECT 1 FROM users WHERE normalize_identity(username) = normalize_identity(?) LIMIT 1",
        (username,),
    ).fetchone():
        return "用户名已存在"
    if db.execute(
        "SELECT 1 FROM users WHERE normalize_identity(email) = normalize_identity(?) LIMIT 1",
        (email,),
    ).fetchone():
        return "邮箱已存在"
    return None


def register_user(username: str, email: str, password: str, invite_code: str) -> dict:
    db = get_db()
    username = username.strip()
    email = email.strip()
    if len(username) < 2:
        raise ValueError("用户名长度至少为 2 个字符")
    if not email:
        raise ValueError("邮箱不能为空")

    duplicate_error = _registration_duplicate_error(db, username, email)
    if duplicate_error:
        raise ValueError(duplicate_error)
    password_hash = hash_password(password)

    try:
        # Serialize the final duplicate checks and insertion. SQLite allows one
        # immediate writer, so concurrent registrations cannot both pass the
        # checks before either account is committed.
        db.execute("BEGIN IMMEDIATE")
        duplicate_error = _registration_duplicate_error(db, username, email)
        if duplicate_error:
            raise ValueError(duplicate_error)
        # Reserve the invite code only after identity checks. Any later failure
        # rolls back this reservation with the user insert.
        if not _reserve_invite_code(db, invite_code):
            raise ValueError("邀请码无效、已使用或已过期")
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise ValueError("用户名已存在")
    except Exception:
        db.rollback()
        raise
    user_id = cursor.lastrowid
    return _user_row_to_dict(
        db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    )


def login_user(username: str, password: str, ip_address: str = "", user_agent: str = "") -> dict:
    db = get_db()
    recent_failures = db.execute(
        "SELECT COUNT(*) FROM login_attempts "
        "WHERE identifier = ? AND success = 0 AND created_at >= datetime('now', ?)",
        (username, f"-{LOGIN_LOCKOUT_WINDOW_MINUTES} minutes"),
    ).fetchone()[0]
    if recent_failures >= LOGIN_LOCKOUT_THRESHOLD:
        raise ValueError("登录失败次数过多，请稍后再试")
    db.execute(
        "INSERT INTO login_attempts (identifier, ip_address, success) VALUES (?, ?, 0)",
        (username, ip_address),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise ValueError("用户名或密码错误")
    if not row["is_active"]:
        raise ValueError("账号已被禁用")
    if not verify_password(password, row["password_hash"]):
        raise ValueError("用户名或密码错误")
    db.execute(
        "UPDATE login_attempts SET success = 1 WHERE id = (SELECT MAX(id) FROM login_attempts WHERE identifier = ?)",
        (username,),
    )
    db.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],))
    db.commit()
    user_dict = _user_row_to_dict(row)
    access_token = create_access_token(row["id"], row["role"])
    refresh_token = create_refresh_token(row["id"], ip_address, user_agent)
    return {"user": user_dict, "access_token": access_token, "refresh_token": refresh_token}


def refresh_access_token(refresh_token_str: str, ip_address: str = "", user_agent: str = "") -> dict:
    payload = decode_token(refresh_token_str)
    if payload is None:
        raise ValueError("无效的 refresh token")
    jti = payload.get("jti")
    user_id = int(payload.get("sub", 0))
    db = get_db()
    session = db.execute(
        "SELECT * FROM sessions WHERE token_jti = ? AND user_id = ?",
        (jti, user_id),
    ).fetchone()
    if session is None:
        raise ValueError("会话已失效")
    db.execute("DELETE FROM sessions WHERE token_jti = ?", (jti,))
    db.commit()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None or not user["is_active"]:
        raise ValueError("用户不存在或已禁用")
    access_token = create_access_token(user_id, user["role"])
    new_refresh_token = create_refresh_token(user_id, ip_address, user_agent)
    return {"access_token": access_token, "refresh_token": new_refresh_token}


def logout_user(refresh_token_str: str) -> None:
    payload = decode_token(refresh_token_str)
    if payload is None:
        return
    jti = payload.get("jti")
    db = get_db()
    db.execute("DELETE FROM sessions WHERE token_jti = ?", (jti,))
    db.commit()


def get_user_by_id(user_id: int) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return _user_row_to_dict(row)


def change_password(user_id: int, old_password: str, new_password: str) -> None:
    """User self-service password change. Verifies old password first."""
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("用户不存在")
    if not verify_password(old_password, row["password_hash"]):
        raise ValueError("原密码错误")
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id),
    )
    db.commit()


def admin_reset_password(user_id: int, new_password: str) -> str:
    """Admin resets a user's password. Returns the new password."""
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("用户不存在")
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id),
    )
    db.commit()
    return new_password


def _user_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }

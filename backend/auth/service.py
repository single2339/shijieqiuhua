"""Authentication service — password hashing, JWT, user CRUD."""

from __future__ import annotations

import os
import re

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


# bcrypt only consumes the first 72 bytes and raises on longer inputs in newer
# versions. Truncate consistently in both hash + verify (back-compatible, since
# bytes beyond 72 were already ignored).
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode()[:_BCRYPT_MAX_BYTES], _bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], password_hash.encode())


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


def verify_invite_code(code: str) -> bool:
    db = get_db()
    row = db.execute(
        "SELECT * FROM registration_codes WHERE code = ? AND is_active = 1",
        (code.upper().strip(),),
    ).fetchone()
    if row is None:
        return False
    if row["current_uses"] >= row["max_uses"]:
        return False
    if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"):
        return False
    return True


def consume_invite_code(code: str, user_id: int) -> None:
    db = get_db()
    db.execute(
        "UPDATE registration_codes SET current_uses = current_uses + 1 WHERE code = ?",
        (code.upper().strip(),),
    )
    db.commit()


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register_user(username: str, email: str, password: str, invite_code: str) -> dict:
    if email and not EMAIL_RE.match(email):
        raise ValueError("邮箱格式不正确")
    db = get_db()
    user_id = 0
    with db:  # commits on success, rolls back on any exception
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise ValueError("用户名已存在")
        code = invite_code.upper().strip()
        row = db.execute(
            "SELECT * FROM registration_codes WHERE code = ? AND is_active = 1", (code,),
        ).fetchone()
        if row is None:
            raise ValueError("邀请码无效、已使用或已过期")
        if row["current_uses"] >= row["max_uses"]:
            raise ValueError("邀请码无效、已使用或已过期")
        if row["expires_at"]:
            expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                raise ValueError("邀请码无效、已使用或已过期")
        password_hash = hash_password(password)
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        user_id = cursor.lastrowid
        updated = db.execute(
            "UPDATE registration_codes SET current_uses = current_uses + 1 "
            "WHERE code = ? AND is_active = 1 AND current_uses < max_uses",
            (code,),
        )
        if updated.rowcount != 1:
            raise ValueError("邀请码无效、已使用或已过期")
    return _user_row_to_dict(
        db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    )


def login_user(username: str, password: str, ip_address: str = "", user_agent: str = "") -> dict:
    db = get_db()
    failures = db.execute(
        """
        SELECT COUNT(*) AS n
        FROM login_attempts
        WHERE identifier = ? AND success = 0 AND created_at >= datetime('now', '-15 minutes')
        """,
        (username,),
    ).fetchone()["n"]
    if failures >= 5:
        raise ValueError("登录失败次数过多，请稍后再试")
    cur = db.execute(
        "INSERT INTO login_attempts (identifier, ip_address, success) VALUES (?, ?, 0)",
        (username, ip_address),
    )
    attempt_id = cur.lastrowid
    db.commit()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise ValueError("用户名或密码错误")
    if not row["is_active"]:
        raise ValueError("账号已被禁用")
    if not verify_password(password, row["password_hash"]):
        raise ValueError("用户名或密码错误")
    db.execute(
        "UPDATE login_attempts SET success = 1 WHERE id = ?", (attempt_id,),
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

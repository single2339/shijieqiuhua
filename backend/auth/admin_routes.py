"""Admin API routes — user management, invite codes, statistics."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException

from backend.auth.db import get_db
from backend.auth import service
from backend.auth.models import (
    AdminUserUpdate,
    AdminResetPasswordRequest,
    AdminUserDetail,
    AdminStats,
    InviteCodeCreate,
    InviteCodeInfo,
)
from backend.auth.routes import require_admin

router = APIRouter(tags=["admin"])


def _generate_code(length: int = 16) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _other_active_admin_exists(db, exclude_user_id: int) -> bool:
    """True if at least one *other* enabled admin remains besides exclude_user_id."""
    row = db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
        (exclude_user_id,),
    ).fetchone()
    return row[0] > 0


@router.get("/users")
def list_users(request: Request, page: int = 1, page_size: int = 20):
    require_admin(request)
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    db = get_db()
    offset = (page - 1) * page_size
    total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    rows = db.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM user_activities a WHERE a.user_id = u.id) as activity_count "
        "FROM users u ORDER BY u.created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()

    users = []
    for r in rows:
        users.append({
            "id": r["id"],
            "username": r["username"],
            "email": r["email"],
            "role": r["role"],
            "is_active": bool(r["is_active"]),
            "created_at": r["created_at"],
            "last_login_at": r["last_login_at"],
            "action_count": r["activity_count"],
        })
    return {"users": users, "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(user_id: int, request: Request):
    require_admin(request)
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    total = db.execute(
        "SELECT COUNT(*) FROM user_activities WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    recent = db.execute(
        "SELECT action_type, details_json, ip_address, created_at "
        "FROM user_activities WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (user_id,),
    ).fetchall()

    return AdminUserDetail(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_active=bool(user["is_active"]),
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
        action_count=total,
        recent_actions=[dict(r) for r in recent],
    )


@router.put("/users/{user_id}")
def update_user(user_id: int, body: AdminUserUpdate, request: Request):
    admin = require_admin(request)
    if body.role is not None and body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="无效的角色")

    if body.is_active is None and body.role is None:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user["id"] == admin["id"] and body.is_active is False:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    # Don't let the last enabled admin be demoted or disabled — that would lock
    # everyone out of the admin panel with no in-app recovery.
    removes_admin = (
        user["role"] == "admin" and bool(user["is_active"])
        and (body.role == "user" or body.is_active is False)
    )
    if removes_admin and not _other_active_admin_exists(db, user["id"]):
        raise HTTPException(status_code=400, detail="必须至少保留一个启用的管理员")

    updates: list[str] = []
    params: list = []
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if body.is_active else 0)
    if body.role is not None:
        updates.append("role = ?")
        params.append(body.role)

    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    return {"detail": "更新成功"}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, body: AdminResetPasswordRequest, request: Request):
    """Admin resets a user's password."""
    require_admin(request)
    try:
        service.admin_reset_password(user_id, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"detail": "密码已重置"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request):
    admin = require_admin(request)
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if (
        user["role"] == "admin" and bool(user["is_active"])
        and not _other_active_admin_exists(db, user["id"])
    ):
        raise HTTPException(status_code=400, detail="必须至少保留一个启用的管理员")

    db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    db.commit()
    return {"detail": "用户已禁用"}


@router.post("/invite-codes")
def create_invite_codes(body: InviteCodeCreate, request: Request):
    admin = require_admin(request)
    db = get_db()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=body.expires_days)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    codes = []
    for _ in range(body.count):
        code = _generate_code()
        db.execute(
            "INSERT INTO registration_codes (code, created_by, max_uses, expires_at) VALUES (?, ?, ?, ?)",
            (code, admin["id"], body.max_uses, expires_at),
        )
        codes.append(code)
    db.commit()

    return {"codes": codes, "expires_at": expires_at}


@router.get("/invite-codes", response_model=list[InviteCodeInfo])
def list_invite_codes(request: Request):
    require_admin(request)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM registration_codes ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    return [
        InviteCodeInfo(
            id=r["id"],
            code=r["code"],
            created_by=r["created_by"],
            max_uses=r["max_uses"],
            current_uses=r["current_uses"],
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            expires_at=r["expires_at"],
        )
        for r in rows
    ]


@router.put("/invite-codes/{code_id}")
def toggle_invite_code(code_id: int, request: Request):
    require_admin(request)
    db = get_db()
    row = db.execute(
        "SELECT * FROM registration_codes WHERE id = ?", (code_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    new_status = 0 if row["is_active"] else 1
    db.execute("UPDATE registration_codes SET is_active = ? WHERE id = ?", (new_status, code_id))
    db.commit()
    return {"detail": "已启用" if new_status else "已禁用"}


@router.get("/stats", response_model=AdminStats)
def admin_stats(request: Request):
    require_admin(request)
    db = get_db()

    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_7d = db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM user_activities WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    active_30d = db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM user_activities WHERE created_at >= datetime('now', '-30 days')"
    ).fetchone()[0]
    today_logins = db.execute(
        "SELECT COUNT(*) FROM user_activities "
        "WHERE action_type = 'login' AND DATE(created_at) = DATE('now')"
    ).fetchone()[0]
    today_actions = db.execute(
        "SELECT COUNT(*) FROM user_activities WHERE DATE(created_at) = DATE('now')"
    ).fetchone()[0]

    daily_logins = [
        dict(r)
        for r in db.execute(
            "SELECT DATE(created_at) as date, COUNT(*) as count "
            "FROM user_activities WHERE action_type = 'login' "
            "AND created_at >= datetime('now', '-30 days') "
            "GROUP BY DATE(created_at) ORDER BY date"
        ).fetchall()
    ]

    daily_actions = [
        dict(r)
        for r in db.execute(
            "SELECT DATE(created_at) as date, action_type, COUNT(*) as count "
            "FROM user_activities WHERE created_at >= datetime('now', '-30 days') "
            "GROUP BY DATE(created_at), action_type ORDER BY date"
        ).fetchall()
    ]

    top_users = [
        dict(r)
        for r in db.execute(
            "SELECT u.username, COUNT(a.id) as action_count "
            "FROM user_activities a JOIN users u ON a.user_id = u.id "
            "WHERE a.created_at >= datetime('now', '-30 days') "
            "GROUP BY a.user_id ORDER BY action_count DESC LIMIT 10"
        ).fetchall()
    ]

    total_codes = db.execute("SELECT COUNT(*) FROM registration_codes").fetchone()[0]
    used_codes = db.execute(
        "SELECT COUNT(*) FROM registration_codes WHERE current_uses > 0"
    ).fetchone()[0]

    return AdminStats(
        total_users=total_users,
        active_7d=active_7d,
        active_30d=active_30d,
        today_logins=today_logins,
        today_actions=today_actions,
        daily_logins=daily_logins,
        daily_actions=daily_actions,
        top_users=top_users,
        invite_code_usage={"total": total_codes, "used": used_codes},
    )

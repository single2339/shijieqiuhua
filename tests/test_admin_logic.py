"""Regression tests for admin-module logic fixes.

Covers: activity tracking no longer crashes on unknown action types, the
last-admin guard helper, and the AdminStats/AdminUserDetail field contract.
"""

from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("JWT_SECRET", "test-secret")  # admin_routes → auth.service needs it

from backend.auth.admin_routes import _other_active_admin_exists
from backend.auth.models import AdminStats, AdminUserDetail
from backend.auth.tracking import ACTION_TYPES, record_activity


# ── activity tracking must never break the request flow ──

def test_record_activity_skips_unknown_type_without_raising():
    # Previously raised ValueError → crashed the calling endpoint.
    record_activity(1, "totally_unknown_type", {})


def test_build_embedding_index_is_a_known_action():
    assert "build_embedding_index" in ACTION_TYPES


# ── last-admin guard ──

def _users_db(rows: list[tuple[int, str, int]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT, is_active INT)")
    conn.executemany("INSERT INTO users (id, role, is_active) VALUES (?, ?, ?)", rows)
    return conn


def test_other_active_admin_exists_when_a_second_admin_is_enabled():
    db = _users_db([(1, "admin", 1), (2, "admin", 1)])
    assert _other_active_admin_exists(db, exclude_user_id=1) is True


def test_no_other_active_admin_when_the_rest_are_disabled_or_users():
    db = _users_db([(1, "admin", 1), (2, "admin", 0), (3, "user", 1)])
    assert _other_active_admin_exists(db, exclude_user_id=1) is False


# ── stats / detail field contract (matches the frontend) ──

def test_admin_stats_accepts_today_counts_and_dict_usage():
    s = AdminStats(
        total_users=1, active_7d=1, active_30d=1, today_logins=2, today_actions=5,
        daily_logins=[], daily_actions=[],
        top_users=[{"username": "a", "action_count": 3}],
        invite_code_usage={"total": 1, "used": 0},
    )
    assert s.today_logins == 2 and s.today_actions == 5


def test_admin_user_detail_uses_action_count():
    d = AdminUserDetail(
        id=1, username="a", email="", role="admin", is_active=True,
        created_at="", last_login_at="", action_count=7, recent_actions=[],
    )
    assert d.action_count == 7

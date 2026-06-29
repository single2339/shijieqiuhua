from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app_football import app
from backend.auth import db as auth_db
from backend.auth import service


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    storage = tmp_path / "bronze_storage"
    storage.mkdir(parents=True)
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    conn = auth_db.get_db()
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        (1, "tester", "tester@example.com", service.hash_password("correct-password"), "user"),
    )
    conn.commit()
    yield conn
    auth_db.close_db()


def test_login_uses_real_login_attempt_schema_and_sets_http_only_cookies(tmp_db):
    res = TestClient(app).post(
        "/api/auth/login",
        json={"username": "tester", "password": "correct-password"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["user"]["username"] == "tester"
    assert "access_token" not in body
    assert "refresh_token" not in body
    set_cookie = res.headers.get("set-cookie", "")
    assert "osint_access_token=" in set_cookie
    assert "osint_refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_login_rate_limit_counts_created_at_failures(tmp_db):
    for _ in range(5):
        tmp_db.execute(
            "INSERT INTO login_attempts (identifier, ip_address, success) VALUES (?, ?, 0)",
            ("tester", "127.0.0.1"),
        )
    tmp_db.commit()

    with pytest.raises(ValueError, match="登录失败次数过多"):
        service.login_user("tester", "correct-password", "127.0.0.1", "pytest")

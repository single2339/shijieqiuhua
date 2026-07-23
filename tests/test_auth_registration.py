"""Registration identity regression tests."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "auth-registration-test-secret")

from backend.auth import db as auth_db
from backend.auth import routes as auth_routes
from backend.auth import service


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[tuple[TestClient, sqlite3.Connection]]:
    auth_db.close_db()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(auth_db, "DB_PATH", tmp_path / "_auth.db")
    monkeypatch.setattr(auth_routes, "record_activity", lambda *_args, **_kwargs: None)

    database = auth_db.get_db()
    database.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        ("inviter", "", service.hash_password("inviter-password")),
    )
    database.execute(
        "INSERT INTO registration_codes (code, created_by, max_uses) VALUES (?, ?, ?)",
        ("TEST-INVITE", 1, 3),
    )
    database.commit()

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/api/auth")
    with TestClient(app) as client:
        yield client, database

    auth_db.close_db()


def _register(client: TestClient, username: str, email: str):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "correct-password",
            "invite_code": "TEST-INVITE",
        },
    )


def test_register_rejects_existing_username_ignoring_case_and_outer_whitespace(auth_client):
    client, database = auth_client
    assert _register(client, " Analyst ", " first@example.test ").status_code == 200
    stored_user = database.execute(
        "SELECT username, email FROM users WHERE username = ?",
        ("Analyst",),
    ).fetchone()
    assert tuple(stored_user) == ("Analyst", "first@example.test")

    response = _register(client, " analyst ", "second@example.test")

    assert response.status_code == 400
    assert response.json()["detail"] == "用户名已存在"
    assert database.execute(
        "SELECT current_uses FROM registration_codes WHERE code = ?",
        ("TEST-INVITE",),
    ).fetchone()[0] == 1


def test_register_rejects_existing_email_without_consuming_invite(auth_client):
    client, database = auth_client
    assert _register(client, "first-user", "Analyst@Example.Test").status_code == 200

    response = _register(client, "second-user", " analyst@example.test ")

    assert response.status_code == 400
    assert response.json()["detail"] == "邮箱已存在"
    assert database.execute("SELECT current_uses FROM registration_codes WHERE code = ?", ("TEST-INVITE",)).fetchone()[0] == 1

def test_register_rejects_username_that_is_empty_after_trimming(auth_client):
    client, _ = auth_client

    response = _register(client, "  ", "user@example.test")

    assert response.status_code == 400
    assert response.json()["detail"] == "用户名长度至少为 2 个字符"

def test_register_rejects_email_that_is_empty_after_trimming(auth_client):
    client, _ = auth_client

    response = _register(client, "new-user", " ")

    assert response.status_code == 400
    assert response.json()["detail"] == "邮箱不能为空"

@pytest.mark.parametrize(
    ("stored_username", "stored_email", "username", "email", "expected_detail"),
    [
        (
            "\tLegacyUser\n",
            "legacy-user@example.test",
            "legacyuser",
            "new@example.test",
            "用户名已存在",
        ),
        (
            "legacy-user",
            "\tlegacy-email@example.test\n",
            "new-user",
            "legacy-email@example.test",
            "邮箱已存在",
        ),
        (
            "\u00a0UnicodeUser\u00a0",
            "unicode-user@example.test",
            "unicodeuser",
            "new@example.test",
            "用户名已存在",
        ),
        (
            "legacy-user",
            "\u00a0unicode-email@example.test\u00a0",
            "new-user",
            "unicode-email@example.test",
            "邮箱已存在",
        ),
        (
            "CleanUser",
            "clean-user@example.test",
            "\u00a0cleanuser\u00a0",
            "new@example.test",
            "用户名已存在",
        ),
        (
            "legacy-user",
            "clean-email@example.test",
            "new-user",
            "\u00a0clean-email@example.test\u00a0",
            "邮箱已存在",
        ),
        (
            "Straße",
            "street@example.test",
            "STRASSE",
            "new@example.test",
            "用户名已存在",
        ),
    ],
)
def test_register_rejects_legacy_whitespace_padded_identity(
    auth_client,
    stored_username,
    stored_email,
    username,
    email,
    expected_detail,
):
    client, database = auth_client
    database.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (stored_username, stored_email, service.hash_password("legacy-password")),
    )
    database.commit()

    response = _register(client, username, email)

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail
    assert database.execute(
        "SELECT current_uses FROM registration_codes WHERE code = ?",
        ("TEST-INVITE",),
    ).fetchone()[0] == 0

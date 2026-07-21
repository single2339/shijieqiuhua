from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "security-regression-test-secret")

from fastapi import Request
from starlette.testclient import TestClient

from backend.auth import routes as auth_routes
from backend.auth import service


def _request(headers: list[tuple[bytes, bytes]], cookies: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
    }
    request = Request(scope)
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items()).encode()
        scope["headers"].append((b"cookie", cookie_header))
        request = Request(scope)
    return request


def test_authorization_header_takes_precedence_over_stale_access_cookie():
    request = _request(
        [(b"authorization", b"Bearer fresh-header")],
        {"osint_access_token": "expired-cookie"},
    )

    assert auth_routes._extract_token(request) == "fresh-header"


def test_revoked_access_token_is_rejected(monkeypatch, tmp_path):
    import backend.auth.db as auth_db

    monkeypatch.setattr(auth_db, "STORAGE_ROOT", tmp_path)
    auth_db.close_db()
    token = service.create_access_token(42, "user")
    payload = service.decode_token(token)
    assert payload is not None

    service.revoke_access_token(token)

    assert service.is_access_token_revoked(payload["jti"]) is True
    auth_db.close_db()

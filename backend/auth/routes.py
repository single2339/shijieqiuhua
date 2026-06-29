"""Authentication API routes — register, login, refresh, logout, me."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.auth.models import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    LoginResponse,
    TokenResponse,
    UserInfo,
)
from backend.auth import service
from backend.auth.tracking import record_activity

router = APIRouter(tags=["auth"])

_ACCESS_COOKIE = "osint_access_token"
_REFRESH_COOKIE = "osint_refresh_token"
_COOKIE_SAMESITE = "lax"
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").lower() not in {"0", "false", "no"}
_TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0").lower() in {"1", "true", "yes"}


def _set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str):
    response.set_cookie(
        _ACCESS_COOKIE, access_token,
        httponly=True, secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE,
        max_age=3600, path="/",
    )
    response.set_cookie(
        _REFRESH_COOKIE, refresh_token,
        httponly=True, secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE,
        max_age=7 * 24 * 3600, path="/",
    )


def _clear_auth_cookies(response: JSONResponse):
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/")


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get(_ACCESS_COOKIE)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    payload = service.decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")

    user_id = int(payload.get("sub", 0))
    user = service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="账号已被禁用")

    return user


def require_admin(request: Request) -> dict:
    user = get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def _get_entitlements(user_id: int) -> list[dict]:
    from backend.auth.db import get_db
    rows = get_db().execute(
        "SELECT type, granted_at, expires_at FROM entitlement WHERE user_id=?", (user_id,),
    ).fetchall()
    return [{"type": r["type"], "granted_at": r["granted_at"], "expires_at": r["expires_at"]} for r in rows]


def _get_client_ip(request: Request) -> str:
    if _TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/register")
def register(body: RegisterRequest, request: Request):
    try:
        user = service.register_user(body.username, body.email, body.password, body.invite_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    access_token = service.create_access_token(user["id"], user["role"])
    refresh_token = service.create_refresh_token(user["id"], ip, ua)
    record_activity(user["id"], "login", ip_address=ip)
    _ents = _get_entitlements(user["id"])
    resp = JSONResponse({"user": {**UserInfo(**user).model_dump(), "entitlements": _ents}})
    _set_auth_cookies(resp, access_token, refresh_token)
    return resp


@router.post("/login")
def login(body: LoginRequest, request: Request):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    try:
        result = service.login_user(body.username, body.password, ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    record_activity(result["user"]["id"], "login", ip_address=ip)
    _ents = _get_entitlements(result["user"]["id"])
    resp = JSONResponse({"user": {**UserInfo(**result["user"]).model_dump(), "entitlements": _ents}})
    _set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    return resp


@router.post("/refresh")
def refresh(request: Request, body: RefreshRequest | None = None):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    refresh_token = body.refresh_token if body and body.refresh_token else request.cookies.get(_REFRESH_COOKIE, "")
    try:
        result = service.refresh_access_token(refresh_token, ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    resp = JSONResponse({"detail": "refreshed"})
    _set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    return resp


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        service.logout_user(token)
    resp = JSONResponse({"detail": "已退出登录"})
    _clear_auth_cookies(resp)
    return resp


@router.get("/me")
def me(request: Request):
    user = get_current_user(request)
    entitlements = _get_entitlements(user["id"])
    return {**UserInfo(**user).model_dump(), "entitlements": entitlements}

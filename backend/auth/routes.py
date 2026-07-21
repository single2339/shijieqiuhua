"""Authentication API routes — register, login, refresh, logout, me."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.auth.models import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    ChangePasswordRequest,
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


def _cookie_secure() -> bool:
    configured = os.getenv("COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    environment = os.getenv("ENVIRONMENT", "production").strip().lower()
    return environment not in {"development", "dev", "test", "testing", "local"}


def _set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str):
    response.set_cookie(
        _ACCESS_COOKIE, access_token,
        httponly=True, secure=_cookie_secure(), samesite=_COOKIE_SAMESITE,
        max_age=3600, path="/",
    )
    response.set_cookie(
        _REFRESH_COOKIE, refresh_token,
        httponly=True, secure=_cookie_secure(), samesite=_COOKIE_SAMESITE,
        max_age=7 * 24 * 3600, path="/",
    )


def _clear_auth_cookies(response: JSONResponse):
    # Both cookies are set with path="/" (see _set_auth_cookies); deletion must
    # use the same path or the browser keeps the cookie.
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/")


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    return request.cookies.get(_ACCESS_COOKIE)


def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    payload = service.decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
    if service.is_access_token_revoked(payload.get("jti", "")):
        raise HTTPException(status_code=401, detail="认证令牌已撤销")

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


def _get_client_ip(request: Request) -> str:
    # nginx sets X-Real-IP to $remote_addr (the real peer), overwriting any
    # client-supplied value, so it's trustworthy. X-Forwarded-For prepends
    # client-supplied entries and is spoofable — don't read the client's IP
    # from it.
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
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
    resp = JSONResponse(
        LoginResponse(user=UserInfo(**user), access_token=access_token, refresh_token=refresh_token).model_dump()
    )
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
    resp = JSONResponse(
        LoginResponse(
            user=UserInfo(**result["user"]),
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        ).model_dump()
    )
    _set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    return resp


@router.post("/refresh")
def refresh(body: RefreshRequest, request: Request):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    try:
        result = service.refresh_access_token(body.refresh_token, ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    resp = JSONResponse(TokenResponse(**result).model_dump())
    _set_auth_cookies(resp, result["access_token"], result["refresh_token"])
    return resp


@router.post("/logout")
def logout(request: Request):
    access_token = _extract_token(request)
    if access_token:
        service.revoke_access_token(access_token)
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        service.logout_user(token)
    resp = JSONResponse({"detail": "已退出登录"})
    _clear_auth_cookies(resp)
    return resp


@router.get("/me", response_model=UserInfo)
def me(request: Request):
    user = get_current_user(request)
    return UserInfo(**user)


@router.post("/me/change-password")
def change_password(body: ChangePasswordRequest, request: Request):
    """User self-service password change."""
    user = get_current_user(request)
    try:
        service.change_password(user["id"], body.old_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    record_activity(user["id"], "change_password", ip_address=_get_client_ip(request))
    return {"detail": "密码已修改"}

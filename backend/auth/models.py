"""Pydantic models for authentication and user management."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(default="")
    password: str = Field(..., min_length=6, max_length=128)
    invite_code: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str


class LoginResponse(BaseModel):
    user: UserInfo
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class InviteCodeCreate(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
    max_uses: int = Field(default=1, ge=1, le=100)
    expires_days: int = Field(default=30, ge=1, le=365)


class InviteCodeInfo(BaseModel):
    id: int
    code: str
    created_by: int
    max_uses: int
    current_uses: int
    is_active: bool
    created_at: str
    expires_at: str


class AdminStats(BaseModel):
    total_users: int
    active_7d: int
    active_30d: int
    today_logins: int
    today_actions: int
    daily_logins: list[dict]
    daily_actions: list[dict]
    top_users: list[dict]
    invite_code_usage: dict


class AdminUserDetail(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str
    action_count: int
    recent_actions: list[dict]

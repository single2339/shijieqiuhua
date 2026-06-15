"""Billing API routes — activation code redemption."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth.routes import get_current_user
from backend.billing import BillingError, redeem_code

router = APIRouter(prefix="/api/billing", tags=["billing"])


class RedeemRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=32)


class RedeemResponse(BaseModel):
    type: str
    granted_at: str
    expires_at: str | None
    source: str


_STATUS: dict[str, int] = {
    "E_CODE_INVALID": 404,
    "E_CODE_USED": 409,
    "E_CODE_EXPIRED": 410,
    "E_ENTITLEMENT_DUPLICATE": 409,
}

_MESSAGE_ZH: dict[str, str] = {
    "E_CODE_INVALID": "付费码无效，请检查后重新输入",
    "E_CODE_USED": "该付费码已被使用",
    "E_CODE_EXPIRED": "该付费码已过期",
    "E_ENTITLEMENT_DUPLICATE": "你已开通完整功能，无需重复兑换",
    "E_DB_TRANSIENT": "服务繁忙，请稍后重试",
}


# Sync def → FastAPI runs it in a threadpool, so the blocking SQLite
# BEGIN IMMEDIATE transaction never stalls the async event loop.
@router.post("/redeem", response_model=RedeemResponse)
def redeem(req: RedeemRequest, request: Request):
    user = get_current_user(request)
    try:
        ent = redeem_code(
            code=req.code,
            user_id=user["id"],
            actor_ip=request.client.host if request.client else None,
            actor_ua=request.headers.get("user-agent", ""),
        )
    except BillingError as exc:
        raise HTTPException(
            status_code=_STATUS.get(exc.error_code, 500),
            detail={
                "error_code": exc.error_code,
                "message_zh": _MESSAGE_ZH.get(exc.error_code, "兑换失败，请稍后重试"),
            },
        )
    return RedeemResponse(
        type=ent.type,
        granted_at=ent.granted_at,
        expires_at=ent.expires_at,
        source=ent.source,
    )

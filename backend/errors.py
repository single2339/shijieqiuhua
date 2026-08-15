"""Centralized error codes — PRD §5.6 / RQ-H-7."""
from __future__ import annotations

CODES: dict[str, str] = {
    "E_INVITE_INVALID":       "邀请码无效",
    "E_INVITE_USED":          "邀请码已使用，请联系邀请人",
    "E_INVITE_EXPIRED":       "邀请码已过期",
    "E_AUTH_FAILED":          "用户名或密码错误",
    "E_AUTH_LOCKED":          "登录尝试过多，请15分钟后重试",
    "E_OTP_INVALID":          "验证码错误",
    "E_OTP_EXPIRED":          "验证码已过期，请重新获取",
    "E_EMAIL_TAKEN":          "该邮箱已注册，请直接登录",
    "E_FORBIDDEN":            "权限不足",
    "E_CODE_INVALID":         "付费码无效",
    "E_CODE_USED":            "付费码已被使用",
    "E_CODE_EXPIRED":         "付费码已过期",
    "E_ENTITLEMENT_DUPLICATE": "您已开通完整功能，无需重复兑换",
    "E_QUOTA_EXCEEDED":       "本月邀请配额已用完",
    "E_DB_TRANSIENT":         "系统繁忙，请稍后重试",
    "E_LLM_DOWN":             "AI 服务暂不可用，已切换为基础分析",
    "E_BAD_COUNT":            "数量超出允许范围",
    "E_CODE_COLLISION":       "生成失败，请重试",
}

def zh(error_code: str) -> str:
    return CODES.get(error_code, error_code)

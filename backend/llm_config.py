"""Shared LLM configuration and httpx client factory.

Centralizes API key, base URL, model, and timeout settings so they
are defined in exactly one place.
"""

from __future__ import annotations

import os

import httpx

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
PROXY_URL = os.environ.get("PROXY_URL", "")

DEFAULT_TIMEOUT = 300
CLASSIFY_TIMEOUT = 30


def _build_client_kwargs(timeout: int) -> dict:
    kwargs = {
        "timeout": timeout,
        "headers": {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    }
    if PROXY_URL:
        kwargs["proxy"] = PROXY_URL
    return kwargs


def get_plain_http_client(timeout: float = 30.0, *, follow_redirects: bool = True) -> httpx.AsyncClient:
    """Create a client for non-LLM HTTP APIs without LLM credentials."""
    kwargs: dict = {
        "timeout": timeout,
        "follow_redirects": follow_redirects,
        "headers": {"User-Agent": "osint-network/1.0"},
    }
    if PROXY_URL:
        kwargs["proxy"] = PROXY_URL
    return httpx.AsyncClient(**kwargs)


def get_llm_client(timeout: int = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    """Return a NEW httpx.AsyncClient for LLM API calls.

    Always creates a fresh client — no singleton caching — to prevent
    stale connection-pool corruption over long-running processes.
    Callers should use ``async with`` to ensure proper cleanup.
    """
    return httpx.AsyncClient(**_build_client_kwargs(timeout))

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

DEFAULT_TIMEOUT = 120
CLASSIFY_TIMEOUT = 30


def create_llm_client(timeout: int = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    """Return a new httpx.AsyncClient configured for LLM API calls."""
    return httpx.AsyncClient(
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )

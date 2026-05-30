"""Shared async translation module — LLM (DeepSeek) + MyMemory fallback."""

from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx

from backend.llm_config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, get_llm_client

log = logging.getLogger(__name__)

CHINESE_CHAR_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")
CHINESE_THRESHOLD = 0.3

MAX_TEXT_LENGTH = 4000
MAX_RETRIES = 3

MYMEMORY_EMAIL = os.environ.get("MYMEMORY_EMAIL", "backfill@osint-network.local")

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the following text to "
    "Simplified Chinese. Return ONLY the translation, no notes, no "
    "explanations. Preserve the original formatting (line breaks, "
    "paragraphs) as much as possible."
)


def is_chinese(text: str) -> bool:
    """Return True if `text` is predominantly Chinese characters."""
    if not text or not text.strip():
        return False
    chinese_chars = CHINESE_CHAR_RE.findall(text)
    if not chinese_chars:
        return False
    meaningful = sum(1 for c in text if c.isalpha() or CHINESE_CHAR_RE.match(c))
    if meaningful == 0:
        return False
    return len(chinese_chars) / meaningful >= CHINESE_THRESHOLD


async def translate_with_llm(text: str) -> str | None:
    """Translate via LLM (OpenAI-compatible API). Returns None on 401."""
    if not text or not text.strip() or is_chinese(text):
        return text

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:MAX_TEXT_LENGTH]},
        ],
        "temperature": 0.1,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with get_llm_client(timeout=60) as client:
                r = await client.post(
                        f"{LLM_BASE_URL}/chat/completions",
                        json=payload,
                    )
            if r.status_code == 200:
                result = r.json()
                translated = result["choices"][0]["message"]["content"].strip()
                return translated or text
            elif r.status_code == 429:
                backoff = min(2 ** attempt * 10, 60)
                log.warning(
                    "LLM rate limited (attempt %d/%d), backoff %ds",
                    attempt, MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
            elif r.status_code == 401:
                log.error("LLM API key rejected (401). Set LLM_API_KEY.")
                return None
            else:
                log.warning(
                    "LLM HTTP %d (attempt %d/%d), retrying",
                    r.status_code, attempt, MAX_RETRIES,
                )
                await asyncio.sleep(2 ** attempt)
        except Exception as exc:
            log.warning(
                "LLM request failed (%s) attempt %d/%d, retrying",
                exc, attempt, MAX_RETRIES,
            )
            await asyncio.sleep(2 ** attempt)

    return text


async def translate_with_mymemory(text: str) -> str | None:
    """Fallback: MyMemory translation. Returns None on quota exhaustion."""
    if not text or not text.strip() or is_chinese(text):
        return text

    url = "https://api.mymemory.translated.net/get"
    params = {"q": text[:499], "langpair": "en-GB|zh-CN", "de": MYMEMORY_EMAIL}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                translated = (
                    data.get("responseData", {}).get("translatedText", "")
                )
                if translated and "MYMEMORY WARNING" not in translated.upper():
                    return translated
                log.warning("MyMemory quota exhausted, pausing")
                return None
            elif r.status_code == 429:
                backoff = min(2 ** attempt * 10, 120)
                log.warning(
                    "MyMemory rate limited (attempt %d/%d), backoff %ds",
                    attempt, MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
        except Exception as exc:
            log.warning(
                "MyMemory request failed (%s) attempt %d/%d, retrying",
                exc, attempt, MAX_RETRIES,
            )
            await asyncio.sleep(2 ** attempt)

    return text


async def translate_text(text: str) -> str | None:
    """Translate text to Simplified Chinese.

    Returns:
        Translated text on success, original text on transient failure,
        None on permanent failure (e.g. quota exhausted or invalid key).
    """
    if not text or not text.strip() or is_chinese(text):
        return text
    if LLM_API_KEY:
        return await translate_with_llm(text)
    return await translate_with_mymemory(text)

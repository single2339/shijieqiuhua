"""LLM-based document summarization — generates concise Chinese summaries."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Optional

from src.models.document import RawDocument
from backend.llm_config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, get_llm_client

log = logging.getLogger(__name__)

SUMMARIZE_DELAY = 0.5
MAX_INPUT_LENGTH = 6000
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "You are a professional intelligence analyst. "
    "Summarize the following text into a concise Simplified Chinese summary "
    "of 2-3 sentences. Focus on the key facts: who, what, where, when, and "
    "why. Return ONLY the summary, no notes, no explanations."
)


async def _summarize_with_llm(text: str) -> Optional[str]:
    """Call LLM to generate a 2-3 sentence Chinese summary."""
    if not text or not text.strip():
        return None
    if not LLM_API_KEY:
        return None

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:MAX_INPUT_LENGTH]},
        ],
        "temperature": 0.3,
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
                summary = result["choices"][0]["message"]["content"].strip()
                return summary or None
            elif r.status_code == 429:
                backoff = min(2 ** attempt * 10, 60)
                log.warning(
                    "Summarize rate limited (attempt %d/%d), backoff %ds",
                    attempt, MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
            elif r.status_code == 401:
                log.error("LLM API key rejected (401). Check LLM_API_KEY.")
                return None
            else:
                log.warning(
                    "Summarize HTTP %d (attempt %d/%d), retrying",
                    r.status_code, attempt, MAX_RETRIES,
                )
                await asyncio.sleep(2 ** attempt)
        except Exception as exc:
            log.warning(
                "Summarize request failed (%s) attempt %d/%d, retrying",
                exc, attempt, MAX_RETRIES,
            )
            await asyncio.sleep(2 ** attempt)

    return None


async def summarize_document(doc: RawDocument) -> RawDocument:
    """Generate an LLM summary and attach to document extensions.

    Only summarizes if body is non-empty, LLM key is configured,
    and the document hasn't already been summarized.
    """
    body = doc.body_inline or doc.body_ref or ""
    if not body or not LLM_API_KEY:
        return doc
    if doc.extensions.get("summarized"):
        return doc

    summary = await _summarize_with_llm(body)
    await asyncio.sleep(SUMMARIZE_DELAY)

    if not summary:
        return doc

    return replace(
        doc,
        extensions={**doc.extensions, "summary": summary, "summarized": True},
    )

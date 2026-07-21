"""Processing policy and deterministic text utilities.

The default path keeps collected intelligence readable by translating it to
Chinese, while summary/classification stay cheap and deterministic. Deeper LLM
enrichment is reserved for explicit workflows or future low-confidence jobs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum


class ProcessingMode(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


@dataclass(frozen=True)
class ProcessingPolicy:
    mode: ProcessingMode
    use_llm_translation: bool = True
    use_llm_summary: bool = False
    use_llm_classification: bool = False
    allow_llm_enrichment: bool = False


def get_processing_policy() -> ProcessingPolicy:
    raw = os.getenv("OSINT_PROCESSING_MODE", "fast").strip().lower()
    try:
        mode = ProcessingMode(raw)
    except ValueError:
        mode = ProcessingMode.FAST

    if mode == ProcessingMode.DEEP:
        return ProcessingPolicy(
            mode=mode,
            use_llm_translation=True,
            use_llm_summary=True,
            use_llm_classification=True,
            allow_llm_enrichment=True,
        )
    if mode == ProcessingMode.BALANCED:
        return ProcessingPolicy(mode=mode, use_llm_translation=True, allow_llm_enrichment=True)
    return ProcessingPolicy(mode=ProcessingMode.FAST)


def deterministic_summary(text: str, title: str = "", max_chars: int = 260) -> str:
    """Create a cheap extractive summary from title + leading sentence."""
    title = " ".join((title or "").split())
    clean = " ".join((text or "").split())
    if not title and not clean:
        return ""

    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s+", clean) if s.strip()]
    lead = sentences[0] if sentences else clean
    if title and lead and lead not in title:
        summary = f"{title}。{lead}"
    else:
        summary = title or lead
    return summary[:max_chars]

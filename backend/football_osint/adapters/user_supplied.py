"""User-supplied URL adapter (W2.7c — extracted from pipeline.py).

Pulls candidate URLs from three sources, in priority order:

1. ``FOOTBALL_OSINT_LIGHTPANDA_URLS`` env (operator override)
2. URLs embedded in the question text
3. URLs embedded in user_supplied.notes

The combined list goes through ``url_safety.valid_urls`` so the SRF
allowlist + DNS public-IP check still apply — this module never reaches
the network on its own.

PRD §5.5 + §5.6.
"""
from __future__ import annotations

import os

from . import url_safety
from ..models import FootballOsintJobRequest


def candidate_urls(request: FootballOsintJobRequest) -> list[str]:
    configured = os.getenv("FOOTBALL_OSINT_LIGHTPANDA_URLS", "")
    candidates = [item.strip() for item in configured.split(",") if item.strip()]
    candidates.extend(url_safety.extract_urls(request.question))
    for note in request.user_supplied.notes:
        candidates.extend(url_safety.extract_urls(note))
    return url_safety.valid_urls(candidates)

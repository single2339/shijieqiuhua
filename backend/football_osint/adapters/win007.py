"""Win007 candidate URL builder (W2.7b — extracted from pipeline.py).

Wraps the WIN007_SOURCE_TEMPLATES catalog. Given a request, returns the
list of (template, [urls]) pairs the lightpanda adapter should fetch. The
match_id is resolved from (in order) the question text, user notes,
FOOTBALL_OSINT_WIN007_MATCH_ID env override.

This module owns no I/O — purely URL construction. The fetch + evidence
mint happen in pipeline._collect_farich_foot_sources (W2.7c+ will move
that orchestration too).

PRD §5.5 sources catalog; §5.4 collection strategy.
"""
from __future__ import annotations

import os
from typing import Any

from ..models import FootballOsintJobRequest
from ..sources import WIN007_SOURCE_TEMPLATES, win007_match_id_from_text


def candidate_urls(request: FootballOsintJobRequest) -> list[tuple[Any, list[str]]]:
    """Return (template, urls) pairs for every default-enabled win007 template.

    Templates that require a match_id but cannot resolve one come back with
    an empty url list — the orchestrator marks them as ``skipped`` instead
    of attempting a fetch with a missing parameter.
    """
    match_level = int(os.getenv("FOOTBALL_OSINT_WIN007_MATCH_LEVEL", "2") or "2")
    match_id = resolve_match_id(request)
    rows: list[tuple[Any, list[str]]] = []
    for source in WIN007_SOURCE_TEMPLATES:
        if not source.default_enabled:
            continue
        if source.adapter == "win007_schedule":
            rows.append((source, [source.render_url(match_level=match_level)]))
            continue
        if source.requires_win007_match_id and not match_id:
            rows.append((source, []))
            continue
        rows.append((source, [source.render_url(match_id=match_id)]))
    return rows


def resolve_match_id(request: FootballOsintJobRequest) -> str:
    """Pull a win007 match id from question / notes / env, in that order."""
    texts = [request.question, *request.user_supplied.notes]
    for text in texts:
        match_id = win007_match_id_from_text(text)
        if match_id:
            return match_id
    return os.getenv("FOOTBALL_OSINT_WIN007_MATCH_ID", "")

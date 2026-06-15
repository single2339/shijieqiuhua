"""Dongqiudi candidate URL builder — replaces win007.py.

Wraps the DONGQIUDI_SOURCE_TEMPLATES catalog. The dongqiudi_analysis
template's matchId is resolved by matching the request's home/away team
names against the dongqiudi schedule fixture list, replacing the old
"win007:<id>" text-marker hack.

This module owns no I/O beyond the schedule fetch needed for match-id
resolution — the actual analysis fetch + evidence mint happen in
pipeline._collect_farich_foot_sources via dongqiudi_analysis.fetch_url.
"""
from __future__ import annotations

from typing import Any

from ..models import FootballOsintJobRequest
from ..sources import DONGQIUDI_SOURCE_TEMPLATES
from . import dongqiudi_schedule


def candidate_urls(request: FootballOsintJobRequest) -> list[tuple[Any, list[str]]]:
    """Return (template, urls) pairs for every default-enabled dongqiudi template.

    The analysis template comes back with an empty url list when no fixture
    matches the request's team names — the orchestrator marks it ``skipped``.
    """
    fixtures = dongqiudi_schedule.fetch_fixtures()
    fixture = dongqiudi_schedule.find_fixture(fixtures, request.home_team, request.away_team)

    rows: list[tuple[Any, list[str]]] = []
    for source in DONGQIUDI_SOURCE_TEMPLATES:
        if not source.default_enabled:
            continue
        if source.adapter == "dongqiudi_schedule":
            rows.append((source, [source.render_url()]))
            continue
        if source.requires_match_id and not fixture:
            rows.append((source, []))
            continue
        rows.append((source, [source.render_url(match_id=fixture.match_id)]))
    return rows

"""RSS feed adapter — parses XML feeds via feedparser, extracts match-relevant news.

PRD §5.5; W4 data source expansion. RSS feeds are fetched in parallel.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import feedparser

from ..evidence import append_evidence
from ..models import FootballOsintJobRequest, OsintEvidence
from ..sources import RSS_FEED_TEMPLATES

log = logging.getLogger(__name__)
MAX_PER_FEED = 5
MAX_ENTRIES = 20
_MAX_WORKERS = 8


def collect_all(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
) -> list[tuple[str, str, int]]:
    home = request.home_team.lower()
    away = request.away_team.lower()

    templates = [src for src in RSS_FEED_TEMPLATES if src.default_enabled]
    results: list[tuple[str, str, int]] = []

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, max(1, len(templates)))) as pool:
        futures = {
            pool.submit(_collect_one, src.label, src.url_template, src.topic, home, away, evidence): src
            for src in templates
        }
        for future in as_completed(futures):
            src = futures[future]
            try:
                cnt = future.result(timeout=30)
            except Exception:
                log.warning("rss %s timed out or failed", src.adapter)
                cnt = 0
            results.append((src.adapter, "ok" if cnt > 0 else "skipped", cnt))

    return results


def _collect_one(label: str, url: str, topic: str, home: str, away: str, evidence: list[OsintEvidence]) -> int:
    try:
        data: dict[str, Any] = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        log.warning("rss %s parse failed: %s", label, e)
        return 0

    cnt = 0
    for entry in (data.get("entries") or [])[:MAX_ENTRIES]:
        title = (entry.get("title") or "").lower()
        summary = (entry.get("summary") or "").lower()
        text = f"{title} {summary}"
        if home in text or away in text:
            append_evidence(evidence, source=label, source_type="news",
                            claim=(entry.get("title") or "")[:200], topic=topic,
                            side="neutral", confidence=0.30,
                            raw_excerpt=(entry.get("summary") or title)[:400],
                            url=entry.get("link") or "")
            cnt += 1
            if cnt >= MAX_PER_FEED:
                break
    return cnt

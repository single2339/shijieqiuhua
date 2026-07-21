"""RSS collection agent — wraps Horizon's RSSScraper."""

from __future__ import annotations

import asyncio
import sys as _sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from backend.agents.base import AgentType, BaseAgent, AgentCallbacks
from backend.agents.collectors._utils import load_existing_hashes, collection_lock
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.collectors.horizon.models import ContentItem, RSSSourceConfig
from backend.collectors.horizon.scrapers.rss import RSSScraper
from backend.collectors.horizon_bridge import (
    _DEFAULT_RSS_FEEDS,
    _persist_intelligence_item,
    _prepare_item_for_storage,
)
from backend.intelligence.store import IntelligenceStore
from backend.llm_config import PROXY_URL
from backend.processors.processing_cache import ProcessingCache
from src.bronze.writer import BronzeWriter


async def _prepare_item(item: ContentItem, sem: asyncio.Semaphore, cache: ProcessingCache | None = None):
    async with sem:
        return await _prepare_item_for_storage(item, cache=cache)


@AgentRegistry.register
class RSSCollector(BaseAgent):
    agent_id = "rss_collector"
    agent_type = AgentType.COLLECTION

    def __init__(self, callbacks: AgentCallbacks | None = None, feeds: list[RSSSourceConfig] | None = None):
        super().__init__(callbacks)
        self._feeds = feeds or list(_DEFAULT_RSS_FEEDS)

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        # Preserve original source material before translation/enrichment.
        # The storage generator records it in extensions for provenance.
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        with collection_lock(storage):
            return await self._execute_unlocked(task)

    async def _execute_unlocked(self, task: AgentTask) -> dict[str, Any]:
        hours = task.params.get("hours", 48)
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sem = asyncio.Semaphore(3)
        existing = load_existing_hashes(storage)
        bronze = BronzeWriter(storage)
        processing_cache = ProcessingCache(storage / "_processing_cache.db")

        import httpx
        client_kwargs = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client, httpx.AsyncClient(timeout=30.0) as local_client:
            scraper = RSSScraper(self._feeds, client, local_client)
            items = await scraper.fetch(since)
        prepared = await asyncio.gather(*[_prepare_item(item, sem, processing_cache) for item in items])

        stored = 0
        intelligence_store = IntelligenceStore(storage)
        for item, (profile, decision) in zip(items, prepared):
            stored += int(_persist_intelligence_item(
                item,
                profile,
                decision,
                bronze=bronze,
                intelligence_store=intelligence_store,
                existing_hashes=existing,
            ))
        stats = {"fetched": len(items), "stored": stored, "skipped": len(items) - stored}
        for status in ("accepted", "quarantined", "rejected"):
            stats[status] = sum(1 for _profile, decision in prepared if decision.status.value == status)
        return stats

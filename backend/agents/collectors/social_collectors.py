"""Reddit, HackerNews, Telegram, GitHub — social/platform collection agents."""

from __future__ import annotations

import asyncio
import sys as _sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from backend.agents.base import AgentType, BaseAgent
from backend.agents.collectors._utils import content_item_to_document, load_existing_hashes
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.collectors.horizon.models import ContentItem
from backend.collectors.horizon.scrapers.hackernews import HackerNewsScraper
from backend.collectors.horizon.scrapers.reddit import RedditScraper
from backend.collectors.horizon.scrapers.telegram import TelegramScraper
from backend.collectors.horizon.scrapers.github import GitHubScraper
from backend.collectors.horizon_bridge import (
    _DEFAULT_HN_CONFIG,
    _DEFAULT_REDDIT_CONFIG,
    _DEFAULT_TELEGRAM_CONFIG,
    _DEFAULT_GITHUB_SOURCES,
    _process_item_for_storage,
)
from backend.llm_config import PROXY_URL
from backend.processors.processing_cache import ProcessingCache
from src.bronze.writer import BronzeWriter


async def _process_item(item: ContentItem, sem: asyncio.Semaphore, cache: ProcessingCache | None = None) -> None:
    async with sem:
        await _process_item_for_storage(item, cache=cache)


async def _store_items(items: list[ContentItem], storage: Path, sem: asyncio.Semaphore, existing: set[str]) -> dict[str, int]:
    processing_cache = ProcessingCache(storage / "_processing_cache.db")
    await asyncio.gather(*[_process_item(item, sem, processing_cache) for item in items])
    bronze = BronzeWriter(storage)
    stored = 0
    for item in items:
        doc = content_item_to_document(item)
        if doc.content_sha256 in existing:
            continue
        bronze.write(doc)
        existing.add(doc.content_sha256)
        stored += 1
    return {"fetched": len(items), "stored": stored, "skipped": len(items) - stored}


@AgentRegistry.register
class RedditCollector(BaseAgent):
    agent_id = "reddit_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        hours = task.params.get("hours", 48)
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sem = asyncio.Semaphore(3)
        existing = load_existing_hashes(storage)

        import httpx
        client_kwargs = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            scraper = RedditScraper(_DEFAULT_REDDIT_CONFIG, client)
            items = await scraper.fetch(since)
        return await _store_items(items, storage, sem, existing)


@AgentRegistry.register
class HackerNewsCollector(BaseAgent):
    agent_id = "hackernews_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        hours = task.params.get("hours", 48)
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sem = asyncio.Semaphore(3)
        existing = load_existing_hashes(storage)

        import httpx
        client_kwargs = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            scraper = HackerNewsScraper(_DEFAULT_HN_CONFIG, client)
            items = await scraper.fetch(since)
            return await _store_items(items, storage, sem, existing)


@AgentRegistry.register
class TelegramCollector(BaseAgent):
    agent_id = "telegram_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        hours = task.params.get("hours", 48)
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sem = asyncio.Semaphore(3)
        existing = load_existing_hashes(storage)

        import httpx
        client_kwargs = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            scraper = TelegramScraper(_DEFAULT_TELEGRAM_CONFIG, client)
            items = await scraper.fetch(since)
            return await _store_items(items, storage, sem, existing)


@AgentRegistry.register
class GitHubCollector(BaseAgent):
    agent_id = "github_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        hours = task.params.get("hours", 48)
        storage = Path(task.params.get("storage_root", "bronze_storage"))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sem = asyncio.Semaphore(3)
        existing = load_existing_hashes(storage)

        import httpx
        client_kwargs = {"timeout": 30.0}
        if PROXY_URL:
            client_kwargs["proxy"] = PROXY_URL
        async with httpx.AsyncClient(**client_kwargs) as client:
            scraper = GitHubScraper(_DEFAULT_GITHUB_SOURCES, client)
            items = await scraper.fetch(since)
            return await _store_items(items, storage, sem, existing)

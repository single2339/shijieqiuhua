"""Bridge between Horizon scrapers and OSINT bronze storage.

Horizon scrapers are vendored under ``backend/collectors/horizon/`` with
fixes to use absolute imports.  Each scraper produces :class:`ContentItem`
objects which are converted to :class:`RawDocument` and written via
:class:`BronzeWriter` under ``bronze_storage/{date}/{source_system}/``.

NOTE: This module imports from ``src/`` (legacy pipeline) for bronze
writing, text cleaning, translation, and summarization utilities.
These utilities are small and stable; the dependency is documented here
rather than duplicated.  The project root is added to sys.path so that
``src.*`` imports resolve correctly regardless of launch directory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys as _sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import httpx

# Ensure project-root ``src/`` is importable even when the process is
# started from a different working directory.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from backend.collectors.horizon.scrapers.rss import RSSScraper
from backend.collectors.horizon.scrapers.hackernews import HackerNewsScraper
from backend.collectors.horizon.scrapers.reddit import RedditScraper
from backend.collectors.horizon.scrapers.telegram import TelegramScraper
from backend.collectors.horizon.scrapers.github import GitHubScraper

from backend.collectors.horizon.models import (
    ContentItem,
    SourceType,
    RSSSourceConfig,
    HackerNewsConfig,
    RedditConfig,
    RedditSubredditConfig,
    TelegramConfig,
    TelegramChannelConfig,
    GitHubSourceConfig,
)
from src.bronze.writer import BronzeWriter  # noqa: E402 (sys.path setup above)
from src.models.document import RawDocument
from src.processor.cleaner import clean_text
from src.processor.summarizer import _summarize_with_llm
from src.processor.translation import translate_text
from backend.processors.llm_classifier import classify_with_llm

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default scraper configurations
# ---------------------------------------------------------------------------

_DEFAULT_RSS_FEEDS = [
    # ── Domestic / fast sources (prioritized) ──
    RSSSourceConfig(name="aihot-daily",     url="https://aihot.virxact.com/rss",                  category="ai_hot"),
    RSSSourceConfig(name="google-news-ai4s",url="https://news.google.com/rss/search?q=ai%20for%20science&hl=en-US&gl=US&ceid=US:en", category="ai4s"),
    # ── AI for Science ──
    RSSSourceConfig(name="aihub-news",      url="https://aihub.org/category/news/feed/",          category="ai4s"),
    RSSSourceConfig(name="aihub-articles",  url="https://aihub.org/category/articles/feed/",      category="ai4s"),
    RSSSourceConfig(name="sciencenews-ai",  url="https://www.sciencenews.org/feed",               category="ai4s"),
    # ── Global news ──
    RSSSourceConfig(name="bbc",         url="https://feeds.bbci.co.uk/news/world/rss.xml",    category="international"),
    RSSSourceConfig(name="guardian",    url="https://www.theguardian.com/world/rss",          category="international"),
    RSSSourceConfig(name="nytimes",     url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml", category="international"),
    RSSSourceConfig(name="cnn",         url="https://rss.cnn.com/rss/cnn_world.rss",          category="international"),
    RSSSourceConfig(name="npr",         url="https://feeds.npr.org/1001/rss.xml",            category="international"),
    RSSSourceConfig(name="al-jazeera",  url="https://www.aljazeera.com/xml/rss/all.xml",      category="international"),
    RSSSourceConfig(name="euronews",    url="https://www.euronews.com/rss",                   category="international"),
    RSSSourceConfig(name="economist",   url="https://www.economist.com/feeds/print-sections/77/the-economist.xml", category="international"),
    # Asia
    RSSSourceConfig(name="nikkei-asia", url="https://www.nikkei.com/rss/",                     category="regional_asia"),
    RSSSourceConfig(name="scmp",        url="https://www.scmp.com/rss/4/feed",                category="regional_asia"),
    # Europe
    RSSSourceConfig(name="le-monde",    url="https://www.lemonde.fr/en/rss/une.xml",          category="regional_europe"),
    RSSSourceConfig(name="el-pais",     url="https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada", category="regional_europe"),
    # Tech
    RSSSourceConfig(name="arstechnica", url="https://feeds.arstechnica.com/arstechnica/index", category="technology"),
    RSSSourceConfig(name="wired",       url="https://www.wired.com/feed/rss",                 category="technology"),
    RSSSourceConfig(name="techcrunch",  url="https://techcrunch.com/feed/",                   category="technology"),
    # Defense / OSINT
    RSSSourceConfig(name="warzone",     url="https://www.twz.com/feed",                       category="defense"),
    RSSSourceConfig(name="bellingcat",  url="https://www.bellingcat.com/feed",                category="osint"),
    # ── China domestic (via RSSHub) ──
    RSSSourceConfig(name="weibo-hot",       url="http://127.0.0.1:1200/weibo/search/hot",        category="social_media_china"),
    RSSSourceConfig(name="cls-telegraph",   url="http://127.0.0.1:1200/cls/telegraph",           category="financial_china"),
    RSSSourceConfig(name="zaobao-china",    url="http://127.0.0.1:1200/zaobao/realtime/china",   category="regional_china"),
]

_DEFAULT_HN_CONFIG = HackerNewsConfig(
    enabled=True,
    fetch_top_stories=30,
    min_score=50,
)

_DEFAULT_REDDIT_CONFIG = RedditConfig(
    enabled=True,
    subreddits=[
        RedditSubredditConfig(subreddit="worldnews",       sort="hot", fetch_limit=25, min_score=100),
        RedditSubredditConfig(subreddit="geopolitics",     sort="hot", fetch_limit=25, min_score=10),
        RedditSubredditConfig(subreddit="credibledefense",  sort="hot", fetch_limit=25, min_score=5),
        RedditSubredditConfig(subreddit="intelligence",    sort="hot", fetch_limit=25, min_score=5),
        RedditSubredditConfig(subreddit="OSINT",           sort="new", fetch_limit=15, min_score=0),
    ],
    users=[],
    fetch_comments=3,
)

_DEFAULT_TELEGRAM_CONFIG = TelegramConfig(
    enabled=True,
    channels=[
        TelegramChannelConfig(channel="osintdefender", fetch_limit=10),
    ],
)

_DEFAULT_GITHUB_SOURCES = [
    GitHubSourceConfig(type="repo_releases", owner="Thysrael", repo="Horizon", enabled=True),
]

async def _translate_item(item: ContentItem) -> None:
    """Translate a ContentItem's title and content using shared translator."""
    if item.title:
        translated = await translate_text(item.title)
        if translated and translated != item.title:
            item.title = translated
    if item.content:
        translated = await translate_text(item.content)
        if translated and translated != item.content:
            item.content = translated


async def _summarize_item(item: ContentItem) -> None:
    """Generate an LLM summary of the translated content."""
    if item.content:
        summary = await _summarize_with_llm(item.content)
        if summary:
            item.ai_summary = summary


async def _classify_item(item: ContentItem) -> None:
    """Classify the item into an IntelLayer using LLM and store in metadata.

    Also extracts geographic location from entity/incident references.
    """
    title = item.title or ""
    content = item.content or ""
    layer, country, city = await classify_with_llm(title, content)
    item.metadata["layer"] = layer.value
    if country:
        item.metadata["location_country"] = country
    if city:
        item.metadata["location_city"] = city


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class HorizonBridge:
    """Wraps Horizon scrapers and writes collected content to bronze storage.

    Usage::

        bridge = HorizonBridge(Path("bronze_storage"))
        results = await bridge.collect_and_store(hours=48)
        await bridge.close()
    """

    def __init__(
        self,
        storage_root: Path,
        rss_feeds: Optional[List[RSSSourceConfig]] = None,
        hn_config: Optional[HackerNewsConfig] = None,
        reddit_config: Optional[RedditConfig] = None,
        telegram_config: Optional[TelegramConfig] = None,
        github_sources: Optional[List[GitHubSourceConfig]] = None,
    ):
        self.storage_root = Path(storage_root)
        self.rss_feeds = rss_feeds or _DEFAULT_RSS_FEEDS
        self.hn_config = hn_config or _DEFAULT_HN_CONFIG
        self.reddit_config = reddit_config or _DEFAULT_REDDIT_CONFIG
        self.telegram_config = telegram_config or _DEFAULT_TELEGRAM_CONFIG
        self.github_sources = github_sources or _DEFAULT_GITHUB_SOURCES
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect_and_store(self, hours: int = 48) -> dict[str, dict]:
        """Run all enabled scrapers and persist new content.

        Returns a dict mapping source name to stats::

            {"rss": {"fetched": 45, "stored": 12, "skipped": 33},
             "reddit": {"error": "rate limited"}, ...}
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        client = await self._get_client()

        existing_hashes = self._load_existing_hashes()
        bronze = BronzeWriter(self.storage_root)

        scrapers: list[tuple[str, object]] = []

        if self.rss_feeds:
            scrapers.append(("rss", RSSScraper(self.rss_feeds, client)))
        if self.hn_config.enabled:
            scrapers.append(("hackernews", HackerNewsScraper(self.hn_config, client)))
        if self.reddit_config.enabled:
            scrapers.append(("reddit", RedditScraper(self.reddit_config, client)))
        if self.telegram_config.enabled:
            scrapers.append(("telegram", TelegramScraper(self.telegram_config, client)))
        if self.github_sources:
            scrapers.append(("github", GitHubScraper(self.github_sources, client)))

        results: dict[str, dict] = {}

        for name, scraper in scrapers:
            try:
                items = await scraper.fetch(since)  # type: ignore[union-attr]
                stored = 0
                skipped = 0
                for item in items:
                    await _translate_item(item)
                    await _summarize_item(item)
                    await _classify_item(item)
                    doc = self._to_raw_document(item)
                    if doc.content_sha256 in existing_hashes:
                        skipped += 1
                        continue
                    bronze.write(doc)
                    existing_hashes.add(doc.content_sha256)
                    stored += 1
                results[name] = {"fetched": len(items), "stored": stored, "skipped": skipped}
                log.info("Horizon %s: %d fetched, %d new, %d duplicate", name, len(items), stored, skipped)
            except Exception as exc:
                log.warning("Horizon scraper %r failed: %s", name, exc)
                results[name] = {"error": str(exc)}

        return results

    # ------------------------------------------------------------------
    # Dedup helpers
    # ------------------------------------------------------------------

    def _load_existing_hashes(self) -> set[str]:
        hashes: set[str] = set()
        if not self.storage_root.exists():
            return hashes
        for p in self.storage_root.rglob("*.json"):
            if p.name == "queue.db":
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                ch = data.get("content_sha256", "")
                if ch:
                    hashes.add(ch)
            except (json.JSONDecodeError, OSError):
                continue
        return hashes

    # ------------------------------------------------------------------
    # ContentItem -> RawDocument
    # ------------------------------------------------------------------

    def _to_raw_document(self, item: ContentItem) -> RawDocument:
        content = clean_text(item.content or "")
        captured_at = (
            item.published_at.isoformat()
            if item.published_at
            else datetime.now(timezone.utc).isoformat()
        )
        source_system = item.author or item.source_type.value

        return RawDocument(
            raw_document_id=hashlib.md5(content.encode()).hexdigest(),
            job_id=f"horizon-{item.source_type.value}-{item.id}",
            channel=item.source_type.value,
            mime_type="text/plain",
            encoding="utf-8",
            body_inline=content if len(content.encode("utf-8")) < 65536 else None,
            body_ref=None if len(content.encode("utf-8")) < 65536 else f"bronze://{hashlib.sha256(content.encode()).hexdigest()}",
            headers_summary={"collector": "horizon-bridge"},
            captured_at=captured_at,
            collector_id=f"horizon-{item.source_type.value}",
            collector_version="1.0",
            source_url=str(item.url) if item.url else "",
            source_system=source_system,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            tenant_id="",
            extensions={
                "horizon_item_id": item.id,
                "horizon_title": item.title,
                "horizon_source_type": item.source_type.value,
                "horizon_metadata": item.metadata,
                "summary": item.ai_summary or "",
                "summarized": bool(item.ai_summary),
            },
        )

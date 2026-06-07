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

import asyncio
import hashlib
import json
import logging
import sys as _sys
import xml.etree.ElementTree as ET
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
from backend.llm_config import PROXY_URL
from src.bronze.writer import BronzeWriter  # noqa: E402 (sys.path setup above)
from src.models.document import RawDocument
from src.processor.cleaner import clean_text
from src.processor.summarizer import _summarize_with_llm
from src.processor.translation import translate_text
from backend.processors.llm_classifier import classify_with_llm
from backend.processors.classifier import classify as keyword_classify
from backend.processors.location import extract_location_with_fallback
from backend.processors.processing_cache import ProcessingCache
from backend.processors.processing_policy import deterministic_summary, get_processing_policy
from backend.bronze_reader import QUEUE_DB_FILENAME

log = logging.getLogger(__name__)

_BESTBLOGS_OPML_PATH = Path(__file__).resolve().parent.parent / "config" / "BestBlogs_RSS_ALL.opml"


def _load_rss_feeds_from_opml(path: Path, category: str) -> list[RSSSourceConfig]:
    """Load RSSSourceConfig entries from a local OPML subscription file."""
    if not path.exists():
        return []

    feeds: list[RSSSourceConfig] = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        log.warning("Unable to parse RSS OPML file %s: %s", path, exc)
        return feeds

    name_counts: dict[str, int] = {}
    for outline in root.findall(".//outline"):
        url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlurl")
        if not url:
            continue
        name = outline.attrib.get("title") or outline.attrib.get("text") or url
        name = name.strip().replace("/", "_")
        url = url.strip()
        if not name or not url:
            continue
        name_counts[name] = name_counts.get(name, 0) + 1
        if name_counts[name] > 1:
            name = f"{name} ({name_counts[name]})"
        try:
            feeds.append(RSSSourceConfig(name=name, url=url, category=category))
        except Exception as exc:
            log.warning("Skipping invalid RSS feed from %s: %s (%s)", path.name, name, exc)
    return feeds


def _dedupe_rss_feeds(feeds: list[RSSSourceConfig]) -> list[RSSSourceConfig]:
    """Keep feed order stable while removing duplicate URLs."""
    seen: set[str] = set()
    deduped: list[RSSSourceConfig] = []
    for feed in feeds:
        url = str(feed.url).rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        deduped.append(feed)
    return deduped

# ---------------------------------------------------------------------------
# Default scraper configurations
# ---------------------------------------------------------------------------

_CORE_RSS_FEEDS = [
    # ── Domestic / fast sources (prioritized) ──
    RSSSourceConfig(name="aihot-daily",     url="https://aihot.virxact.com/rss",                  category="ai_hot", enabled=False),
    RSSSourceConfig(name="google-news-ai4s",url="https://news.google.com/rss/search?q=ai%20for%20science&hl=en-US&gl=US&ceid=US:en", category="ai4s"),
    # ── AI for Science ──
    RSSSourceConfig(name="aihub-news",      url="https://aihub.org/category/news/feed/",          category="ai4s"),
    RSSSourceConfig(name="aihub-articles",  url="https://aihub.org/category/articles/feed/",      category="ai4s"),
    RSSSourceConfig(name="sciencenews-ai",  url="https://www.sciencenews.org/feed",               category="ai4s"),
    # ── Global news ──
    RSSSourceConfig(name="bbc",         url="https://feeds.bbci.co.uk/news/world/rss.xml",    category="international"),
    RSSSourceConfig(name="guardian",    url="https://www.theguardian.com/world/rss",          category="international"),
    RSSSourceConfig(name="nytimes",     url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml", category="international"),
    RSSSourceConfig(name="cnn",         url="https://rss.cnn.com/rss/cnn_world.rss",          category="international", enabled=False),
    RSSSourceConfig(name="npr",         url="https://feeds.npr.org/1001/rss.xml",            category="international"),
    RSSSourceConfig(name="al-jazeera",  url="https://www.aljazeera.com/xml/rss/all.xml",      category="international"),
    RSSSourceConfig(name="euronews",    url="https://www.euronews.com/rss",                   category="international"),
    RSSSourceConfig(name="economist",   url="https://www.economist.com/feeds/print-sections/77/the-economist.xml", category="international", enabled=False),
    # Asia
    RSSSourceConfig(name="nikkei-asia", url="https://www.nikkei.com/rss/",                     category="regional_asia", enabled=False),
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
    # ── Crypto / Blockchain ──
    RSSSourceConfig(name="coindesk",      url="https://www.coindesk.com/arc/outboundfeeds/rss/",    category="crypto"),
    RSSSourceConfig(name="cointelegraph", url="https://cointelegraph.com/rss",                      category="crypto"),
    RSSSourceConfig(name="theblock",      url="https://www.theblock.co/rss.xml",                   category="crypto"),
    RSSSourceConfig(name="decrypt",       url="https://decrypt.co/feed",                            category="crypto"),
    RSSSourceConfig(name="jinse-lives",    url="http://127.0.0.1:1200/jinse/lives",    category="crypto"),
    RSSSourceConfig(name="jinse-timeline", url="http://127.0.0.1:1200/jinse/timeline", category="crypto"),
    # ── China domestic (via RSSHub) ──
    RSSSourceConfig(name="cls-telegraph",   url="http://127.0.0.1:1200/cls/telegraph",           category="financial_china"),
    RSSSourceConfig(name="zaobao-china",    url="http://127.0.0.1:1200/zaobao/realtime/china",   category="regional_china"),
]

_BESTBLOGS_RSS_FEEDS = _load_rss_feeds_from_opml(_BESTBLOGS_OPML_PATH, category="bestblogs")
_DEFAULT_RSS_FEEDS = _dedupe_rss_feeds([*_CORE_RSS_FEEDS, *_BESTBLOGS_RSS_FEEDS])

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
        RedditSubredditConfig(subreddit="CryptoCurrency", sort="hot", fetch_limit=20, min_score=50),
        RedditSubredditConfig(subreddit="Binance",        sort="hot", fetch_limit=10, min_score=5),
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


def _classify_item_deterministic(item: ContentItem) -> None:
    """Classify and locate without calling an LLM."""
    title = item.title or ""
    content = item.content or ""
    combined = f"{title}\n{content}"
    layer = keyword_classify(combined)
    country, city, _lat, _lng = extract_location_with_fallback(combined, item.author or item.source_type.value)
    item.metadata["layer"] = layer.value
    if country:
        item.metadata["location_country"] = country
    if city:
        item.metadata["location_city"] = city


def _content_hash_for_processing(item: ContentItem) -> str:
    return hashlib.sha256((item.content or "").encode()).hexdigest()


def _apply_cached_processing(item: ContentItem, cached: dict) -> None:
    translated_title = cached.get("translated_title", "")
    translated_content = cached.get("translated_content", "")
    if translated_title:
        item.title = translated_title
    if translated_content:
        item.content = translated_content
    item.ai_summary = cached.get("summary", "") or item.ai_summary
    layer = cached.get("layer", "")
    country = cached.get("country", "")
    city = cached.get("city", "")
    if layer:
        item.metadata["layer"] = layer
    if country:
        item.metadata["location_country"] = country
    if city:
        item.metadata["location_city"] = city


async def _process_item_for_storage(item: ContentItem, cache: ProcessingCache | None = None) -> ContentItem:
    """Apply the configured processing policy before bronze storage."""
    policy = get_processing_policy()
    content_hash = _content_hash_for_processing(item)
    if cache is not None:
        cached = cache.get(content_hash)
        if cached is not None:
            _apply_cached_processing(item, cached)
            return item

    if policy.use_llm_translation:
        await _translate_item(item)
    if policy.use_llm_summary:
        await _summarize_item(item)
    else:
        item.ai_summary = deterministic_summary(item.content or "", item.title)
    if policy.use_llm_classification:
        await _classify_item(item)
    else:
        _classify_item_deterministic(item)
    if cache is not None:
        cache.put(
            content_hash,
            translated_title=item.title or "",
            translated_content=item.content or "",
            summary=item.ai_summary or "",
            layer=str(item.metadata.get("layer", "")),
            country=str(item.metadata.get("location_country", "")),
            city=str(item.metadata.get("location_city", "")),
            mode=policy.mode.value,
            llm_used=policy.use_llm_translation or policy.use_llm_summary or policy.use_llm_classification,
        )
    return item


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
        self._local_client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            kwargs: dict = {"timeout": 10.0, "follow_redirects": True}
            if PROXY_URL:
                kwargs["proxy"] = PROXY_URL
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def _get_local_client(self) -> httpx.AsyncClient:
        if self._local_client is None:
            self._local_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        return self._local_client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._local_client is not None:
            await self._local_client.aclose()
            self._local_client = None

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
        processing_cache = ProcessingCache(self.storage_root / "_processing_cache.db")

        scrapers: list[tuple[str, object]] = []

        if self.rss_feeds:
            local_client = await self._get_local_client()
            scrapers.append(("rss", RSSScraper(self.rss_feeds, client, local_client)))
        if self.hn_config.enabled:
            scrapers.append(("hackernews", HackerNewsScraper(self.hn_config, client)))
        if self.reddit_config.enabled:
            scrapers.append(("reddit", RedditScraper(self.reddit_config, client)))
        if self.telegram_config.enabled:
            scrapers.append(("telegram", TelegramScraper(self.telegram_config, client)))
        if self.github_sources:
            scrapers.append(("github", GitHubScraper(self.github_sources, client)))

        sem = asyncio.Semaphore(3)

        async def _process_one(item: ContentItem) -> bool:
            """Process a single item through the configured pipeline. Returns True if stored."""
            async with sem:
                await _process_item_for_storage(item, cache=processing_cache)
            doc = self._to_raw_document(item)
            if doc.content_sha256 in existing_hashes:
                return False
            bronze.write(doc)
            existing_hashes.add(doc.content_sha256)
            return True

        async def _run_scraper(name: str, scraper: object) -> tuple[str, dict]:
            try:
                items = await scraper.fetch(since)  # type: ignore[union-attr]
                results = await asyncio.gather(*[_process_one(item) for item in items])
                stored = sum(1 for r in results if r)
                skipped = len(results) - stored
                log.info("Horizon %s: %d fetched, %d new, %d duplicate", name, len(items), stored, skipped)
                return (name, {"fetched": len(items), "stored": stored, "skipped": skipped})
            except Exception as exc:
                log.warning("Horizon scraper %r failed: %s", name, exc)
                return (name, {"error": str(exc)})

        results_list = await asyncio.gather(
            *[_run_scraper(name, scraper) for name, scraper in scrapers]
        )
        return dict(results_list)

    # ------------------------------------------------------------------
    # Dedup helpers
    # ------------------------------------------------------------------

    def _load_existing_hashes(self) -> set[str]:
        index_db = self.storage_root / "_index.db"
        if index_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(index_db))
                rows = conn.execute(
                    "SELECT content_sha256 FROM bronze_index WHERE content_sha256 != ''"
                ).fetchall()
                conn.close()
                return {r[0] for r in rows}
            except Exception:
                pass

        hashes: set[str] = set()
        if not self.storage_root.exists():
            return hashes
        for p in self.storage_root.rglob("*.json"):
            if p.name == QUEUE_DB_FILENAME:
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

"""RSS feed scraper implementation."""

import asyncio
import calendar
import logging
import os
import re
import sys as _sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from email.utils import parsedate_to_datetime
import httpx
import feedparser

# Ensure project-root ``src/`` is importable.
_project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from .base import BaseScraper
from ..models import ContentItem, SourceType, RSSSourceConfig

from src.processor.cleaner import clean_text  # noqa: E402

logger = logging.getLogger(__name__)


class RSSScraper(BaseScraper):
    """Scraper for RSS/Atom feeds."""

    def __init__(self, sources: List[RSSSourceConfig], http_client: httpx.AsyncClient, local_client: httpx.AsyncClient | None = None):
        """Initialize RSS scraper.

        Args:
            sources: List of RSS feed configurations
            http_client: Shared async HTTP client (proxied for external URLs)
            local_client: Direct HTTP client for localhost URLs (bypasses proxy)
        """
        super().__init__({"sources": sources}, http_client)
        self._local_client = local_client

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch RSS feed items concurrently.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        sources = [s for s in self.config["sources"] if s.enabled]
        sem = asyncio.Semaphore(5)

        async def _fetch_one(source: RSSSourceConfig) -> List[ContentItem]:
            async with sem:
                return await self._fetch_feed(source, since)

        results = await asyncio.gather(*[_fetch_one(s) for s in sources])
        items: list[ContentItem] = []
        for result in results:
            items.extend(result)
        return items

    async def _fetch_feed(
        self,
        source: RSSSourceConfig,
        since: datetime
    ) -> List[ContentItem]:
        """Fetch items from a single RSS feed.

        Args:
            source: RSS feed configuration
            since: Only fetch items after this time

        Returns:
            List[ContentItem]: Feed content items
        """
        items = []

        try:
            # Expand environment variables in URL (e.g. ${LWN_TOKEN})
            feed_url = re.sub(
                r'\$\{(\w+)\}',
                lambda m: os.environ.get(m.group(1), m.group(0)).strip(),
                str(source.url),
            )

            # Use direct client for localhost URLs (proxy can't route them)
            is_localhost = feed_url.startswith("http://127.0.0.1") or feed_url.startswith("http://localhost")
            fetch_client = self._local_client if is_localhost and self._local_client else self.client
            response = await fetch_client.get(feed_url, follow_redirects=True)
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                # Parse published date; treat items without dates as just-published
                published_at = self._parse_date(entry) or datetime.now(timezone.utc)
                if published_at < since:
                    continue

                # Generate unique ID from feed URL and entry ID
                feed_id = str(source.url).split("//")[1].replace("/", "_")
                entry_id = entry.get("id", entry.get("link", ""))
                unique_id = f"{feed_id}:{hash(entry_id)}"

                # Extract content
                content = self._extract_content(entry)

                item = ContentItem(
                    id=self._generate_id("rss", feed_id, str(hash(entry_id))),
                    source_type=SourceType.RSS,
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", str(source.url)),
                    content=content,
                    author=entry.get("author", source.name),
                    published_at=published_at,
                    metadata={
                        "feed_name": source.name,
                        "category": source.category,
                        "tags": [tag.term for tag in entry.get("tags", [])],
                    }
                )
                items.append(item)

        except httpx.HTTPError as e:
            logger.warning("Error fetching RSS feed %s: %s", source.name, e)
        except Exception as e:
            logger.warning("Error parsing RSS feed %s: %s", source.name, e)

        return items

    def _parse_date(self, entry: dict) -> datetime:
        """Parse publication date from feed entry.

        Args:
            entry: Feed entry data

        Returns:
            datetime: Parsed publication date or None
        """
        # Try different date fields
        for field in ["published", "updated", "created"]:
            if field in entry:
                try:
                    # Try parsing structured time first
                    if f"{field}_parsed" in entry and entry[f"{field}_parsed"]:
                        return datetime.fromtimestamp(
                            calendar.timegm(entry[f"{field}_parsed"]),
                            tz=timezone.utc
                        )
                    # Fallback to string parsing
                    date_str = entry[field]
                    return parsedate_to_datetime(date_str)
                except Exception:
                    continue

        return None

    def _extract_content(self, entry: dict) -> str:
        """Extract and clean text content from feed entry."""
        if "summary" in entry:
            raw = entry.summary
        elif "description" in entry:
            raw = entry.description
        elif "content" in entry and entry.content:
            raw = entry.content[0].get("value", "")
        else:
            return ""

        return clean_text(raw, mime_hint="text/html")

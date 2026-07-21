from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.collectors.horizon.models import RSSSourceConfig
from backend.collectors.horizon.scrapers import rss as rss_module
from backend.collectors.horizon.scrapers.rss import RSSScraper
from scripts import collect as standalone_collect


RSS_XML = """
<rss version="2.0"><channel><title>Example</title><item>
<guid>stable-entry-1</guid><title>Stable title</title>
<link>https://example.test/stable-entry-1</link>
<pubDate>Sun, 12 Jul 2026 00:00:00 GMT</pubDate>
<description>Stable body</description>
</item></channel></rss>
"""


class _Response:
    text = RSS_XML

    def raise_for_status(self) -> None:
        return None


class _Client:
    async def get(self, *_args, **_kwargs):
        return _Response()


def _fail_process_hash(_value):
    raise AssertionError("RSS IDs must not use process-random hash()")


@pytest.mark.asyncio
async def test_horizon_rss_id_does_not_use_process_hash(monkeypatch) -> None:
    monkeypatch.setattr(rss_module, "hash", _fail_process_hash, raising=False)
    scraper = RSSScraper(
        [RSSSourceConfig(name="example", url="https://example.test/feed")],
        _Client(),
    )

    items = await scraper._fetch_feed(
        scraper.config["sources"][0],
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert len(items) == 1
    assert items[0].id.startswith("rss:")


@pytest.mark.asyncio
async def test_standalone_rss_id_does_not_use_process_hash(monkeypatch) -> None:
    monkeypatch.setattr(standalone_collect, "hash", _fail_process_hash, raising=False)

    items = await standalone_collect.fetch_feed(
        "example",
        "https://example.test/feed",
        _Client(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert len(items) == 1
    assert items[0]["id"].startswith("example:")

#!/usr/bin/env python3
"""Standalone collection script — each RSS feed runs as its own timed task.

Usage: source .venv/bin/activate && python scripts/collect.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

import httpx
import feedparser

from src.bronze.writer import BronzeWriter
from src.processor.cleaner import clean_text
from src.processor.translation import translate_text
from src.processor.summarizer import _summarize_with_llm
from src.models.document import RawDocument

_log = logging.getLogger("collect")

RSS_FEEDS = [
    ("bbc",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("guardian",    "https://www.theguardian.com/world/rss"),
    ("ars-technica","https://feeds.arstechnica.com/arstechnica/index"),
    ("bellingcat",  "https://www.bellingcat.com/feed"),
    ("scmp",        "https://www.scmp.com/rss/4/feed"),
    ("warzone",     "https://www.twz.com/feed"),
]

FEED_TIMEOUT = 15  # seconds per individual feed
ENTRY_AGE = timedelta(hours=48)

HEADERS = {"User-Agent": "OSINT-Network/1.0 (+https://github.com/osint-network)"}


def load_existing_hashes(storage_root: Path) -> set[str]:
    hashes: set[str] = set()
    if not storage_root.exists():
        return hashes
    for p in storage_root.rglob("*.json"):
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


async def fetch_feed(name: str, url: str, client: httpx.AsyncClient, since: datetime) -> list[dict]:
    """Fetch a single RSS feed and return parsed items."""
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        _log.warning("feed %s: fetch failed: %s", name, exc)
        return []

    feed = feedparser.parse(resp.text)
    items = []
    for entry in feed.entries:
        published = _parse_date(entry)
        if not published or published < since:
            continue
        content = (
            entry.get("summary", "") or
            entry.get("description", "") or
            entry.get("content", [{}])[0].get("value", "")
        )
        if not content:
            continue
        title = entry.get("title", "Untitled")
        entry_key = (
            entry.get("id")
            or entry.get("link")
            or f"{title}|{published.isoformat()}|{content}"
        )
        items.append({
            "id": f"{name}:{hashlib.sha256(str(entry_key).encode('utf-8')).hexdigest()}",
            "title": title,
            "url": entry.get("link", url),
            "content": clean_text(content),
            "author": entry.get("author", name),
            "published_at": published,
            "source_type": "rss",
        })
    _log.info("feed %s: %d items", name, len(items))
    return items


def _parse_date(entry) -> datetime | None:
    from email.utils import parsedate_to_datetime
    import calendar
    for field in ("published_parsed", "updated_parsed"):
        tp = entry.get(field)
        if tp:
            try:
                return datetime.fromtimestamp(calendar.timegm(tp), tz=timezone.utc)
            except Exception:
                pass
    for field in ("published", "updated"):
        val = entry.get(field, "")
        try:
            return parsedate_to_datetime(val)
        except Exception:
            pass
    return None


async def translate_if_needed(text: str) -> str:
    if not text:
        return text
    try:
        result = await translate_text(text)
        return result if result else text
    except Exception:
        return text


async def summarize_if_possible(text: str) -> str:
    if not text:
        return ""
    try:
        result = await _summarize_with_llm(text)
        return result if result else ""
    except Exception:
        return ""


def to_raw_document(item: dict) -> RawDocument:
    content = item.get("content", "") or ""
    content_bytes = content.encode("utf-8")
    content_sha256 = hashlib.sha256(content_bytes).hexdigest()
    item_id = str(item.get("id", ""))
    captured_at = (
        item["published_at"].isoformat()
        if item.get("published_at")
        else datetime.now(timezone.utc).isoformat()
    )
    source_system = item.get("author") or item.get("source_type", "unknown")
    return RawDocument(
        raw_document_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"osint:raw:{item_id}")),
        job_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"osint:job:{item_id}")),
        channel="web",
        mime_type="text/plain",
        encoding="utf-8",
        body_inline=content if len(content_bytes) < 65536 else None,
        body_ref=None if len(content_bytes) < 65536 else f"bronze://{content_sha256}",
        headers_summary={"collector": "rss-collector"},
        captured_at=captured_at,
        collector_id=f"rss-{item['source_type']}",
        collector_version="1.0.0",
        source_url=item.get("url", ""),
        source_system=source_system,
        content_sha256=content_sha256,
        tenant_id="default",
        body=content,
        extensions={
            "summary": item.get("ai_summary", ""),
            "summarized": bool(item.get("ai_summary")),
            "rss_title": item.get("title", ""),
        },
        ext_schema_version="1.0.0",
    )


async def process_feed(name: str, url: str, client, since, existing_hashes, storage_root) -> dict:
    """Fetch, translate, summarize, and store a single feed."""
    try:
        items = await asyncio.wait_for(
            fetch_feed(name, url, client, since),
            timeout=FEED_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {"feed": name, "error": "timeout"}
    except Exception as exc:
        return {"feed": name, "error": str(exc)}

    bronze = BronzeWriter(storage_root)
    stored = 0
    skipped = 0
    for item in items:
        # Translation and summarization via DeepSeek LLM
        item["content"] = await translate_if_needed(item["content"])
        ai_summary = await summarize_if_possible(item["content"])
        if ai_summary:
            item["ai_summary"] = ai_summary

        doc = to_raw_document(item)
        if doc.content_sha256 in existing_hashes:
            skipped += 1
            continue
        bronze.write(doc)
        existing_hashes.add(doc.content_sha256)
        stored += 1

    return {"feed": name, "fetched": len(items), "new": stored, "dup": skipped}


async def main():
    storage_root = Path(__file__).resolve().parent.parent / "bronze_storage"
    since = datetime.now(timezone.utc) - ENTRY_AGE
    existing_hashes = load_existing_hashes(storage_root)
    _log.info("existing bronze docs: %d", len(existing_hashes))

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
        tasks = [
            process_feed(name, url, client, since, existing_hashes, storage_root)
            for name, url in RSS_FEEDS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    print("\n=== Collection Results ===")
    total_new = 0
    for r in results:
        if isinstance(r, Exception):
            print(f"  error: {r}")
        elif "error" in r:
            print(f"  {r['feed']:15s} ERROR {r['error']}")
        else:
            print(f"  {r['feed']:15s} fetched={r['fetched']}, new={r['new']}, dup={r['dup']}")
            total_new += r["new"]
    print(f"\n  Total new documents: {total_new}")


if __name__ == "__main__":
    asyncio.run(main())

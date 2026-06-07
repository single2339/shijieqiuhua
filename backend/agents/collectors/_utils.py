"""Shared utilities for collection agents — extracted from HorizonBridge for reuse."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.bronze_reader import QUEUE_DB_FILENAME
from backend.collectors.horizon.models import ContentItem
from src.models.document import RawDocument
from src.processor.cleaner import clean_text


def content_item_to_document(item: ContentItem) -> RawDocument:
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
            "horizon_ai_summary": item.ai_summary,
        },
    )


def load_existing_hashes(storage: Path) -> set[str]:
    hashes: set[str] = set()
    if not storage.exists():
        return hashes
    for p in storage.rglob("*.json"):
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

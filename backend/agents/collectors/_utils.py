"""Shared utilities for collection agents — extracted from HorizonBridge for reuse."""

from __future__ import annotations

import hashlib
import json
import fcntl
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend.bronze_reader import QUEUE_DB_FILENAME
from backend.collectors.horizon.models import ContentItem
from src.models.document import RawDocument
from src.processor.cleaner import clean_text


_INLINE_BODY_LIMIT = 65536
_CHANNEL_BY_SOURCE = {
    "rss": "web",
    "hackernews": "web",
    "github": "api",
    "reddit": "social",
    "telegram": "social",
    "twitter": "social",
}


@contextmanager
def collection_lock(storage: Path):
    """Prevent concurrent collector processes from racing on dedupe/write."""
    storage.mkdir(parents=True, exist_ok=True)
    lock_path = storage / "_collection.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another collection is already running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def content_item_to_document(item: ContentItem) -> RawDocument:
    content = clean_text(item.content or "")
    fetched_at = item.fetched_at or datetime.now(timezone.utc)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    captured_at = fetched_at.isoformat()
    source_profile = item.metadata.get("source_profile")
    canonical_source = (
        str(source_profile.get("source_key") or "").strip()
        if isinstance(source_profile, dict)
        else ""
    )
    source_system = canonical_source or (
        str(item.metadata.get("feed_name") or "").strip()
        or item.author
        or item.source_type.value
    )
    source_type = item.source_type.value
    body_bytes = content.encode("utf-8")
    content_sha256 = hashlib.sha256(body_bytes).hexdigest()
    raw_document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"osint:raw:{item.id}"))
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"osint:job:{item.id}"))
    body_inline = content if len(body_bytes) < _INLINE_BODY_LIMIT else None
    body_ref = None if body_inline is not None else f"bronze://{content_sha256}"

    return RawDocument(
        raw_document_id=raw_document_id,
        job_id=job_id,
        channel=_CHANNEL_BY_SOURCE.get(source_type, "web"),
        mime_type="text/plain",
        encoding="utf-8",
        body_inline=body_inline,
        body_ref=body_ref,
        headers_summary={"collector": "horizon-bridge"},
        captured_at=captured_at,
        collector_id=f"horizon-{source_type}",
        collector_version="1.0.0",
        source_url=str(item.url) if item.url else "",
        source_system=source_system,
        content_sha256=content_sha256,
        tenant_id="default",
        body=content,
        extensions={
            "horizon_item_id": item.id,
            "horizon_title": item.title,
            "horizon_source_type": source_type,
            "horizon_metadata": item.metadata,
            "author": item.author or "",
            "source_profile": source_profile if isinstance(source_profile, dict) else {},
            "intelligence_admission": item.metadata.get("intelligence_admission", {}),
            "summary": item.ai_summary or "",
            "summarized": bool(item.ai_summary),
            "published_at": item.published_at.isoformat() if item.published_at else "",
            "original_title": str(item.metadata.get("_original_title", "")),
            "original_content": str(item.metadata.get("_original_content", "")),
        },
        ext_schema_version="1.0.0",
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
                hashes.add(f"{data.get('source_system', 'unknown')}\0{ch}")
        except (json.JSONDecodeError, OSError):
            continue
    return hashes

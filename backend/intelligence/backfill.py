"""将不可变的原始证据文档重放到专业情报模型。"""

from __future__ import annotations

import logging
from itertools import islice
from pathlib import Path

from backend.bronze_reader import BronzeDocument, iter_bronze
from backend.collectors.horizon.models import ContentItem, SourceType
from backend.intelligence.admission import AdmissionEngine
from backend.intelligence.source_policy import SourceRegistry
from backend.intelligence.store import IntelligenceStore


log = logging.getLogger(__name__)


def _content_item_from_bronze(document: BronzeDocument) -> ContentItem:
    extensions = document.extensions if isinstance(document.extensions, dict) else {}
    metadata = extensions.get("horizon_metadata", {})
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata.setdefault("feed_name", document.source_system)
    source_value = str(extensions.get("horizon_source_type") or "rss")
    try:
        source_type = SourceType(source_value)
    except ValueError:
        source_type = SourceType.RSS
    original_title = str(extensions.get("original_title") or "").strip()
    title = original_title or str(extensions.get("horizon_title") or "").strip()
    if not title:
        title = document.text[:160].splitlines()[0]
    original_content = str(extensions.get("original_content") or "").strip()
    content = original_content or document.text
    timestamp = str(extensions.get("published_at") or document.captured_at)
    url = document.source_url or f"https://bronze.invalid/{document.raw_document_id}"
    return ContentItem(
        id=str(extensions.get("horizon_item_id") or document.raw_document_id),
        source_type=source_type,
        title=title,
        url=url,
        content=content,
        author=str(extensions.get("author") or ""),
        published_at=timestamp,
        fetched_at=document.captured_at or timestamp,
        metadata=metadata,
    )


def backfill_intelligence(
    storage_root: str | Path,
    *,
    limit: int = 0,
) -> dict[str, int]:
    """在不修改原始证据文档的前提下回填标准证据层和情报产品层。"""
    storage = Path(storage_root)
    store = IntelligenceStore(storage)
    existing = store.decision_ids()
    engine = AdmissionEngine()
    registry = SourceRegistry.default()
    stats = {
        "scanned": 0,
        "accepted": 0,
        "quarantined": 0,
        "rejected": 0,
        "skipped": 0,
        "errors": 0,
    }
    documents = iter_bronze(storage)
    if limit:
        documents = islice(documents, limit)
    for document in documents:
        stats["scanned"] += 1
        if document.raw_document_id in existing:
            stats["skipped"] += 1
            continue
        try:
            item = _content_item_from_bronze(document)
            profile = registry.resolve(item)
            decision = engine.evaluate(item, profile)
            store.record_document(document.raw_document_id, item, profile, decision)
            stats[decision.status.value] += 1
        except Exception as exc:
            stats["errors"] += 1
            log.warning("无法回填原始证据文档 %s：%s", document.raw_document_id, exc)
    return stats

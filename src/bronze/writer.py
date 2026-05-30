from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models.document import RawDocument


class BronzeWriter:
    def __init__(self, storage_root: str | Path) -> None:
        self._root = Path(storage_root)

    def write(self, doc: RawDocument) -> Path:
        captured = datetime.fromisoformat(doc.captured_at)
        partition = captured.strftime("%Y-%m-%d")
        dest_dir = self._root / partition / doc.source_system.replace("/", "_")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{doc.raw_document_id}.json"

        payload = {
            "$schema": "https://osint-network.local/schemas/raw-document.schema.json",
            "raw_document_id": doc.raw_document_id,
            "job_id": doc.job_id,
            "channel": doc.channel,
            "mime_type": doc.mime_type,
            "encoding": doc.encoding,
            "body_ref": doc.body_ref,
            "body_inline": doc.body_inline,
            "headers_summary": doc.headers_summary,
            "captured_at": doc.captured_at,
            "collector_id": doc.collector_id,
            "collector_version": doc.collector_version,
            "source_url": doc.source_url,
            "source_system": doc.source_system,
            "content_sha256": doc.content_sha256,
            "classification": doc.classification,
            "extensions": doc.extensions,
            "tenant_id": doc.tenant_id,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

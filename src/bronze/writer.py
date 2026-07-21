from __future__ import annotations

import json
import os
import tempfile
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
            "headers_summary": doc.headers_summary,
            "captured_at": doc.captured_at,
            "collector_id": doc.collector_id,
            "collector_version": doc.collector_version,
            "source_url": doc.source_url,
            "source_system": doc.source_system,
            "content_sha256": doc.content_sha256,
            "classification": doc.classification,
            "extensions": doc.extensions,
            "ext_schema_version": doc.ext_schema_version,
            "tenant_id": doc.tenant_id,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        if doc.body_ref:
            payload["body_ref"] = doc.body_ref
            body = doc.body_inline if doc.body_inline is not None else doc.body
            blob_path = self._blob_path(doc.body_ref)
            if body is not None and blob_path is not None:
                self._atomic_write(blob_path, body.encode(doc.encoding or "utf-8"))
        elif doc.body_inline is not None:
            payload["body_inline"] = doc.body_inline
        payload = {k: v for k, v in payload.items() if v is not None}
        self._atomic_write(
            dest,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return dest

    def _blob_path(self, body_ref: str) -> Path | None:
        """Map writer-owned bronze references to files below ``_blobs``."""
        prefix = "bronze://"
        if not body_ref.startswith(prefix):
            return None
        key = body_ref[len(prefix):]
        if not key or Path(key).name != key:
            return None
        return self._root / "_blobs" / key

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, str(path))
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

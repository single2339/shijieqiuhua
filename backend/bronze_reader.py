from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List


class BronzeDocument:
    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.raw_document_id: str = raw.get("raw_document_id", "")
        self.body_inline: str = raw.get("body_inline") or ""
        self.body_ref: str | None = raw.get("body_ref")
        self.source_system: str = raw.get("source_system", "unknown")
        self.captured_at: str = raw.get("captured_at", "")
        self.source_url: str = raw.get("source_url", "")
        self.content_sha256: str = raw.get("content_sha256", "")
        self.channel: str = raw.get("channel", "")
        self.collector_id: str = raw.get("collector_id", "")
        self.collector_version: str = raw.get("collector_version", "")
        self.extensions: dict = raw.get("extensions", {})

    @property
    def text(self) -> str:
        return self.body_inline or ""


def scan_bronze(storage_root: str | Path) -> List[BronzeDocument]:
    root = Path(storage_root)
    docs: list[BronzeDocument] = []

    if not root.exists():
        return docs

    for json_file in sorted(root.rglob("*.json")):
        if json_file.name == "queue.db":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            docs.append(BronzeDocument(data))
        except (json.JSONDecodeError, OSError):
            continue

    return docs


async def scan_bronze_async(storage_root: str | Path) -> List[BronzeDocument]:
    """Async wrapper: runs scan_bronze in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(scan_bronze, storage_root)

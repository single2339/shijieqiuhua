from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import List
from urllib.parse import unquote, urlparse


QUEUE_DB_FILENAME = "queue.db"
MERGE_INDEX_FILENAME = "_merge_index.json"


class BronzeDocument:
    def __init__(self, raw: dict, storage_root: str | Path | None = None) -> None:
        self.raw = raw
        self._storage_root = Path(storage_root) if storage_root is not None else None
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
        if self.raw.get("body_inline") is not None:
            return self.raw.get("body_inline") or ""
        return self.read_body()

    def read_body(self) -> str:
        """Read a referenced body, retaining inline/legacy compatibility."""
        if self.raw.get("body_inline") is not None:
            return self.raw.get("body_inline") or ""
        path = self._resolve_body_ref()
        if path is None:
            return ""
        try:
            return path.read_text(encoding=self.raw.get("encoding") or "utf-8")
        except (OSError, UnicodeError):
            return ""

    def _resolve_body_ref(self) -> Path | None:
        if not self.body_ref:
            return None
        parsed = urlparse(self.body_ref)
        if parsed.scheme == "bronze":
            if self._storage_root is None:
                return None
            key = unquote(parsed.netloc + parsed.path).lstrip("/")
            if not key or Path(key).name != key:
                return None
            candidates = (
                self._storage_root / "_blobs" / key,
                self._storage_root / key,
            )
            return next((candidate for candidate in candidates if candidate.is_file()), None)
        if parsed.scheme == "file":
            # 原始证据读取器不得把数据中提供的引用转换为任意本地文件读取。
            return None
        if self._storage_root is None:
            return None
        ref_path = Path(self.body_ref)
        return ref_path if ref_path.is_absolute() else self._storage_root / ref_path


def iter_bronze(
    storage_root: str | Path,
    *,
    sort_paths: bool = False,
) -> Iterator[BronzeDocument]:
    root = Path(storage_root)
    if not root.exists():
        return

    json_files = root.rglob("*.json")
    paths = sorted(json_files) if sort_paths else json_files
    for json_file in paths:
        if json_file.name in (QUEUE_DB_FILENAME, MERGE_INDEX_FILENAME):
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            yield BronzeDocument(data, storage_root=root)
        except (json.JSONDecodeError, OSError):
            continue


def scan_bronze(storage_root: str | Path) -> List[BronzeDocument]:
    return list(iter_bronze(storage_root, sort_paths=True))


async def scan_bronze_async(storage_root: str | Path) -> List[BronzeDocument]:
    """异步包装：在线程池执行扫描，避免阻塞事件循环。"""
    return await asyncio.to_thread(scan_bronze, storage_root)

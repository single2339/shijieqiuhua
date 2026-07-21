"""Persistent, lazy metadata catalogue for Bronze documents.

The collector keeps source bodies in Bronze storage.  Super-analysis should not
materialise that entire corpus on every request, so this catalogue stores only
the metadata and a short retrieval excerpt needed to choose candidate IDs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import jieba

from backend.bronze_reader import BronzeDocument, MERGE_INDEX_FILENAME, QUEUE_DB_FILENAME

CATALOG_FILENAME = "_analysis_catalog.json"
CATALOG_VERSION = 2
CATALOG_EXCERPT_CHARS = 1000
CATALOG_STALE_CHECK_INTERVAL_SECONDS = float(
    os.getenv("CATALOG_STALE_CHECK_INTERVAL_SECONDS", "30")
)


class BronzeCatalog:
    def __init__(self, storage_root: str | Path) -> None:
        self.root = Path(storage_root)
        self.path = self.root / CATALOG_FILENAME
        self._entries: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._last_stale_check = 0.0

    def ensure(self) -> None:
        if not self._loaded:
            self._load()
        now = time.monotonic()
        if not self._entries:
            self._rebuild()
            self._last_stale_check = now
            return
        if now - self._last_stale_check < CATALOG_STALE_CHECK_INTERVAL_SECONDS:
            return
        self._last_stale_check = now
        if self._is_stale():
            self._rebuild()

    @property
    def size(self) -> int:
        self.ensure()
        return len(self._entries)

    def _load(self) -> None:
        self._loaded = True
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("version") != CATALOG_VERSION:
                return
            entries = payload.get("entries", {})
            if isinstance(entries, dict):
                self._entries = {
                    str(body_hash): entry
                    for body_hash, entry in entries.items()
                    if isinstance(entry, dict) and entry.get("path")
                }
        except (OSError, json.JSONDecodeError):
            self._entries = {}

    def _document_paths(self):
        if not self.root.exists():
            return
        for path in self.root.rglob("*.json"):
            if path.name in {QUEUE_DB_FILENAME, MERGE_INDEX_FILENAME, CATALOG_FILENAME}:
                continue
            yield path

    def _is_stale(self) -> bool:
        if not self.path.is_file():
            return True
        try:
            catalog_mtime = self.path.stat().st_mtime_ns
        except OSError:
            return True
        # This enumerates paths and stats only.  It deliberately does not open
        # every JSON document or any body blobs during normal requests.
        for path in self._document_paths() or ():
            try:
                if path.stat().st_mtime_ns > catalog_mtime:
                    return True
            except OSError:
                return True
        return False

    def _rebuild(self) -> None:
        indexed = self._entries_from_sqlite_index()
        entries, indexed_paths = indexed if indexed is not None else ({}, set())
        for path in self._document_paths() or ():
            if path.resolve() in indexed_paths:
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                doc = BronzeDocument(raw, storage_root=self.root)
                text = doc.text
                if not text:
                    continue
                body_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
                extensions = doc.extensions if isinstance(doc.extensions, dict) else {}
                entries[body_hash] = {
                    "path": str(path.relative_to(self.root)),
                    "raw_document_id": doc.raw_document_id,
                    "captured_at": doc.captured_at,
                    "source_system": doc.source_system,
                    "source_url": doc.source_url,
                    "title": str(extensions.get("summary") or extensions.get("horizon_title") or text[:80]).split("\n")[0],
                    "text_excerpt": text[:CATALOG_EXCERPT_CHARS],
                }
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
        self._entries = entries
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                {"version": CATALOG_VERSION, "entries": entries},
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def _entries_from_sqlite_index(
        self,
    ) -> tuple[dict[str, dict[str, Any]], set[Path]] | None:
        """Build retrieval metadata from the existing Bronze SQLite index."""
        db_path = self.root / "_index.db"
        if not db_path.is_file():
            return None

        root = self.root.resolve()
        entries: dict[str, dict[str, Any]] = {}
        indexed_paths: set[Path] = set()
        try:
            connection = sqlite3.connect(str(db_path))
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(
                    "SELECT raw_document_id, captured_at, source_system, source_url, "
                    "title, body_text, body_size, file_path FROM bronze_index"
                )
                for row in rows:
                    path = Path(str(row["file_path"] or ""))
                    if not path.is_absolute():
                        path = (Path.cwd() / path).resolve()
                    try:
                        relative_path = str(path.relative_to(root))
                    except ValueError:
                        continue
                    indexed_paths.add(path)

                    text = str(row["body_text"] or "")
                    if int(row["body_size"] or 0) > len(text.encode("utf-8")):
                        try:
                            raw = json.loads(path.read_text(encoding="utf-8"))
                            if isinstance(raw, dict):
                                text = BronzeDocument(raw, storage_root=self.root).text
                        except (OSError, UnicodeError, json.JSONDecodeError):
                            continue
                    if not text:
                        continue

                    body_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
                    entries[body_hash] = {
                        "path": relative_path,
                        "raw_document_id": str(row["raw_document_id"] or ""),
                        "captured_at": str(row["captured_at"] or ""),
                        "source_system": str(row["source_system"] or ""),
                        "source_url": str(row["source_url"] or ""),
                        "title": str(row["title"] or text[:80]).split("\n")[0],
                        "text_excerpt": text[:CATALOG_EXCERPT_CHARS],
                    }
            finally:
                connection.close()
        except (OSError, sqlite3.Error):
            return None
        return (entries, indexed_paths) if indexed_paths else None

    def hydrate(self, body_hashes: list[str] | set[str]) -> list[BronzeDocument]:
        self.ensure()
        documents: list[BronzeDocument] = []
        for body_hash in body_hashes:
            entry = self._entries.get(body_hash)
            if not entry:
                continue
            path = self.root / str(entry["path"])
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    documents.append(BronzeDocument(raw, storage_root=self.root))
            except (OSError, json.JSONDecodeError):
                continue
        return documents

    def entries_for(self, body_hashes: list[str] | set[str]) -> dict[str, dict[str, Any]]:
        self.ensure()
        return {
            body_hash: self._entries[body_hash]
            for body_hash in body_hashes
            if body_hash in self._entries
        }

    def search_tokens(
        self,
        query: str,
        *,
        limit: int = 200,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        """Return candidate hashes using only persisted excerpts, never bodies."""
        self.ensure()
        query = query.strip().lower()
        if not query:
            return []
        tokens = {query}
        tokens.update(part for part in query.replace("，", " ").replace("。", " ").split() if len(part) > 1)
        tokens.update(part.strip().lower() for part in jieba.cut_for_search(query) if len(part.strip()) > 1)
        scored: list[tuple[int, str]] = []
        for body_hash, entry in self._entries.items():
            captured = str(entry.get("captured_at") or "")[:10]
            if start_date and captured < start_date:
                continue
            if end_date and captured > end_date:
                continue
            text = f"{entry.get('title', '')} {entry.get('text_excerpt', '')}".lower()
            score = sum(1 for token in tokens if token in text)
            if score:
                scored.append((score, body_hash))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [body_hash for _score, body_hash in scored[:limit]]

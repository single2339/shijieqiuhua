"""原始证据文档的磁盘检索目录。

原始证据层 JSON 文件仍是事实源。本目录仅在 SQLite 中存储“超级分析”需要的
少量元数据和摘要，避免将大型语料库完整加载为 Python 字典。
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

import jieba

from backend.bronze_reader import BronzeDocument, MERGE_INDEX_FILENAME, QUEUE_DB_FILENAME

CATALOG_FILENAME = "_analysis_catalog.db"
CATALOG_VERSION = 3
CATALOG_EXCERPT_CHARS = 1000
CATALOG_STALE_CHECK_INTERVAL_SECONDS = float(
    os.getenv("CATALOG_STALE_CHECK_INTERVAL_SECONDS", "30")
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_entries (
    body_hash TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    raw_document_id TEXT NOT NULL DEFAULT '',
    captured_at TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    text_excerpt TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_catalog_captured_at
ON catalog_entries(captured_at);
"""

_INSERT_SQL = """
INSERT OR REPLACE INTO catalog_entries (
    body_hash, path, raw_document_id, captured_at, source_system,
    source_url, title, text_excerpt
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


class BronzeCatalog:
    def __init__(self, storage_root: str | Path) -> None:
        self.root = Path(storage_root)
        self.path = self.root / CATALOG_FILENAME
        self._loaded = False
        self._last_stale_check = 0.0

    def _connect(self, path: Path | None = None) -> sqlite3.Connection:
        connection = sqlite3.connect(str(path or self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA cache_size=-8000")
        return connection

    def ensure(self) -> None:
        now = time.monotonic()
        if not self._loaded:
            self._loaded = True
            if not self._is_ready():
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
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT COUNT(*) FROM catalog_entries").fetchone()
                return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0

    def _is_ready(self) -> bool:
        if not self.path.is_file():
            return False
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM catalog_meta WHERE key = 'version'"
                ).fetchone()
                return bool(row and int(row[0]) == CATALOG_VERSION)
        except (sqlite3.Error, ValueError):
            return False

    def _source_signature(self) -> str:
        parts: list[str] = []
        for candidate in (
            self.root / "_index.db",
            self.root / "_index.db-wal",
        ):
            try:
                stat = candidate.stat()
            except OSError:
                continue
            parts.append(f"{candidate.name}:{stat.st_mtime_ns}:{stat.st_size}")
        return "|".join(parts)

    def _document_paths(self) -> Iterable[Path]:
        if not self.root.exists():
            return
        for path in self.root.rglob("*.json"):
            if path.name in {
                QUEUE_DB_FILENAME,
                MERGE_INDEX_FILENAME,
                "_analysis_catalog.json",
            }:
                continue
            yield path

    def _is_stale(self) -> bool:
        if not self._is_ready():
            return True
        signature = self._source_signature()
        if signature:
            try:
                with self._connect() as connection:
                    row = connection.execute(
                        "SELECT value FROM catalog_meta WHERE key = 'source_signature'"
                    ).fetchone()
                return not row or row[0] != signature
            except sqlite3.Error:
                return True

        try:
            catalog_mtime = self.path.stat().st_mtime_ns
        except OSError:
            return True
        for path in self._document_paths() or ():
            try:
                if path.stat().st_mtime_ns > catalog_mtime:
                    return True
            except OSError:
                return True
        return False

    def _rebuild(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        connection = self._connect(temporary)
        try:
            connection.executescript(_SCHEMA)
            has_source_index = self._insert_from_sqlite_index(connection)
            for path in self._document_paths() or ():
                if has_source_index:
                    try:
                        relative_path = str(path.resolve().relative_to(self.root.resolve()))
                    except (OSError, ValueError):
                        continue
                    indexed = connection.execute(
                        "SELECT 1 FROM source_paths WHERE path = ?",
                        (relative_path,),
                    ).fetchone()
                    if indexed:
                        continue
                row = self._entry_from_path(path)
                if row is not None:
                    connection.execute(_INSERT_SQL, row)

            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta (key, value) VALUES (?, ?)",
                ("version", str(CATALOG_VERSION)),
            )
            connection.execute(
                "INSERT OR REPLACE INTO catalog_meta (key, value) VALUES (?, ?)",
                ("source_signature", self._source_signature()),
            )
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, self.path)

    def _insert_from_sqlite_index(self, destination: sqlite3.Connection) -> bool:
        db_path = self.root / "_index.db"
        if not db_path.is_file():
            return False

        root = self.root.resolve()
        source: sqlite3.Connection | None = None
        batch: list[tuple[str, ...]] = []
        path_batch: list[tuple[str]] = []
        try:
            destination.execute(
                "CREATE TEMP TABLE source_paths (path TEXT PRIMARY KEY) WITHOUT ROWID"
            )
            source = sqlite3.connect(str(db_path))
            source.row_factory = sqlite3.Row
            rows = source.execute(
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
                path_batch.append((relative_path,))
                if len(path_batch) >= 1000:
                    destination.executemany(
                        "INSERT OR IGNORE INTO source_paths (path) VALUES (?)",
                        path_batch,
                    )
                    path_batch.clear()

                text = str(row["body_text"] or "")
                if int(row["body_size"] or 0) > len(text.encode("utf-8")):
                    text = self._read_document_text(path)
                if not text:
                    continue
                batch.append((
                    hashlib.md5(text.encode("utf-8")).hexdigest(),
                    relative_path,
                    str(row["raw_document_id"] or ""),
                    str(row["captured_at"] or ""),
                    str(row["source_system"] or ""),
                    str(row["source_url"] or ""),
                    str(row["title"] or text[:80]).split("\n")[0],
                    text[:CATALOG_EXCERPT_CHARS],
                ))
                if len(batch) >= 1000:
                    destination.executemany(_INSERT_SQL, batch)
                    batch.clear()
            if batch:
                destination.executemany(_INSERT_SQL, batch)
            if path_batch:
                destination.executemany(
                    "INSERT OR IGNORE INTO source_paths (path) VALUES (?)",
                    path_batch,
                )
        except (OSError, sqlite3.Error):
            return False
        finally:
            if source is not None:
                source.close()
        return True

    def _read_document_text(self, path: Path) -> str:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return BronzeDocument(raw, storage_root=self.root).text
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        return ""

    def _entry_from_path(self, path: Path) -> tuple[str, ...] | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            doc = BronzeDocument(raw, storage_root=self.root)
            text = doc.text
            if not text:
                return None
            extensions = doc.extensions if isinstance(doc.extensions, dict) else {}
            title = str(
                extensions.get("summary")
                or extensions.get("horizon_title")
                or text[:80]
            ).split("\n")[0]
            return (
                hashlib.md5(text.encode("utf-8")).hexdigest(),
                str(path.relative_to(self.root)),
                doc.raw_document_id,
                doc.captured_at,
                doc.source_system,
                doc.source_url,
                title,
                text[:CATALOG_EXCERPT_CHARS],
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return None

    def entries_for(self, body_hashes: list[str] | set[str]) -> dict[str, dict[str, Any]]:
        self.ensure()
        hashes = list(dict.fromkeys(body_hashes))
        entries: dict[str, dict[str, Any]] = {}
        try:
            with self._connect() as connection:
                for offset in range(0, len(hashes), 400):
                    chunk = hashes[offset:offset + 400]
                    if not chunk:
                        continue
                    placeholders = ",".join("?" for _ in chunk)
                    rows = connection.execute(
                        f"SELECT * FROM catalog_entries WHERE body_hash IN ({placeholders})",
                        chunk,
                    )
                    for row in rows:
                        entries[str(row["body_hash"])] = {
                            key: row[key]
                            for key in row.keys()
                            if key != "body_hash"
                        }
        except sqlite3.Error:
            return {}
        return entries

    def hydrate(self, body_hashes: list[str] | set[str]) -> list[BronzeDocument]:
        hashes = list(dict.fromkeys(body_hashes))
        entries = self.entries_for(hashes)
        documents: list[BronzeDocument] = []
        for body_hash in hashes:
            entry = entries.get(body_hash)
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

    def search_tokens(
        self,
        query: str,
        *,
        limit: int = 200,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        """Search persisted excerpts in SQLite without loading the corpus."""
        self.ensure()
        query = query.strip().lower()
        if not query or limit <= 0:
            return []
        tokens = {query}
        tokens.update(
            part for part in query.replace("，", " ").replace("。", " ").split()
            if len(part) > 1
        )
        tokens.update(
            part.strip().lower()
            for part in jieba.cut_for_search(query)
            if len(part.strip()) > 1
        )
        ordered_tokens = sorted(tokens, key=lambda token: (-len(token), token))[:12]
        patterns = [
            "%" + token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            for token in ordered_tokens
        ]
        score_parts = [
            "CASE WHEN (title || ' ' || text_excerpt) LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END"
            for _ in patterns
        ]
        match_parts = [
            "(title || ' ' || text_excerpt) LIKE ? ESCAPE '\\'"
            for _ in patterns
        ]
        conditions: list[str] = []
        condition_params: list[Any] = []
        if start_date:
            conditions.append("captured_at >= ?")
            condition_params.append(start_date)
        if end_date:
            conditions.append("captured_at <= ?")
            condition_params.append(f"{end_date}T99")
        conditions.append("(" + " OR ".join(match_parts) + ")")
        sql = (
            "SELECT body_hash, (" + " + ".join(score_parts) + ") AS relevance "
            "FROM catalog_entries WHERE " + " AND ".join(conditions) + " "
            "ORDER BY relevance DESC, body_hash LIMIT ?"
        )
        params = [*patterns, *condition_params, *patterns, int(limit)]
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, params).fetchall()
            return [str(row["body_hash"]) for row in rows]
        except sqlite3.Error:
            return []

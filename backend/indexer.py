"""SQLite index layer for bronze storage.

Provides indexed queries over JSON files without scanning the filesystem
or parsing JSON on every request. The JSON files remain source of truth;
SQLite stores key metadata + body for fast retrieval.

Usage::

    indexer = Indexer(Path("bronze_storage"))
    indexer.build_index()           # first run: scan all JSON → SQLite
    indexer.incremental_update()    # subsequent: only index new files
    docs = indexer.query(start_date="2026-01-01", layer="military")
"""

from __future__ import annotations

import json
import fcntl
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.bronze_reader import BronzeDocument, MERGE_INDEX_FILENAME, QUEUE_DB_FILENAME

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze_index (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_document_id TEXT NOT NULL DEFAULT '',
    captured_at TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    layer TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    body_ref TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    extensions_json TEXT NOT NULL DEFAULT '{}',
    file_path TEXT NOT NULL DEFAULT '' UNIQUE,
    body_size INTEGER NOT NULL DEFAULT 0,
    file_mtime_ns INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_captured_at ON bronze_index(captured_at);
CREATE INDEX IF NOT EXISTS idx_layer ON bronze_index(layer);
CREATE INDEX IF NOT EXISTS idx_country ON bronze_index(country);
CREATE INDEX IF NOT EXISTS idx_sha256 ON bronze_index(content_sha256);
CREATE INDEX IF NOT EXISTS idx_source ON bronze_index(source_system);
"""

_INDEX_COLUMNS = (
    "raw_document_id", "captured_at", "source_system", "source_url",
    "content_sha256", "layer", "country", "city", "title", "summary",
    "body_ref", "body_text", "extensions_json", "file_path", "body_size",
    "file_mtime_ns", "file_size", "indexed_at",
)
_INSERT_SQL = (
    f"INSERT OR REPLACE INTO bronze_index ({', '.join(_INDEX_COLUMNS)}) "
    f"VALUES ({','.join('?' for _ in _INDEX_COLUMNS)})"
)


class Indexer:
    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_root / "_index.db"
        # Per-thread connections: a single sqlite3.Connection is NOT safe for
        # concurrent use across the thread-pool threads that serve requests and
        # the background reindex loop. WAL mode allows concurrent readers + one
        # writer when each thread holds its own connection.
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")
            lock_path = self.storage_root / "_index.schema.lock"
            with lock_path.open("a+", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    self._ensure_schema(conn)
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            self._local.conn = conn
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'bronze_index'"
        ).fetchone()
        if table is None:
            conn.executescript(SCHEMA)
            conn.commit()
            return

        columns = conn.execute("PRAGMA table_info(bronze_index)").fetchall()
        names = {row["name"] for row in columns}
        raw_is_primary_key = any(
            row["name"] == "raw_document_id" and row["pk"] == 1
            for row in columns
        )
        if "record_id" not in names or raw_is_primary_key:
            self._migrate_legacy_schema(conn)
            return

        conn.executescript(SCHEMA)
        for name, definition in (
            ("body_ref", "TEXT NOT NULL DEFAULT ''"),
            ("file_mtime_ns", "INTEGER NOT NULL DEFAULT 0"),
            ("file_size", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in names:
                conn.execute(f"ALTER TABLE bronze_index ADD COLUMN {name} {definition}")
        conn.commit()

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        """Rebuild old raw-ID-primary-key tables without dropping their rows."""
        legacy_rows = [
            dict(row) for row in conn.execute("SELECT * FROM bronze_index").fetchall()
        ]
        index_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = 'bronze_index' "
                "AND name NOT LIKE 'sqlite_autoindex%'"
            ).fetchall()
        ]
        legacy_table = f"bronze_index_legacy_{uuid.uuid4().hex}"
        conn.execute(f'ALTER TABLE bronze_index RENAME TO "{legacy_table}"')
        for index_name in index_names:
            safe_name = index_name.replace('"', '""')
            conn.execute(f'DROP INDEX IF EXISTS "{safe_name}"')
        conn.executescript(SCHEMA)

        seen_paths: set[str] = set()
        for row_number, legacy in enumerate(legacy_rows):
            path = str(legacy.get("file_path") or "")
            if not path or path in seen_paths:
                path = (
                    f".legacy/{row_number}/"
                    f"{legacy.get('raw_document_id') or 'unknown'}"
                )
            seen_paths.add(path)
            try:
                stat = Path(path).stat()
                mtime_ns = stat.st_mtime_ns
                file_size = stat.st_size
            except OSError:
                mtime_ns = 0
                file_size = 0
            row = (
                str(legacy.get("raw_document_id") or ""),
                str(legacy.get("captured_at") or ""),
                str(legacy.get("source_system") or ""),
                str(legacy.get("source_url") or ""),
                str(legacy.get("content_sha256") or ""),
                str(legacy.get("layer") or ""),
                str(legacy.get("country") or ""),
                str(legacy.get("city") or ""),
                str(legacy.get("title") or ""),
                str(legacy.get("summary") or ""),
                str(legacy.get("body_ref") or ""),
                str(legacy.get("body_text") or ""),
                str(legacy.get("extensions_json") or "{}"),
                path,
                int(legacy.get("body_size") or 0),
                mtime_ns,
                file_size,
                str(legacy.get("indexed_at") or ""),
            )
            self._insert_row(row, conn)

        conn.execute(f'DROP TABLE "{legacy_table}"')
        conn.commit()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ── build / update ──

    def build_index(self) -> int:
        """Full rebuild: scan all JSON files and index them. Returns count."""
        conn = self._get_conn()
        conn.execute("DELETE FROM bronze_index")
        return self._index_files(self.storage_root.rglob("*.json"), conn)

    def incremental_update(self) -> int:
        """Index new/modified files and remove deleted files.

        The return value counts newly indexed or re-indexed files. File path,
        size, and nanosecond mtime are persisted so unchanged files remain
        cheap to skip while atomic JSON replacement is detected.
        """
        conn = self._get_conn()
        current_files = [
            json_file
            for json_file in sorted(self.storage_root.rglob("*.json"))
            if json_file.name not in (QUEUE_DB_FILENAME, MERGE_INDEX_FILENAME)
        ]
        existing = {
            row["file_path"]: row
            for row in conn.execute(
                "SELECT file_path, file_mtime_ns, file_size "
                "FROM bronze_index WHERE file_path != ''"
            )
        }
        current_paths = {str(path) for path in current_files}
        changed_count = 0
        for json_file in current_files:
            path_key = str(json_file)
            try:
                stat = json_file.stat()
            except OSError:
                continue
            previous = existing.get(path_key)
            if previous is not None and (
                previous["file_mtime_ns"] == stat.st_mtime_ns
                and previous["file_size"] == stat.st_size
            ):
                continue
            if self._index_one(json_file, conn):
                changed_count += 1

        deleted = [path for path in existing if path not in current_paths]
        for path in deleted:
            conn.execute("DELETE FROM bronze_index WHERE file_path = ?", (path,))
        if changed_count or deleted:
            conn.commit()
        return changed_count

    def _insert_row(self, row: tuple, conn: sqlite3.Connection) -> None:
        conn.execute(_INSERT_SQL, row)

    def _index_files(self, files, conn: sqlite3.Connection) -> int:
        count = 0
        batch: list[tuple] = []
        for json_file in sorted(files):
            if json_file.name in (QUEUE_DB_FILENAME, MERGE_INDEX_FILENAME):
                continue
            row = self._make_row(json_file)
            if row:
                batch.append(row)
                count += 1
            if len(batch) >= 500:
                conn.executemany(_INSERT_SQL, batch)
                batch.clear()
        if batch:
            conn.executemany(_INSERT_SQL, batch)
        conn.commit()
        return count

    def _index_one(self, json_file: Path, conn: sqlite3.Connection) -> bool:
        row = self._make_row(json_file)
        if row is None:
            return False
        conn.execute("DELETE FROM bronze_index WHERE file_path = ?", (str(json_file),))
        self._insert_row(row, conn)
        return True

    def _make_row(self, json_file: Path) -> tuple | None:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        raw_id = data.get("raw_document_id", "") or json_file.stem
        captured = data.get("captured_at", "")
        source_system = data.get("source_system", "") or data.get("collector_id", "")
        source_url = data.get("source_url", "")
        sha = data.get("content_sha256", "")
        bronze_doc = BronzeDocument(data, storage_root=self.storage_root)
        body = bronze_doc.text
        body_ref = data.get("body_ref", "") or ""

        ext = data.get("extensions", {}) or {}
        if not isinstance(ext, dict):
            ext = {}
        meta = ext.get("horizon_metadata", {}) or {}
        if not isinstance(meta, dict):
            meta = {}

        layer = meta.get("layer", "")
        country = meta.get("location_country", "")
        city = meta.get("location_city", "")
        title = ext.get("horizon_title", "") or ext.get("summary", "") or body[:80]
        summary = ext.get("summary", "") or body[:300]
        try:
            stat = json_file.stat()
        except OSError:
            return None

        return (
            raw_id,
            captured,
            source_system,
            source_url,
            sha,
            layer,
            country,
            city,
            title.split("\n")[0][:200],
            summary[:500],
            body_ref,
            body[:10000],
            json.dumps(ext, ensure_ascii=False),
            str(json_file),
            len(body.encode("utf-8")),
            stat.st_mtime_ns,
            stat.st_size,
            datetime.now(timezone.utc).isoformat(),
        )

    # ── query ──

    def query(
        self,
        start_date: str = "",
        end_date: str = "",
        layer: str = "",
        country: str = "",
        limit: int = 0,
    ) -> list[BronzeDocument]:
        conn = self._get_conn()
        where: list[str] = ["1=1"]
        params: list[str | int] = []

        if start_date:
            where.append("captured_at >= ?")
            params.append(start_date)
        if end_date:
            where.append("captured_at <= ?")
            params.append(end_date + "Z")
        if layer:
            where.append("layer = ?")
            params.append(layer)
        if country:
            where.append("country LIKE ?")
            params.append(f"%{country}%")

        sql = f"SELECT * FROM bronze_index WHERE {' AND '.join(where)} ORDER BY captured_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_doc(r) for r in rows]

    def get_by_id(self, raw_document_id: str) -> BronzeDocument | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM bronze_index WHERE raw_document_id = ? "
            "ORDER BY record_id DESC LIMIT 1",
            (raw_document_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_doc(row)

    def get_all_hashes(self) -> set[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT content_sha256 FROM bronze_index WHERE content_sha256 != ''"
        ).fetchall()
        return {r[0] for r in rows}

    def get_all(self) -> list[BronzeDocument]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM bronze_index ORDER BY captured_at DESC"
        ).fetchall()
        return [self._row_to_doc(r) for r in rows]

    def count(self) -> int:
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM bronze_index").fetchone()[0]

    def get_available_dates(self) -> list[str]:
        """Return distinct dates from the index, sorted newest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT substr(captured_at, 1, 10) AS d FROM bronze_index WHERE captured_at != '' ORDER BY d DESC"
        ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        conn = self._get_conn()
        return {
            "total": conn.execute("SELECT COUNT(*) FROM bronze_index").fetchone()[0],
            "layers": {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT layer, COUNT(*) FROM bronze_index WHERE layer != '' GROUP BY layer"
                ).fetchall()
            },
            "countries": {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT country, COUNT(*) FROM bronze_index WHERE country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20"
                ).fetchall()
            },
        }

    # ── doc reconstruction ──

    def _row_to_doc(self, row: sqlite3.Row) -> BronzeDocument:
        extensions = {}
        try:
            extensions = json.loads(row["extensions_json"] or "{}")
        except json.JSONDecodeError:
            pass

        raw = {
            "raw_document_id": row["raw_document_id"],
            "captured_at": row["captured_at"],
            "source_system": row["source_system"],
            "source_url": row["source_url"],
            "content_sha256": row["content_sha256"],
            "body_ref": row["body_ref"],
            "body_inline": None if row["body_ref"] else row["body_text"],
            "extensions": extensions,
            "channel": "",
            "collector_id": "",
            "collector_version": "",
        }
        return BronzeDocument(raw, storage_root=self.storage_root)

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
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.bronze_reader import BronzeDocument, MERGE_INDEX_FILENAME, QUEUE_DB_FILENAME

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze_index (
    raw_document_id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    layer TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    extensions_json TEXT NOT NULL DEFAULT '{}',
    file_path TEXT NOT NULL DEFAULT '',
    body_size INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_captured_at ON bronze_index(captured_at);
CREATE INDEX IF NOT EXISTS idx_layer ON bronze_index(layer);
CREATE INDEX IF NOT EXISTS idx_country ON bronze_index(country);
CREATE INDEX IF NOT EXISTS idx_sha256 ON bronze_index(content_sha256);
CREATE INDEX IF NOT EXISTS idx_source ON bronze_index(source_system);
"""


class Indexer:
    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root)
        self.db_path = self.storage_root / "_index.db"
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-8000")
            self._conn.executescript(SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── build / update ──

    def build_index(self) -> int:
        """Full rebuild: scan all JSON files and index them. Returns count."""
        conn = self._get_conn()
        conn.execute("DELETE FROM bronze_index")
        return self._index_files(self.storage_root.rglob("*.json"), conn)

    def incremental_update(self) -> int:
        """Index only new or modified files. Returns count of new files."""
        conn = self._get_conn()
        existing = set(
            row[0] for row in conn.execute("SELECT raw_document_id FROM bronze_index")
        )
        new_count = 0
        for json_file in sorted(self.storage_root.rglob("*.json")):
            if json_file.name in (QUEUE_DB_FILENAME, MERGE_INDEX_FILENAME):
                continue
            did = json_file.stem
            if did in existing:
                continue
            if self._index_one(json_file, conn):
                new_count += 1
        if new_count:
            conn.commit()
        return new_count

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
                conn.executemany(
                    "INSERT OR REPLACE INTO bronze_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                batch.clear()
        if batch:
            conn.executemany(
                "INSERT OR REPLACE INTO bronze_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
        conn.commit()
        return count

    def _index_one(self, json_file: Path, conn: sqlite3.Connection) -> bool:
        row = self._make_row(json_file)
        if row is None:
            return False
        conn.execute(
            "INSERT OR REPLACE INTO bronze_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
        return True

    def _make_row(self, json_file: Path) -> tuple | None:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        raw_id = data.get("raw_document_id", "")
        captured = data.get("captured_at", "")
        source_system = data.get("source_system", "") or data.get("collector_id", "")
        source_url = data.get("source_url", "")
        sha = data.get("content_sha256", "")
        body = data.get("body_inline", "") or ""

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
            body[:10000],
            json.dumps(ext, ensure_ascii=False),
            str(json_file),
            len(body),
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
            "SELECT * FROM bronze_index WHERE raw_document_id = ?",
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
            "body_inline": row["body_text"],
            "extensions": extensions,
            "channel": "",
            "collector_id": "",
            "collector_version": "",
        }
        return BronzeDocument(raw)

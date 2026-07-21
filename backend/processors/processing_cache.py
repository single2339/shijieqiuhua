"""SQLite cache for deterministic and optional LLM processing results."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProcessingCache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_cache (
                    content_sha256 TEXT PRIMARY KEY,
                    translated_title TEXT NOT NULL DEFAULT '',
                    translated_content TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    layer TEXT NOT NULL DEFAULT '',
                    country TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT '',
                    llm_used INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(processing_cache)").fetchall()
            }
            if "translated_title" not in columns:
                self._conn.execute("ALTER TABLE processing_cache ADD COLUMN translated_title TEXT NOT NULL DEFAULT ''")
            if "translated_content" not in columns:
                self._conn.execute("ALTER TABLE processing_cache ADD COLUMN translated_content TEXT NOT NULL DEFAULT ''")
            self._conn.commit()
        return self._conn

    def get(self, content_sha256: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM processing_cache WHERE content_sha256 = ?",
            (content_sha256,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["llm_used"] = bool(data["llm_used"])
        return data

    def put(
        self,
        content_sha256: str,
        *,
        translated_title: str = "",
        translated_content: str = "",
        summary: str,
        layer: str,
        country: str,
        city: str,
        mode: str,
        llm_used: bool,
    ) -> None:
        self._get_conn().execute(
            """
            INSERT OR REPLACE INTO processing_cache
            (content_sha256, translated_title, translated_content, summary, layer, country, city, mode, llm_used, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_sha256,
                translated_title,
                translated_content,
                summary,
                layer,
                country,
                city,
                mode,
                1 if llm_used else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._get_conn().commit()

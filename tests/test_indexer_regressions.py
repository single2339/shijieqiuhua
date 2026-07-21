from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from backend.indexer import Indexer
from src.bronze.writer import BronzeWriter
from src.models.document import RawDocument


def _doc(
    body: str,
    raw_document_id: str = "same-id",
    source_system: str = "test",
) -> RawDocument:
    return RawDocument(
        raw_document_id=raw_document_id,
        job_id="job-1",
        channel="web",
        mime_type="text/plain",
        encoding="utf-8",
        body_ref=None,
        body_inline=body,
        headers_summary={},
        captured_at="2026-07-12T00:00:00+00:00",
        collector_id="test",
        collector_version="1.0.0",
        source_url="https://example.test/article",
        source_system=source_system,
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


def test_incremental_update_reindexes_modified_json(tmp_path: Path) -> None:
    path = BronzeWriter(tmp_path).write(_doc("before"))
    indexer = Indexer(tmp_path)

    assert indexer.build_index() == 1
    assert indexer.query()[0].text == "before"

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["body_inline"] = "after"
    payload["content_sha256"] = hashlib.sha256(b"after").hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert indexer.incremental_update() == 1
    assert indexer.query()[0].text == "after"


def test_index_keeps_duplicate_legacy_ids_from_distinct_files(tmp_path: Path) -> None:
    writer = BronzeWriter(tmp_path)
    writer.write(_doc("first", source_system="source-a"))
    writer.write(_doc("second", source_system="source-b"))
    indexer = Indexer(tmp_path)

    assert indexer.build_index() == 2
    assert indexer.count() == 2
    assert {doc.text for doc in indexer.query()} == {"first", "second"}


def test_old_index_migrates_to_file_unique_records(tmp_path: Path) -> None:
    writer = BronzeWriter(tmp_path)
    first_path = writer.write(_doc("first", source_system="source-a"))
    writer.write(_doc("second", source_system="source-b"))
    db_path = tmp_path / "_index.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE bronze_index (
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
        """
    )
    conn.execute(
        "INSERT INTO bronze_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "same-id",
            "2026-07-12T00:00:00+00:00",
            "source-a",
            "https://example.test/article",
            hashlib.sha256(b"first").hexdigest(),
            "",
            "",
            "",
            "first",
            "first",
            "first",
            "{}",
            str(first_path),
            5,
            "2026-07-12T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    indexer = Indexer(tmp_path)
    assert indexer.count() == 1
    assert indexer.incremental_update() == 1
    assert indexer.count() == 2
    assert {doc.text for doc in indexer.query()} == {"first", "second"}

    with sqlite3.connect(db_path) as check:
        columns = check.execute("PRAGMA table_info(bronze_index)").fetchall()
    record_id = next(column for column in columns if column[1] == "record_id")
    raw_id = next(column for column in columns if column[1] == "raw_document_id")
    assert record_id[5] == 1
    assert raw_id[5] == 0


def test_indexer_reads_body_ref_content(tmp_path: Path) -> None:
    body = "大正文" * 40_000
    doc = RawDocument.from_body(
        job_id="job-large",
        channel="web",
        mime_type="text/plain",
        body=body,
        collector_id="test",
        collector_version="1.0.0",
        source_url="https://example.test/large",
        source_system="test",
    )
    BronzeWriter(tmp_path).write(doc)
    indexer = Indexer(tmp_path)

    assert indexer.build_index() == 1
    indexed = indexer.get_by_id(doc.raw_document_id)
    assert indexed is not None
    assert indexed.text.startswith("大正文")

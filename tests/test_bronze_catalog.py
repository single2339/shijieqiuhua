from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.bronze_catalog import BronzeCatalog
from backend import bronze_catalog
from backend.indexer import Indexer


def _write_document(root, name: str, body_ref: str, *, captured_at: str):
    (root / name).write_text(json.dumps({
        "raw_document_id": name,
        "body_ref": body_ref,
        "captured_at": captured_at,
        "source_system": "test-source",
        "extensions": {"summary": f"{name} summary"},
    }), encoding="utf-8")


def test_catalog_hydrates_only_selected_documents_after_initial_build(tmp_path):
    blobs = tmp_path / "_blobs"
    blobs.mkdir()
    first_text = "港口吞吐量出现显著上升"
    second_text = "无关的测试文档"
    (blobs / "one.txt").write_text(first_text, encoding="utf-8")
    (blobs / "two.txt").write_text(second_text, encoding="utf-8")
    _write_document(tmp_path, "one.json", "bronze://one.txt", captured_at="2026-07-20T00:00:00Z")
    _write_document(tmp_path, "two.json", "bronze://two.txt", captured_at="2026-07-21T00:00:00Z")

    catalog = BronzeCatalog(tmp_path)
    catalog.ensure()
    first_hash = hashlib.md5(first_text.encode()).hexdigest()

    # A later query must not reopen unrelated document bodies merely to answer
    # an already indexed candidate request.
    (blobs / "two.txt").unlink()
    selected = catalog.hydrate([first_hash])

    assert [doc.raw_document_id for doc in selected] == ["one.json"]
    assert selected[0].text == first_text
    assert catalog.search_tokens("港口吞吐量", limit=10) == [first_hash]


def test_catalog_skips_repeated_filesystem_freshness_scans(tmp_path, monkeypatch):
    (tmp_path / "one.json").write_text(json.dumps({
        "raw_document_id": "one",
        "body_inline": "港口吞吐量上升",
        "captured_at": "2026-07-21T00:00:00Z",
        "source_system": "test-source",
    }), encoding="utf-8")
    catalog = BronzeCatalog(tmp_path)
    catalog.ensure()
    checks = 0

    def count_stale_checks():
        nonlocal checks
        checks += 1
        return False

    monkeypatch.setattr(catalog, "_is_stale", count_stale_checks)
    catalog.ensure()
    catalog.search_tokens("港口")

    assert checks == 0


def test_catalog_bounds_each_in_memory_retrieval_excerpt(tmp_path):
    text = "港口" + "测试内容" * 2000
    (tmp_path / "long.json").write_text(json.dumps({
        "raw_document_id": "long",
        "body_inline": text,
        "captured_at": "2026-07-21T00:00:00Z",
        "source_system": "test-source",
    }), encoding="utf-8")
    catalog = BronzeCatalog(tmp_path)
    catalog.ensure()
    body_hash = hashlib.md5(text.encode()).hexdigest()

    entry = catalog.entries_for([body_hash])[body_hash]

    assert len(entry["text_excerpt"]) <= 1000


def test_catalog_rebuild_uses_sqlite_index_instead_of_reopening_json(tmp_path, monkeypatch):
    text = "港口吞吐量上升，集装箱延误正在缓解。"
    (tmp_path / "indexed.json").write_text(json.dumps({
        "raw_document_id": "indexed",
        "body_inline": text,
        "captured_at": "2026-07-21T00:00:00Z",
        "source_system": "test-source",
        "extensions": {"summary": "港口更新"},
    }), encoding="utf-8")
    indexer = Indexer(tmp_path)
    assert indexer.build_index() == 1
    indexer.close()
    new_text = "索引构建后新增的情报"
    (tmp_path / "new.json").write_text(json.dumps({
        "raw_document_id": "new",
        "body_inline": new_text,
        "captured_at": "2026-07-21T01:00:00Z",
        "source_system": "test-source",
    }), encoding="utf-8")

    catalog = BronzeCatalog(tmp_path)
    original_read_text = Path.read_text

    def reject_indexed_json_reopen(path, *args, **kwargs):
        if path == tmp_path / "indexed.json":
            raise AssertionError("catalog must reuse the SQLite row for indexed documents")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_indexed_json_reopen)

    catalog.ensure()

    body_hash = hashlib.md5(text.encode()).hexdigest()
    new_hash = hashlib.md5(new_text.encode()).hexdigest()
    assert catalog.entries_for([body_hash])[body_hash]["title"] == "港口更新"
    assert catalog.entries_for([new_hash])[new_hash]["raw_document_id"] == "new"


def test_catalog_persists_incrementally_without_materializing_one_large_json_string(tmp_path, monkeypatch):
    (tmp_path / "one.json").write_text(json.dumps({
        "raw_document_id": "one",
        "body_inline": "港口吞吐量上升",
        "captured_at": "2026-07-21T00:00:00Z",
        "source_system": "test-source",
    }), encoding="utf-8")
    catalog = BronzeCatalog(tmp_path)
    monkeypatch.setattr(
        bronze_catalog.json,
        "dumps",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("catalog persistence must stream to disk")
        ),
    )

    catalog.ensure()

    assert catalog.path.is_file()


def test_catalog_keeps_corpus_metadata_out_of_python_memory(tmp_path):
    for index in range(25):
        (tmp_path / f"{index}.json").write_text(json.dumps({
            "raw_document_id": str(index),
            "body_inline": f"港口吞吐量记录 {index}",
            "captured_at": "2026-07-21T00:00:00Z",
            "source_system": "test-source",
        }), encoding="utf-8")

    catalog = BronzeCatalog(tmp_path)
    catalog.ensure()

    assert catalog.size == 25
    assert not any(
        isinstance(value, dict) and len(value) == 25
        for value in vars(catalog).values()
    )

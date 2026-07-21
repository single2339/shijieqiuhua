from __future__ import annotations

from pathlib import Path

from backend.bronze_reader import BronzeDocument
import backend.merger as merger_module


def _doc() -> BronzeDocument:
    return BronzeDocument({
        "raw_document_id": "doc-1",
        "body_inline": "one document",
        "source_system": "test",
        "source_url": "https://example.test/one",
        "content_sha256": "a" * 64,
        "captured_at": "2026-07-12T00:00:00+00:00",
        "extensions": {"horizon_title": "One document"},
    })


def test_unchanged_merge_index_is_reused_in_process(tmp_path: Path) -> None:
    merger_module.build_merge_index(tmp_path, docs=[_doc()])
    getattr(merger_module, "_merge_index_cache", {}).clear()

    first = merger_module.load_merge_index(tmp_path)
    second = merger_module.load_merge_index(tmp_path)

    assert first is not None
    assert second is first

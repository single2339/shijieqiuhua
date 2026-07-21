from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.bronze_reader import BronzeDocument
import backend.merger as merger_module


def _doc() -> BronzeDocument:
    return BronzeDocument(
        {
            "raw_document_id": "doc-1",
            "body_inline": "one document",
            "source_system": "test",
            "source_url": "https://example.test/one",
            "content_sha256": "a" * 64,
            "captured_at": "2026-07-12T00:00:00+00:00",
            "extensions": {"horizon_title": "One document"},
        }
    )


def test_concurrent_merge_builds_have_one_owner(tmp_path: Path, monkeypatch) -> None:
    original = merger_module._build_merge_index
    call_count = 0
    count_lock = threading.Lock()

    def wrapped(root, docs=None):
        nonlocal call_count
        with count_lock:
            call_count += 1
        time.sleep(0.1)
        return original(root, docs)

    monkeypatch.setattr(merger_module, "_build_merge_index", wrapped)
    docs = [_doc()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: merger_module.build_merge_index(tmp_path, docs=docs), range(2))
        )

    assert call_count == 1
    assert [result.total_docs for result in results] == [1, 1]
    assert not (tmp_path / "_merge.lock").exists()
    assert not (tmp_path / "_merge_index.json.tmp").exists()

from __future__ import annotations

import json

import numpy as np

from backend.agents.intelligence import super_analyst
from backend.processors.embedding_index import EmbeddingIndex


def test_embedding_matrix_is_memory_mapped_on_load(tmp_path):
    index_dir = tmp_path / "embedding"
    index_dir.mkdir()
    np.save(index_dir / "embeddings.npy", np.ones((4, 3), dtype=np.float32))
    (index_dir / "metadata.json").write_text(
        json.dumps([f"hash-{index}" for index in range(4)]),
        encoding="utf-8",
    )

    index = EmbeddingIndex(tmp_path, index_dir=index_dir)

    assert index.load() is True
    assert isinstance(index._embeddings, np.memmap)


def test_super_analysis_reuses_embedding_index_between_requests(monkeypatch, tmp_path):
    calls = {"init": 0, "load": 0, "search": 0}

    class CountingIndex:
        def __init__(self, *_args, **_kwargs):
            calls["init"] += 1
            self.is_loaded = False
            self.doc_hashes = ["hash-1"]
            self.size = 1

        def load(self):
            calls["load"] += 1
            self.is_loaded = True
            return True

        def search(self, _question, top_k=100):
            calls["search"] += 1
            return [("hash-1", 0.8)]

    monkeypatch.setattr(super_analyst, "EmbeddingIndex", CountingIndex)
    super_analyst._embedding_index_cache.clear()

    super_analyst._load_embedding_candidates(tmp_path, "第一次查询")
    super_analyst._load_embedding_candidates(tmp_path, "第二次查询")

    assert calls == {"init": 1, "load": 1, "search": 2}


def test_super_analysis_reuses_bronze_catalog_between_requests(monkeypatch, tmp_path):
    calls = {"init": 0, "ensure": 0}

    class CountingCatalog:
        size = 0

        def __init__(self, _storage):
            calls["init"] += 1

        def ensure(self):
            calls["ensure"] += 1

        def search_tokens(self, *_args, **_kwargs):
            return []

        def entries_for(self, _hashes):
            return {}

        def hydrate(self, _hashes):
            return []

    monkeypatch.setattr(super_analyst, "BronzeCatalog", CountingCatalog)
    super_analyst._bronze_catalog_cache.clear()

    super_analyst._load_catalog_documents(tmp_path, "第一次查询", None, None, {})
    super_analyst._load_catalog_documents(tmp_path, "第二次查询", None, None, {})

    assert calls == {"init": 1, "ensure": 2}


def test_super_analysis_prewarm_loads_catalog_and_model_once(monkeypatch, tmp_path):
    calls = {"index_init": 0, "index_load": 0, "model_prewarm": 0, "catalog_init": 0, "catalog_ensure": 0}

    class CountingIndex:
        is_loaded = False

        def __init__(self, *_args, **_kwargs):
            calls["index_init"] += 1

        def load(self):
            calls["index_load"] += 1
            self.is_loaded = True
            return True

        def prewarm(self):
            calls["model_prewarm"] += 1
            return True

    class CountingCatalog:
        def __init__(self, _storage):
            calls["catalog_init"] += 1

        def ensure(self):
            calls["catalog_ensure"] += 1

    monkeypatch.setattr(super_analyst, "EmbeddingIndex", CountingIndex)
    monkeypatch.setattr(super_analyst, "BronzeCatalog", CountingCatalog)
    super_analyst._embedding_index_cache.clear()
    super_analyst._bronze_catalog_cache.clear()

    result = super_analyst.prewarm_super_analysis(tmp_path)

    assert result == {"catalog": "ready", "embedding": "ready"}
    assert calls == {
        "index_init": 1,
        "index_load": 1,
        "model_prewarm": 1,
        "catalog_init": 1,
        "catalog_ensure": 1,
    }


def test_embedding_prewarm_is_safe_when_no_index_exists(tmp_path):
    index = EmbeddingIndex(tmp_path, index_dir=tmp_path / "missing-index")

    assert index.prewarm() is False

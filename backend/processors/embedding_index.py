"""Embedding-based semantic search index using BAAI/bge-small-zh-v1.5.

Pre-computes document embeddings once, stores on disk, and provides
cosine-similarity search at query time. Model is lazy-loaded.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class EmbeddingIndex:
    """Pre-computed embedding index for semantic document search."""

    def __init__(self, storage_root: str | Path, index_dir: str | Path = "embedding_index"):
        self._storage_root = Path(storage_root)
        self._index_dir = Path(index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._embeddings: np.ndarray | None = None
        self._doc_hashes: list[str] = []
        self._model = None

    # ── model ──

    def _get_model(self):
        if self._model is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                "BAAI/bge-small-zh-v1.5",
                local_files_only=True,
            )
        return self._model

    # ── persistence ──

    def _embeddings_path(self) -> Path:
        return self._index_dir / "embeddings.npy"

    def _metadata_path(self) -> Path:
        return self._index_dir / "metadata.json"

    def load(self) -> bool:
        emb_path = self._embeddings_path()
        meta_path = self._metadata_path()
        if emb_path.exists() and meta_path.exists():
            self._embeddings = np.load(emb_path, mmap_mode="r")
            self._doc_hashes = json.loads(meta_path.read_text(encoding="utf-8"))
            return True
        return False

    def prewarm(self) -> bool:
        """Load the on-disk matrix and semantic model before the first query."""
        if not self.is_loaded and not self.load():
            return False
        self._get_model()
        return True

    def _save(self):
        if self._embeddings is not None and len(self._embeddings) > 0:
            np.save(str(self._embeddings_path()), self._embeddings)
            self._metadata_path().write_text(
                json.dumps(self._doc_hashes, ensure_ascii=False), encoding="utf-8"
            )

    @property
    def is_loaded(self) -> bool:
        return self._embeddings is not None and len(self._embeddings) > 0

    @property
    def size(self) -> int:
        return len(self._embeddings) if self._embeddings is not None else 0

    @property
    def doc_hashes(self) -> list[str]:
        return self._doc_hashes

    # ── build ──

    def build(self, docs, batch_size: int = 128, show_progress: bool = True):
        texts: list[str] = []
        hashes: list[str] = []

        for doc in docs:
            text = doc.text
            if not text or len(text.strip()) < 10:
                continue
            h = hashlib.md5(text.encode("utf-8")).hexdigest()
            texts.append(text[:2000])
            hashes.append(h)

        if not texts:
            self._embeddings = np.array([]).reshape(0, 512)
            self._doc_hashes = []
            return 0

        model = self._get_model()
        t0 = time.time()

        if show_progress:
            log.info("编码 %d 篇文档...", len(texts))

        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
        )

        self._embeddings = np.asarray(embeddings, dtype=np.float32)
        self._doc_hashes = hashes
        self._save()

        elapsed = time.time() - t0
        if show_progress:
            size_mb = self._embeddings_path().stat().st_size / 1024 / 1024
            log.info("完成: %d 篇, %.1fs, 索引大小 %.1fMB", len(hashes), elapsed, size_mb)

        return len(hashes)

    # ── search ──

    def search(self, query: str, top_k: int = 100) -> list[tuple[str, float]]:
        """Search for semantically similar documents.

        Returns list of (doc_hash, similarity) sorted by similarity descending.
        """
        if not self.is_loaded:
            self.load()
        if not self.is_loaded:
            return []

        model = self._get_model()
        query_embedding = model.encode(
            [query],
            normalize_embeddings=True,
        )

        similarities = np.dot(self._embeddings, query_embedding.T).flatten()

        if top_k >= len(similarities):
            top_indices = np.argsort(similarities)[::-1]
        else:
            top_indices = np.argpartition(similarities, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        results: list[tuple[str, float]] = []
        for idx in top_indices:
            score = float(similarities[int(idx)])
            if score > 0:
                results.append((self._doc_hashes[int(idx)], score))

        return results

    # ── incremental update ──

    def update(self, new_docs, batch_size: int = 64):
        if not self.is_loaded:
            return self.build(new_docs, batch_size=batch_size, show_progress=False)

        existing = set(self._doc_hashes)
        new_texts: list[str] = []
        new_hashes: list[str] = []

        for doc in new_docs:
            text = doc.text
            if not text or len(text.strip()) < 10:
                continue
            h = hashlib.md5(text.encode("utf-8")).hexdigest()
            if h in existing:
                continue
            new_texts.append(text[:2000])
            new_hashes.append(h)

        if not new_texts:
            return 0

        model = self._get_model()
        new_embeddings = model.encode(
            new_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        self._embeddings = np.vstack([
            self._embeddings,
            np.asarray(new_embeddings, dtype=np.float32),
        ])
        self._doc_hashes.extend(new_hashes)
        self._save()

        return len(new_hashes)

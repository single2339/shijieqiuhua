"""Daily content merge engine.

Groups bronze documents by content similarity (same source_url, same
content_sha256, same normalized title) using union-find, then produces
a MergeIndex used by the API to build multi-source IntelItems.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from backend.bronze_reader import BronzeDocument


# ── title normalisation ──

_TITLE_CLEAN = re.compile(r"[^a-zA-Z0-9一-鿿\s]")

def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _TITLE_CLEAN.sub("", title.lower().strip())


def _best_title(doc: BronzeDocument) -> str:
    """Extract the most useful title from a bronze document."""
    ext = doc.extensions if isinstance(doc.extensions, dict) else {}
    t = ext.get("horizon_title", "") or ext.get("summary", "") or doc.text
    return t.split("\n")[0].strip()[:200]


def _best_source_name(doc: BronzeDocument) -> str:
    """Resolve the best source identifier for a document.

    Uses feed_name from horizon metadata (the actual publication name)
    instead of the author name stored in source_system.
    """
    ext = getattr(doc, "extensions", {}) or {}
    if isinstance(ext, dict):
        meta = ext.get("horizon_metadata", {})
        if isinstance(meta, dict) and meta.get("feed_name"):
            return meta["feed_name"]
    return doc.source_system


# ── union-find ──

class UnionFind:
    """Disjoint-set / union-find for grouping documents."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        if x not in self._parent:
            self._parent[x] = x

    def find(self, x: str) -> str:
        p = self._parent.get(x)
        if p is None:
            return x
        if p != x:
            self._parent[x] = self.find(p)
        return self._parent[x]

    def union(self, a: str, b: str) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> list[list[str]]:
        """Return each connected component as a list of element IDs."""
        root_map: dict[str, list[str]] = {}
        for x in self._parent:
            root = self.find(x)
            root_map.setdefault(root, []).append(x)
        return list(root_map.values())


# ── merge data structures ──

@dataclass
class MergedGroup:
    group_id: str
    primary_doc_id: str
    title: str
    summary: str
    source_url: str
    sources: list[str]
    documents: list[dict] = field(default_factory=list)


@dataclass
class MergeIndex:
    generated_at: str
    total_docs: int
    total_groups: int
    groups: list[MergedGroup]
    orphaned_doc_ids: set[str] = field(default_factory=set)


_merge_index_cache: dict[str, tuple[int, int, MergeIndex]] = {}
_merge_index_cache_lock = threading.RLock()


# ── build ──

import time as _time

_MERGE_LOCK_TTL = 300  # 5 minutes — if lock is older than this, assume stale


def build_merge_index(
    storage_root: str | Path,
    docs: list[BronzeDocument] | None = None,
) -> MergeIndex:
    """Scan bronze storage and build a merge index.

    Documents are grouped by three keys in order of confidence:
    1. Same ``source_url`` → definitely the same article.
    2. Same ``content_sha256`` → identical cleaned content.
    3. Same normalized title → likely syndication / wire story.

    Union-find is used so that transitive matches (A matches B by URL,
    B matches C by title) end up in the same group.

    If *docs* is provided, uses those directly (caller is responsible for
    loading, e.g. via Indexer). Otherwise falls back to scan_bronze().
    """
    root = Path(storage_root)
    lock_path = root / "_merge.lock"

    # Check for recent lock file first
    try:
        lock_age = _time.time() - lock_path.stat().st_mtime
        if lock_age < _MERGE_LOCK_TTL:
            existing = load_merge_index(root)
            if existing is not None:
                return existing
    except OSError:
        pass

    # Atomic lock acquisition via O_CREAT|O_EXCL
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(_time.time()).encode())
        os.close(fd)
    except FileExistsError:
        existing = load_merge_index(root)
        if existing is not None:
            return existing
        lock_path.write_text(str(_time.time()))

    try:
        return _build_merge_index(root, docs)
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _build_merge_index(
    root: Path,
    docs: list[BronzeDocument] | None = None,
) -> MergeIndex:
    if docs is None:
        from backend.bronze_reader import scan_bronze
        docs = scan_bronze(root)
    if not docs:
        return MergeIndex(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_docs=0,
            total_groups=0,
            groups=[],
            orphaned_doc_ids=set(),
        )

    # Index docs by raw_document_id (MD5-based)
    doc_by_id: dict[str, BronzeDocument] = {}
    for d in docs:
        did = d.raw_document_id or hashlib.md5(
            d.text.encode() if d.text else d.source_url.encode()
        ).hexdigest()
        doc_by_id[did] = d

    uf = UnionFind()
    for did in doc_by_id:
        uf.add(did)

    # --- Key 1: source_url ---
    url_buckets: dict[str, list[str]] = {}
    for did, d in doc_by_id.items():
        url = (d.source_url or "").strip()
        if url:
            url_buckets.setdefault(url, []).append(did)
    for bucket in url_buckets.values():
        for i in range(1, len(bucket)):
            uf.union(bucket[0], bucket[i])

    # --- Key 2: content_sha256 ---
    sha_buckets: dict[str, list[str]] = {}
    for did, d in doc_by_id.items():
        ch = (d.content_sha256 or "").strip()
        if ch:
            sha_buckets.setdefault(ch, []).append(did)
    for bucket in sha_buckets.values():
        for i in range(1, len(bucket)):
            uf.union(bucket[0], bucket[i])

    # --- Key 3: normalised title ---
    title_buckets: dict[str, list[str]] = {}
    for did, d in doc_by_id.items():
        nt = _normalize_title(_best_title(d))
        if nt:
            title_buckets.setdefault(nt, []).append(did)
    for bucket in title_buckets.values():
        for i in range(1, len(bucket)):
            uf.union(bucket[0], bucket[i])

    # --- Build groups ---
    groups: list[MergedGroup] = []
    orphaned: set[str] = set()

    for component in uf.groups():
        if len(component) == 1:
            orphaned.add(component[0])
            continue

        comp_docs = [doc_by_id[did] for did in component]
        # Primary: document with longest body
        primary = max(comp_docs, key=lambda d: len(d.text or ""))

        # Collect unique sources
        sources: list[str] = []
        seen_src: set[str] = set()
        for d in comp_docs:
            name = _best_source_name(d)
            if name and name not in seen_src:
                sources.append(name)
                seen_src.add(name)

        first_url = ""
        for d in comp_docs:
            if d.source_url:
                first_url = d.source_url
                break

        groups.append(MergedGroup(
            group_id=str(uuid.uuid4())[:12],
            primary_doc_id=primary.raw_document_id or component[0],
            title=_best_title(primary),
            summary=(
                (isinstance(primary.extensions, dict) and primary.extensions.get("summary"))
                or primary.text[:300]
            ),
            source_url=first_url or primary.source_url,
            sources=sources,
            documents=[
                {
                    "doc_id": d.raw_document_id or "",
                    "source_system": d.source_system,
                    "source_url": d.source_url,
                    "captured_at": d.captured_at,
                }
                for d in comp_docs
            ],
        ))

    index = MergeIndex(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_docs=len(doc_by_id),
        total_groups=len(groups),
        groups=groups,
        orphaned_doc_ids=orphaned,
    )

    # Atomic write: temp file → rename
    index_path = root / "_merge_index.json"
    tmp_path = root / "_merge_index.json.tmp"
    tmp_path.write_text(
        json.dumps(
            {
                "generated_at": index.generated_at,
                "generator_version": "1.0",
                "total_docs": index.total_docs,
                "total_groups": index.total_groups,
                "orphaned_count": len(orphaned),
                "groups": [
                    {
                        "group_id": g.group_id,
                        "primary_doc_id": g.primary_doc_id,
                        "title": g.title,
                        "summary": g.summary,
                        "source_url": g.source_url,
                        "sources": g.sources,
                        "documents": g.documents,
                    }
                    for g in groups
                ],
                "orphaned_doc_ids": sorted(orphaned),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(tmp_path, index_path)

    return index


def load_merge_index(storage_root: str | Path) -> Optional[MergeIndex]:
    """Load a previously-built merge index, or None if not found."""
    root = Path(storage_root)
    index_path = root / "_merge_index.json"
    if not index_path.exists():
        return None
    try:
        stat = index_path.stat()
    except OSError:
        return None
    cache_key = str(index_path.resolve())
    with _merge_index_cache_lock:
        cached = _merge_index_cache.get(cache_key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        groups = [
            MergedGroup(
                group_id=g["group_id"],
                primary_doc_id=g["primary_doc_id"],
                title=g.get("title", ""),
                summary=g.get("summary", ""),
                source_url=g.get("source_url", ""),
                sources=g.get("sources", []),
                documents=g.get("documents", []),
            )
            for g in data.get("groups", [])
        ]
        result = MergeIndex(
            generated_at=data["generated_at"],
            total_docs=data["total_docs"],
            total_groups=data["total_groups"],
            groups=groups,
            orphaned_doc_ids=set(data.get("orphaned_doc_ids", [])),
        )
        with _merge_index_cache_lock:
            _merge_index_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, result)
        return result
    except (json.JSONDecodeError, KeyError, OSError):
        return None

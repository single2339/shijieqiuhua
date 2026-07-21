"""Durable SQLite queue for collection jobs.

The API process only enqueues work. A worker claims and completes jobs, so a
process restart cannot silently discard a requested collection run.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CollectionJobQueue:
    def __init__(self, storage_root: str | Path):
        self.root = Path(storage_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "queue.db"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS collection_jobs (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    collector_key TEXT NOT NULL,
                    target_json TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    created_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_collection_jobs_claim
                    ON collection_jobs(status, priority DESC, created_at);
                """
            )

    def enqueue(
        self,
        *,
        hours: int,
        tenant_id: str = "default",
        priority: int = 0,
        max_attempts: int = 3,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            # A collection already pending/running is enough to satisfy the
            # request and prevents duplicate expensive scrapes.
            active = conn.execute(
                "SELECT job_id FROM collection_jobs WHERE collector_key = ? "
                "AND status IN ('pending', 'running') ORDER BY created_at DESC LIMIT 1",
                ("horizon",),
            ).fetchone()
            if active:
                return active["job_id"]
            conn.execute(
                "INSERT INTO collection_jobs "
                "(job_id, tenant_id, channel, collector_key, target_json, priority, "
                "max_attempts, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    tenant_id,
                    "api",
                    "horizon",
                    json.dumps({"hours": hours}, ensure_ascii=False),
                    priority,
                    max(1, max_attempts),
                    now,
                    now,
                ),
            )
        return job_id

    def claim_next(self, lease_seconds: int = 1800) -> dict | None:
        now = _now()
        lease_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max(60, lease_seconds))).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Return jobs left running by a dead worker to the pending queue.
            conn.execute(
                "UPDATE collection_jobs SET status='pending', updated_at=?, last_error=? "
                "WHERE status='running' AND updated_at < ?",
                (now, "worker lease expired", lease_cutoff),
            )
            row = conn.execute(
                "SELECT * FROM collection_jobs WHERE status='pending' "
                "AND attempts < max_attempts ORDER BY priority DESC, created_at LIMIT 1"
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            conn.execute(
                "UPDATE collection_jobs SET status='running', attempts=attempts+1, "
                "started_at=?, updated_at=? WHERE job_id=?",
                (now, now, row["job_id"]),
            )
            conn.commit()
            result = dict(row)
            result["status"] = "running"
            result["attempts"] = row["attempts"] + 1
            result["target"] = json.loads(row["target_json"])
            return result

    def complete(self, job_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE collection_jobs SET status='completed', finished_at=?, updated_at=? WHERE job_id=?",
                (now, now, job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        now = _now()
        with self._connect() as conn:
            row = conn.execute("SELECT attempts, max_attempts FROM collection_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return
            status = "dead" if row["attempts"] >= row["max_attempts"] else "pending"
            conn.execute(
                "UPDATE collection_jobs SET status=?, finished_at=?, updated_at=?, last_error=? WHERE job_id=?",
                (status, now, now, error[:2000], job_id),
            )

    def get(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM collection_jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def latest(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM collection_jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

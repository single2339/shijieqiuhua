"""Owner-scoped, durable analyst sign-off state for super-analysis cases."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.models import InvestigationAnalystReview


class InvestigationReviewStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS super_analysis_reviews (
                    request_id TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    playbook TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewer_id INTEGER,
                    reviewed_at TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (request_id, owner_id)
                )
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_case(self, request_id: str, owner_id: int, playbook: str) -> InvestigationAnalystReview:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO super_analysis_reviews
                (request_id, owner_id, playbook, created_at) VALUES (?, ?, ?, ?)""",
                (request_id, owner_id, playbook, self._now()),
            )
        review = self.get_review(request_id, owner_id)
        if review is None:  # pragma: no cover - protects against storage corruption
            raise RuntimeError("review case could not be created")
        return review

    def get_review(self, request_id: str, owner_id: int) -> InvestigationAnalystReview | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT status, reviewer_id, reviewed_at, notes
                FROM super_analysis_reviews WHERE request_id = ? AND owner_id = ?""",
                (request_id, owner_id),
            ).fetchone()
        if row is None:
            return None
        return InvestigationAnalystReview(
            status=row["status"],
            reviewer_id=row["reviewer_id"],
            reviewed_at=row["reviewed_at"],
            notes=row["notes"],
        )

    def submit_review(
        self,
        request_id: str,
        *,
        owner_id: int,
        reviewer_id: int,
        status: str,
        notes: str,
    ) -> InvestigationAnalystReview:
        if status not in {"approved", "needs_follow_up", "rejected"}:
            raise ValueError("invalid review status")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE super_analysis_reviews
                SET status = ?, reviewer_id = ?, reviewed_at = ?, notes = ?
                WHERE request_id = ? AND owner_id = ?""",
                (status, reviewer_id, self._now(), notes, request_id, owner_id),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM super_analysis_reviews WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if exists:
                    raise PermissionError("review case belongs to another user")
                raise KeyError("review case does not exist")
        review = self.get_review(request_id, owner_id)
        if review is None:  # pragma: no cover - protects against storage corruption
            raise RuntimeError("review case could not be updated")
        return review

"""基于 SQLite 持久化标准证据层和情报产品层数据。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.collectors.horizon.models import ContentItem
from backend.intelligence.admission import AdmissionDecision
from backend.intelligence.source_policy import SourceProfile


@dataclass(frozen=True)
class StoreResult:
    silver_document_id: str | None = None
    point_id: str | None = None
    event_id: str | None = None
    claim_id: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(kind: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"osint-network:{kind}:{value}"))


def _event_key(item: ContentItem, decision: AdmissionDecision) -> str:
    original_title = str((item.metadata or {}).get("_original_title") or item.title)
    title = re.sub(r"[^\w]+", " ", original_title.casefold(), flags=re.UNICODE).strip()
    title = " ".join(title.split())
    event_date = item.published_at.date().isoformat()
    material = f"{decision.event_type}|{decision.layer.value}|{event_date}|{title}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _confidence_level(independent_sources: int, reliable_sources: int) -> str:
    if independent_sources >= 3 and reliable_sources >= 2:
        return "L1"
    if (independent_sources >= 2 and reliable_sources >= 1) or independent_sources >= 3:
        return "L2"
    if reliable_sources >= 1 or independent_sources >= 2:
        return "L3"
    return "L4"


class IntelligenceStore:
    """存储准入审计、标准证据文档、情报要点、情报事件和可验证主张。"""

    def __init__(self, storage_path: str | Path) -> None:
        path = Path(storage_path)
        self.db_path = path if path.suffix == ".db" else path / "_intelligence.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS collection_decisions (
                    raw_document_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    score REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    pir_ids_json TEXT NOT NULL,
                    indicator_ids_json TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    source_tier TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS silver_documents (
                    silver_document_id TEXT PRIMARY KEY,
                    raw_document_id TEXT NOT NULL UNIQUE,
                    canonical_text TEXT NOT NULL,
                    title TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    author TEXT NOT NULL,
                    url TEXT NOT NULL,
                    language TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_key TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    title TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    confidence_level TEXT NOT NULL,
                    independent_source_count INTEGER NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    impact TEXT NOT NULL,
                    urgency TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS intelligence_points (
                    point_id TEXT PRIMARY KEY,
                    silver_document_id TEXT NOT NULL UNIQUE,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    impact TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    source_key TEXT NOT NULL,
                    source_reliability TEXT NOT NULL,
                    information_credibility INTEGER NOT NULL,
                    independence_group TEXT NOT NULL,
                    pir_ids_json TEXT NOT NULL,
                    indicator_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (silver_document_id) REFERENCES silver_documents(silver_document_id),
                    FOREIGN KEY (event_id) REFERENCES events(event_id)
                );

                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    point_id TEXT NOT NULL UNIQUE,
                    silver_document_id TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id),
                    FOREIGN KEY (point_id) REFERENCES intelligence_points(point_id),
                    FOREIGN KEY (silver_document_id) REFERENCES silver_documents(silver_document_id)
                );

                CREATE INDEX IF NOT EXISTS idx_points_event ON intelligence_points(event_id);
                CREATE INDEX IF NOT EXISTS idx_claims_event ON claims(event_id);
                CREATE INDEX IF NOT EXISTS idx_events_last_seen ON events(last_seen DESC);
                """
            )

    def record_document(
        self,
        raw_document_id: str,
        item: ContentItem,
        profile: SourceProfile,
        decision: AdmissionDecision,
    ) -> StoreResult:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collection_decisions (
                    raw_document_id, status, score, reasons_json, pir_ids_json,
                    indicator_ids_json, source_key, source_tier, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(raw_document_id) DO UPDATE SET
                    status=excluded.status,
                    score=excluded.score,
                    reasons_json=excluded.reasons_json,
                    pir_ids_json=excluded.pir_ids_json,
                    indicator_ids_json=excluded.indicator_ids_json,
                    source_key=excluded.source_key,
                    source_tier=excluded.source_tier
                """,
                (
                    raw_document_id,
                    decision.status.value,
                    decision.score,
                    json.dumps(decision.reasons, ensure_ascii=False),
                    json.dumps(decision.pir_ids, ensure_ascii=False),
                    json.dumps(decision.indicator_ids, ensure_ascii=False),
                    profile.source_key,
                    profile.tier.value,
                    now,
                ),
            )
            if not decision.accepted:
                return StoreResult()

            existing = conn.execute(
                """
                SELECT d.silver_document_id, p.point_id, p.event_id, c.claim_id
                FROM silver_documents d
                LEFT JOIN intelligence_points p USING (silver_document_id)
                LEFT JOIN claims c USING (point_id)
                WHERE d.raw_document_id = ?
                """,
                (raw_document_id,),
            ).fetchone()
            if existing:
                return StoreResult(**dict(existing))

            silver_id = _stable_id("silver", raw_document_id)
            event_key = _event_key(item, decision)
            event_id = _stable_id("event", event_key)
            point_id = _stable_id("point", raw_document_id)
            claim_id = _stable_id("claim", raw_document_id)
            published_at = item.published_at.isoformat()
            statement = (item.content or item.title).strip()
            language = str((item.metadata or {}).get("language") or "unknown")

            conn.execute(
                """
                INSERT INTO silver_documents (
                    silver_document_id, raw_document_id, canonical_text, title,
                    published_at, source_key, author, url, language, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    silver_id, raw_document_id, statement, item.title, published_at,
                    profile.source_key, profile.author, str(item.url), language, now,
                ),
            )
            conn.execute(
                """
                INSERT INTO events (
                    event_id, event_key, event_type, layer, title, event_time,
                    first_seen, last_seen, confidence_level,
                    independent_source_count, evidence_count, impact, urgency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'L4', 0, 0, ?, ?)
                ON CONFLICT(event_key) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    impact=CASE WHEN events.impact = 'high' THEN events.impact ELSE excluded.impact END,
                    urgency=CASE WHEN events.urgency = 'high' THEN events.urgency ELSE excluded.urgency END
                """,
                (
                    event_id, event_key, decision.event_type, decision.layer.value,
                    item.title, published_at, now, now, decision.impact, decision.urgency,
                ),
            )
            canonical_event_id = conn.execute(
                "SELECT event_id FROM events WHERE event_key = ?", (event_key,)
            ).fetchone()["event_id"]
            information_credibility = {
                "A": 1, "B": 2, "C": 3, "D": 4, "E": 5,
            }.get(profile.reliability, 6)
            conn.execute(
                """
                INSERT INTO intelligence_points (
                    point_id, silver_document_id, event_id, event_type, layer,
                    statement, impact, urgency, relevance_score, source_key,
                    source_reliability, information_credibility, independence_group,
                    pir_ids_json, indicator_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    point_id, silver_id, canonical_event_id, decision.event_type,
                    decision.layer.value, statement, decision.impact, decision.urgency,
                    decision.score, profile.source_key, profile.reliability,
                    information_credibility, profile.independence_group,
                    json.dumps(decision.pir_ids), json.dumps(decision.indicator_ids), now,
                ),
            )
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id, event_id, point_id, silver_document_id, statement,
                    verification_status, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, 'unverified', ?, ?)
                """,
                (
                    claim_id, canonical_event_id, point_id, silver_id,
                    statement, decision.score, now,
                ),
            )
            self._refresh_event(conn, canonical_event_id)
            return StoreResult(silver_id, point_id, canonical_event_id, claim_id)

    def _refresh_event(self, conn: sqlite3.Connection, event_id: str) -> None:
        aggregate = conn.execute(
            """
            SELECT COUNT(*) AS evidence_count,
                   COUNT(DISTINCT independence_group) AS independent_source_count,
                   COUNT(DISTINCT CASE
                       WHEN source_reliability IN ('A', 'B') THEN independence_group
                   END) AS reliable_source_count
            FROM intelligence_points
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        independent = int(aggregate["independent_source_count"] or 0)
        evidence = int(aggregate["evidence_count"] or 0)
        confidence_level = _confidence_level(
            independent,
            int(aggregate["reliable_source_count"] or 0),
        )
        conn.execute(
            """
            UPDATE events
            SET confidence_level = ?, independent_source_count = ?, evidence_count = ?
            WHERE event_id = ?
            """,
            (confidence_level, independent, evidence, event_id),
        )
        if independent >= 2:
            conn.execute(
                "UPDATE claims SET verification_status = 'supported' WHERE event_id = ?",
                (event_id,),
            )

    def list_events(self, *, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY last_seen DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
            events = [dict(row) for row in rows]
            for event in events:
                source_rows = conn.execute(
                    """
                    SELECT silver_document_id FROM intelligence_points
                    WHERE event_id = ? ORDER BY created_at
                    """,
                    (event["event_id"],),
                ).fetchall()
                event["source_silver_document_ids"] = [row[0] for row in source_rows]
            return events

    def list_claims(self, event_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE event_id = ? ORDER BY created_at", (event_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def list_points(self, *, limit: int = 100, event_id: str = "") -> list[dict]:
        with self._connect() as conn:
            query = """
                SELECT p.*, d.title, d.published_at, d.url, d.author
                FROM intelligence_points p
                JOIN silver_documents d USING (silver_document_id)
            """
            params: list[object] = []
            if event_id:
                query += " WHERE p.event_id = ?"
                params.append(event_id)
            query += " ORDER BY p.created_at DESC LIMIT ?"
            params.append(max(1, limit))
            rows = conn.execute(query, params).fetchall()
            points = [dict(row) for row in rows]
            for point in points:
                point["pir_ids"] = json.loads(point.pop("pir_ids_json"))
                point["indicator_ids"] = json.loads(point.pop("indicator_ids_json"))
            return points

    def get_collection_decision(self, raw_document_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM collection_decisions WHERE raw_document_id = ?",
                (raw_document_id,),
            ).fetchone()
            if not row:
                return None
            decision = dict(row)
            decision["reasons"] = json.loads(decision.pop("reasons_json"))
            decision["pir_ids"] = json.loads(decision.pop("pir_ids_json"))
            decision["indicator_ids"] = json.loads(decision.pop("indicator_ids_json"))
            return decision

    def quality_summary(self) -> dict:
        with self._connect() as conn:
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM collection_decisions GROUP BY status"
            ).fetchall()
            statuses = {row["status"]: int(row["count"]) for row in status_rows}
            tier_rows = conn.execute(
                "SELECT source_tier, COUNT(*) AS count FROM collection_decisions GROUP BY source_tier"
            ).fetchall()
            confidence_rows = conn.execute(
                "SELECT confidence_level, COUNT(*) AS count FROM events GROUP BY confidence_level"
            ).fetchall()
            total = sum(statuses.values())
            accepted = statuses.get("accepted", 0)
            return {
                "total_decisions": total,
                "accepted": accepted,
                "quarantined": statuses.get("quarantined", 0),
                "rejected": statuses.get("rejected", 0),
                "acceptance_rate": round(accepted / total, 4) if total else 0.0,
                "source_tiers": {row["source_tier"]: int(row["count"]) for row in tier_rows},
                "intelligence_points": int(conn.execute("SELECT COUNT(*) FROM intelligence_points").fetchone()[0]),
                "events": int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
                "claims": int(conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]),
                "events_by_confidence": {
                    row["confidence_level"]: int(row["count"]) for row in confidence_rows
                },
            }

    def decision_ids(self) -> set[str]:
        with self._connect() as conn:
            return {
                str(row[0])
                for row in conn.execute("SELECT raw_document_id FROM collection_decisions").fetchall()
            }

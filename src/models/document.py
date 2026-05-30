from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class RawChunk:
    sequence: int
    bytes_data: bytes
    last: bool

    @staticmethod
    def final(sequence: int) -> RawChunk:
        return RawChunk(sequence=sequence, bytes_data=b"", last=True)


@dataclass(frozen=True)
class RawDocument:
    raw_document_id: str
    job_id: str
    channel: str
    mime_type: str
    encoding: str
    body_ref: Optional[str]
    body_inline: Optional[str]
    headers_summary: dict
    captured_at: str
    collector_id: str
    collector_version: str
    source_url: Optional[str]
    source_system: str
    content_sha256: str
    classification: Optional[str] = None
    extensions: dict = field(default_factory=dict)
    ext_schema_version: Optional[str] = None
    tenant_id: str = "default"

    @classmethod
    def from_body(
        cls,
        *,
        job_id: str,
        channel: str,
        mime_type: str,
        body: str,
        collector_id: str,
        collector_version: str,
        source_url: Optional[str],
        source_system: str,
        headers_summary: Optional[dict] = None,
        tenant_id: str = "default",
    ) -> RawDocument:
        body_bytes = body.encode("utf-8")
        sha256 = hashlib.sha256(body_bytes).hexdigest()

        body_inline = body if len(body_bytes) < 65536 else None
        body_ref = None if body_inline else f"bronze://{sha256}"

        return cls(
            raw_document_id=str(uuid.uuid4()),
            job_id=job_id,
            channel=channel,
            mime_type=mime_type,
            encoding="utf-8",
            body_ref=body_ref,
            body_inline=body_inline,
            headers_summary=headers_summary or {},
            captured_at=datetime.now(timezone.utc).isoformat(),
            collector_id=collector_id,
            collector_version=collector_version,
            source_url=source_url,
            source_system=source_system,
            content_sha256=sha256,
            tenant_id=tenant_id,
        )

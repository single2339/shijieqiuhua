from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from backend.agents.collectors._utils import content_item_to_document
from backend.bronze_reader import scan_bronze
from backend.collectors.horizon.models import ContentItem, SourceType
from src.bronze import writer as writer_module
from src.bronze.writer import BronzeWriter
from src.models.document import RawDocument


def _document(*, body: str, raw_document_id: str = "doc-1") -> RawDocument:
    return RawDocument(
        raw_document_id=raw_document_id,
        job_id=str(uuid.uuid4()),
        channel="web",
        mime_type="text/plain",
        encoding="utf-8",
        body_ref=None,
        body_inline=body,
        headers_summary={},
        captured_at="2026-07-12T00:00:00+00:00",
        collector_id="test-collector",
        collector_version="1.0.0",
        source_url="https://example.test/article",
        source_system="test",
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


def test_large_body_ref_is_written_and_read_back(tmp_path: Path) -> None:
    body = "正文" * 40_000
    doc = RawDocument.from_body(
        job_id=str(uuid.uuid4()),
        channel="web",
        mime_type="text/plain",
        body=body,
        collector_id="test-collector",
        collector_version="1.0.0",
        source_url="https://example.test/large",
        source_system="test",
    )

    path = BronzeWriter(tmp_path).write(doc)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["body_ref"] == f"bronze://{doc.content_sha256}"
    assert "body_inline" not in payload
    assert (tmp_path / "_blobs" / doc.content_sha256).read_text(encoding="utf-8") == body
    assert scan_bronze(tmp_path)[0].text == body


def test_bronze_writer_replaces_json_atomically(tmp_path: Path, monkeypatch) -> None:
    replacements: list[tuple[str, str]] = []
    real_replace = os.replace

    def record_replace(source: str, destination: str) -> None:
        replacements.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(writer_module.os, "replace", record_replace)

    path = BronzeWriter(tmp_path).write(_document(body="atomic"))

    assert any(destination == str(path) for _, destination in replacements)
    assert json.loads(path.read_text(encoding="utf-8"))["body_inline"] == "atomic"


def test_raw_document_schema_accepts_current_and_legacy_generator_output(tmp_path: Path) -> None:
    writer = BronzeWriter(tmp_path)
    current_path = writer.write(_document(body="current"))
    legacy = RawDocument(
        raw_document_id="a" * 32,
        job_id="rss-bbc:123",
        channel="rss",
        mime_type="text/plain",
        encoding="utf-8",
        body_ref=None,
        body_inline="legacy",
        headers_summary={"collector": "rss-collector"},
        captured_at="2026-07-12T00:00:00+00:00",
        collector_id="rss-rss",
        collector_version="1.0",
        source_url="",
        source_system="BBC",
        content_sha256=hashlib.sha256(b"legacy").hexdigest(),
        tenant_id="",
    )
    legacy_path = writer.write(legacy)
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "raw-document.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert list(validator.iter_errors(json.loads(current_path.read_text(encoding="utf-8")))) == []
    assert list(validator.iter_errors(json.loads(legacy_path.read_text(encoding="utf-8")))) == []


def test_agent_collector_generator_emits_stable_schema_compatible_document(tmp_path: Path) -> None:
    item = ContentItem(
        id="rss:example:stable-entry",
        source_type=SourceType.RSS,
        title="Stable title",
        url="https://example.test/stable",
        content="Stable content",
        author="Example",
        published_at="2026-07-12T00:00:00+00:00",
    )

    first = content_item_to_document(item)
    second = content_item_to_document(item)

    assert first.raw_document_id == second.raw_document_id
    assert first.job_id == second.job_id
    assert first.channel == "web"
    assert first.collector_version == "1.0.0"
    assert first.tenant_id == "default"
    assert first.body_ref is None
    assert first.body_inline == "Stable content"

    path = BronzeWriter(tmp_path).write(first)
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "raw-document.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            json.loads(path.read_text(encoding="utf-8"))
        )
    )
    assert errors == []


def test_agent_collector_generator_persists_large_body_ref_blob(tmp_path: Path) -> None:
    body = "agent正文" * 20_000
    item = ContentItem(
        id="rss:example:large-entry",
        source_type=SourceType.RSS,
        title="Large stable title",
        url="https://example.test/large",
        content=body,
        author="Example",
        published_at="2026-07-12T00:00:00+00:00",
    )
    document = content_item_to_document(item)

    assert document.body_inline is None
    assert document.body_ref == f"bronze://{document.content_sha256}"
    BronzeWriter(tmp_path).write(document)
    assert (tmp_path / "_blobs" / document.content_sha256).read_text(encoding="utf-8") == body
    assert scan_bronze(tmp_path)[0].text == body

"""Unit tests for the summarization module."""

import asyncio
import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processor.summarizer import summarize_document
from src.models.document import RawDocument


def run(coro):
    return asyncio.run(coro)


class TestSummarizeDocument:
    def make_doc(self, body: str, **extensions) -> RawDocument:
        return RawDocument(
            raw_document_id="test-id",
            job_id="test-job",
            channel="web",
            mime_type="text/plain",
            encoding="utf-8",
            body_inline=body,
            body_ref=None,
            headers_summary={},
            captured_at="2026-01-01T00:00:00Z",
            collector_id="test",
            collector_version="1.0",
            source_url="https://example.com",
            source_system="test",
            content_sha256=hashlib.sha256(body.encode()).hexdigest(),
            tenant_id="default",
            extensions=extensions,
        )

    @patch(
        "src.processor.summarizer._summarize_with_llm",
        new_callable=lambda: AsyncMock(return_value="这是2-3句中文摘要"),
    )
    @patch(
        "src.processor.summarizer.LLM_API_KEY",
        new="sk-test-key",
    )
    def test_generates_summary(self, mock_summarize):
        doc = self.make_doc("Breaking news: major event in global geopolitics today.")
        result = run(summarize_document(doc))
        assert result.extensions.get("summary") == "这是2-3句中文摘要"
        assert result.extensions.get("summarized") is True
        mock_summarize.assert_called_once()

    @patch("src.processor.summarizer._summarize_with_llm", new_callable=AsyncMock)
    @patch("src.processor.summarizer.LLM_API_KEY", new="sk-test-key")
    def test_skips_empty_body(self, mock_summarize):
        doc = self.make_doc("")
        result = run(summarize_document(doc))
        mock_summarize.assert_not_called()
        assert result is doc

    @patch("src.processor.summarizer._summarize_with_llm", new_callable=AsyncMock)
    @patch("src.processor.summarizer.LLM_API_KEY", new="sk-test-key")
    def test_skips_already_summarized(self, mock_summarize):
        doc = self.make_doc("Some text", summarized=True, summary="Already done")
        result = run(summarize_document(doc))
        mock_summarize.assert_not_called()
        assert result is doc

    @patch(
        "src.processor.summarizer._summarize_with_llm",
        new_callable=lambda: AsyncMock(return_value=None),
    )
    @patch("src.processor.summarizer.LLM_API_KEY", new="sk-test-key")
    def test_returns_original_on_none_summary(self, mock_summarize):
        doc = self.make_doc("Some text that fails to summarize")
        result = run(summarize_document(doc))
        assert result is doc

    @patch("src.processor.summarizer._summarize_with_llm", new_callable=AsyncMock)
    @patch("src.processor.summarizer.LLM_API_KEY", new="")
    def test_skips_when_no_llm_key(self, mock_summarize):
        doc = self.make_doc("Some text, no API key configured")
        result = run(summarize_document(doc))
        mock_summarize.assert_not_called()
        assert result is doc

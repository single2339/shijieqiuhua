from datetime import datetime, timezone
import hashlib

import pytest

from backend.collectors.horizon.models import ContentItem, SourceType
from backend.collectors.horizon_bridge import _process_item_for_storage
from backend.models import IntelLayer
from backend.processors.processing_cache import ProcessingCache


def _item() -> ContentItem:
    return ContentItem(
        id="rss:test:1",
        source_type=SourceType.RSS,
        title="Military deployment reported near border",
        url="https://example.com/a",
        content="Military deployment reported near border with multiple units moving overnight.",
        author="Reuters",
        published_at=datetime.now(timezone.utc),
        metadata={},
    )


@pytest.mark.asyncio
async def test_fast_collection_processing_translates_but_skips_deep_llm(monkeypatch):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "fast")
    translations = []

    async def translate(text: str):
        translations.append(text)
        if "Military deployment" in text:
            return "边境附近出现军事部署报告"
        return text

    async def fail_summarize(*_args, **_kwargs):
        raise AssertionError("fast mode must not summarize through LLM")

    async def fail_classify(*_args, **_kwargs):
        raise AssertionError("fast mode must not classify through LLM")

    monkeypatch.setattr("backend.collectors.horizon_bridge.translate_text", translate)
    monkeypatch.setattr("backend.collectors.horizon_bridge._summarize_with_llm", fail_summarize)
    monkeypatch.setattr("backend.collectors.horizon_bridge.classify_with_llm", fail_classify)

    processed = await _process_item_for_storage(_item())

    assert translations
    assert processed.title == "边境附近出现军事部署报告"
    assert processed.content == "边境附近出现军事部署报告"
    assert processed.ai_summary
    assert processed.metadata["layer"] == "military"
    assert "location_country" in processed.metadata

@pytest.mark.asyncio
async def test_collection_processing_does_not_reuse_fast_cache_in_deep_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "deep")
    cache = ProcessingCache(tmp_path / "processing_cache.db")
    item = _item()
    content_hash = hashlib.sha256((item.content or "").encode()).hexdigest()
    cache.put(
        content_hash,
        translated_title="缓存标题",
        translated_content="缓存正文",
        summary="缓存摘要",
        layer="energy",
        country="中国",
        city="上海",
        mode="fast",
        llm_used=False,
    )

    async def translate(text: str):
        return text

    async def summarize(_text: str):
        return "深度摘要"

    async def classify(_title: str, _content: str):
        return IntelLayer.MILITARY, "", ""

    monkeypatch.setattr("backend.collectors.horizon_bridge.translate_text", translate)
    monkeypatch.setattr("backend.collectors.horizon_bridge._summarize_with_llm", summarize)
    monkeypatch.setattr("backend.collectors.horizon_bridge.classify_with_llm", classify)

    processed = await _process_item_for_storage(item, cache=cache)

    assert processed.title == item.title
    assert processed.content == item.content
    assert processed.ai_summary == "深度摘要"
    assert processed.metadata["layer"] == "military"
    assert cache.get(content_hash)["mode"] == "deep"

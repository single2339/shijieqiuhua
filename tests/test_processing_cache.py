from backend.processors.processing_cache import ProcessingCache


def test_processing_cache_round_trips_document_processing_result(tmp_path):
    cache = ProcessingCache(tmp_path / "processing_cache.db")

    cache.put(
        "hash-1",
        translated_title="中文标题",
        translated_content="中文正文",
        summary="确定性摘要",
        layer="energy",
        country="中国",
        city="上海",
        mode="fast",
        llm_used=False,
    )

    result = cache.get("hash-1")

    assert result is not None
    assert result["translated_title"] == "中文标题"
    assert result["translated_content"] == "中文正文"
    assert result["summary"] == "确定性摘要"
    assert result["layer"] == "energy"
    assert result["country"] == "中国"
    assert result["city"] == "上海"
    assert result["llm_used"] is False

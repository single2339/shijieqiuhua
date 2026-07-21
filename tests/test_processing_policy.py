from backend.processors.processing_policy import (
    ProcessingMode,
    deterministic_summary,
    get_processing_policy,
)


def test_processing_policy_defaults_to_fast(monkeypatch):
    monkeypatch.delenv("OSINT_PROCESSING_MODE", raising=False)

    policy = get_processing_policy()

    assert policy.mode == ProcessingMode.FAST
    assert policy.use_llm_translation is True
    assert policy.use_llm_summary is False
    assert policy.use_llm_classification is False


def test_processing_policy_deep_allows_llm(monkeypatch):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "deep")

    policy = get_processing_policy()

    assert policy.mode == ProcessingMode.DEEP
    assert policy.use_llm_translation is True
    assert policy.use_llm_summary is True
    assert policy.use_llm_classification is True


def test_deterministic_summary_prefers_title_and_short_lead():
    text = "第一段说明事件背景，包含足够的信息。第二段提供更多细节，但是不应该完整塞入摘要。"

    summary = deterministic_summary(text, title="港口能源供应异常", max_chars=40)

    assert summary.startswith("港口能源供应异常")
    assert len(summary) <= 40

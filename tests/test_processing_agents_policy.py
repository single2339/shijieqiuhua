import pytest

from backend.agents.models import AgentTask
from backend.agents.processors.classification import ClassificationAgent
from backend.agents.processors.summarization import SummarizationAgent
from backend.agents.processors.translation import TranslationAgent


@pytest.mark.asyncio
async def test_translation_agent_uses_llm_translation_in_fast_mode(monkeypatch):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "fast")
    agent = TranslationAgent()

    async def translate(text: str):
        assert text == "hello"
        return "你好"

    monkeypatch.setattr("src.processor.translation.translate_text", translate)

    result = await agent.run(AgentTask(task_type="translate", params={"text": "hello"}))

    assert result.data["translated"] == "你好"


@pytest.mark.asyncio
async def test_summarization_agent_uses_deterministic_summary_in_fast_mode(monkeypatch):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "fast")
    agent = SummarizationAgent()

    result = await agent.run(AgentTask(task_type="summarize", params={
        "text": "港口能源供应异常。多源报道显示供应链受阻。",
        "title": "能源供应",
    }))

    assert result.data["summary"].startswith("能源供应")


@pytest.mark.asyncio
async def test_classification_agent_uses_keyword_classifier_in_fast_mode(monkeypatch):
    monkeypatch.setenv("OSINT_PROCESSING_MODE", "fast")
    agent = ClassificationAgent()

    result = await agent.run(AgentTask(task_type="classify", params={
        "title": "Missile deployment reported",
        "content": "Military forces and missile systems deployed near border.",
    }))

    assert result.data["layer"] == "military"

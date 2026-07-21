import pytest

from backend.agents.intelligence.interpretation import InterpretationAgent
from backend.agents.intelligence.report_writer import ReportAgent
from backend.agents.models import AgentTask


@pytest.mark.asyncio
async def test_interpretation_is_template_first_by_default(monkeypatch):
    monkeypatch.delenv("INTERPRET_LLM_ENABLED", raising=False)
    agent = InterpretationAgent()

    async def fail_llm(*_args, **_kwargs):
        raise AssertionError("default interpretation must not call LLM")

    monkeypatch.setattr(agent, "_call_llm", fail_llm)

    result = await agent.run(
        AgentTask(task_type="interpret", params={
            "analysis_type": "events",
            "context": {"total_items": 3000, "total_clusters": 94, "unclustered_count": 0},
        })
    )

    assert "事件核查" in result.data["interpretation"]
    assert "3000" in result.data["interpretation"]


@pytest.mark.asyncio
async def test_report_writer_is_template_first_by_default(monkeypatch):
    monkeypatch.delenv("REPORT_LLM_ENABLED", raising=False)
    agent = ReportAgent(indexer=None)

    async def fail_llm(*_args, **_kwargs):
        raise AssertionError("default report generation must not call LLM")

    monkeypatch.setattr(agent, "_call_llm", fail_llm)

    result = await agent.run(
        AgentTask(task_type="report", params={
            "topic": "能源态势",
            "source_materials": [{
                "id": "item-1",
                "type": "item",
                "title": "港口能源供应异常",
                "summary": "多源报道显示供应链受阻",
                "source": "bbc",
                "sources": ["bbc", "guardian"],
                "date": "2026-06-01",
                "layer": "energy",
                "country": "中国",
            }],
        })
    )

    assert result.data["summary"].startswith("共1条情报")
    assert result.data["sections"]
    assert "港口能源供应异常" in result.data["sections"][0]["body"]

import pytest

from backend.agents.intelligence.report_writer import ReportAgent
from backend.agents.models import AgentTask


@pytest.mark.asyncio
async def test_report_writer_uses_selected_materials_without_indexer(monkeypatch):
    async def no_llm(*_args, **_kwargs):
        return None

    agent = ReportAgent(indexer=None)
    monkeypatch.setattr(agent, "_call_llm", no_llm)

    result = await agent.run(
        AgentTask(
            task_type="report",
            params={
                "topic": "能源态势",
                "source_materials": [
                    {
                        "id": "item-1",
                        "type": "item",
                        "title": "港口能源供应异常",
                        "summary": "多源报道显示供应链受阻",
                        "source": "bbc",
                        "sources": ["bbc", "guardian"],
                        "date": "2026-06-01",
                        "layer": "energy",
                        "country": "中国",
                    }
                ],
            },
        )
    )

    assert result.data["item_count"] == 1
    assert result.data["source_count"] == 2
    assert "港口能源供应异常" in result.data["sections"][0]["body"]

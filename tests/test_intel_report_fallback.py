from types import SimpleNamespace

import pytest

from backend import main
from backend.models import ReportRequest


@pytest.mark.asyncio
async def test_intel_report_falls_back_when_opencode_returns_empty_placeholder(monkeypatch):
    async def placeholder_agent(*_args, **_kwargs):
        return "Agent 未产生文本输出，请尝试重新提问。"

    class FakeLocalAgent:
        async def run(self, _task):
            return SimpleNamespace(
                data={
                    "title": "态势简报：能源态势",
                    "summary": "本地简报已基于候选材料生成。",
                    "sections": [{"heading": "## energy 层面", "body": "- 港口能源供应异常"}],
                    "item_count": 1,
                    "source_count": 1,
                }
            )

    monkeypatch.setattr(main, "_run_opencode_agent", placeholder_agent)
    monkeypatch.setattr(main, "_get_indexer", lambda: None)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_args, **_kwargs: FakeLocalAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_args, **_kwargs: None)

    response = await main.intel_report(
        ReportRequest(
            topic="能源态势",
            source_materials=[
                {
                    "id": "item-1",
                    "type": "item",
                    "title": "港口能源供应异常",
                    "source": "bbc",
                    "sources": ["bbc"],
                    "date": "2026-06-01",
                    "layer": "energy",
                }
            ],
        ),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.summary == "本地简报已基于候选材料生成。"
    assert response.item_count == 1
    assert response.sections[0].body == "- 港口能源供应异常"

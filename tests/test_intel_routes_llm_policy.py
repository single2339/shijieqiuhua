from types import SimpleNamespace

import pytest

from backend import main
from backend.models import AnalysisInterpretRequest, ReportRequest


@pytest.mark.asyncio
async def test_intel_interpret_route_skips_opencode_by_default(monkeypatch):
    monkeypatch.delenv("OPENCODE_INTERPRET_ENABLED", raising=False)
    calls = 0

    async def fail_opencode(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return "不应出现"

    class FakeLocalAgent:
        async def run(self, _task):
            return SimpleNamespace(data={"analysis_type": "events", "interpretation": "本地解读"})

    monkeypatch.setattr(main, "_run_opencode_agent", fail_opencode)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_args, **_kwargs: FakeLocalAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_args, **_kwargs: None)

    response = await main.intel_interpret(
        AnalysisInterpretRequest(analysis_type="events", context={}),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.interpretation == "本地解读"
    assert calls == 0


@pytest.mark.asyncio
async def test_intel_report_route_skips_opencode_by_default(monkeypatch):
    monkeypatch.delenv("OPENCODE_REPORT_ENABLED", raising=False)
    calls = 0

    async def fail_opencode(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return "不应出现"

    monkeypatch.setattr(main, "_run_opencode_agent", fail_opencode)
    monkeypatch.setattr(main, "record_activity", lambda *_args, **_kwargs: None)

    response = await main.intel_report(
        ReportRequest(
            topic="能源态势",
            source_materials=[{
                "id": "item-1",
                "type": "item",
                "title": "港口能源供应异常",
                "summary": "多源报道显示供应链受阻",
                "source": "bbc",
                "sources": ["bbc", "guardian"],
                "date": "2026-06-01",
                "layer": "energy",
            }],
        ),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.item_count == 1
    assert "港口能源供应异常" in response.summary or response.sections
    assert calls == 0

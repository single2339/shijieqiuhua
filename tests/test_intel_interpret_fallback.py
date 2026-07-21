from types import SimpleNamespace

import pytest

from backend import main
from backend.models import AnalysisInterpretRequest


class _FakeInterpretAgent:
    async def run(self, _task):
        return SimpleNamespace(
            data={
                "analysis_type": "events",
                "interpretation": "本地解释器已完成事件核查解读。",
            }
        )


@pytest.mark.asyncio
async def test_intel_interpret_falls_back_when_opencode_returns_empty_placeholder(monkeypatch):
    async def placeholder_agent(*_args, **_kwargs):
        return "Agent 未产生文本输出，请尝试重新提问。"

    monkeypatch.setattr(main, "_run_opencode_agent", placeholder_agent)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_args, **_kwargs: _FakeInterpretAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_args, **_kwargs: None)

    response = await main.intel_interpret(
        AnalysisInterpretRequest(analysis_type="events", context={"total_clusters": 3}),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.interpretation == "本地解释器已完成事件核查解读。"


@pytest.mark.asyncio
async def test_intel_interpret_uses_short_configurable_opencode_timeout(monkeypatch):
    calls = []

    async def fake_agent(agent, prompt, timeout=180):
        calls.append({"agent": agent, "prompt": prompt, "timeout": timeout})
        return "OpenCode 实时核查解读。"

    monkeypatch.setenv("OPENCODE_INTERPRET_TIMEOUT", "35")
    monkeypatch.setenv("OPENCODE_INTERPRET_ENABLED", "true")
    monkeypatch.setattr(main, "_run_opencode_agent", fake_agent)
    monkeypatch.setattr(main, "record_activity", lambda *_args, **_kwargs: None)

    response = await main.intel_interpret(
        AnalysisInterpretRequest(analysis_type="events", context={"total_clusters": 3}),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.interpretation == "OpenCode 实时核查解读。"
    assert calls[0]["agent"] == "intel-interpreter"
    assert calls[0]["timeout"] == 35

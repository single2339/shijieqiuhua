"""SummarizationAgent — wraps src.processor.summarizer._summarize_with_llm()."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class SummarizationAgent(BaseAgent):
    agent_id = "summarizer"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.processors.processing_policy import deterministic_summary, get_processing_policy
        from src.processor.summarizer import _summarize_with_llm

        text = task.params.get("text", "")
        title = task.params.get("title", "")
        if not get_processing_policy().use_llm_summary:
            return {"summary": deterministic_summary(text, title=title) or text}
        result = await _summarize_with_llm(text)
        return {"summary": result or deterministic_summary(text, title=title) or text}

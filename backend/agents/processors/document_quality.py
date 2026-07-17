"""Document quality agent without hypothesis-truth claims."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class DocumentQualityAgent(BaseAgent):
    agent_id = "document_quality"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.agents.intelligence._bayesian import assess_document_quality

        return assess_document_quality(
            task.params.get("text", ""),
            task.params.get("source_system", ""),
        )

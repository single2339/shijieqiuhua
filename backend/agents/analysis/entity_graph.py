"""Entity graph analysis agent — extracts entities and co-occurrence relationships."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import extract_entity_graph


@AgentRegistry.register
class EntityGraphAgent(BaseAgent):
    agent_id = "entity_graph"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return extract_entity_graph(items)

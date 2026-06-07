"""Corroboration analysis agent — cross-source agreement matrix between sources."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import compute_corroboration


@AgentRegistry.register
class CorroborationAgent(BaseAgent):
    agent_id = "corroboration"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return compute_corroboration(items)

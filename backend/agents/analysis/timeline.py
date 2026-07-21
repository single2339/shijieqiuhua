"""Timeline analysis agent — groups intel items by date and computes layer distribution."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import compute_timeline


@AgentRegistry.register
class TimelineAgent(BaseAgent):
    agent_id = "timeline"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return compute_timeline(items)

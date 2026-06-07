"""Gap analysis agent — identifies topic, region, time, and cross-source coverage gaps."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import analyze_gaps


@AgentRegistry.register
class GapAnalysisAgent(BaseAgent):
    agent_id = "gap_analyzer"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return analyze_gaps(items)

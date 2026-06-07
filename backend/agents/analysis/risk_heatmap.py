"""Risk heatmap agent — regional risk scoring by intel density, confidence, and layer risk."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import compute_risk_heatmap


@AgentRegistry.register
class RiskHeatmapAgent(BaseAgent):
    agent_id = "risk_heatmap"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return compute_risk_heatmap(items)

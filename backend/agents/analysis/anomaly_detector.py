"""Anomaly detection agent — Z-score based anomaly detection on layer-date counts."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry
from backend.processors.analysis import detect_anomalies


@AgentRegistry.register
class AnomalyDetectionAgent(BaseAgent):
    agent_id = "anomaly_detector"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        items = task.params.get("items", [])
        return detect_anomalies(items)

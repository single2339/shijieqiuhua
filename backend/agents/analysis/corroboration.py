"""Corroboration analysis agent — cross-source agreement matrix between sources."""

from __future__ import annotations

import asyncio
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
        # compute_corroboration runs event clustering over the full window;
        # keep it off the event loop so dashboard polling stays responsive.
        return await asyncio.to_thread(compute_corroboration, items)

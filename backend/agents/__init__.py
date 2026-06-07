"""Multi-agent system for osint-network.

Agents are independent async units that encapsulate a piece of business logic.
They are registered via AgentRegistry and orchestrated by OrchestratorAgent.

Usage:
    from backend.agents import AgentRegistry

    agent = AgentRegistry.create("qa_analyst")
    result = await agent.run(task)
"""

from backend.agents.base import (
    AgentCallbacks,
    AgentEvent,
    AgentStatus,
    AgentType,
    BaseAgent,
)
from backend.agents.config import is_agent_mode
from backend.agents.models import AgentResult, AgentTask, PipelineContext
from backend.agents.registry import AgentRegistry

__all__ = [
    "AgentCallbacks",
    "AgentEvent",
    "AgentRegistry",
    "AgentResult",
    "AgentStatus",
    "AgentTask",
    "AgentType",
    "BaseAgent",
    "PipelineContext",
    "is_agent_mode",
]

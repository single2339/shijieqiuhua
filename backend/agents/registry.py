"""Agent registry — decorator-based registration with lazy import support."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.base import BaseAgent, AgentCallbacks, AgentType

log = logging.getLogger(__name__)


class AgentRegistry:
    _agents: dict[str, type[BaseAgent]] = {}
    _module_hints: dict[str, str] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseAgent]) -> type[BaseAgent]:
        cls._agents[agent_cls.agent_id] = agent_cls
        log.debug("Registered agent: %s", agent_cls.agent_id)
        return agent_cls

    @classmethod
    def get(cls, agent_id: str) -> type[BaseAgent]:
        if agent_id not in cls._agents and agent_id in cls._module_hints:
            importlib.import_module(cls._module_hints[agent_id])
        if agent_id not in cls._agents:
            raise KeyError(f"Agent '{agent_id}' not registered. Available: {list(cls._agents)}")
        return cls._agents[agent_id]

    @classmethod
    def create(cls, agent_id: str, callbacks: AgentCallbacks | None = None, **kwargs) -> BaseAgent:
        agent_cls = cls.get(agent_id)
        return agent_cls(callbacks=callbacks, **kwargs)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._agents)

    @classmethod
    def list_by_type(cls, agent_type: AgentType) -> list[str]:
        return [aid for aid, a in cls._agents.items() if a.agent_type == agent_type]

    @classmethod
    def hint(cls, agent_id: str, module_path: str) -> None:
        """Register a lazy-load hint so agent modules are imported on first use."""
        cls._module_hints[agent_id] = module_path

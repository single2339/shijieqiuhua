"""Base agent class and shared types.

Pattern ported from intel-verify's BaseAgent, adapted for osint-network's
httpx-based LLM client and broader task semantics.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

import httpx

from backend.agents.config import load_agent_config
from backend.agents.skill import Skill, SkillLoader
from backend.llm_config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, get_llm_client

log = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    COLLECTION = "collection"
    PROCESSING = "processing"
    ANALYSIS = "analysis"
    INTELLIGENCE = "intelligence"
    SYSTEM = "system"


@dataclass
class AgentEvent:
    agent_id: str
    event_type: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCallbacks:
    on_event: Optional[Callable[[AgentEvent], Awaitable[None]]] = None
    on_status_change: Optional[Callable[[str, AgentStatus, AgentStatus], Awaitable[None]]] = None
    on_error: Optional[Callable[[str, str], Awaitable[None]]] = None


class BaseAgent(ABC):
    agent_id: str = "base"
    agent_type: AgentType = AgentType.PROCESSING

    def __init__(self, callbacks: AgentCallbacks | None = None):
        self.callbacks = callbacks or AgentCallbacks()
        self.status = AgentStatus.IDLE
        cfg = load_agent_config(self.agent_id)
        self.model = cfg.get("model", LLM_MODEL)
        self.max_tokens = cfg.get("max_tokens", 1024)
        self.temperature = cfg.get("temperature", 0.3)
        self._loaded_skills: list[Skill] = []

    def load_skill(self, name: str) -> None:
        skill = SkillLoader.load(name)
        self._loaded_skills.append(skill)

    def load_skills(self, names: list[str]) -> None:
        for name in names:
            self.load_skill(name)

    def _build_system_prompt(self, base: str) -> str:
        parts = [base]
        for skill in self._loaded_skills:
            aug = skill.render_prompt_augment()
            if aug:
                parts.append(aug)
        return "\n\n".join(parts)

    def _skill_param(self, key: str, default):
        for skill in reversed(self._loaded_skills):
            if key in skill.params:
                return skill.params[key]
        return default

    async def _call_llm(
        self, system: str, user: str, temperature: float | None = None
    ) -> str | None:
        if not LLM_API_KEY:
            return None
        temp = temperature if temperature is not None else self._skill_param("temperature", self.temperature)
        max_tok = self._skill_param("max_tokens", self.max_tokens)
        merged_system = self._build_system_prompt(system)
        payload = {
            "model": self.model,
            "max_tokens": max_tok,
            "messages": [
                {"role": "system", "content": merged_system},
                {"role": "user", "content": user},
            ],
            "temperature": temp,
        }
        try:
            async with get_llm_client() as client:
                r = await client.post(f"{LLM_BASE_URL}/chat/completions", json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                log.warning("Agent %s LLM call returned %d: %s", self.agent_id, r.status_code, r.text[:200])
        except httpx.HTTPError as exc:
            log.warning("Agent %s LLM HTTP error: %s", self.agent_id, exc)
        except Exception:
            log.exception("Agent %s LLM unexpected error", self.agent_id)
        return None

    async def _update_status(self, new_status: AgentStatus) -> None:
        old = self.status
        self.status = new_status
        if self.callbacks.on_status_change:
            try:
                await self.callbacks.on_status_change(self.agent_id, old, new_status)
            except Exception:
                log.exception("Agent %s status callback failed", self.agent_id)

    async def _emit_event(self, event: AgentEvent) -> None:
        if self.callbacks.on_event:
            try:
                await self.callbacks.on_event(event)
            except Exception:
                log.exception("Agent %s event callback failed", self.agent_id)

    async def run(self, task: "AgentTask") -> "AgentResult":
        from backend.agents.models import AgentResult

        if task.skills:
            self.load_skills(task.skills)

        await self._update_status(AgentStatus.RUNNING)
        t0 = time.monotonic()
        try:
            data = await self._execute(task)
            duration = (time.monotonic() - t0) * 1000
            await self._update_status(AgentStatus.COMPLETED)
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                data=data,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            await self._update_status(AgentStatus.FAILED)
            if self.callbacks.on_error:
                try:
                    await self.callbacks.on_error(self.agent_id, str(exc))
                except Exception:
                    pass
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.FAILED,
                data={},
                error=str(exc),
                duration_ms=duration,
            )

    @abstractmethod
    async def _execute(self, task: "AgentTask") -> dict[str, Any]:
        ...

"""Agent task, result, and pipeline context models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.base import AgentStatus


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=_new_id)
    task_type: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_task_id: str | None = None
    skills: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    task_id: str
    agent_id: str
    status: AgentStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class PipelineContext:
    """Carries shared state through a pipeline run.

    Agents read and write to this object without a database —
    everything is ephemeral for the duration of one run.
    """

    def __init__(self, run_id: str = "", storage_root: Path | None = None):
        self.run_id = run_id or _new_id()
        self.storage_root = storage_root or Path("bronze_storage")
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: list[dict[str, Any]] = []
        self.metrics: dict[str, float] = {}
        self.collected: list[dict[str, Any]] = []

    def record(self, agent_id: str, duration_ms: float) -> None:
        self.metrics[agent_id] = duration_ms

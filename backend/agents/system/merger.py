"""MergeAgent — wraps backend/merger.py union-find content merge engine."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class MergeAgent(BaseAgent):
    agent_id = "merger"
    agent_type = AgentType.SYSTEM

    def __init__(self, callbacks=None, storage_root: Path | None = None):
        super().__init__(callbacks)
        self.storage_root = storage_root or Path("bronze_storage")

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.merger import build_merge_index, load_merge_index

        action = task.params.get("action", "build")
        storage = Path(task.params.get("storage_root", self.storage_root))

        if action == "load":
            idx = await asyncio.get_running_loop().run_in_executor(
                None, load_merge_index, storage
            )
            if idx is None:
                return {"status": "no_index", "groups": 0}
            return {
                "status": "ok",
                "groups": len(idx.groups),
                "generated_at": idx.generated_at,
            }

        result = await asyncio.get_running_loop().run_in_executor(
            None, build_merge_index, storage
        )
        return {
            "status": "ok",
            "groups": len(result.groups),
            "generated_at": result.generated_at,
        }

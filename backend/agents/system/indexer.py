"""IndexAgent — wraps backend/indexer.py SQLite-based document index."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class IndexAgent(BaseAgent):
    agent_id = "indexer"
    agent_type = AgentType.SYSTEM

    def __init__(self, callbacks=None, storage_root: Path | None = None):
        super().__init__(callbacks)
        self.storage_root = storage_root or Path("bronze_storage")
        self._indexer = None

    def _get_indexer(self):
        if self._indexer is None:
            from backend.indexer import Indexer
            self._indexer = Indexer(self.storage_root)
        return self._indexer

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        action = task.params.get("action", "build")
        idx = self._get_indexer()

        if action == "build":
            await asyncio.get_running_loop().run_in_executor(None, idx.build_index)
            return {"status": "ok", "count": idx.count()}

        elif action == "update":
            docs = task.params.get("docs", [])
            await asyncio.get_running_loop().run_in_executor(
                None, idx.incremental_update, docs
            )
            return {"status": "ok", "count": idx.count()}

        elif action == "query":
            sql = task.params.get("sql", "")
            params = task.params.get("params", [])
            rows = await asyncio.get_running_loop().run_in_executor(
                None, lambda: idx.query(sql, params)
            )
            return {"status": "ok", "rows": rows}

        elif action == "stats":
            return {"status": "ok", "stats": idx.stats()}

        return {"error": f"Unknown action: {action}"}

    def get_all(self):
        return self._get_indexer().get_all()

    def get_by_id(self, doc_id: str):
        return self._get_indexer().get_by_id(doc_id)

    def close(self):
        if self._indexer:
            self._indexer.close()
            self._indexer = None

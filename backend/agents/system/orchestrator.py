"""OrchestratorAgent — central scheduler for collection and merge pipelines."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from backend.agents.base import AgentCallbacks, AgentEvent, AgentStatus, AgentType, BaseAgent
from backend.agents.models import AgentResult, AgentTask, PipelineContext
from backend.agents.registry import AgentRegistry

log = logging.getLogger(__name__)

HORIZON_INTERVAL = 15 * 60  # 15 minutes
MERGE_HOUR_UTC = 3


@AgentRegistry.register
class OrchestratorAgent(BaseAgent):
    """Central orchestrator — runs collection loops and scheduled tasks.

    In agent mode, replaces horizon_loop() and merge_loop() from main.py.
    """

    agent_id = "orchestrator"
    agent_type = AgentType.SYSTEM

    def __init__(self, callbacks: AgentCallbacks | None = None, storage_root: Path | None = None):
        super().__init__(callbacks)
        self.storage_root = storage_root or Path("bronze_storage")
        self._collection_task: asyncio.Task | None = None
        self._merge_task: asyncio.Task | None = None
        self._last_collection: dict[str, dict] = {}
        self._collecting = False

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        action = task.params.get("action", "collect")
        if action == "collect":
            return await self._run_collection_cycle(task.params.get("hours", 48))
        elif action == "merge":
            return await self._run_merge()
        elif action == "status":
            return self._get_status()
        return {"error": f"Unknown action: {action}"}

    async def _run_collection_cycle(self, hours: int = 48) -> dict[str, Any]:
        if self._collecting:
            return {"status": "already_running"}
        self._collecting = True
        try:
            await self._emit_event(AgentEvent(
                agent_id=self.agent_id,
                event_type="collection_started",
                data={"hours": hours},
            ))

            collector_ids = ["rss_collector"]
            if AgentRegistry._agents.get("reddit_collector"):
                collector_ids.extend(["reddit_collector", "hackernews_collector",
                                      "telegram_collector", "github_collector"])

            results: dict[str, dict] = {}
            storage = str(self.storage_root)

            async def _run_collector(aid: str) -> tuple[str, dict]:
                try:
                    agent = AgentRegistry.create(aid, callbacks=self.callbacks)
                    task = AgentTask(
                        task_type="collect",
                        params={"hours": hours, "storage_root": storage},
                    )
                    result = await agent.run(task)
                    if result.status == AgentStatus.FAILED:
                        return (aid, {"error": result.error or "collector failed"})
                    return (aid, result.data)
                except Exception as exc:
                    log.warning("Collector %s failed: %s", aid, exc)
                    return (aid, {"error": str(exc)})

            pairs = await asyncio.gather(*[_run_collector(cid) for cid in collector_ids])
            results = dict(pairs)
            self._last_collection = results
            self._last_collection["_ts"] = datetime.now(timezone.utc).isoformat()

            await self._emit_event(AgentEvent(
                agent_id=self.agent_id,
                event_type="collection_completed",
                data=results,
            ))
            return results
        finally:
            self._collecting = False

    async def _run_merge(self) -> dict[str, Any]:
        from backend.merger import build_merge_index
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, build_merge_index, self.storage_root)
        return result

    def _get_status(self) -> dict[str, Any]:
        return {
            "collecting": self._collecting,
            "last_collection": self._last_collection,
            "storage_root": str(self.storage_root),
        }

    # ── Background loops (call from lifespan) ──

    async def start_collection_loop(self) -> None:
        """Run collection every HORIZON_INTERVAL seconds. Cancel to stop."""

        async def _loop() -> None:
            while True:
                try:
                    await self._run_collection_cycle(hours=48)
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("Collection cycle failed")
                await asyncio.sleep(HORIZON_INTERVAL)

        self._collection_task = asyncio.create_task(_loop())

    async def start_merge_loop(self) -> None:
        """Run merge daily at MERGE_HOUR_UTC."""

        async def _loop() -> None:
            while True:
                now = datetime.now(timezone.utc)
                next_run = now.replace(hour=MERGE_HOUR_UTC, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    next_run += timedelta(days=1)
                wait_sec = (next_run - now).total_seconds()
                try:
                    await asyncio.sleep(wait_sec)
                    await self._run_merge()
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("Merge cycle failed")
                    await asyncio.sleep(3600)

        self._merge_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        for t in [self._collection_task, self._merge_task]:
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

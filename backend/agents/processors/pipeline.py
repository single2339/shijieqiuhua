"""CollectionPipelineAgent — composable processing chain for raw content."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class CollectionPipelineAgent(BaseAgent):
    """Chains translate → summarize → classify → locate.

    Bayesian scoring is available only when explicitly enabled by task.params.
    """

    agent_id = "collection_pipeline"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        text = task.params.get("text", "")
        source_system = task.params.get("source_system", "")
        title = task.params.get("title", "")
        steps_enabled = {
            "translate": task.params.get("translate", True),
            "summarize": task.params.get("summarize", True),
            "classify": task.params.get("classify", True),
            "locate": task.params.get("locate", True),
            "bayesian": task.params.get("bayesian", False),
        }

        result: dict[str, Any] = {"original": text[:200]}
        working_text = text
        working_title = title

        if steps_enabled["translate"]:
            agent = AgentRegistry.create("translator", callbacks=self.callbacks)
            r = await agent.run(AgentTask(task_type="translate", params={"text": working_text}))
            working_text = r.data.get("translated", working_text)
            if working_title:
                r2 = await agent.run(AgentTask(task_type="translate", params={"text": working_title}))
                working_title = r2.data.get("translated", working_title)
            result["translated"] = working_text[:200]

        if steps_enabled["summarize"]:
            agent = AgentRegistry.create("summarizer", callbacks=self.callbacks)
            r = await agent.run(AgentTask(task_type="summarize", params={"text": working_text}))
            result["summary"] = r.data.get("summary", "")[:300]

        if steps_enabled["classify"]:
            agent = AgentRegistry.create("classifier", callbacks=self.callbacks)
            r = await agent.run(AgentTask(task_type="classify", params={
                "title": working_title, "content": working_text,
            }))
            result["layer"] = r.data.get("layer", "")
            result["country"] = r.data.get("country", "")

        if steps_enabled["locate"]:
            agent = AgentRegistry.create("location_extractor", callbacks=self.callbacks)
            r = await agent.run(AgentTask(task_type="locate", params={"text": working_text}))
            result["location"] = {
                "country": r.data.get("country", ""),
                "city": r.data.get("city", ""),
                "lat": r.data.get("lat", 0.0),
                "lng": r.data.get("lng", 0.0),
            }

        if steps_enabled["bayesian"]:
            agent = AgentRegistry.create("bayesian_scorer", callbacks=self.callbacks)
            r = await agent.run(AgentTask(task_type="bayesian_score", params={
                "text": working_text, "source_system": source_system,
            }))
            result["bayesian"] = {
                "posterior": r.data.get("posterior", 0.5),
                "verdict": r.data.get("verdict", "uncertain"),
                "prior_quality": r.data.get("prior_quality", ""),
                "prior_class": r.data.get("prior_class", ""),
            }

        return result

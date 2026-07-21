"""ClassificationAgent — wraps backend.processors.llm_classifier.classify_with_llm()."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class ClassificationAgent(BaseAgent):
    agent_id = "classifier"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.processors.classifier import classify
        from backend.processors.llm_classifier import classify_with_llm
        from backend.processors.location import extract_location_with_fallback
        from backend.processors.processing_policy import get_processing_policy

        title = task.params.get("title", "")
        content = task.params.get("content", "")
        if not get_processing_policy().use_llm_classification:
            text = f"{title}\n{content}"
            layer = classify(text)
            country, city, _lat, _lng = extract_location_with_fallback(text)
            return {
                "layer": layer.value,
                "country": country or "",
                "city": city or "",
            }
        layer, country, city = await classify_with_llm(title, content)
        return {
            "layer": layer.value,
            "country": country or "",
            "city": city or "",
        }

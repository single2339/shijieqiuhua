"""LocationExtractionAgent — wraps backend.processors.location.extract_location_with_fallback()."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class LocationExtractionAgent(BaseAgent):
    agent_id = "location_extractor"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.processors.location import extract_location_with_fallback

        text = task.params.get("text", "")
        source = task.params.get("source_system", "")
        country, city, lat, lng = extract_location_with_fallback(text, source)
        return {
            "country": country,
            "city": city,
            "lat": lat,
            "lng": lng,
        }

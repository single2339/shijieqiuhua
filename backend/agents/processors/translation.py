"""TranslationAgent — wraps src.processor.translation.translate_text()."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class TranslationAgent(BaseAgent):
    agent_id = "translator"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.processors.processing_policy import get_processing_policy
        from src.processor.translation import translate_text

        text = task.params.get("text", "")
        if not get_processing_policy().use_llm_translation:
            return {"translated": text}
        result = await translate_text(text)
        return {"translated": result or text}

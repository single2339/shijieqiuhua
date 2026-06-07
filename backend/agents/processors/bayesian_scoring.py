"""BayesianScoringAgent — wraps backend.agents.intelligence._bayesian.compute_bayesian()."""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry


@AgentRegistry.register
class BayesianScoringAgent(BaseAgent):
    agent_id = "bayesian_scorer"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        from backend.agents.intelligence._bayesian import compute_bayesian

        text = task.params.get("text", "")
        source = task.params.get("source_system", "")
        posterior, trace, verdict, method, quality, src_class, evidence = \
            compute_bayesian(text, source)
        return {
            "posterior": posterior,
            "trace": trace,
            "verdict": verdict.value,
            "method": method,
            "prior_quality": quality,
            "prior_class": src_class,
            "evidence_items": evidence,
        }

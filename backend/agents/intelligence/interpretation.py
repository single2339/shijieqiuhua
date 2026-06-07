"""Interpretation agent — generates AI interpretation for analysis views."""

from __future__ import annotations

import json
import os
from typing import Any

from backend.agents.base import AgentType, BaseAgent
from backend.agents.models import AgentTask
from backend.agents.registry import AgentRegistry

_ANALYSIS_PROMPTS: dict[str, str] = {
    "timeline": (
        "你是一名专业的情报分析官。基于以下时间线统计数据，用简体中文进行阶段性分析总结"
        "（200-400字）：识别事件发展的关键阶段、转折点和时间模式。"
        "只使用提供的数据，不编造信息。"
    ),
    "entities": (
        "你是一名专业的情报网络分析师。基于以下实体关联数据，用简体中文分析情报网络结构"
        "（200-400字）：识别人物、组织和地点之间的关键节点、聚类和桥梁实体。"
        "只使用提供的数据，不编造信息。"
    ),
    "corroboration": (
        "你是一名专业的情报来源分析官。基于以下信源一致性数据，用简体中文分析报道格局"
        "（200-400字）：识别信息茧房、独立验证最强的报道，以及可能存在的虚假信息。"
        "只使用提供的数据，不编造信息。"
    ),
    "anomalies": (
        "你是一名专业的情报预警分析官。基于以下异常检测数据，用简体中文解释可能的原因"
        "（200-400字）：对检测到的情报量异常激增提出合理解释假设。"
        "只使用提供的数据，不编造信息。"
    ),
    "risk-heatmap": (
        "你是一名战略风险评估专家。基于以下区域风险数据，用简体中文进行战略评估"
        "（200-400字）：分析高风险区域的风险驱动因素和可能的地缘政治影响。"
        "只使用提供的数据，不编造信息。"
    ),
    "gaps": (
        "你是一名情报采集规划专家。基于以下情报缺口数据，用简体中文提出采集优先级建议"
        "（200-400字）：建议优先填补哪些缺口以及可能的采集策略。"
        "只使用提供的数据，不编造信息。"
    ),
}


def _template_interpretation(analysis_type: str, context: dict[str, Any]) -> str:
    if analysis_type == "events":
        total_items = context.get("total_items", 0)
        total_clusters = context.get("total_clusters", 0)
        unclustered = context.get("unclustered_count", 0)
        return (
            f"事件核查：当前窗口包含 {total_items} 条样本，形成 {total_clusters} 个事件簇，"
            f"未入簇线索 {unclustered} 条。建议优先查看多源支撑事件，并对单源高敏线索补充反证。"
        )
    if analysis_type == "warnings":
        level = context.get("overall_level", "normal")
        count = context.get("active_indicator_count", 0)
        return f"预警指标：当前整体等级为 {level}，活跃指标 {count} 个。优先处理高等级指标的证据链和复核任务。"
    if analysis_type == "timeline":
        points = context.get("points", [])
        return f"态势时间线：当前时间窗口包含 {len(points)} 个时间点。重点关注样本激增日期和跨图层同步变化。"
    if analysis_type == "gaps":
        gaps = context.get("gaps", [])
        return f"情报缺口：当前识别 {len(gaps)} 个缺口。优先补齐高严重度主题、地区和多源验证缺口。"
    return "分析解读：已基于当前结构化数据生成初步判断。请优先核查来源链路、独立来源数量和待确认问题。"


@AgentRegistry.register
class InterpretationAgent(BaseAgent):
    agent_id = "interpretation"
    agent_type = AgentType.INTELLIGENCE

    async def _execute(self, task: AgentTask) -> dict[str, Any]:
        analysis_type = task.params.get("analysis_type", "timeline")
        context = task.params.get("context", {})

        fallback = _template_interpretation(analysis_type, context)
        if os.getenv("INTERPRET_LLM_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
            return {
                "analysis_type": analysis_type,
                "interpretation": fallback,
            }

        system_prompt = _ANALYSIS_PROMPTS.get(analysis_type, _ANALYSIS_PROMPTS["timeline"])
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        user_prompt = f"## 分析数据\n\n{context_json}\n\n请生成分析解读。"
        result = await self._call_llm(system_prompt, user_prompt, temperature=0.3)

        return {
            "analysis_type": analysis_type,
            "interpretation": result or fallback,
        }

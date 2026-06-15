"""Confidence rating (W2.4 — extracted from pipeline.py).

Maps the evidence + factor state to an L1-L4 grade aligned with osint-core:
- L1: ≥ 3 distinct sources AND fundamental evidence → 事实确凿
- L2: ≥ 2 distinct sources AND fundamental evidence → 高度可信
- L3: ≥ 1 distinct source → 中等可信
- L4: otherwise → 推测
"""
from __future__ import annotations

from ..models import (
    ConfidenceRating,
    FactorImpact,
    MatchProfile,
    OsintEvidence,
)


def grade(
    profile: MatchProfile,
    evidence: list[OsintEvidence],
    factors: list[FactorImpact],
) -> ConfidenceRating:
    enabled_sources = len({ev.source for ev in evidence})
    fundamental_evidence = any(ev.topic.startswith("fundamental.") for ev in evidence)

    if enabled_sources >= 3 and fundamental_evidence:
        return ConfidenceRating(
            level="L1", reason="≥3 个独立来源交叉验证，包含结构化基本面数据，可作为决策依据"
        )
    if enabled_sources >= 2 and fundamental_evidence:
        return ConfidenceRating(
            level="L2", reason="多源证据覆盖，包含懂球帝赛前分析数据，可行动但需持续监控"
        )
    if enabled_sources >= 1:
        return ConfidenceRating(
            level="L3", reason="零配置公开源形成基础判断，但关键结构化数据不足，需补充验证"
        )
    return ConfidenceRating(level="L4", reason="仅有基础输入和采集计划，预测偏推测，仅作参考")

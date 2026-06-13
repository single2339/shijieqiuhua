"""Confidence rating (W2.4 — extracted from pipeline.py).

Maps the evidence + factor state to an L1-L4 grade. v1 thresholds:
- L2: ≥ 4 distinct sources AND any fundamental.* evidence
- L3: ≥ 2 distinct sources
- L4: otherwise

These thresholds are deliberately conservative for v1 — most real jobs
land at L4 or L3 because public sources only get us so far. PRD §4.1
contract; admin CLI may tune via system_config in W2 follow-ups.
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
    if enabled_sources >= 4 and fundamental_evidence:
        return ConfidenceRating(
            level="L2", reason="多源证据覆盖，且包含 Win007/球探基本面数据"
        )
    if enabled_sources >= 2:
        return ConfidenceRating(
            level="L3", reason="零配置公开源形成基础判断，但关键结构化数据不足"
        )
    return ConfidenceRating(level="L4", reason="仅有基础输入和采集计划，预测偏推测")

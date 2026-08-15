"""Confidence rating (W2.4 — extracted from pipeline.py).

Maps the evidence + factor state to an L1-L4 grade aligned with osint-core:
- L1: ≥ 3 distinct sources AND fundamental evidence AND ≥ 3 strong evidence
      AND ≥ 2 high-confidence active factors → 事实确凿
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

    # Evidence density: count items with confidence ≥ 0.50 (the "strong evidence"
    # threshold from PRD §4.5).  This prevents L1 when the pipeline has many weak
    # signals from distinct sources but very few high-quality items.
    strong_count = sum(1 for ev in evidence if ev.confidence >= 0.50)

    # Active factors whose own confidence ≥ 0.40 count as "high-confidence".
    # L1 demands ≥ 2 such factors so the prediction isn't driven by a single
    # weak signal.  fixture.existence is always enabled but never carries a
    # directional signal, so it is excluded from this count.
    high_conf_factors = sum(
        1 for f in factors
        if f.enabled and f.confidence >= 0.40 and f.factor_id != "fixture.existence"
    )

    if enabled_sources >= 3 and fundamental_evidence and strong_count >= 3 and high_conf_factors >= 2:
        return ConfidenceRating(
            level="L1",
            reason="≥3 个独立来源交叉验证，包含结构化基本面数据，≥3 条强证据，≥2 个高置信因子，可作为决策依据",
        )
    if enabled_sources >= 2 and fundamental_evidence:
        shortfalls: list[str] = []
        if strong_count < 3:
            shortfalls.append(f"强证据不足（{strong_count}/3）")
        if high_conf_factors < 2:
            shortfalls.append(f"高置信因子不足（{high_conf_factors}/2）")
        suffix = f"；{'，'.join(shortfalls)}" if shortfalls else ""
        return ConfidenceRating(
            level="L2",
            reason=f"多源证据覆盖，包含懂球帝赛前分析数据，可行动但需持续监控{suffix}",
        )
    if enabled_sources >= 1:
        return ConfidenceRating(
            level="L3", reason="零配置公开源形成基础判断，但关键结构化数据不足，需补充验证"
        )
    return ConfidenceRating(level="L4", reason="仅有基础输入和采集计划，预测偏推测，仅作参考")

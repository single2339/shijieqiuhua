"""Intelligence-cycle artifacts (W2.5 — extracted from pipeline.py).

PRD §4.1 + §4.2 + §4.4. Five small builders that turn the raw factor /
evidence / source state into the human-facing intelligence cycle stages,
confirmed findings, assessments, alternatives, and next steps. They live
together because they all read the same input and feed the same renderer
(analysis/report.py).

No state, no I/O — pure transformation. The 12 OSINT tests pin the exact
output shape via report_markdown contains/startswith assertions, so any
drift here breaks the contract.
"""
from __future__ import annotations

from ..models import (
    ConfidenceRating,
    FactorImpact,
    IntelligenceCycleStage,
    IntelligenceFinding,
    OsintEvidence,
    OsintMatch,
    OsintSourceStatus,
    PredictionResult,
)


def build_intelligence_cycle(
    sources: list[OsintSourceStatus],
    evidence: list[OsintEvidence],
) -> list[IntelligenceCycleStage]:
    ok_sources = [source for source in sources if source.status == "ok"]
    skipped_sources = [source for source in sources if source.status == "skipped"]
    return [
        IntelligenceCycleStage(
            name="收集",
            status="completed" if ok_sources else "partial",
            summary=f"已记录 {len(ok_sources)} 个可用来源，{len(skipped_sources)} 个来源因零配置或缺少定位信息跳过。",
        ),
        IntelligenceCycleStage(
            name="加工",
            status="completed" if evidence else "partial",
            summary=f"已将输入和采集计划加工为 {len(evidence)} 条可追溯证据，保留来源、主题和置信度。",
        ),
        IntelligenceCycleStage(
            name="开发",
            status="partial",
            summary="基于 OSINT 核心原则区分确认事实与推断；未满足三方验证的判断保持 L3/L4。",
        ),
        IntelligenceCycleStage(
            name="生产",
            status="completed",
            summary="输出摘要简报与详细分析报告，包含证据链、替代解释和下一步。",
        ),
    ]


def confirmed_findings(
    match: OsintMatch,
    evidence: list[OsintEvidence],
) -> list[IntelligenceFinding]:
    fixture_ids = [ev.id for ev in evidence if ev.topic.startswith("fixture.")]
    fundamental_ids = [ev.id for ev in evidence if ev.topic.startswith("fundamental.")]
    fallback_ids = [evidence[0].id] if evidence else []
    findings = [
        IntelligenceFinding(
            id="finding_fixture_query",
            statement=f"分析目标已确定为 {match.home_team} vs {match.away_team}，赛事为 {match.competition or '未指定'}。",
            finding_type="confirmed",
            confidence_level="L3",
            evidence_ids=fixture_ids or fallback_ids,
            source_summary="来自用户输入和基础赛程验证记录。",
        )
    ]
    if fundamental_ids:
        findings.append(
            IntelligenceFinding(
                id="finding_fundamental_collected",
                statement="已抓取到懂球帝赛前分析页面，可作为后续多源验证起点。",
                finding_type="confirmed",
                confidence_level="L3",
                evidence_ids=fundamental_ids,
                source_summary="来自懂球帝赛前分析页面。",
            )
        )
    return findings


def assessments(
    match: OsintMatch,
    factors: list[FactorImpact],
    prediction: PredictionResult,
    confidence: ConfidenceRating,
) -> list[IntelligenceFinding]:
    driver_labels = [factor.label for factor in factors if factor.factor_id in prediction.drivers]
    statement = (
        f"当前倾向为 {prediction.lean}，但该判断属于 {confidence.level}，"
        f"主要依据为{('、'.join(driver_labels) or '基础输入与公开源计划')}。"
    )
    return [
        IntelligenceFinding(
            id="assessment_match_lean",
            statement=statement,
            finding_type="assessment",
            confidence_level=confidence.level,
            evidence_ids=[eid for factor in factors for eid in factor.evidence_ids][:4],
            source_summary="基于已加工证据和 OSINT 核心框架的分析判断。",
        )
    ]


def alternative_explanations(
    match: OsintMatch,
    sources: list[OsintSourceStatus],
    factors: list[FactorImpact],
) -> list[str]:
    alternatives = [
        "若官方赛程、球队公告或主流比分平台无法交叉确认，本场可能存在日期、赛事归属或对阵信息误差。",
        "若临场首发与伤停信息发生变化，赛前倾向可能被推翻。",
    ]
    if "u23" in match.profile.competition_type:
        alternatives.append("青年赛事阵容透明度和临场波动更高，历史战绩对本场解释力可能偏弱。")
    if any(factor.missing_reason for factor in factors):
        alternatives.append("部分高价值因子缺失，当前结论应视为可更新判断，而非确认事实。")
    return alternatives


def next_steps(
    sources: list[OsintSourceStatus],
    factors: list[FactorImpact],
) -> list[str]:
    steps = [
        "执行三方验证：至少补充官方赛程、主流比分平台、球队/赛事公告三个独立来源。",
        "补充临场阵容、伤停和天气信息，重新加工证据链。",
    ]
    if any(source.adapter == "dongqiudi_analysis" and source.status != "ok" for source in sources):
        steps.append("补充懂球帝 matchId 后抓取赛前分析页，核对积分排名、历史交锋、近期战绩和未来赛程。")
    return steps

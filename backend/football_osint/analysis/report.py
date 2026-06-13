"""Markdown report rendering for OSINT jobs (W2.3 — extracted from pipeline.py).

Owns the human-readable artifact written to bronze_storage/.../report.md.
The output is byte-identical to the previous pipeline._render_report — the
12 OSINT tests verify report_markdown.startswith(...), so any drift here
breaks the contract.

W2 split rationale (PRD §5.1):
- pipeline orchestrates the run
- analysis/* owns deterministic transformations (this file, prediction,
  confidence, intelligence_cycle, alternatives)

Two helper functions live here too because they are used both by the
report and (today) by adapter code paths in pipeline.py:
- compact_markdown: collapse whitespace for evidence excerpts
- claim_from_markdown: derive a one-line claim about both teams
"""
from __future__ import annotations

from ..models import (
    ConfidenceRating,
    FactorImpact,
    FootballOsintJobRequest,
    IntelligenceCycleStage,
    IntelligenceFinding,
    OsintEvidence,
    OsintMatch,
    OsintSourceStatus,
    PredictionResult,
)


def compact_markdown(markdown: str, limit: int = 900) -> str:
    lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line:
            lines.append(line)
    text = " ".join(lines)
    return text[:limit]


def claim_from_markdown(
    request: FootballOsintJobRequest,
    excerpt: str,
    source_label: str = "公开页面",
) -> str:
    home_hit = request.home_team.lower() in excerpt.lower()
    away_hit = request.away_team.lower() in excerpt.lower()
    if home_hit and away_hit:
        return f"{source_label} 同时提及双方，可作为赛前公开源线索。"
    if home_hit or away_hit:
        team = request.home_team if home_hit else request.away_team
        return f"{source_label} 提及 {team}，可作为单方背景线索。"
    return f"{source_label} 抓取到公开页面内容，但尚未形成双方直接交叉验证。"


def render_report(
    match: OsintMatch,
    sources: list[OsintSourceStatus],
    evidence: list[OsintEvidence],
    factors: list[FactorImpact],
    prediction: PredictionResult,
    confidence: ConfidenceRating,
    cycle: list[IntelligenceCycleStage],
    confirmed_findings: list[IntelligenceFinding],
    assessments: list[IntelligenceFinding],
    alternatives: list[str],
    next_steps: list[str],
) -> str:
    enabled = [f for f in factors if f.enabled]
    missing = [f for f in factors if f.missing_reason]
    lines = [
        "# 世界球花 OSINT 核心情报报告",
        "",
        "情报摘要",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"目标:      {match.home_team} vs {match.away_team}",
        f"赛事:      {match.competition or '未指定'}",
        f"时间:      {match.kickoff_at or '未指定'}",
        f"情报等级:  {confidence.level} — {confidence.reason}",
        "",
        "## 1. 任务背景",
        "",
        f"围绕 {match.home_team} vs {match.away_team} 进行赛前开源情报分析，范围包括比赛存在性、球队基本面、已知缺口、推断倾向和可推翻条件。",
        "",
        "## 2. 方法论：OSINT 情报循环",
        "",
    ]
    for stage in cycle:
        lines.append(f"- {stage.name}: {stage.status} — {stage.summary}")
    lines.extend([
        "",
        "## 3. 证据链与核心发现",
        "",
    ])
    for finding in confirmed_findings:
        lines.append(f"- {finding.statement} — 来源: {', '.join(finding.evidence_ids)} — 可信度: {finding.confidence_level}")
    lines.extend(["", "## 4. 分析判断", "", "### 确认事实", ""])
    for finding in confirmed_findings:
        lines.append(f"- {finding.statement} — {finding.confidence_level}")
    lines.extend(["", "### 推测判断", ""])
    for assessment in assessments:
        lines.append(f"- {assessment.statement} — {assessment.confidence_level}")
    lines.extend(["", f"可能比分区间: {', '.join(prediction.scoreline_band)}", "", "### 替代解释", ""])
    for item in alternatives:
        lines.append(f"- {item}")
    lines.extend(["", "## 5. 因子与缺口", ""])
    for factor in enabled:
        lines.append(f"- {factor.label}: direction={factor.direction}, impact={factor.impact:.2f}, confidence={factor.confidence:.2f}")
    for factor in missing:
        lines.append(f"- {factor.label}: {factor.missing_reason}")
    for source in sources:
        if source.status == "skipped":
            lines.append(f"- {source.label}: {source.reason}")
    lines.extend(["", "## 6. 建议下一步", ""])
    for step in next_steps:
        lines.append(f"- {step}")
    lines.extend(["", "## 附录：来源清单", ""])
    for ev in evidence:
        suffix = f" ({ev.url})" if ev.url else ""
        lines.append(f"- [{ev.id}] {ev.source}: {ev.claim}{suffix}")
    lines.extend(["", "本报告用于研究和风险分析，不构成投注建议。"])
    return "\n".join(lines)

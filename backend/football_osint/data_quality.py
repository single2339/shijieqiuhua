from __future__ import annotations

from dataclasses import dataclass

from .models import (
    DataQualitySummary,
    FactorImpact,
    FootballOsintJobRequest,
    OsintEvidence,
    OsintSourceStatus,
    PredictionResult,
)

_REASON_PRIORITY = [
    "source_runtime_failure",
    "detail_fixture_unmatched",
    "structured_stats_unresolved",
    "irrelevant_search_results",
    "no_relevant_search_results",
    "llm_extraction_empty",
    "too_early",
    "no_user_supplied_context",
]


@dataclass(frozen=True)
class SearchQualityStats:
    relevant_count: int = 0
    dropped_count: int = 0


def build_data_quality(
    request: FootballOsintJobRequest,
    sources: list[OsintSourceStatus],
    evidence: list[OsintEvidence],
    factors: list[FactorImpact],
    prediction: PredictionResult | None,
    *,
    search_stats: SearchQualityStats | None = None,
    extraction_attempted: bool = False,
) -> DataQualitySummary:
    stats = search_stats or SearchQualityStats()
    source_summary = {"ok": 0, "skipped": 0, "failed": 0}
    for source in sources:
        source_summary[source.status] = source_summary.get(source.status, 0) + 1

    fundamental_factor_count = sum(
        1
        for factor in factors
        if factor.group in {"form", "h2h", "squad"} and factor.enabled
    )

    reasons: list[str] = []
    if any(source.status == "failed" for source in sources):
        reasons.append("source_runtime_failure")
    if any(
        source.adapter == "dongqiudi_analysis" and source.status != "ok"
        for source in sources
    ):
        reasons.append("detail_fixture_unmatched")
    if any(
        source.adapter == "football_data_stats" and source.status != "ok"
        for source in sources
    ):
        reasons.append("structured_stats_unresolved")
    if stats.dropped_count > 0 and stats.relevant_count == 0:
        reasons.append("irrelevant_search_results")
    elif any(
        source.adapter in {"cn_search", "ddg_search"} and source.status != "ok"
        for source in sources
    ):
        reasons.append("no_relevant_search_results")
    if extraction_attempted and fundamental_factor_count == 0:
        reasons.append("llm_extraction_empty")
    if (
        not request.user_supplied.notes
        and not request.user_supplied.injuries
        and not request.user_supplied.lineups
    ):
        reasons.append("no_user_supplied_context")

    is_insufficient = prediction is not None and prediction.lean == "info_insufficient"
    if is_insufficient and fundamental_factor_count == 0 and not reasons:
        reasons.append("structured_stats_unresolved")
    if not is_insufficient:
        reasons = []

    reason_set = set(reasons)
    ordered = [reason for reason in _REASON_PRIORITY if reason in reason_set]
    extraction_status = "not_run"
    if extraction_attempted:
        extraction_status = "empty" if fundamental_factor_count == 0 else "ok"

    return DataQualitySummary(
        insufficiency_reasons=ordered,
        primary_insufficiency_reason=ordered[0] if ordered else "",
        source_summary=source_summary,
        fundamental_factor_count=fundamental_factor_count,
        relevant_search_results_count=stats.relevant_count,
        dropped_search_results_count=stats.dropped_count,
        extraction_status=extraction_status,
    )

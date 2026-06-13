"""OSINT football prediction pipeline — job orchestration.

W1-W2 split per PRD §5.1 / decision Q5. This file is now thin orchestration:
- ``run_prediction_sync()`` — entry point that wires adapters / analysis /
  persistence into one synchronous call tree
- ``_job_id()`` / ``_profile_match()`` — small leaf utilities kept here
  because they're pure and coupling-free
- ``_collect_zero_config_sources()`` / ``_collect_farich_foot_sources()`` —
  W2.8 keeps these two as the collector hub; each delegates to adapters/
  and evidence.py, no longer owning subprocess or URL logic

Everything else lives in:
- adapters/        — data sources (lightpanda, win007, user_supplied, url_safety)
- analysis/        — prediction / confidence / intelligence / report
- factor_registry  — per-match factor scoring rules
- evidence         — evidence construction + classification
- storage          — bronze filesystem persistence
"""
from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import lightpanda as lightpanda_adapter
from .adapters import user_supplied as user_supplied_adapter
from .adapters import win007 as win007_adapter
from .analysis import confidence as confidence_module
from .analysis import intelligence as intelligence_module
from .analysis import prediction as prediction_module
from .analysis import report as report_module
from . import evidence as evidence_module
from . import factor_registry as factor_registry_module
from . import storage
from .models import (
    FootballOsintJob,
    FootballOsintJobRequest,
    FootballOsintJobStatus,
    MatchProfile,
    OsintEvidence,
    OsintMatch,
    OsintSourceStatus,
)
from .sources import WIN007_SOURCE_TEMPLATES


# ── public entry point ──

def run_prediction_sync(
    payload: dict[str, Any] | FootballOsintJobRequest,
    storage_root: str | Path | None = None,
) -> FootballOsintJob:
    request = payload if isinstance(payload, FootballOsintJobRequest) else FootballOsintJobRequest(**payload)
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    match_id = _job_id(request)
    match = OsintMatch(
        home_team=request.home_team,
        away_team=request.away_team,
        kickoff_at=request.kickoff_at,
        competition=request.competition,
        venue=request.venue,
        profile=_profile_match(request),
    )

    _collect_zero_config_sources(request, evidence, sources)
    factors = factor_registry_module.build_factors(request, match.profile, evidence)
    prediction = prediction_module.predict(request, factors)
    confidence = confidence_module.grade(match.profile, evidence, factors)
    cycle = intelligence_module.build_intelligence_cycle(sources, evidence)
    confirmed_findings = intelligence_module.confirmed_findings(match, evidence)
    assessments = intelligence_module.assessments(match, factors, prediction, confidence)
    alternatives = intelligence_module.alternative_explanations(match, sources, factors)
    next_steps = intelligence_module.next_steps(sources, factors)
    report = report_module.render_report(
        match, sources, evidence, factors, prediction, confidence,
        cycle, confirmed_findings, assessments, alternatives, next_steps,
    )

    job = FootballOsintJob(
        job_id=match_id,
        status=FootballOsintJobStatus.COMPLETED,
        phase="done",
        progress=100,
        match=match,
        sources=sources,
        evidence=evidence,
        factors=factors,
        prediction=prediction,
        confidence=confidence,
        intelligence_cycle=cycle,
        confirmed_findings=confirmed_findings,
        assessments=assessments,
        alternative_explanations=alternatives,
        next_steps=next_steps,
        report_markdown=report,
    )
    storage.persist_job(job, storage_root)
    return job


# ── internal helpers ──

def _job_id(request: FootballOsintJobRequest) -> str:
    seed = "|".join([request.home_team, request.away_team, request.kickoff_at, request.competition])
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"fo_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{digest}"


def _profile_match(request: FootballOsintJobRequest) -> MatchProfile:
    text = " ".join([request.home_team, request.away_team, request.competition]).lower()
    competition_type = "u23" if "u23" in text or "u-23" in text else "club"
    if "friendly" in text or "友谊" in text:
        competition_type = "friendly_u23" if competition_type == "u23" else "friendly"
    factor_pack = "youth_match" if "u23" in competition_type else ("friendly" if "friendly" in competition_type else "default")
    return MatchProfile(
        competition_type=competition_type,
        time_to_kickoff_hours=None,
        data_density="medium" if request.user_supplied.notes else "low",
        factor_pack=factor_pack,
    )


# ── collector hub (W2.8: thin orchestrator, each leaf delegating to adapters/) ──

def _collect_zero_config_sources(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> None:
    fixture_id = evidence_module.append_evidence(
        evidence,
        source="User request",
        source_type="fixture",
        claim=f"{request.home_team} vs {request.away_team} entered for OSINT verification",
        topic="fixture.query",
        side="both",
        confidence=0.55,
        raw_excerpt=f"{request.competition} {request.kickoff_at}".strip(),
    )
    sources.append(OsintSourceStatus(adapter="fixtures_public", label="公开赛程探测", status="ok", evidence_ids=[fixture_id]))

    sources.append(
        OsintSourceStatus(
            adapter="farich_foot_plan",
            label="farich/foot 数据源计划",
            status="skipped",
            reason="未抓取到结构化基本面，仅作为后续采集占位。",
        )
    )
    _collect_farich_foot_sources(request, evidence, sources)

    if request.user_supplied.notes:
        note_ids = []
        for note in request.user_supplied.notes:
            note_ids.append(
                evidence_module.append_evidence(
                    evidence,
                    source="User note",
                    source_type="note",
                    claim=note[:240],
                    topic="user.note",
                    side="neutral",
                    confidence=0.6,
                    raw_excerpt=note[:500],
                )
            )
        sources.append(OsintSourceStatus(adapter="user_supplied", label="用户补充基本面", status="ok", evidence_ids=note_ids))
    else:
        sources.append(OsintSourceStatus(adapter="user_supplied", label="用户补充基本面", status="skipped", reason="未提供伤病、首发或球队新闻补充"))


def _collect_farich_foot_sources(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> None:
    command = os.getenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", "lp-fetch-md")
    binary = command if Path(command).exists() else shutil.which(command)
    if not binary:
        for source in WIN007_SOURCE_TEMPLATES:
            if source.default_enabled:
                sources.append(OsintSourceStatus(adapter=source.adapter, label=source.label, status="skipped", reason=f"{command} not available"))
        return

    for source, urls in win007_adapter.candidate_urls(request):
        if not urls:
            sources.append(OsintSourceStatus(adapter=source.adapter, label=source.label, status="skipped", reason="缺少 Win007 matchId 或历史赛程参数"))
            continue
        evidence_ids: list[str] = []
        failures: list[str] = []
        for url in urls:
            evidence_id, failure = lightpanda_adapter.fetch_url(binary, url, source_type=source.source_type, topic=source.topic, source_label=source.label, request=request, evidence=evidence)
            if evidence_id:
                evidence_ids.append(evidence_id)
            elif failure:
                failures.append(failure)
        if evidence_ids:
            sources.append(
                OsintSourceStatus(
                    adapter=source.adapter,
                    label=source.label,
                    status="ok",
                    evidence_ids=evidence_ids,
                    reason="" if not failures else f"{len(failures)} 个页面未成功抓取",
                )
            )
        else:
            sources.append(
                OsintSourceStatus(
                    adapter=source.adapter,
                    label=source.label,
                    status="failed" if failures else "skipped",
                    reason="; ".join(failures[:2]) if failures else "未配置公开页面候选",
                )
            )

    manual_urls = user_supplied_adapter.candidate_urls(request)
    if manual_urls:
        evidence_ids = []
        failures = []
        for url in manual_urls[:3]:
            evidence_id, failure = lightpanda_adapter.fetch_url(binary, url, source_type="web", topic="collection.manual_url", source_label="用户补充公开来源", request=request, evidence=evidence)
            if evidence_id:
                evidence_ids.append(evidence_id)
            elif failure:
                failures.append(failure)
        sources.append(
            OsintSourceStatus(
                adapter="manual_public_url",
                label="用户补充公开来源",
                status="ok" if evidence_ids else "failed",
                evidence_ids=evidence_ids,
                reason="" if evidence_ids else "; ".join(failures[:2]),
            )
        )

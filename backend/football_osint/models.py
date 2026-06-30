from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FootballOsintJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"


class UserSuppliedInput(BaseModel):
    injuries: list[dict[str, Any]] = Field(default_factory=list)
    lineups: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FootballOsintJobRequest(BaseModel):
    home_team: str
    away_team: str
    kickoff_at: str = ""
    competition: str = ""
    venue: str = ""
    locale: str = "zh-CN"
    question: str = ""
    provider: str = ""
    provider_match_id: str = ""
    home_provider_id: str = ""
    away_provider_id: str = ""
    home_aliases: list[str] = Field(default_factory=list)
    away_aliases: list[str] = Field(default_factory=list)
    user_supplied: UserSuppliedInput = Field(default_factory=UserSuppliedInput)


class MatchProfile(BaseModel):
    competition_type: str = "club"
    time_to_kickoff_hours: float | None = None
    data_density: str = "low"
    factor_pack: str = "default"


class OsintMatch(BaseModel):
    home_team: str
    away_team: str
    kickoff_at: str = ""
    competition: str = ""
    venue: str = ""
    profile: MatchProfile = Field(default_factory=MatchProfile)


class OsintSourceStatus(BaseModel):
    adapter: str
    label: str
    status: Literal["ok", "skipped", "failed"]
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class OsintEvidence(BaseModel):
    id: str
    source: str
    source_type: str
    url: str = ""
    observed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    claim: str
    topic: str
    side: Literal["home", "away", "both", "neutral"] = "neutral"
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_excerpt: str = ""


class FactorImpact(BaseModel):
    factor_id: str
    label: str
    group: str
    enabled: bool
    weight: float = Field(ge=0.0)
    impact: float
    direction: Literal["home", "away", "draw", "neutral"] = "neutral"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    missing_reason: str = ""


class PredictionResult(BaseModel):
    lean: Literal["home", "away", "draw", "home_or_draw", "away_or_draw", "info_insufficient"]
    summary: str
    probability_band: dict[str, tuple[float, float]]
    scoreline_band: list[str]
    drivers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ConfidenceRating(BaseModel):
    level: Literal["L1", "L2", "L3", "L4"]
    reason: str


class DataQualitySummary(BaseModel):
    insufficiency_reasons: list[str] = Field(default_factory=list)
    primary_insufficiency_reason: str = ""
    source_summary: dict[str, int] = Field(default_factory=dict)
    fundamental_factor_count: int = 0
    relevant_search_results_count: int = 0
    dropped_search_results_count: int = 0
    extraction_status: str = "not_run"


class IntelligenceCycleStage(BaseModel):
    name: Literal["收集", "加工", "开发", "生产"]
    status: Literal["completed", "partial", "skipped"]
    summary: str


class IntelligenceFinding(BaseModel):
    id: str
    statement: str
    finding_type: Literal["confirmed", "assessment"]
    confidence_level: Literal["L1", "L2", "L3", "L4"]
    evidence_ids: list[str] = Field(default_factory=list)
    source_summary: str = ""


class FootballOsintJob(BaseModel):
    job_id: str
    status: FootballOsintJobStatus
    phase: str = "queued"
    progress: int = Field(ge=0, le=100)
    match: OsintMatch
    sources: list[OsintSourceStatus] = Field(default_factory=list)
    evidence: list[OsintEvidence] = Field(default_factory=list)
    factors: list[FactorImpact] = Field(default_factory=list)
    prediction: PredictionResult | None = None
    confidence: ConfidenceRating | None = None
    data_quality: DataQualitySummary | None = None
    intelligence_cycle: list[IntelligenceCycleStage] = Field(default_factory=list)
    confirmed_findings: list[IntelligenceFinding] = Field(default_factory=list)
    assessments: list[IntelligenceFinding] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    report_markdown: str = ""
    error: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FootballOsintAnswer(BaseModel):
    related: bool
    analysis_started: bool
    answer: str
    judgment: str = ""
    reasons: list[str] = Field(default_factory=list)
    confidence_level: Literal["L1", "L2", "L3", "L4"] = "L4"

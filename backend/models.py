from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class IntelLayer(str, Enum):
    NATURE = "nature"
    ECONOMY = "economy"
    FINANCE = "finance"
    POLITICS = "politics"
    MILITARY = "military"
    AVIATION = "aviation"
    TECHNOLOGY = "technology"
    SOCIETY = "society"
    ENERGY = "energy"
    AGRICULTURE = "agriculture"
    HEALTH = "health"
    CYBER = "cyber"


class Verdict(str, Enum):
    VERIFIED = "verified"
    FALSE = "false"
    UNCERTAIN = "uncertain"


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class BayesianEvidence(BaseModel):
    name: str = ""
    quality: str = ""
    lr: float = 1.0
    dep_discount: float = 1.0
    direction: str = "support"


class IntelItem(BaseModel):
    id: str
    title: str
    summary: str
    layer: IntelLayer
    location: GeoPoint
    location_name: str
    country: str
    confidence: float = Field(ge=0.0, le=1.0)
    verdict: Verdict
    bayesian_trace: list[float] = Field(default_factory=list)
    evidence_count: int = 0
    sources: list[str] = Field(default_factory=list)
    source_system: str = ""
    captured_at: str = ""
    url: str = ""
    # yao-bayesian-skill detail fields
    bayesian_method: str = ""
    bayesian_prior_quality: str = ""
    bayesian_prior_class: str = ""
    bayesian_evidence_items: list[BayesianEvidence] = Field(default_factory=list)


class SourceInfo(BaseModel):
    name: str
    credibility: float = Field(ge=0.0, le=1.0)
    document_count: int = 0
    last_seen: str = ""


class LayerSummary(BaseModel):
    layer: IntelLayer
    count: int
    avg_confidence: float


class DashboardData(BaseModel):
    intel_items: list[IntelItem]
    sources: list[SourceInfo]
    layers: list[LayerSummary]
    total_items: int
    page: int = 1
    page_size: int = 100
    has_more: bool = False
    available_dates: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── AI Q&A ──
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=20000)
    start_date: str = ""
    end_date: str = ""
    layer: str = ""
    skills: list[str] = Field(default_factory=list, max_length=20)


class AskResponse(BaseModel):
    answer: str
    references: list[dict] = Field(default_factory=list)
    model: str = "deepseek-v4-flash"


# ── Dashboard Stats ──
class TrendPoint(BaseModel):
    date: str
    count: int


class SourceMatrix(BaseModel):
    name: str
    credibility: float
    document_count: int
    layer_distribution: dict[str, int] = Field(default_factory=dict)


class DashboardStats(BaseModel):
    total_items: int
    total_sources: int
    by_layer: list[LayerSummary]
    daily_trend: list[TrendPoint] = Field(default_factory=list)
    source_matrix: list[SourceMatrix] = Field(default_factory=list)
    geo_distribution: list[dict] = Field(default_factory=list)
    top_keywords: list[dict] = Field(default_factory=list)


# ── Situation Report ──
class BriefWorkspaceMaterial(BaseModel):
    id: str
    type: str = "item"
    title: str
    summary: str = ""
    source: str = ""
    sources: list[str] = Field(default_factory=list)
    date: str = ""
    layer: str = ""
    country: str = ""
    confidence_level: str = ""
    url: str = ""
    origin: str = ""


class ReportRequest(BaseModel):
    topic: str = Field(default="", max_length=500)
    country: str = Field(default="", max_length=100)
    days: int = Field(default=7, ge=1, le=365)
    layer: str = Field(default="", max_length=50)
    detail_level: str = "standard"  # "brief", "standard", "deep"
    skills: list[str] = Field(default_factory=list, max_length=20)
    item_ids: list[str] = Field(default_factory=list, max_length=500)
    event_ids: list[str] = Field(default_factory=list, max_length=500)
    warning_ids: list[str] = Field(default_factory=list, max_length=500)
    source_materials: list[BriefWorkspaceMaterial] = Field(default_factory=list, max_length=100)


class ReportSection(BaseModel):
    heading: str
    body: str


class SituationReport(BaseModel):
    title: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    item_count: int = 0
    source_count: int = 0


# ── Intelligence Analysis ──

class TimelinePoint(BaseModel):
    date: str
    count: int
    items: list[dict] = Field(default_factory=list)
    layer_counts: dict[str, int] = Field(default_factory=dict)


class TimelineResult(BaseModel):
    points: list[TimelinePoint] = Field(default_factory=list)
    date_range: dict = Field(default_factory=dict)


class EntityNode(BaseModel):
    id: str
    label: str
    type: str
    count: int


class EntityEdge(BaseModel):
    source: str
    target: str
    weight: int


class EntityGraphResult(BaseModel):
    nodes: list[EntityNode] = Field(default_factory=list)
    edges: list[EntityEdge] = Field(default_factory=list)


class SourcePairOverlap(BaseModel):
    source_a: str
    source_b: str
    shared_topics: int
    total_a: int
    total_b: int
    agreement_score: float
    shared_events: int = 0
    confirmed_events: int = 0
    high_confidence_events: int = 0
    shared_event_ids: list[str] = Field(default_factory=list)
    shared_event_titles: list[str] = Field(default_factory=list)
    verification_summary: str = ""


class CorroborationResult(BaseModel):
    sources: list[str] = Field(default_factory=list)
    matrix: list[list[float]] = Field(default_factory=list)
    top_pairs: list[SourcePairOverlap] = Field(default_factory=list)
    event_count: int = 0
    claim_count: int = 0
    methodology: str = "按事件簇/Claim 计算共同支撑关系，而非按单条情报 ID 直接重合。"


class AnomalyEvent(BaseModel):
    date: str
    layer: str
    country: str = ""
    actual_count: int
    expected_count: float
    z_score: float
    severity: str


class AnomalyResult(BaseModel):
    anomalies: list[AnomalyEvent] = Field(default_factory=list)
    baseline: dict = Field(default_factory=dict)


class RegionRisk(BaseModel):
    country: str
    risk_score: float
    intel_density: int
    avg_confidence: float
    layer_breakdown: dict[str, float] = Field(default_factory=dict)


class RiskHeatmapResult(BaseModel):
    regions: list[RegionRisk] = Field(default_factory=list)


class CoverageGap(BaseModel):
    gap_type: str
    description: str
    severity: str
    affected_region: str = ""
    affected_layer: str = ""
    recommendation: str = ""


class GapAnalysisResult(BaseModel):
    gaps: list[CoverageGap] = Field(default_factory=list)
    coverage_stats: dict = Field(default_factory=dict)


class BriefEvidence(BaseModel):
    id: str
    item_id: str
    title: str
    summary: str = ""
    source: str = ""
    sources: list[str] = Field(default_factory=list)
    date: str = ""
    layer: str = ""
    country: str = ""
    confidence: float = 0.0
    confidence_level: str = "L4"
    confidence_label: str = "推测"
    url: str = ""
    verification: str = ""
    independent_source_count: int = 0


class ConfidenceAssessment(BaseModel):
    level: str
    label: str
    rationale: str
    independent_source_count: int = 0
    evidence_count: int = 0
    evidence_ids: list[str] = Field(default_factory=list)


class KeyJudgment(BaseModel):
    id: str
    judgment: str
    confidence_level: str
    confidence_score: float
    impact: str
    time_sensitivity: str
    support_count: int
    evidence_ids: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    confidence_assessment: Optional[ConfidenceAssessment] = None


class IntelligenceStatement(BaseModel):
    id: str
    statement: str
    confidence: ConfidenceAssessment
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class CoreFinding(BaseModel):
    id: str
    finding: str
    fact_basis: str = ""
    assessment: str = ""
    confidence: ConfidenceAssessment
    evidence_ids: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)


class AlternativeExplanation(BaseModel):
    id: str
    explanation: str
    indicators: list[str] = Field(default_factory=list)
    related_evidence_ids: list[str] = Field(default_factory=list)
    confidence_level: str = "L4"


class PendingVerification(BaseModel):
    id: str
    question: str
    priority: str = "中"
    rationale: str = ""
    related_evidence_ids: list[str] = Field(default_factory=list)


class EventClaim(BaseModel):
    id: str
    claim: str
    confidence: ConfidenceAssessment
    support_count: int = 0
    source_count: int = 0
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: str = "待核查"


class EventCluster(BaseModel):
    id: str
    title: str
    summary: str = ""
    start_date: str = ""
    end_date: str = ""
    countries: list[str] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    item_count: int = 0
    source_count: int = 0
    confidence: ConfidenceAssessment
    verification_status: str = "待核查"
    key_terms: list[str] = Field(default_factory=list)
    claims: list[EventClaim] = Field(default_factory=list)
    evidence: list[BriefEvidence] = Field(default_factory=list)


class EventClusterResult(BaseModel):
    scope: dict = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_items: int = 0
    total_clusters: int = 0
    unclustered_count: int = 0
    clusters: list[EventCluster] = Field(default_factory=list)


class BriefIssue(BaseModel):
    description: str
    severity: str = "medium"
    related_evidence_ids: list[str] = Field(default_factory=list)


class CollectionTask(BaseModel):
    priority: str
    task: str
    rationale: str
    query: str = ""


class WarningIndicator(BaseModel):
    id: str
    title: str
    severity: str = "medium"
    status: str = "watch"
    confidence: ConfidenceAssessment
    trigger: str
    rationale: str = ""
    countries: list[str] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    related_event_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    review_window: str = "24h"


class WarningIndicatorResult(BaseModel):
    scope: dict = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_items: int = 0
    overall_level: str = "normal"
    active_indicator_count: int = 0
    methodology: str = "I&W: 基于事件簇、L1-L4 可信度、高敏感图层和采集缺口生成可复核预警指标。"
    indicators: list[WarningIndicator] = Field(default_factory=list)
    collection_requirements: list[CollectionTask] = Field(default_factory=list)


class SituationBriefResult(BaseModel):
    scope: dict = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str
    total_items: int = 0
    methodology: str = "OSINT-core: 三方验证、事实/推断分离、结论可追溯至证据。"
    intelligence_level: ConfidenceAssessment | None = None
    source_count: int = 0
    core_findings: list[CoreFinding] = Field(default_factory=list)
    confirmed_facts: list[IntelligenceStatement] = Field(default_factory=list)
    assessments: list[IntelligenceStatement] = Field(default_factory=list)
    alternative_explanations: list[AlternativeExplanation] = Field(default_factory=list)
    pending_verification: list[PendingVerification] = Field(default_factory=list)
    key_judgments: list[KeyJudgment] = Field(default_factory=list)
    evidence: list[BriefEvidence] = Field(default_factory=list)
    contradictions: list[BriefIssue] = Field(default_factory=list)
    collection_gaps: list[BriefIssue] = Field(default_factory=list)
    recommended_tasks: list[CollectionTask] = Field(default_factory=list)
    recommended_next_steps: list[CollectionTask] = Field(default_factory=list)


class AnalysisInterpretRequest(BaseModel):
    analysis_type: str = Field(..., min_length=1, max_length=100)
    context: dict = Field(default_factory=dict)


class AnalysisInterpretResponse(BaseModel):
    analysis_type: str
    interpretation: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Super Analysis ──

SUPER_ANALYSIS_ALLOWED_SKILLS = frozenset({"super-analysis"})


class SuperAnalysisRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=20000)
    start_date: str = ""
    end_date: str = ""
    skills: list[str] = Field(default_factory=list, max_length=20)
    request_id: str = Field(
        default="",
        max_length=64,
        pattern=r"^(?:[A-Za-z0-9_-]{8,64})?$",
    )

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, skills: list[str]) -> list[str]:
        invalid = sorted(set(skills) - SUPER_ANALYSIS_ALLOWED_SKILLS)
        if invalid:
            raise ValueError(f"unsupported super-analysis skills: {', '.join(invalid)}")
        return skills


class BayesianIntelItem(BaseModel):
    title: str
    source: str
    date: str
    layer: str
    quality_score: float = Field(ge=0, le=1)
    independent_source_count: int = Field(ge=1)
    source_class: Literal[
        "high-credibility",
        "medium-credibility",
        "low-credibility",
        "kol",
        "unknown",
    ]
    content_snippet: str = ""


class HypothesisEvidenceAssessment(BaseModel):
    evidence_id: str
    source: str
    relation: Literal["support", "contradict", "neutral"]
    strength: Literal["weak", "moderate", "strong"]
    likelihood_ratio: float = Field(gt=0)
    posterior_probability: float = Field(ge=0, le=1)
    rationale: str


class HypothesisAssessment(BaseModel):
    hypothesis: str
    prior_probability: float = Field(ge=0, le=1)
    posterior_probability: float = Field(ge=0, le=1)
    verdict: Literal["verified", "refuted", "uncertain"]
    confidence_level: Literal["L1", "L2", "L3", "L4", "L5"]
    independent_source_count: int = Field(ge=0)
    evidence: list[HypothesisEvidenceAssessment] = Field(default_factory=list)


class WebResult(BaseModel):
    title: str = ""
    snippet: str = ""
    url: str = ""


class SuperAnalysisResponse(BaseModel):
    question: str
    analysis: str
    relevant_items: list[BayesianIntelItem] = Field(default_factory=list)
    web_results: list[WebResult] = Field(default_factory=list)
    hypothesis_assessment: HypothesisAssessment | None = None
    collection_status: Literal["complete", "empty", "partial", "unavailable"] = "complete"
    provider_statuses: dict[
        str,
        Literal["success", "empty", "error", "disabled"],
    ] = Field(default_factory=dict)
    degraded: bool = False
    analysis_status: Literal["complete", "unavailable", "error"] = "complete"
    errors: list[str] = Field(default_factory=list)
    model: str
    request_id: str = ""

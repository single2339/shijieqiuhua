from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── AI Q&A ──
class AskRequest(BaseModel):
    question: str
    start_date: str = ""
    end_date: str = ""
    layer: str = ""


class AskResponse(BaseModel):
    answer: str
    references: list[dict] = Field(default_factory=list)
    model: str = "deepseek-chat"


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
class ReportRequest(BaseModel):
    topic: str = ""
    country: str = ""
    days: int = 7
    layer: str = ""
    detail_level: str = "standard"  # "brief", "standard", "deep"


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


class CorroborationResult(BaseModel):
    sources: list[str] = Field(default_factory=list)
    matrix: list[list[float]] = Field(default_factory=list)
    top_pairs: list[SourcePairOverlap] = Field(default_factory=list)


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


class AnalysisInterpretRequest(BaseModel):
    analysis_type: str
    context: dict = Field(default_factory=dict)


class AnalysisInterpretResponse(BaseModel):
    analysis_type: str
    interpretation: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Super Analysis ──

class SuperAnalysisRequest(BaseModel):
    question: str
    start_date: str = ""
    end_date: str = ""


class BayesianIntelItem(BaseModel):
    title: str
    source: str
    date: str
    layer: str
    confidence: float
    verdict: str
    prior_class: str
    prior_probability: float
    evidence_items: list[dict] = Field(default_factory=list)
    bayesian_trace: list[float] = Field(default_factory=list)
    content_snippet: str = ""


class SuperAnalysisResponse(BaseModel):
    question: str
    analysis: str
    relevant_items: list[BayesianIntelItem] = Field(default_factory=list)
    web_results: list[dict] = Field(default_factory=list)
    model: str = "deepseek-chat"

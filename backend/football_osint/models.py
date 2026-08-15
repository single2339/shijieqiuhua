from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import isclose
from typing import Any, Literal, Mapping, Self

from pydantic import BaseModel, Field, model_validator


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

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        if not isinstance(copied.user_supplied, UserSuppliedInput):
            copied.user_supplied = UserSuppliedInput.model_validate(copied.user_supplied)
        return copied


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


class OutcomeProbabilities(BaseModel):
    home_win: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away_win: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_total(self) -> OutcomeProbabilities:
        if not isclose(self.home_win + self.draw + self.away_win, 1.0, abs_tol=1e-5):
            raise ValueError("outcome probabilities must sum to 1")
        return self


class OutcomeOdds(BaseModel):
    home_win: float = Field(gt=0.0)
    draw: float = Field(gt=0.0)
    away_win: float = Field(gt=0.0)


class MarketSourceSnapshot(BaseModel):
    source_id: str
    odds: OutcomeOdds
    observed_at: datetime


class MarketConsensus(BaseModel):
    status: Literal["consensus", "single_source", "insufficient_sources"]
    fresh_source_count: int = Field(ge=0)
    source_ids: list[str] = Field(default_factory=list)
    probabilities: OutcomeProbabilities | None = None

    @model_validator(mode="after")
    def validate_status(self) -> MarketConsensus:
        if self.status == "consensus":
            if self.fresh_source_count < 3 or self.probabilities is None:
                raise ValueError("consensus requires three fresh sources and probabilities")
        elif self.probabilities is not None:
            raise ValueError("non-consensus market states cannot include probabilities")
        return self


class MarketComparison(BaseModel):
    status: Literal["aligned", "divergent", "limited"]
    model_leader: Literal["home_win", "draw", "away_win"] | None = None
    market_leader: Literal["home_win", "draw", "away_win"] | None = None
    leader_delta: float | None = Field(default=None, ge=0.0, le=1.0)


class MarketContext(BaseModel):
    snapshots: list[MarketSourceSnapshot] = Field(default_factory=list)
    consensus: MarketConsensus | None = None
    comparison: MarketComparison | None = None


class ActualResult(BaseModel):
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


class MatchDecision(BaseModel):
    outcome: Literal["home_win", "draw", "away_win", "info_insufficient"]
    outcome_probabilities: OutcomeProbabilities | None = None
    reason: str = ""


class SportteryMarket(BaseModel):
    provider: Literal["sporttery"] = "sporttery"
    had_odds: OutcomeOdds | None = None
    had_implied_probabilities: OutcomeProbabilities
    home_handicap: int | None = None
    hhad_odds: OutcomeOdds | None = None
    hhad_implied_probabilities: OutcomeProbabilities | None = None
    observed_at: str

    @model_validator(mode="after")
    def validate_hhad_group(self) -> SportteryMarket:
        hhad_fields = (
            self.home_handicap,
            self.hhad_odds,
            self.hhad_implied_probabilities,
        )
        if any(field is not None for field in hhad_fields) and not all(field is not None for field in hhad_fields):
            raise ValueError("home_handicap, hhad_odds, and hhad_implied_probabilities must be provided together")
        return self


class HandicapConclusion(BaseModel):
    home_handicap: int
    outcome: Literal["home", "draw", "away"]
    handicap_probabilities: OutcomeProbabilities
    probability: float = Field(ge=0.0, le=1.0)
    margin_to_runner_up: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "close"]

    @model_validator(mode="after")
    def validate_derived_fields(self) -> HandicapConclusion:
        probabilities = self.handicap_probabilities.model_dump()
        ranked = sorted(probabilities.values(), reverse=True)
        probability = ranked[0]
        margin_to_runner_up = probability - ranked[1]
        clarity = "clear" if margin_to_runner_up >= 0.05 else "close"
        outcome_key = {"home": "home_win", "draw": "draw", "away": "away_win"}[self.outcome]
        if not isclose(probabilities[outcome_key], probability, abs_tol=1e-6):
            raise ValueError("outcome must match the highest handicap probability")
        if not isclose(self.probability, probability, abs_tol=1e-6):
            raise ValueError("probability must match the highest handicap probability")
        if not isclose(self.margin_to_runner_up, margin_to_runner_up, abs_tol=1e-6):
            raise ValueError("margin_to_runner_up must match the top-two handicap probability margin")
        if self.clarity != clarity:
            raise ValueError("clarity must match the top-two handicap probability margin")
        return self


class PredictionResult(BaseModel):
    lean: Literal["home", "away", "draw", "home_or_draw", "away_or_draw", "info_insufficient"]
    summary: str
    outcome_probabilities: OutcomeProbabilities
    primary_probability: float = Field(ge=0.0, le=1.0)
    margin_to_runner_up: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "close", "insufficient"]
    scoreline_band: list[str]
    drivers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    sporttery_market: SportteryMarket | None = None
    handicap_conclusion: HandicapConclusion | None = None

    @model_validator(mode="before")
    @classmethod
    def convert_legacy_probability_band(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "probability_band" not in value:
            return value

        payload = dict(value)
        bands = payload.pop("probability_band") or {}
        midpoint = {
            outcome: (float(band[0]) + float(band[1])) / 2
            for outcome, band in bands.items()
            if isinstance(band, (list, tuple)) and len(band) == 2
        }
        outcomes = ("home_win", "draw", "away_win")
        if set(midpoint) != set(outcomes) or sum(midpoint.values()) <= 0:
            midpoint = {outcome: 1 / 3 for outcome in outcomes}

        total = sum(midpoint.values())
        probabilities = {
            outcome: round(midpoint[outcome] / total, 6)
            for outcome in outcomes
        }
        ranked = sorted(probabilities.values(), reverse=True)
        payload["outcome_probabilities"] = probabilities
        payload["primary_probability"] = ranked[0]
        payload["margin_to_runner_up"] = round(ranked[0] - ranked[1], 6)
        payload["clarity"] = (
            "insufficient"
            if payload.get("lean") == "info_insufficient"
            else "clear" if ranked[0] - ranked[1] >= 0.05 else "close"
        )
        return payload

    @model_validator(mode="after")
    def validate_derived_fields(self) -> PredictionResult:
        ranked = sorted(self.outcome_probabilities.model_dump().values(), reverse=True)
        primary_probability = ranked[0]
        margin_to_runner_up = primary_probability - ranked[1]
        clarity = (
            "insufficient"
            if self.lean == "info_insufficient"
            else "clear" if margin_to_runner_up >= 0.05 else "close"
        )
        if not isclose(self.primary_probability, primary_probability, abs_tol=1e-6):
            raise ValueError("primary_probability must match the highest outcome probability")
        if not isclose(self.margin_to_runner_up, margin_to_runner_up, abs_tol=1e-6):
            raise ValueError("margin_to_runner_up must match the top-two probability margin")
        if self.clarity != clarity:
            raise ValueError("clarity must match the lean and top-two probability margin")
        if self.handicap_conclusion is not None:
            market = self.sporttery_market
            if (
                market is None
                or market.home_handicap is None
                or market.hhad_odds is None
                or market.hhad_implied_probabilities is None
            ):
                raise ValueError("handicap_conclusion requires a complete HHAD market")
            if self.handicap_conclusion.home_handicap != market.home_handicap:
                raise ValueError("handicap_conclusion home_handicap must match the HHAD market")
        return self


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

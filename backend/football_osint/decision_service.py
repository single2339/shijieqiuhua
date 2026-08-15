"""Composition of the paid, first-view match decision.

The OSINT pipeline owns prediction generation.  This module only reads that
completed prediction and, afterwards, compares it with independently collected
market data.  It must never feed a market value back into the prediction.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from . import warm_cache
from .adapters import dongqiudi_schedule, football_data_schedule
from .analysis.market import compare_market_consensus
from .models import (
    ActualResult,
    FootballOsintJob,
    FootballOsintJobRequest,
    MatchDecision,
    OutcomeProbabilities,
    PostMatchReview,
)


FULLTIME_QUESTION = "全场比分预测是多少？"
DECISION_DISCLAIMER = "本研判基于赛前公开信息与独立模型生成，仅供信息参考，不构成投注或投资建议。"


async def resolve(request: FootballOsintJobRequest) -> MatchDecision:
    """Resolve the cache-backed full-time job and compose its decision desk.

    A supplied specialist question is intentionally discarded so opening a
    fixture always resolves the single primary, full-time prediction.
    """
    fulltime_request = request.model_copy(update={"question": FULLTIME_QUESTION})
    entry = await warm_cache.cache_or_compute(fulltime_request)
    fixture_status, actual_result = await _resolve_fixture_state(fulltime_request, entry.job)
    return compose(entry.job, fixture_status=fixture_status, actual_result=actual_result)


def compose(
    job: FootballOsintJob,
    *,
    fixture_status: Literal["scheduled", "live", "finished"],
    actual_result: ActualResult | None = None,
) -> MatchDecision:
    """Build a display response from an already-completed job snapshot."""
    prediction = job.prediction
    outcome, probabilities = _model_outcome(prediction.lean if prediction else "info_insufficient", prediction.outcome_probabilities if prediction else None)
    consensus = job.market_context.consensus if job.market_context else None
    comparison = compare_market_consensus(
        MatchDecision(outcome=outcome, outcome_probabilities=probabilities),
        consensus,
    )
    review = _review(prediction, actual_result)
    return MatchDecision(
        outcome=outcome,
        outcome_probabilities=probabilities,
        reason=prediction.summary if prediction else "暂未形成系统研判。",
        match=job.match,
        fixture_status=fixture_status,
        model_prediction=prediction,
        confidence=job.confidence,
        market_consensus=consensus,
        market_sources=list(job.market_context.snapshots) if job.market_context else [],
        market_comparison=comparison,
        evidence_summary=(job.confirmed_findings + job.assessments)[:6],
        updated_at=_as_utc(job.updated_at),
        actual_result=actual_result,
        review=review,
        disclaimer=DECISION_DISCLAIMER,
    )


async def _resolve_fixture_state(
    request: FootballOsintJobRequest,
    job: FootballOsintJob,
) -> tuple[Literal["scheduled", "live", "finished"], ActualResult | None]:
    fixture = await asyncio.to_thread(_find_fixture, request)
    if fixture is not None:
        status = getattr(fixture, "status", "")
        if status in {"scheduled", "live", "finished"}:
            home_score = getattr(fixture, "home_score", None)
            away_score = getattr(fixture, "away_score", None)
            if status == "finished" and isinstance(home_score, int) and isinstance(away_score, int):
                return "finished", ActualResult(
                    home_score=home_score,
                    away_score=away_score,
                    outcome=_actual_outcome(home_score, away_score),
                    settled_at=_fixture_settled_at(fixture),
                )
            return status, None

    kickoff = _parse_kickoff(request.kickoff_at)
    if kickoff is not None and kickoff > datetime.now(timezone.utc):
        return "scheduled", None
    # No verified final score means elapsed fixtures stay live: do not invent a
    # finished state from an arbitrary elapsed-time heuristic.
    return "live", None


def _find_fixture(request: FootballOsintJobRequest):
    """Return a provider fixture only when the request identity is unambiguous."""
    provider = request.provider.strip()
    fixtures = []
    if provider in {"", "football-data"}:
        fixtures.extend(football_data_schedule.fetch_fixtures(days_ahead=3))
    if provider in {"", "dongqiudi"}:
        # The Dongqiudi tab feed labels many records as ``Fixture`` even when
        # it already carries a final score.  Reuse its tested state derivation
        # before composing a decision or a post-match review.
        fixtures.extend(
            dongqiudi_schedule.fixtures_in_range(dongqiudi_schedule.fetch_fixtures())
        )

    candidates = [fixture for fixture in fixtures if _same_provider(request, fixture)]
    if request.provider_match_id:
        exact = [fixture for fixture in candidates if _fixture_id(fixture) == request.provider_match_id]
        return exact[0] if len(exact) == 1 else None

    matched = [fixture for fixture in candidates if _same_fixture_identity(request, fixture)]
    return matched[0] if len(matched) == 1 else None


def _same_provider(request: FootballOsintJobRequest, fixture: object) -> bool:
    requested = request.provider.strip()
    actual = str(getattr(fixture, "provider", "dongqiudi"))
    return not requested or requested == actual


def _fixture_id(fixture: object) -> str:
    return str(getattr(fixture, "provider_match_id", "") or getattr(fixture, "match_id", ""))


def _same_fixture_identity(request: FootballOsintJobRequest, fixture: object) -> bool:
    if _normalise(request.home_team) != _normalise(str(getattr(fixture, "home_team", ""))):
        return False
    if _normalise(request.away_team) != _normalise(str(getattr(fixture, "away_team", ""))):
        return False
    requested_kickoff = _parse_kickoff(request.kickoff_at)
    fixture_kickoff = getattr(fixture, "kickoff_at", None)
    if requested_kickoff is None or not isinstance(fixture_kickoff, datetime):
        return True
    if fixture_kickoff.tzinfo is None or fixture_kickoff.utcoffset() is None:
        return False
    return requested_kickoff == fixture_kickoff.astimezone(timezone.utc)


def _normalise(value: str) -> str:
    return "".join(value.lower().split())


def _parse_kickoff(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _fixture_settled_at(fixture: object) -> datetime | None:
    """Use provider settlement metadata only; never substitute a job timestamp."""
    for field in ("settled_at", "updated_at"):
        value = getattr(fixture, field, None)
        if isinstance(value, datetime):
            if value.tzinfo is not None and value.utcoffset() is not None:
                return value.astimezone(timezone.utc)
        elif isinstance(value, str):
            parsed = _parse_kickoff(value)
            if parsed is not None:
                return parsed
    return None


def _as_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc)


def _model_outcome(
    lean: str,
    probabilities: OutcomeProbabilities | None,
) -> tuple[Literal["home_win", "draw", "away_win", "info_insufficient"], OutcomeProbabilities | None]:
    if lean in {"home", "home_or_draw"}:
        return "home_win", probabilities
    if lean in {"away", "away_or_draw"}:
        return "away_win", probabilities
    if lean == "draw":
        return "draw", probabilities
    return "info_insufficient", None


def _actual_outcome(home_score: int, away_score: int) -> Literal["home", "draw", "away"]:
    if home_score > away_score:
        return "home"
    if home_score < away_score:
        return "away"
    return "draw"


def _review(prediction, actual_result: ActualResult | None) -> PostMatchReview | None:
    if prediction is None or actual_result is None:
        return None
    outcome_by_lean = {
        "home": {"home"},
        "home_or_draw": {"home", "draw"},
        "away": {"away"},
        "away_or_draw": {"away", "draw"},
        "draw": {"draw"},
        "info_insufficient": set(),
    }
    lean_correct = actual_result.outcome in outcome_by_lean[prediction.lean]
    scoreline = f"{actual_result.home_score}-{actual_result.away_score}"
    scoreline_hit = scoreline in prediction.scoreline_band
    return PostMatchReview(
        lean_correct=lean_correct,
        scoreline_hit=scoreline_hit,
        summary=("赛果方向命中。" if lean_correct else "赛果方向未命中。")
        + (" 推荐比分命中。" if scoreline_hit else " 推荐比分未命中。"),
    )

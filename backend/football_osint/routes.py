from __future__ import annotations

import asyncio
import os
import re


from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from .adapters import dongqiudi_schedule, football_data_schedule
from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest
from . import warm_cache
from . import track_record
from . import history as history_module

_JOB_ID_RE = re.compile(r"^fo_\d{8}_[0-9a-f]{10}$")


def _validate_job_id(job_id: str) -> str:
    if not _JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=422, detail="job_id 格式无效")
    return job_id


class CompareRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=3)

    @field_validator("job_ids")
    @classmethod
    def validate_job_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("job_ids 不能重复")
        invalid = [jid for jid in value if not _JOB_ID_RE.fullmatch(jid)]
        if invalid:
            raise ValueError("job_ids 含无效格式")
        return value


def _require_registered(http_request: Request) -> dict:
    """Gate behind login only — no entitlement check (registered free users allowed)."""
    from backend.auth.routes import get_current_user
    return get_current_user(http_request)  # raises 401 if not authenticated


def _require_paid(http_request: Request) -> dict:
    """Gate analysis endpoints behind login + an active full_analysis entitlement.

    Mirrors the frontend AuthGate(requiredTier="paid"): guests/free users are
    rejected here so the paywall cannot be bypassed by calling the API directly.
    """
    from backend.auth.routes import get_current_user
    from backend.billing import has_entitlement

    user = get_current_user(http_request)  # raises 401 if not authenticated
    if not has_entitlement(user["id"]):
        raise HTTPException(status_code=403, detail="需要开通完整功能（付费）后使用")
    return user

router = APIRouter(prefix="/api/football/osint", tags=["football-osint"])

_ANSWER_CONCURRENCY = max(1, int(os.getenv("FOOTBALL_OSINT_ANSWER_CONCURRENCY", "4")))
_ANSWER_SEMAPHORE = asyncio.Semaphore(_ANSWER_CONCURRENCY)


@router.post("/predict-sync", response_model=FootballOsintJob)
async def predict_sync(request: FootballOsintJobRequest, http_request: Request):
    _require_paid(http_request)
    async with _ANSWER_SEMAPHORE:
        entry = await warm_cache.cache_or_compute(request)
    return entry.job


@router.post("/jobs", response_model=FootballOsintJob)
async def create_job(request: FootballOsintJobRequest, http_request: Request):
    _require_paid(http_request)
    async with _ANSWER_SEMAPHORE:
        entry = await warm_cache.cache_or_compute(request)
    return entry.job


@router.post("/answer", response_model=FootballOsintAnswer)
async def answer_question(request: FootballOsintJobRequest, http_request: Request):
    _require_paid(http_request)
    if not _is_match_related(request):
        return FootballOsintAnswer(
            related=False,
            analysis_started=False,
            answer="问题与比赛无关",
            reasons=[],
        )

    async with _ANSWER_SEMAPHORE:
        entry = await warm_cache.cache_or_compute(request)
    return entry.answer


@router.get("/track-record")
async def get_track_record():
    """Public hit-rate stats (settled predictions vs actual results) for the landing page."""
    return await asyncio.to_thread(track_record.get_stats)


@router.get("/fixtures")
async def list_fixtures(days: int = Query(3, ge=0, le=14)):
    fixtures = await asyncio.to_thread(football_data_schedule.fetch_fixtures, days)

    upcoming = football_data_schedule.upcoming(fixtures)
    return [
        {
            "id": f.match_id,
            "league": f.league,
            "kickoff_at": f.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M"),
            "kickoff_iso": f.kickoff_at.astimezone(football_data_schedule.CST).isoformat(),
            "home_team": f.home_team,
            "away_team": f.away_team,
            "status": f.status,
            "home_score": f.home_score,
            "away_score": f.away_score,
        }
        for f in upcoming
    ]


@router.get("/jobs/{job_id}", response_model=FootballOsintJob)
async def get_job(job_id: str, http_request: Request):
    job_id = _validate_job_id(job_id)
    _require_paid(http_request)
    job = warm_cache.get_cached_by_job_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job


@router.get("/jobs/{job_id}/report.md", response_class=PlainTextResponse)
async def get_report(job_id: str, http_request: Request):
    job_id = _validate_job_id(job_id)
    _require_paid(http_request)
    job = warm_cache.get_cached_by_job_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job.report_markdown


def _is_match_related(request: FootballOsintJobRequest) -> bool:
    question = request.question.strip().lower()
    if not question:
        return True
    match_terms = [
        request.home_team,
        request.away_team,
        request.competition,
        "这场",
        "本场",
        "比赛",
        "球队",
        "主队",
        "客队",
        "胜",
        "平",
        "负",
        "进球",
        "比分",
        "角球",
        "红黄牌",
        "半场",
        "阵容",
        "伤停",
        "首发",
        "状态",
        "交锋",
        "赛程",
    ]
    return any(term and term.lower() in question for term in match_terms)


_LEAN_JUDGMENT: dict[str, str] = {
    "home": "主队占优",
    "away": "客队占优",
    "draw": "平局倾向",
    "home_or_draw": "主队不败",
    "away_or_draw": "客队不败",
    "info_insufficient": "信息不足",
}


def _answer_from_job(job: FootballOsintJob, question: str = "") -> FootballOsintAnswer:
    prediction = job.prediction
    confidence = job.confidence

    # ── preferred: LLM synthesis over all collected multi-source evidence ──
    from .analysis import match_report

    report = match_report.synthesize(job, question)
    if report:
        return FootballOsintAnswer(
            related=True,
            analysis_started=True,
            answer=report,
            judgment=_LEAN_JUDGMENT.get(prediction.lean, "") if prediction else "",
            reasons=prediction.drivers[:3] if prediction else [],
            confidence_level=confidence.level if confidence else "L4",
        )

    # ── fallback: osint-core template / short LLM / prediction summary ──
    from .analysis import osint_qa

    lean = prediction.lean if prediction else ""
    analysis = osint_qa.analyze(job, question, lean)

    if analysis.dimension:
        answer = analysis.answer
        judgment = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        reasons = analysis.assessments[:2] + analysis.data_gaps[:1]
        if not reasons:
            reasons = analysis.confirmed_facts[:2]
    elif question:
        # ── no dimension match: try LLM ──
        match_ctx = f"{job.match.home_team} vs {job.match.away_team}，{job.match.competition or '未指定'}"
        ev_lines = []
        for ev in job.evidence[-10:]:
            ev_lines.append(f"[{ev.source}] {(ev.raw_excerpt or ev.claim)[:200]}")
        evidence_text = "\n".join(ev_lines) if ev_lines else "暂无有效证据"

        from .analysis import llm_qa
        lean_cn = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        llm_answer = llm_qa.answer_question(question, evidence_text, match_ctx, lean_cn)
        if llm_answer:
            answer = llm_answer
        else:
            answer = prediction.summary if prediction else "已完成基本面判断，但暂时没有形成明确倾向。"
        judgment = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        reasons = prediction.drivers[:2] if prediction else []
    else:
        answer = prediction.summary if prediction else "已完成基本面判断，但暂时没有形成明确倾向。"
        judgment = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        reasons = prediction.drivers[:2] if prediction else []

    return FootballOsintAnswer(
        related=True,
        analysis_started=True,
        answer=answer,
        judgment=judgment,
        reasons=reasons[:3],
        confidence_level=confidence.level if confidence else "L4",
    )


# ── v2: 赛后回看 & 多场对比 ──────────────────────────────────────────────────

@router.get("/history")
async def list_history(http_request: Request, days: int = Query(30, ge=1, le=90)):
    """已结束比赛历史列表（摘要）。已注册用户可访问。"""
    _require_registered(http_request)
    return await asyncio.to_thread(history_module.get_history_list, days=days)


@router.get("/history/{job_id}")
async def get_history_detail(job_id: str, http_request: Request):
    """单场回顾。lean/比分/命中标记对已注册用户开放；因子+retrospective 需付费。"""
    job_id = _validate_job_id(job_id)
    user = _require_registered(http_request)
    from backend.billing import has_entitlement
    paid = has_entitlement(user["id"])
    result = await asyncio.to_thread(history_module.get_history_detail, job_id, paid=paid)
    if result is None:
        raise HTTPException(status_code=404, detail="未找到该比赛的已结算记录")
    return result


@router.post("/compare")
async def compare_matches(body: CompareRequest, http_request: Request):
    """多场对比（最多 3 场）。需付费。body: {"job_ids": ["fo_...", ...]}"""
    _require_paid(http_request)
    return await asyncio.to_thread(history_module.compare_jobs, body.job_ids)

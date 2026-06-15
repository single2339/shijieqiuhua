from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import OrderedDict


from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .adapters import dongqiudi_schedule, football_data_schedule
from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest
from .pipeline import run_prediction_sync
from . import warm_cache


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

_JOB_CACHE_MAX = max(64, int(os.getenv("FOOTBALL_OSINT_JOB_CACHE_MAX", "512")))
_JOB_CACHE_TTL = max(60, int(os.getenv("FOOTBALL_OSINT_JOB_CACHE_TTL", "3600")))


class _JobCache:
    """Bounded LRU + TTL cache for completed OSINT jobs.

    Keeps the in-memory store from growing unboundedly when the public
    endpoint is hit by many distinct match queries.
    """

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, FootballOsintJob]] = OrderedDict()
        self._max = max_size
        self._ttl = ttl_seconds

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._store)

    def get(self, key: str) -> FootballOsintJob | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, job = entry
            if time.time() - ts >= self._ttl:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return job

    def set(self, key: str, job: FootballOsintJob) -> None:
        with self._lock:
            self._evict_expired()
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.time(), job)
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts >= self._ttl]
        for k in expired:
            del self._store[k]


_JOBS = _JobCache(_JOB_CACHE_MAX, _JOB_CACHE_TTL)


@router.post("/predict-sync", response_model=FootballOsintJob)
async def predict_sync(request: FootballOsintJobRequest, http_request: Request):
    _require_paid(http_request)
    cached = warm_cache.get_cached_job(request)
    if cached is not None:
        return cached
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


@router.post("/jobs", response_model=FootballOsintJob)
async def create_job(request: FootballOsintJobRequest, http_request: Request):
    _require_paid(http_request)
    cached = warm_cache.get_cached_job(request)
    if cached is not None:
        return cached
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


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

    cached = warm_cache.get_cached_answer(request)
    if cached is not None:
        return cached

    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    # _answer_from_job does blocking LLM calls — keep it off the event loop.
    return await asyncio.to_thread(_answer_from_job, job, request.question)


@router.get("/fixtures")
async def list_fixtures(days: int = 3):
    fixtures = await asyncio.to_thread(football_data_schedule.fetch_fixtures, days)

    upcoming = football_data_schedule.upcoming(fixtures)
    return [
        {
            "id": f.match_id,
            "league": f.league,
            "kickoff_at": f.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M"),
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
    _require_paid(http_request)
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job


@router.get("/jobs/{job_id}/report.md", response_class=PlainTextResponse)
async def get_report(job_id: str, http_request: Request):
    _require_paid(http_request)
    job = _JOBS.get(job_id)
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

    analysis = osint_qa.analyze(job, question)

    if analysis.dimension:
        answer = analysis.answer
        judgment = analysis.confidence_level
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
        llm_answer = llm_qa.answer_question(question, evidence_text, match_ctx)
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

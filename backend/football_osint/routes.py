from __future__ import annotations

import asyncio
import os
import time
from collections import OrderedDict

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest
from .pipeline import run_prediction_sync

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
        self._store: OrderedDict[str, tuple[float, FootballOsintJob]] = OrderedDict()
        self._max = max_size
        self._ttl = ttl_seconds

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._store)

    def get(self, key: str) -> FootballOsintJob | None:
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
async def predict_sync(request: FootballOsintJobRequest):
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


@router.post("/jobs", response_model=FootballOsintJob)
async def create_job(request: FootballOsintJobRequest):
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


@router.post("/answer", response_model=FootballOsintAnswer)
async def answer_question(request: FootballOsintJobRequest):
    if not _is_match_related(request):
        return FootballOsintAnswer(
            related=False,
            analysis_started=False,
            answer="问题与比赛无关",
            reasons=[],
        )

    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return _answer_from_job(job)


@router.get("/jobs/{job_id}", response_model=FootballOsintJob)
async def get_job(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job


@router.get("/jobs/{job_id}/report.md", response_class=PlainTextResponse)
async def get_report(job_id: str):
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
        "win007:",
    ]
    return any(term and term.lower() in question for term in match_terms)


def _answer_from_job(job: FootballOsintJob) -> FootballOsintAnswer:
    prediction = job.prediction
    confidence = job.confidence
    judgment = prediction.lean if prediction else ""
    reasons = []
    if prediction:
        reasons.extend(prediction.drivers[:2])
        reasons.extend(prediction.uncertainties[:1])
    if not reasons and job.assessments:
        reasons.append(job.assessments[0].statement)
    answer = prediction.summary if prediction else "已完成基本面判断，但暂时没有形成明确倾向。"
    return FootballOsintAnswer(
        related=True,
        analysis_started=True,
        answer=answer,
        judgment=judgment,
        reasons=reasons[:3],
        confidence_level=confidence.level if confidence else "L4",
    )

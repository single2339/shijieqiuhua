"""Pre-warmed LLM answers for today's matches.

On startup (and every hour after, until a match finishes) this module runs
the full OSINT pipeline + LLM answer for each of the preset "common
questions" shown as chips in the frontend. ``/jobs`` and ``/answer`` then
serve these pre-computed results instantly; only questions outside the
preset set fall through to a live pipeline run.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from .adapters import football_data_schedule
from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest

log = logging.getLogger(__name__)

# Must match frontend/src/shijieqiuhua/mockData.ts QUESTION_PRESETS prompts.
PRESET_QUESTIONS: list[str] = [
    "上半场哪一方更容易占据主动？",
    "本场红黄牌风险是否偏高？",
    "上半场角球会不会偏多？",
    "全场进球数压力更偏大还是偏小？",
    "核心球员状态会怎样影响比赛？",
    "这场比赛最大的临场风险是什么？",
]

REFRESH_INTERVAL_SECONDS = 3600

_WARM_ENABLED = os.getenv("FOOTBALL_OSINT_WARM_ENABLED", "1") not in ("0", "false", "False")
_WARM_MAX_MATCHES = max(0, int(os.getenv("FOOTBALL_OSINT_WARM_MAX_MATCHES", "6")))

_lock = asyncio.Lock()
_warm_jobs: dict[str, FootballOsintJob] = {}
_warm_answers: dict[str, FootballOsintAnswer] = {}


def cache_key(home_team: str, away_team: str, kickoff_at: str, question: str) -> str:
    return f"{home_team}|{away_team}|{kickoff_at}|{question.strip()}"


def get_cached_job(request: FootballOsintJobRequest) -> FootballOsintJob | None:
    return _warm_jobs.get(cache_key(request.home_team, request.away_team, request.kickoff_at, request.question))


def get_cached_answer(request: FootballOsintJobRequest) -> FootballOsintAnswer | None:
    return _warm_answers.get(cache_key(request.home_team, request.away_team, request.kickoff_at, request.question))


async def _warm_match(fixture: football_data_schedule.Fixture) -> None:
    from .pipeline import run_prediction_sync
    from .routes import _answer_from_job

    kickoff_at = fixture.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M")

    for question in PRESET_QUESTIONS:
        request = FootballOsintJobRequest(
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            kickoff_at=kickoff_at,
            competition=fixture.league,
            question=question,
        )
        try:
            job = await asyncio.to_thread(run_prediction_sync, request)
            answer = await asyncio.to_thread(_answer_from_job, job, question)
        except Exception:
            log.exception(
                "football osint warm cache failed for %s vs %s / %s",
                fixture.home_team, fixture.away_team, question,
            )
            continue

        key = cache_key(request.home_team, request.away_team, request.kickoff_at, question)
        async with _lock:
            _warm_jobs[key] = job
            _warm_answers[key] = answer


async def _warm_today_matches() -> None:
    fixtures = await asyncio.to_thread(football_data_schedule.fetch_fixtures, 1)
    today = datetime.now(football_data_schedule.CST).date()
    todays = [
        f for f in fixtures
        if f.status != "finished" and f.kickoff_at.astimezone(football_data_schedule.CST).date() == today
    ]
    for fixture in todays[:_WARM_MAX_MATCHES]:
        await _warm_match(fixture)


async def warm_loop() -> None:
    """Run forever: warm today's matches now, then every hour."""
    if not _WARM_ENABLED:
        return
    while True:
        try:
            await _warm_today_matches()
        except Exception:
            log.exception("football osint warm cache loop iteration failed")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)

"""Unified match analysis cache — lazy-first with scheduled refresh.

Any question about a match (preset or free-text) is cached on first request.
All users accessing the same match + question get the identical cached answer.

Scheduled refreshes at T-5h and T-2h before kickoff force-overwrite preset
question caches with the latest data closer to match time.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .adapters import football_data_schedule
from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest

log = logging.getLogger(__name__)

# Must match frontend/src/shijieqiuhua/mockData.ts QUESTION_PRESETS prompts.
PRESET_QUESTIONS: list[str] = [
    "上半场比分预计是多少？",
    "全场红黄牌的预测数量是多少？",
    "全场角球数预测是多少？",
    "全场比分预测是多少？",
    "核心球员状态会怎样影响比赛？",
    "这场比赛最大的临场风险是什么？",
]

# How often to re-scan fixtures for new/updated matches.
_FIXTURE_RESCAN_SECONDS = 15 * 60  # 15 min

_WARM_ENABLED = os.getenv("FOOTBALL_OSINT_WARM_ENABLED", "1") not in ("0", "false", "False")
_WARM_MAX_MATCHES = max(0, int(os.getenv("FOOTBALL_OSINT_WARM_MAX_MATCHES", "6")))
_CACHE_MAX = max(64, int(os.getenv("FOOTBALL_OSINT_CACHE_MAX", "512")))

_lock = asyncio.Lock()

# ── unified cache ──

_cache: OrderedDict[str, "CacheEntry"] = OrderedDict()
_by_job_id: dict[str, str] = {}  # job_id → cache_key

# ── in-flight dedup ──

_inflight: dict[str, asyncio.Event] = {}

# ── scheduled window tracking ──

_completed_windows: set[tuple[str, str]] = set()  # {(match_prefix, "t-5h"|"t-2h")}


@dataclass
class CacheEntry:
    job: FootballOsintJob
    answer: FootballOsintAnswer
    cached_at: float  # time.time()
    source: str  # "on-demand" | "t-5h" | "t-2h"


# ── key helpers ──

def cache_key(home_team: str, away_team: str, kickoff_at: str, question: str) -> str:
    """Stable key for a (match, question) pair.

    Preset questions use the literal text; free-text questions are hashed
    so identical wording produces the same key.
    """
    q = question.strip()
    if q in PRESET_QUESTIONS:
        return f"{home_team}|{away_team}|{kickoff_at}|{q}"
    return f"{home_team}|{away_team}|{kickoff_at}|free:{hashlib.sha1(q.encode()).hexdigest()[:16]}"


def match_prefix(home_team: str, away_team: str, kickoff_at: str) -> str:
    """Stable prefix for a match, used to track completed analysis windows."""
    return f"{home_team}|{away_team}|{kickoff_at}"


def is_preset_question(question: str) -> bool:
    """Check whether a question matches one of the preset templates."""
    return question.strip() in PRESET_QUESTIONS


# ── public cache access ──

async def get_cached(request: FootballOsintJobRequest) -> CacheEntry | None:
    """Return cached entry for a match+question pair, or None."""
    key = cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
    async with _lock:
        entry = _cache.get(key)
        if entry is not None:
            _cache.move_to_end(key)
        return entry


async def get_cached_job(request: FootballOsintJobRequest) -> FootballOsintJob | None:
    entry = await get_cached(request)
    return entry.job if entry else None


async def get_cached_answer(request: FootballOsintJobRequest) -> FootballOsintAnswer | None:
    entry = await get_cached(request)
    return entry.answer if entry else None


def get_cached_by_job_id(job_id: str) -> FootballOsintJob | None:
    """Look up a cached job by its job_id (for GET /jobs/{job_id})."""
    key = _by_job_id.get(job_id)
    if key is None:
        return None
    entry = _cache.get(key)
    return entry.job if entry else None


# ── internal helpers ──

def _store_entry(key: str, entry: CacheEntry) -> None:
    """Insert into cache with LRU eviction.  Caller must hold _lock."""
    if key in _cache:
        _cache.move_to_end(key)
    else:
        while len(_cache) >= _CACHE_MAX:
            oldest_key, _ = _cache.popitem(last=False)
            for jid, ck in list(_by_job_id.items()):
                if ck == oldest_key:
                    del _by_job_id[jid]
                    break
    _cache[key] = entry
    _by_job_id[entry.job.job_id] = key


async def _compute_and_cache(
    request: FootballOsintJobRequest,
    *,
    source: str = "on-demand",
) -> CacheEntry:
    """Run pipeline and store the result in cache."""
    from .pipeline import run_prediction_sync
    from .routes import _answer_from_job

    job = await asyncio.to_thread(run_prediction_sync, request)
    answer = await asyncio.to_thread(_answer_from_job, job, request.question)
    entry = CacheEntry(job=job, answer=answer, cached_at=time.time(), source=source)

    key = cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
    async with _lock:
        _store_entry(key, entry)
    return entry


# ── main entry point ──

async def cache_or_compute(
    request: FootballOsintJobRequest,
    *,
    force_refresh: bool = False,
) -> CacheEntry:
    """Get cached result or compute + cache it.

    On cache miss, only one request computes while others wait (in-flight
    dedup via asyncio.Event).

    Set ``force_refresh=True`` to bypass cache and in-flight wait — used
    by the warm loop at T-5h / T-2h to overwrite with fresher data.
    """
    if not force_refresh:
        entry = await get_cached(request)
        if entry is not None:
            return entry

    # ── in-flight dedup ──
    key = cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
    event: asyncio.Event | None = None
    is_runner = False
    async with _lock:
        if key in _inflight:
            event = _inflight[key]
        else:
            event = asyncio.Event()
            _inflight[key] = event
            is_runner = True

    if is_runner:
        try:
            return await _compute_and_cache(request, source="on-demand")
        finally:
            event.set()
            async with _lock:
                _inflight.pop(key, None)
    else:
        await event.wait()
        entry = await get_cached(request)
        if entry is not None:
            return entry
        # Edge case: previous runner failed but didn't cache. Compute ourselves.
        return await _compute_and_cache(request, source="on-demand")


async def _force_refresh(request: FootballOsintJobRequest, *, window: str) -> None:
    """Force-overwrite cache for a match+question (warm loop only)."""
    from .pipeline import run_prediction_sync
    from .routes import _answer_from_job

    key = cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
    try:
        job = await asyncio.to_thread(run_prediction_sync, request)
        answer = await asyncio.to_thread(_answer_from_job, job, request.question)
        entry = CacheEntry(job=job, answer=answer, cached_at=time.time(), source=window)
        async with _lock:
            _store_entry(key, entry)
    except Exception:
        log.exception(
            "warm cache %s force-refresh failed for %s vs %s / %s",
            window, request.home_team, request.away_team, request.question,
        )


# ── warm loop ──

async def _run_analysis_for_match(
    fixture: football_data_schedule.Fixture,
    *,
    window: str,  # "t-5h" or "t-2h"
) -> int:
    """Run full pipeline for all preset questions on one match. Returns count of successful runs."""
    kickoff_at = fixture.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M")
    mp = match_prefix(fixture.home_team, fixture.away_team, kickoff_at)
    ok_count = 0

    for question in PRESET_QUESTIONS:
        request = FootballOsintJobRequest(
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            kickoff_at=kickoff_at,
            competition=fixture.league,
            question=question,
        )
        try:
            await _force_refresh(request, window=window)
            ok_count += 1
        except Exception:
            log.exception(
                "warm cache %s failed for %s vs %s / %s",
                window, fixture.home_team, fixture.away_team, question,
            )

    async with _lock:
        _completed_windows.add((mp, window))

    log.warning(
        "warm cache %s: %s vs %s done (%d/%d questions)",
        window, fixture.home_team, fixture.away_team, ok_count, len(PRESET_QUESTIONS),
    )
    return ok_count


def _next_analysis_time(
    fixtures: list[football_data_schedule.Fixture],
) -> tuple[datetime | None, list[tuple[football_data_schedule.Fixture, str]]]:
    """Find the earliest upcoming analysis window and which matches need it.

    Returns (next_time, [(fixture, window), ...]) where window is "t-5h" or "t-2h".
    If no upcoming windows remain, returns (None, []).
    """
    now = datetime.now(timezone.utc)
    candidates: list[tuple[datetime, football_data_schedule.Fixture, str]] = []

    for f in fixtures:
        kickoff_str = f.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M")
        mp = match_prefix(f.home_team, f.away_team, kickoff_str)

        for offset, window in [(timedelta(hours=5), "t-5h"), (timedelta(hours=2), "t-2h")]:
            target = f.kickoff_at - offset
            if target > now and (mp, window) not in _completed_windows:
                candidates.append((target, f, window))

    if not candidates:
        return None, []

    candidates.sort(key=lambda x: x[0])
    next_time = candidates[0][0]
    due = [(f, w) for t, f, w in candidates if t <= next_time + timedelta(seconds=60)]
    return next_time, due


async def _warm_due_matches(fixtures: list[football_data_schedule.Fixture]) -> None:
    """Run analysis for all matches whose T-5h or T-2h window has arrived."""
    now = datetime.now(timezone.utc)

    for f in fixtures:
        kickoff_str = f.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M")
        mp = match_prefix(f.home_team, f.away_team, kickoff_str)

        for offset, window in [(timedelta(hours=5), "t-5h"), (timedelta(hours=2), "t-2h")]:
            target = f.kickoff_at - offset
            if target <= now and (mp, window) not in _completed_windows:
                log.warning("warm cache: running %s for %s vs %s", window, f.home_team, f.away_team)
                await _run_analysis_for_match(f, window=window)


async def warm_loop() -> None:
    """Run forever: analyse matches at T-5h and T-2h before each kickoff.

    On startup, immediately runs any overdue windows (e.g. server restarted
    between T-5h and T-2h). Then sleeps until the next scheduled window.
    Re-scans fixtures every 15 minutes in case new matches appear.
    """
    if not _WARM_ENABLED:
        return

    while True:
        try:
            fixtures = await asyncio.to_thread(football_data_schedule.fetch_fixtures, 3)
            candidates = football_data_schedule.upcoming(fixtures)
            matches = candidates[:_WARM_MAX_MATCHES]

            # Run any windows that are already due (catch-up after restart).
            await _warm_due_matches(matches)

            # Find the next scheduled window.
            next_time, due = _next_analysis_time(matches)

            if next_time is None:
                log.warning("warm cache: no upcoming analysis windows, sleeping %ds", _FIXTURE_RESCAN_SECONDS)
                await asyncio.sleep(_FIXTURE_RESCAN_SECONDS)
                continue

            wait_seconds = max(1, (next_time - datetime.now(timezone.utc)).total_seconds())
            # Cap the wait so we re-scan fixtures periodically even if the next
            # window is far away.
            wait_seconds = min(wait_seconds, _FIXTURE_RESCAN_SECONDS)
            log.warning(
                "warm cache: next analysis at %s (in %.0f min), %d match(es) due",
                next_time.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M"),
                wait_seconds / 60,
                len(due),
            )
            await asyncio.sleep(wait_seconds)

        except Exception:
            log.exception("warm cache loop iteration failed")
            await asyncio.sleep(60)

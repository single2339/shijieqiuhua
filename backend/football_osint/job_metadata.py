"""Match/question metadata helpers for football OSINT jobs."""
from __future__ import annotations

import hashlib
from typing import Any

from .models import FootballOsintJobRequest

PRESET_QUESTION_IDS: dict[str, str] = {
    "上半场比分预计是多少？": "first_half_score",
    "全场红黄牌的预测数量是多少？": "cards_total",
    "全场角球数预测是多少？": "corners_total",
    "全场比分预测是多少？": "fulltime_score",
    "核心球员状态会怎样影响比赛？": "key_player_state",
    "这场比赛最大的临场风险是什么？": "late_risk",
}


def match_key(home_team: str, away_team: str, kickoff_at: str) -> str:
    return "|".join([_norm(home_team), _norm(away_team), _norm(kickoff_at)])


def question_metadata(
    question: str,
    *,
    warm_window: str = "on-demand",
    cache_source: str = "on-demand",
) -> dict[str, str | None]:
    q = (question or "").strip()
    if q in PRESET_QUESTION_IDS:
        return {
            "question": q,
            "question_kind": "preset",
            "question_id": PRESET_QUESTION_IDS[q],
            "question_hash": None,
            "warm_window": warm_window,
            "cache_source": cache_source,
        }
    if q:
        return {
            "question": "",
            "question_kind": "free_text",
            "question_id": "free_text",
            "question_hash": hashlib.sha1(q.encode("utf-8")).hexdigest()[:16],
            "warm_window": warm_window,
            "cache_source": cache_source,
        }
    return {
        "question": "",
        "question_kind": "none",
        "question_id": "none",
        "question_hash": None,
        "warm_window": warm_window,
        "cache_source": cache_source,
    }


def record_request_metadata(
    request: FootballOsintJobRequest,
    *,
    warm_window: str = "on-demand",
    cache_source: str = "on-demand",
) -> dict[str, Any]:
    meta = question_metadata(
        request.question,
        warm_window=warm_window,
        cache_source=cache_source,
    )
    return {
        "home_team": request.home_team,
        "away_team": request.away_team,
        "kickoff_at": request.kickoff_at,
        "competition": request.competition,
        "venue": request.venue,
        "locale": request.locale,
        "match_key": match_key(request.home_team, request.away_team, request.kickoff_at),
        **meta,
        "user_supplied_summary": {
            "injuries_count": len(request.user_supplied.injuries),
            "lineups_count": len(request.user_supplied.lineups),
            "notes_count": len(request.user_supplied.notes),
        },
    }


def _norm(value: str) -> str:
    return " ".join((value or "").strip().split())

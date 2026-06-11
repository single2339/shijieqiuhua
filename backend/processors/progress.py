"""Per-request progress tracker for super-analysis."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgressState:
    phase: str = "idle"
    message: str = ""
    percent: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)


_states: dict[str, ProgressState] = {}
_MAX_STATES = 64


def _evict_oldest() -> None:
    if len(_states) > _MAX_STATES:
        oldest = sorted(_states.items(), key=lambda kv: kv[1].started_at or float("inf"))[:16]
        for k, _ in oldest:
            del _states[k]


def reset_progress() -> str:
    request_id = uuid.uuid4().hex[:12]
    init_progress(request_id)
    return request_id


def init_progress(request_id: str):
    _evict_oldest()
    _states[request_id] = ProgressState()


def set_progress(request_id: str, phase: str, message: str, percent: int = 0, **detail):
    state = _states.get(request_id)
    if state is None:
        return
    state.phase = phase
    state.message = message
    state.percent = percent
    if state.started_at == 0:
        state.started_at = time.time()
    state.detail = detail


def get_progress(request_id: str) -> dict:
    state = _states.get(request_id)
    if state is None:
        return {"phase": "idle", "message": "", "percent": 0, "elapsed_seconds": 0, "detail": {}}
    elapsed = time.time() - state.started_at if state.started_at else 0
    return {
        "phase": state.phase,
        "message": state.message,
        "percent": state.percent,
        "elapsed_seconds": round(elapsed, 1),
        "detail": state.detail,
    }


def mark_finished(request_id: str):
    state = _states.get(request_id)
    if state is None:
        return
    state.finished_at = time.time()
    state.phase = "done"
    state.percent = 100
    state.message = "分析完成"


def mark_error(request_id: str, error: str):
    state = _states.get(request_id)
    if state is None:
        return
    state.phase = "error"
    state.message = error
    state.finished_at = time.time()

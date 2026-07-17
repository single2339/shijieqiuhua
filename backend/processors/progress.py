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
    created_at: float = field(default_factory=time.time)
    owner_id: int | None = None


_states: dict[tuple[int | None, str], ProgressState] = {}
_MAX_STATES_PER_OWNER = 64
_MAX_STATES_TOTAL = 4096


def _state_key(request_id: str, owner_id: int | None) -> tuple[int | None, str]:
    return owner_id, request_id


def _evict_oldest(owner_id: int | None) -> None:
    owner_states = [
        (key, state)
        for key, state in _states.items()
        if key[0] == owner_id
    ]
    if len(owner_states) >= _MAX_STATES_PER_OWNER:
        oldest = sorted(owner_states, key=lambda item: item[1].created_at)[:16]
        for key, _state in oldest:
            del _states[key]

    if len(_states) >= _MAX_STATES_TOTAL:
        oldest = sorted(_states.items(), key=lambda item: item[1].created_at)[:256]
        for key, _state in oldest:
            del _states[key]


def reset_progress(owner_id: int | None = None) -> str:
    request_id = uuid.uuid4().hex[:12]
    init_progress(request_id, owner_id)
    return request_id


def init_progress(request_id: str, owner_id: int | None = None):
    _evict_oldest(owner_id)
    _states[_state_key(request_id, owner_id)] = ProgressState(owner_id=owner_id)


def set_progress(
    request_id: str,
    phase: str,
    message: str,
    percent: int = 0,
    *,
    owner_id: int | None = None,
    **detail,
):
    state = _states.get(_state_key(request_id, owner_id))
    if state is None:
        return
    state.phase = phase
    state.message = message
    state.percent = percent
    if state.started_at == 0:
        state.started_at = time.time()
    state.detail = detail


def get_progress(request_id: str, owner_id: int | None = None) -> dict | None:
    state = _states.get(_state_key(request_id, owner_id))
    if state is None:
        return None
    elapsed = time.time() - state.started_at if state.started_at else 0
    return {
        "phase": state.phase,
        "message": state.message,
        "percent": state.percent,
        "elapsed_seconds": round(elapsed, 1),
        "detail": state.detail,
    }


def mark_finished(request_id: str, owner_id: int | None = None):
    state = _states.get(_state_key(request_id, owner_id))
    if state is None:
        return
    state.finished_at = time.time()
    state.phase = "done"
    state.percent = 100
    state.message = "分析完成"


def mark_error(request_id: str, error: str, owner_id: int | None = None):
    state = _states.get(_state_key(request_id, owner_id))
    if state is None:
        return
    state.phase = "error"
    state.message = error
    state.finished_at = time.time()

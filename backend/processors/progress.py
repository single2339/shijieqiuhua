"""In-memory progress tracker for super-analysis."""

from __future__ import annotations

import time
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


_state = ProgressState()


def set_progress(phase: str, message: str, percent: int = 0, **detail):
    _state.phase = phase
    _state.message = message
    _state.percent = percent
    if _state.started_at == 0:
        _state.started_at = time.time()
    _state.detail = detail


def get_progress() -> dict:
    elapsed = time.time() - _state.started_at if _state.started_at else 0
    return {
        "phase": _state.phase,
        "message": _state.message,
        "percent": _state.percent,
        "elapsed_seconds": round(elapsed, 1),
        "detail": _state.detail,
    }


def reset_progress():
    global _state
    _state = ProgressState()


def mark_finished():
    _state.finished_at = time.time()
    _state.phase = "done"
    _state.percent = 100
    _state.message = "分析完成"


def mark_error(error: str):
    _state.phase = "error"
    _state.message = error
    _state.finished_at = time.time()

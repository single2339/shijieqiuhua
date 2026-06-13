"""Adapter base contract (W1 skeleton).

W2 implementations will subclass / use this protocol; W1 provides only the
type alias so callers can already write annotations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus


@dataclass(frozen=True)
class AdapterResult:
    evidence: list[OsintEvidence]
    status: OsintSourceStatus


class Adapter(Protocol):
    """Protocol all adapters will implement in W2.

    Adapters MUST:
    - never raise (return status='failed' instead)
    - return status='skipped' with reason when missing API keys
    - respect FOOTBALL_OSINT_URL_ALLOWLIST for any outbound URL
    """

    name: str
    label: str

    def collect(self, request: FootballOsintJobRequest) -> AdapterResult:  # pragma: no cover
        ...

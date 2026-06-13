"""Evidence construction + classification helpers.

PRD §4.5 + §6.1. W2.7 added append_evidence so adapters can mint new
OsintEvidence rows without depending on pipeline.py internals.
"""
from __future__ import annotations

from .models import OsintEvidence

STRONG_THRESHOLD = 0.50
WEAK_THRESHOLD = 0.25


def append_evidence(
    evidence: list[OsintEvidence],
    *,
    source: str,
    source_type: str,
    claim: str,
    topic: str,
    side: str,
    confidence: float,
    raw_excerpt: str = "",
    url: str = "",
) -> str:
    """Mint a new ev_NNN id, append the OsintEvidence row, return the id.

    Adapters call this so the id sequence stays monotonic across the whole
    job. Mutation rather than immutable return is intentional: the surrounding
    job assembly tracks evidence as one growing list.
    """
    eid = f"ev_{len(evidence) + 1:03d}"
    evidence.append(
        OsintEvidence(
            id=eid,
            source=source,
            source_type=source_type,
            claim=claim,
            topic=topic,
            side=side,  # type: ignore[arg-type]
            confidence=confidence,
            raw_excerpt=raw_excerpt,
            url=url,
        )
    )
    return eid


def classify_strength(confidence: float) -> str:
    """Return 'strong' | 'weak' | 'insufficient' for an evidence confidence.

    Thresholds locked by PRD §4.5 / decisions.md Q14 default. admin CLI may
    swap these via system_config in W2.
    """
    if confidence >= STRONG_THRESHOLD:
        return "strong"
    if confidence >= WEAK_THRESHOLD:
        return "weak"
    return "insufficient"


def by_strength(evidence: list[OsintEvidence]) -> dict[str, list[OsintEvidence]]:
    """Bucket evidence into strong/weak/insufficient lists for the UI."""
    buckets: dict[str, list[OsintEvidence]] = {"strong": [], "weak": [], "insufficient": []}
    for ev in evidence:
        buckets[classify_strength(ev.confidence)].append(ev)
    return buckets

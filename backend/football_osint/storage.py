"""OSINT job persistence helpers (W1 skeleton).

Owns the bronze layout described in PRD §5.4. W1 ships only the entry
points (job_dir, persist_job); pipeline.py keeps its own _persist() until
W2 swaps it over.

PRD §5.4 file layout:
    bronze_storage/football_osint/{job_id}/
        request.json
        status.json
        report.md
        provenance.json
        verify.json       # W2
        raw/*             # W2
        normalized.json   # W2
        factors.json      # W2
        prediction.json   # W2

W1 only persists the four core files (decision Q18).
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import FootballOsintJob

DEFAULT_STORAGE_ROOT = Path("bronze_storage") / "football_osint"


def job_dir(job_id: str, storage_root: str | Path | None = None) -> Path:
    root = Path(storage_root) if storage_root else DEFAULT_STORAGE_ROOT
    return root / job_id


def persist_job(
    job: FootballOsintJob,
    storage_root: str | Path | None = None,
    *,
    request=None,
    warm_window: str = "on-demand",
    cache_source: str = "on-demand",
) -> Path:
    """Write request/status/report/provenance for a completed job.

    ``request`` is optional for legacy callers/tests; new pipeline callers pass
    the original ``FootballOsintJobRequest`` so the bronze artifact explains
    the question/window that produced this job.
    """
    target = job_dir(job.job_id, storage_root)
    target.mkdir(parents=True, exist_ok=True)

    (target / "status.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
    (target / "report.md").write_text(job.report_markdown, encoding="utf-8")

    if request is not None:
        from . import job_metadata
        request_payload = job_metadata.record_request_metadata(
            request,
            warm_window=warm_window,
            cache_source=cache_source,
        )
    else:
        request_payload = {
            "home_team": job.match.home_team,
            "away_team": job.match.away_team,
            "kickoff_at": job.match.kickoff_at,
            "competition": job.match.competition,
            "venue": job.match.venue,
        }
    (target / "request.json").write_text(
        json.dumps(request_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    provenance = {
        "job_id": job.job_id,
        "created_at": job.created_at,
        "sources": [s.model_dump() for s in job.sources],
    }
    (target / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target

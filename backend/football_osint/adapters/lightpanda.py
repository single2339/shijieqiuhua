"""lightpanda subprocess adapter (W2.7a — extracted from pipeline.py).

Wraps the `lp-fetch-md` external binary. Pure function — given a binary
path + URL + topic metadata, runs the subprocess with a hard timeout,
hands back either an evidence id or a failure reason.

Security boundary:
- The caller is responsible for passing only allowlisted URLs (see
  url_safety.valid_urls). This module does NOT re-validate; if you skip
  url_safety, you reopen the SSRF hole.
- Subprocess uses argv form (no shell=True), so the URL itself cannot be
  command-injected even on a malicious value.

PRD trace: §5.6 SRF mitigation, §5.4 evidence schema.
"""
from __future__ import annotations

import os
import subprocess

from ..analysis import report as report_module
from ..evidence import append_evidence
from ..models import FootballOsintJobRequest, OsintEvidence

DEFAULT_TIMEOUT_SECONDS = 18.0


def fetch_url(
    binary: str,
    url: str,
    *,
    source_type: str,
    topic: str,
    source_label: str,
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
) -> tuple[str, str]:
    """Run `binary url` and append evidence if it produced anything useful.

    Returns ``(evidence_id, "")`` on success, or ``("", reason)`` on failure
    (timeout, non-zero exit, empty markdown). Never raises.
    """
    try:
        result = subprocess.run(
            [binary, url],
            check=False,
            capture_output=True,
            text=True,
            timeout=float(os.getenv("FOOTBALL_OSINT_LIGHTPANDA_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"{url}: {exc}"
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return "", f"{url}: {stderr[:160] or f'exit {result.returncode}'}"
    excerpt = report_module.compact_markdown(result.stdout)
    if not excerpt:
        return "", f"{url}: empty markdown"
    evidence_id = append_evidence(
        evidence,
        source=source_label,
        source_type=source_type,
        claim=report_module.claim_from_markdown(request, excerpt, source_label),
        topic=topic,
        side="neutral",
        confidence=0.52,
        raw_excerpt=excerpt,
        url=url,
    )
    return evidence_id, ""

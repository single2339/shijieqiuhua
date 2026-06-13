"""URL safety helpers (W2.2 — extracted from pipeline.py).

Single owner of:
- the host allowlist (default win007.com + FOOTBALL_OSINT_URL_ALLOWLIST env)
- DNS-resolution-based private/loopback/link-local rejection
- the candidate URL → safe URL filter

These were originally inlined in pipeline.py; W2.2 hoists them so future
adapters in adapters/* can import a single canonical SRF guard.

PRD trace: §5.6 SRF mitigation; security review fixes (commit history).
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

DEFAULT_HOST_ALLOWLIST = (
    "win007.com",
    "m.win007.com",
    "live.win007.com",
)


def host_allowlist() -> tuple[str, ...]:
    extra = os.getenv("FOOTBALL_OSINT_URL_ALLOWLIST", "")
    extras = tuple(host.strip().lower() for host in extra.split(",") if host.strip())
    return DEFAULT_HOST_ALLOWLIST + extras


def is_host_allowed(host: str, allowlist: tuple[str, ...]) -> bool:
    host = host.lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowlist)


def is_safe_public_host(host: str) -> bool:
    """True iff host resolves entirely to public IP space.

    Set FOOTBALL_OSINT_SKIP_DNS_CHECK=1 in tests to bypass DNS — the allowlist
    layer alone is the real defense; DNS is belt-and-suspenders for the case
    where an allowlisted hostname is later repointed at an internal address.
    """
    if not host:
        return False
    if os.getenv("FOOTBALL_OSINT_SKIP_DNS_CHECK", "").strip() == "1":
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def valid_urls(candidates: list[str]) -> list[str]:
    """Return the subset of candidate URLs safe to fetch.

    Filters: scheme ∈ {http, https}, host on allowlist, host resolves to
    public address. Preserves input order; deduplicates.
    """
    urls: list[str] = []
    seen: set[str] = set()
    allowlist = host_allowlist()
    for url in candidates:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        if url in seen:
            continue
        host = parsed.hostname
        if not is_host_allowed(host, allowlist):
            continue
        if not is_safe_public_host(host):
            continue
        urls.append(url)
        seen.add(url)
    return urls


_URL_RE = re.compile(r"https?://[^\s，。；、）)\]}>\"']+")


def extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;:") for m in _URL_RE.finditer(text)]

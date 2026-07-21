"""Bounded public-web capture for OSINT verification artefacts.

This module deliberately returns extracted metadata rather than raw HTML.  Its
callers must treat the returned text as untrusted evidence, never as model
instructions.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from collections.abc import Callable
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_CAPTURE_BYTES = 512 * 1024
MAX_REDIRECTS = 3
_ALLOWED_PORTS = {80, 443}
_HEADERS = {
    "User-Agent": "osint-network-verifier/1.0 (+controlled-capture)",
    "Accept": "text/html,application/xhtml+xml",
}


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _resolve_host(hostname: str) -> list[str]:
    return list({entry[4][0] for entry in socket.getaddrinfo(hostname, None)})


def validate_public_url(
    value: str,
    *,
    resolver: Callable[[str], list[str]] | None = None,
) -> str:
    """Validate a capture URL before any connection is made.

    This rejects non-web protocols, credentialed URLs, private literal IPs and
    hostnames that resolve only to private/reserved addresses.
    """
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs may be captured")
    if parsed.username or parsed.password:
        raise ValueError("credentialed URLs may not be captured")
    if not parsed.hostname:
        raise ValueError("capture URL must include a hostname")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("capture URL has an invalid port") from exc
    if port is not None and port not in _ALLOWED_PORTS:
        raise ValueError("capture URL port is not allowed")

    host = parsed.hostname.rstrip(".").lower()
    try:
        if not _is_public_address(host):
            raise ValueError("capture URL resolves to a non-public address")
    except ValueError as exc:
        # A syntactically valid IP that failed the public-address check must
        # never fall through to hostname DNS resolution.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise exc

    lookup = resolver or _resolve_host
    try:
        addresses = lookup(host)
    except OSError as exc:
        raise ValueError("capture hostname could not be resolved") from exc
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise ValueError("capture URL resolves to a non-public address")
    return parsed.geturl()


def extract_page_metadata(html: str) -> dict[str, object]:
    """Extract a small, auditable metadata set while discarding executable DOM."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "template", "svg"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = ""
    description_tag = soup.find("meta", attrs={"name": lambda value: str(value).lower() == "description"})
    if description_tag:
        description = str(description_tag.get("content") or "").strip()
    text = " ".join(soup.stripped_strings)
    text = unescape(text)
    analytics_ids: list[str] = []
    for pattern in (r"\bG-[A-Z0-9]{4,}\b", r"\bUA-\d+-\d+\b", r"\bca-pub-\d+\b"):
        for match in re.findall(pattern, html, flags=re.I):
            value = str(match).upper() if match.lower().startswith("g-") else str(match)
            if value not in analytics_ids:
                analytics_ids.append(value)
    return {
        "title": title[:300],
        "description": description[:500],
        "text_excerpt": text[:4000],
        "analytics_ids": analytics_ids[:20],
    }


async def capture_public_page(url: str) -> dict[str, object]:
    """Capture a bounded, HTML-only public page and record its immutable hash."""
    current = validate_public_url(url)
    redirects = 0
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, headers=_HEADERS) as client:
        while True:
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location or redirects >= MAX_REDIRECTS:
                        return {"url": url, "final_url": current, "status_code": response.status_code, "error": "redirect_not_allowed"}
                    current = validate_public_url(urljoin(current, location))
                    redirects += 1
                    continue
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type:
                    return {"url": url, "final_url": current, "status_code": response.status_code, "error": "unsupported_content_type"}
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_CAPTURE_BYTES:
                        return {"url": url, "final_url": current, "status_code": response.status_code, "error": "capture_too_large"}
                    chunks.append(chunk)
            body = b"".join(chunks)
            html = body.decode("utf-8", errors="replace")
            metadata = extract_page_metadata(html)
            return {
                "url": url,
                "final_url": current,
                "status_code": response.status_code,
                "content_sha256": hashlib.sha256(body).hexdigest(),
                "verification_status": "captured",
                **metadata,
            }

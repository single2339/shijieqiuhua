"""Dependency-free, passive image metadata extraction for OSINT verification."""

from __future__ import annotations

import hashlib
import json
import os
import struct
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.agents.intelligence.controlled_fetch import MAX_REDIRECTS, validate_public_url

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REVERSE_SEARCH_RESPONSE_BYTES = 1024 * 1024

_SOF_MARKERS = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
_EXIF_TAGS = {
    0x010F: "Make",
    0x0110: "Model",
    0x0132: "DateTime",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x0131: "Software",
}


def extract_image_metadata(data: bytes) -> dict[str, Any]:
    """Return format, dimensions, a content hash and selected Exif fields.

    Metadata can be forged, so callers must present it as a verification lead,
    not as location or identity proof.
    """
    result: dict[str, Any] = {"content_sha256": hashlib.sha256(data).hexdigest(), "exif": {}}
    if data.startswith(b"\xff\xd8"):
        result.update(_jpeg_metadata(data))
    elif data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        result.update({"format": "PNG", "width": int.from_bytes(data[16:20], "big"), "height": int.from_bytes(data[20:24], "big")})
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        result.update(_webp_metadata(data))
    else:
        result.update({"format": "unknown", "width": 0, "height": 0})
    return result


async def capture_public_image(url: str) -> dict[str, Any]:
    """Download a bounded public image for metadata extraction only."""
    current = validate_public_url(url)
    redirects = 0
    headers = {"User-Agent": "osint-network-verifier/1.0 (+image-metadata)"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False, headers=headers) as client:
        while True:
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location or redirects >= MAX_REDIRECTS:
                        return {"url": url, "final_url": current, "status_code": response.status_code, "error": "redirect_not_allowed"}
                    from urllib.parse import urljoin
                    current = validate_public_url(urljoin(current, location))
                    redirects += 1
                    continue
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"):
                    return {"url": url, "final_url": current, "status_code": response.status_code, "error": "unsupported_content_type"}
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        return {"url": url, "final_url": current, "status_code": response.status_code, "error": "capture_too_large"}
                    chunks.append(chunk)
            metadata = extract_image_metadata(b"".join(chunks))
            return {"url": url, "final_url": current, "status_code": response.status_code, **metadata}


async def reverse_image_search(image_url: str) -> dict[str, Any] | None:
    """Query an explicitly configured reverse-image service using only its URL.

    The deployment must opt in with ``REVERSE_IMAGE_SEARCH_URL``.  The image is
    never uploaded by this adapter; the configured service receives a validated
    public image URL and returns only compact match metadata for review.
    """
    endpoint = os.getenv("REVERSE_IMAGE_SEARCH_URL", "").strip()
    if not endpoint:
        return None
    try:
        public_image_url = validate_public_url(image_url)
        public_endpoint = validate_public_url(endpoint)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            async with client.stream("POST", public_endpoint, json={"image_url": public_image_url}) as response:
                if response.status_code >= 400:
                    return {"error": "reverse_image_search_failed", "status_code": response.status_code}
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_REVERSE_SEARCH_RESPONSE_BYTES:
                        return {"error": "reverse_image_search_response_too_large"}
                    chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
    except (ValueError, json.JSONDecodeError, httpx.HTTPError) as exc:
        return {"error": "reverse_image_search_failed", "detail": str(exc)[:200]}

    raw_results = payload.get("results", payload.get("matches", [])) if isinstance(payload, dict) else []
    results = []
    for match in raw_results[:20] if isinstance(raw_results, list) else []:
        if not isinstance(match, dict):
            continue
        result_url = str(match.get("url") or match.get("source_url") or "")
        if result_url:
            try:
                result_url = validate_public_url(result_url)
            except ValueError:
                result_url = ""
        results.append({
            "title": str(match.get("title") or "未命名匹配")[:300],
            "url": result_url,
            "source": str(match.get("source") or "")[:120],
        })
    provider = str(payload.get("provider") or urlparse(public_endpoint).hostname or "configured-reverse-search") if isinstance(payload, dict) else "configured-reverse-search"
    return {"provider": provider, "results": results}


def _jpeg_metadata(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"format": "JPEG", "width": 0, "height": 0, "exif": {}}
    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        segment = data[index + 2:index + length]
        if marker in _SOF_MARKERS and len(segment) >= 5:
            result["height"] = int.from_bytes(segment[1:3], "big")
            result["width"] = int.from_bytes(segment[3:5], "big")
        elif marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            result["exif"] = _parse_exif(segment[6:])
        index += length
    return result


def _webp_metadata(data: bytes) -> dict[str, Any]:
    if len(data) >= 30 and data[12:16] == b"VP8X":
        return {
            "format": "WEBP",
            "width": 1 + int.from_bytes(data[24:27], "little"),
            "height": 1 + int.from_bytes(data[27:30], "little"),
            "exif": {},
        }
    return {"format": "WEBP", "width": 0, "height": 0, "exif": {}}


def _parse_exif(data: bytes) -> dict[str, str]:
    if len(data) < 8 or data[:2] not in {b"II", b"MM"}:
        return {}
    endian = "<" if data[:2] == b"II" else ">"
    try:
        if struct.unpack_from(f"{endian}H", data, 2)[0] != 42:
            return {}
        offset = struct.unpack_from(f"{endian}I", data, 4)[0]
        if offset + 2 > len(data):
            return {}
        count = struct.unpack_from(f"{endian}H", data, offset)[0]
    except struct.error:
        return {}
    result: dict[str, str] = {}
    for index in range(count):
        entry = offset + 2 + index * 12
        if entry + 12 > len(data):
            break
        try:
            tag, field_type, value_count, value_offset = struct.unpack_from(f"{endian}HHII", data, entry)
        except struct.error:
            continue
        name = _EXIF_TAGS.get(tag)
        if name and field_type == 2 and value_count > 0 and value_offset < len(data):
            raw = data[value_offset:min(value_offset + value_count, len(data))]
            result[name] = raw.rstrip(b"\x00").decode("utf-8", errors="replace")[:200]
    return result

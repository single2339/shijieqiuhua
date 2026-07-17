"""Python MCP Server — exposes 15 tools bridging the OSINT data layer to OpenCode agents.

Run:  python backend/mcp_server.py
Defaults to http://0.0.0.0:8001/mcp (streamable HTTP transport).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.agents.intelligence._bayesian import assess_document_quality
from backend.bronze_reader import scan_bronze, scan_bronze_async
from backend.llm_config import get_llm_client, get_plain_http_client
from backend.models import IntelLayer
from backend.processors.classifier import classify
from backend.processors.location import extract_location, extract_location_with_fallback
from backend.processors.analysis import (
    compute_timeline,
    extract_entity_graph,
    compute_corroboration,
    detect_anomalies,
    compute_risk_heatmap,
    analyze_gaps,
)

BING_API_KEY = os.getenv("BING_API_KEY", "")
BRONZE_STORAGE = os.getenv("BRONZE_STORAGE", str(ROOT / "bronze_storage"))

mcp = FastMCP(
    "osint-network",
    instructions="OSINT Network — intelligence data layer for multi-agent systems",
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_doc_dict(doc) -> dict:
    """Convert a BronzeDocument to a JSON-safe dict."""
    return {
        "id": doc.raw_document_id,
        "text": doc.text[:500],
        "source_system": doc.source_system,
        "captured_at": doc.captured_at,
        "url": doc.source_url,
        "channel": doc.channel,
    }


# ═══════════════════════════════════════════════════════════════
# Tool 1 — search_intel
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def search_intel(
    query: str,
    max_results: int = 20,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """Search the bronze intelligence database by keyword.

    Args:
        query: Search keywords (space-separated). Matches against title + first 300 chars.
        max_results: Maximum results to return (default 20).
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).
    """
    query = query.strip()[:1000]
    max_results = min(max(int(max_results), 1), 100)
    if not query:
        return []
    docs = await scan_bronze_async(BRONZE_STORAGE)
    q_tokens = set(query.lower().split())
    seen: set[str] = set()
    scored: list[tuple[int, dict]] = []

    for doc in docs:
        text = doc.text
        if not text:
            continue
        body_hash = hashlib.md5(text.encode()).hexdigest()
        if body_hash in seen:
            continue
        seen.add(body_hash)

        captured = doc.captured_at[:10] if doc.captured_at else ""
        if start_date and captured < start_date:
            continue
        if end_date and captured > end_date:
            continue

        ext = doc.extensions or {}
        title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]
        search_text = (title + " " + text[:300]).lower()
        score = sum(1 for t in q_tokens if t in search_text) if q_tokens else 0

        scored.append((score, {
            "title": title.split("\n")[0][:120],
            "source": doc.source_system,
            "date": captured,
            "content_snippet": text[:300],
            "url": doc.source_url,
        }))

    scored.sort(key=lambda x: -x[0])
    if q_tokens:
        scored = [(score, item) for score, item in scored if score > 0]
    return [item for _, item in scored[:max_results]]


# ═══════════════════════════════════════════════════════════════
# Tool 2 — assess_document_quality
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def assess_document_quality_tool(text: str, source_system: str = "") -> dict:
    """Assess source and document quality without claiming hypothesis truth.

    Args:
        text: The intelligence text to evaluate.
        source_system: Source identifier for credibility classification.
    """
    return assess_document_quality(text, source_system)


# ═══════════════════════════════════════════════════════════════
# Tool 3 — web_search_bing
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def web_search_bing(query: str, top_n: int = 8) -> list[dict]:
    """Search Bing (China market) for web results.

    Args:
        query: Search query string.
        top_n: Number of results to return (default 8).
    """
    top_n = min(max(int(top_n), 1), 20)
    query = query.strip()[:1000]
    if not BING_API_KEY:
        return []
    results: list[dict] = []
    try:
        async with get_plain_http_client(timeout=20.0) as client:
            r = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": min(top_n, 20), "mkt": "zh-CN"},
                headers={"Ocp-Apim-Subscription-Key": BING_API_KEY},
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("webPages", {}).get("value", []):
                    results.append({
                        "title": item.get("name", ""),
                        "snippet": (item.get("snippet", "") or "")[:300],
                        "url": item.get("url", ""),
                    })
    except Exception:
        pass
    return results


# ═══════════════════════════════════════════════════════════════
# Tool 4 — classify_intel
# ═══════════════════════════════════════════════════════════════

_LAYER_NAMES = {
    "nature": "自然生态", "economy": "经济产业", "finance": "金融",
    "politics": "政治外交", "military": "军事", "aviation": "民航交通",
    "technology": "科技", "society": "社会民生", "energy": "能源资源",
    "agriculture": "农业食品", "health": "公共卫生", "cyber": "网络空间",
}


@mcp.tool()
async def classify_intel(text: str) -> dict:
    """Classify intelligence text into one of 12 layers (keyword-based fallback).

    Args:
        text: The text to classify.
    """
    layer = classify(text)
    return {
        "layer": layer.value,
        "layer_name": _LAYER_NAMES.get(layer.value, layer.value),
    }


# ═══════════════════════════════════════════════════════════════
# Tool 5 — translate_text
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def translate_text(text: str) -> str:
    """Translate text to Chinese (via LLM, falls back to MyMemory).

    Args:
        text: The text to translate.
    """
    from src.processor.translation import translate_text as _translate
    result = await _translate(text)
    return result or text


# ═══════════════════════════════════════════════════════════════
# Tool 6 — summarize_text
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def summarize_text(text: str, max_length: int = 200) -> str:
    """Summarize a piece of text via LLM.

    Args:
        text: The text to summarize.
        max_length: Maximum summary length in characters.
    """
    from src.processor.summarizer import _summarize_with_llm
    result = await _summarize_with_llm(text[:3000])
    return result or text[:max_length]


# ═══════════════════════════════════════════════════════════════
# Tool 7 — extract_location
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def extract_location_tool(text: str) -> dict:
    """Extract geographic location (country, city, coordinates) from text.

    Args:
        text: The text to extract location from.
    """
    result = extract_location(text)
    return {
        "location_name": result.get("location_name", ""),
        "country": result.get("country", ""),
        "lat": result.get("lat", 0.0),
        "lng": result.get("lng", 0.0),
    }


# ═══════════════════════════════════════════════════════════════
# Tool 8 — get_timeline
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_timeline(
    layer: str = "",
    country: str = "",
    days: int = 30,
) -> dict:
    """Get intelligence timeline with date-grouped event counts.

    Args:
        layer: Optional layer filter (e.g. 'military', 'politics').
        country: Optional country filter.
        days: Number of days to look back (default 30).
    """
    from backend.main import _build_items_async
    items = await _build_items_async()
    if layer:
        items = [it for it in items if it.layer.value == layer]
    if country:
        items = [it for it in items if it.country == country]
    return compute_timeline(items)


# ═══════════════════════════════════════════════════════════════
# Tool 9 — get_entity_graph
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_entity_graph(
    layer: str = "",
    country: str = "",
) -> dict:
    """Extract entity co-occurrence graph from intelligence items.

    Args:
        layer: Optional layer filter.
        country: Optional country filter.
    """
    from backend.main import _build_items_async
    items = await _build_items_async()
    if layer:
        items = [it for it in items if it.layer.value == layer]
    if country:
        items = [it for it in items if it.country == country]
    return extract_entity_graph(items)


# ═══════════════════════════════════════════════════════════════
# Tool 10 — get_corroboration
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_corroboration() -> dict:
    """Compute cross-source corroboration matrix showing source agreement."""
    from backend.main import _build_items_async
    items = await _build_items_async()
    return compute_corroboration(items)


# ═══════════════════════════════════════════════════════════════
# Tool 11 — get_anomalies
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_anomalies() -> dict:
    """Detect statistical anomalies in intelligence volume by layer and date."""
    from backend.main import _build_items_async
    items = await _build_items_async()
    return detect_anomalies(items)


# ═══════════════════════════════════════════════════════════════
# Tool 12 — get_risk_heatmap
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_risk_heatmap() -> dict:
    """Compute regional risk heatmap from intelligence density and confidence."""
    from backend.main import _build_items_async
    items = await _build_items_async()
    return compute_risk_heatmap(items)


# ═══════════════════════════════════════════════════════════════
# Tool 13 — get_gap_analysis
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_gap_analysis() -> dict:
    """Analyze intelligence coverage gaps (topic, region, time, cross-source)."""
    from backend.main import _build_items_async
    items = await _build_items_async()
    return analyze_gaps(items)


# ═══════════════════════════════════════════════════════════════
# Tool 14 — trigger_collection
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def trigger_collection(hours: int = 2) -> dict:
    """Trigger an intelligence collection run.

    Args:
        hours: Hours of data to collect (default 2).
    """
    hours = min(max(int(hours), 1), 168)
    try:
        from backend.collectors.horizon_bridge import run_horizon_collection
        await run_horizon_collection(hours=hours)
        return {"status": "completed", "hours": hours}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ═══════════════════════════════════════════════════════════════
# Tool 15 — get_skills
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def get_skills() -> list[dict]:
    """List all available intelligence analysis skills with descriptions."""
    skills_dir = ROOT / "backend" / "config" / "skills"
    result: list[dict] = []
    if skills_dir.exists():
        for yf in sorted(skills_dir.glob("*.yaml")):
            try:
                import yaml
                data = yaml.safe_load(yf.read_text(encoding="utf-8"))
                result.append({
                    "name": data.get("name", yf.stem),
                    "description": data.get("description", ""),
                    "agent_types": data.get("agent_types", []),
                })
            except Exception:
                result.append({"name": yf.stem, "description": "", "agent_types": []})
    return result


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════


class _MCPAuthMiddleware:
    """Minimal bearer-token guard for the streamable HTTP MCP transport."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        provided = headers.get(b"authorization", b"")
        if not provided.startswith(b"Bearer "):
            await self._reject(send)
            return
        candidate = provided[7:].decode("utf-8", "ignore").strip()
        if not hmac.compare_digest(candidate, self.token):
            await self._reject(send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send):
        body = b'{"detail":"MCP authentication required"}'
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})

def main():
    import uvicorn
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MCP_AUTH_TOKEN must be configured before starting the HTTP MCP server")
    uvicorn.run(
        _MCPAuthMiddleware(mcp.streamable_http_app(), token),
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8001")),
        log_level="info",
    )


if __name__ == "__main__":
    main()

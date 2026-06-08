from __future__ import annotations

import hashlib
import json
import os

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

# ── load .env from project root ──
_dotenv = Path(__file__).resolve().parent.parent / ".env"
if _dotenv.exists():
    import dotenv
    dotenv.load_dotenv(_dotenv)

import httpx
from fastapi import Depends, FastAPI, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from backend.bronze_reader import scan_bronze, scan_bronze_async
from backend.football import FootballAnalysisRequest, FootballAnalysisResponse, analyze_football_match
from backend.indexer import Indexer
from backend.models import (
    AnalysisInterpretRequest,
    AnalysisInterpretResponse,
    AnomalyEvent,
    AnomalyResult,
    AskRequest,
    AskResponse,
    BayesianEvidence,
    BayesianIntelItem,
    CorroborationResult,
    CoverageGap,
    DashboardData,
    DashboardStats,
    EntityEdge,
    EntityGraphResult,
    EntityNode,
    GapAnalysisResult,
    GeoPoint,
    IntelItem,
    IntelLayer,
    LayerSummary,
    RegionRisk,
    ReportRequest,
    ReportSection,
    RiskHeatmapResult,
    SituationReport,
    SourceInfo,
    SourceMatrix,
    SourcePairOverlap,
    SuperAnalysisRequest,
    SuperAnalysisResponse,
    TimelinePoint,
    TimelineResult,
    TrendPoint,
    Verdict,
)
from backend.processors.classifier import classify
from backend.processors.llm_classifier import classify_with_llm
from backend.processors.location import extract_location, extract_location_with_fallback
from backend.seed_data import main as reseed
from backend.merger import build_merge_index, load_merge_index

RESEED_INTERVAL = 30  # seconds
HORIZON_INTERVAL = 15 * 60  # 15 minutes between Horizon scraper runs
MERGE_HOUR_UTC = 3  # daily merge at 03:00 UTC (Beijing 11:00)
COLLECTOR_MODE = os.environ.get("OSINT_COLLECTOR", "horizon")  # "demo" or "horizon"
STATS_DEFAULT_DAYS = int(os.environ.get("STATS_DEFAULT_DAYS", "14"))
OSINT_ROLE_VALUES = {"api", "worker", "all"}


def osint_role() -> str:
    """Return this process role.

    api: serve HTTP only
    worker: run background jobs only
    all: legacy single-process mode
    """
    role = os.environ.get("OSINT_ROLE", "api").strip().lower()
    if role not in OSINT_ROLE_VALUES:
        log.warning("Unknown OSINT_ROLE=%s; falling back to api", role)
        return "api"
    return role


def should_start_background_workers() -> bool:
    return osint_role() in {"worker", "all"}


def should_prewarm_api_cache() -> bool:
    return osint_role() in {"api", "all"}


def resolve_stats_window(start_date: str, end_date: str) -> tuple[str, str]:
    if start_date or end_date:
        return start_date, end_date
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(STATS_DEFAULT_DAYS, 1) - 1)
    return start.isoformat(), end.isoformat()

# ── Agent system ──
from backend.agents.config import is_agent_mode
from backend.agents.registry import AgentRegistry
from backend.agents.base import AgentCallbacks, AgentEvent
from backend.agents.models import AgentTask as AgentTaskModel
from backend.agents.intelligence._bayesian import compute_bayesian
from backend.websocket.manager import ws_manager
from backend.auth.routes import router as auth_router, get_current_user
from backend.auth.admin_routes import router as admin_router
from backend.auth.tracking import record_activity

# Import agent modules so they self-register via AgentRegistry
import backend.agents.collectors.api_collectors  # noqa: F401
import backend.agents.collectors.rss_collector  # noqa: F401
import backend.agents.collectors.social_collectors  # noqa: F401
import backend.agents.processors.bayesian_scoring  # noqa: F401
import backend.agents.processors.pipeline  # noqa: F401
import backend.agents.processors.classification  # noqa: F401
import backend.agents.processors.location_extraction  # noqa: F401
import backend.agents.processors.summarization  # noqa: F401
import backend.agents.processors.translation  # noqa: F401
import backend.agents.system.indexer  # noqa: F401
import backend.agents.system.merger  # noqa: F401
import backend.agents.system.orchestrator  # noqa: F401
import backend.agents.intelligence.interpretation  # noqa: F401
import backend.agents.intelligence.qa_analyst  # noqa: F401
import backend.agents.intelligence.report_writer  # noqa: F401
import backend.agents.intelligence.super_analyst  # noqa: F401
import backend.agents.analysis.anomaly_detector  # noqa: F401
import backend.agents.analysis.corroboration  # noqa: F401
import backend.agents.analysis.entity_graph  # noqa: F401
import backend.agents.analysis.gap_analyzer  # noqa: F401
import backend.agents.analysis.risk_heatmap  # noqa: F401
import backend.agents.analysis.timeline  # noqa: F401


def _ws_callbacks(channel: str = "collection") -> AgentCallbacks:
    """Build AgentCallbacks that broadcast events to WebSocket clients."""
    async def on_event(event: AgentEvent):
        await ws_manager.broadcast(channel, event.event_type, {
            "agent_id": event.agent_id,
            "message": event.message,
            "data": event.data,
        })

    async def on_status_change(agent_id: str, old, new):
        await ws_manager.broadcast(channel, "status_change", {
            "agent_id": agent_id,
            "old_status": old.value,
            "new_status": new.value,
        })

    async def on_error(agent_id: str, error: str):
        await ws_manager.broadcast(channel, "error", {
            "agent_id": agent_id,
            "error": error,
        })

    return AgentCallbacks(
        on_event=on_event,
        on_status_change=on_status_change,
        on_error=on_error,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    role = osint_role()

    # Seed demo data once so the dashboard has something on first load
    if not any(STORAGE.rglob("*.json")):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: reseed(clear=True))

    # Initialize indexer and build index if needed
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _init_indexer)

    if should_prewarm_api_cache():
        # Pre-warm dashboard cache for today's date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        def _build_safe():
            try:
                _build_items(start_date=today, end_date=today)
            except Exception:
                log.exception("Failed to pre-warm dashboard cache")
        loop.run_in_executor(None, _build_safe)

    _reindex_task: asyncio.Task | None = None
    _agent_orch = None

    if should_start_background_workers():
        log.info("Starting OSINT background workers in %s role", role)

        # Periodic reindex to pick up newly collected files
        async def _reindex_loop():
            while True:
                await asyncio.sleep(300)  # every 5 minutes
                try:
                    n = await loop.run_in_executor(None, _get_indexer().incremental_update)
                    if n:
                        log.info("Periodic reindex: %d new docs", n)
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("Periodic reindex failed")

        _reindex_task = asyncio.create_task(_reindex_loop())

        # ── Agent orchestrator ──
        from backend.agents.system.orchestrator import OrchestratorAgent
        _agent_orch = OrchestratorAgent(storage_root=STORAGE, callbacks=_ws_callbacks())
        await _agent_orch.start_collection_loop()
        await _agent_orch.start_merge_loop()

    try:
        yield
    finally:
        if _reindex_task is not None:
            _reindex_task.cancel()
            try:
                await _reindex_task
            except asyncio.CancelledError:
                pass
        if _agent_orch is not None:
            await _agent_orch.stop()
        if _indexer is not None:
            _indexer.close()


app = FastAPI(title="OSINT Network API", version="1.0.0", lifespan=lifespan)

_allowed_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request body size limit — reject oversized payloads early
_MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MB


@app.middleware("http")
async def body_size_limit_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "请求体过大"})
    return await call_next(request)


# ── Auth routes ──
app.include_router(auth_router, prefix="/api/auth")
app.include_router(admin_router, prefix="/api/admin")

# Cache-Control middleware — short TTL for live data, longer for analysis snapshots
_CACHE_RULES: dict[str, str] = {
    "/api/dashboard": "public, max-age=10",
    "/api/stats": "public, max-age=10",
    "/api/health": "no-cache",
    "/api/analysis/": "public, max-age=60",
}


@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        return response
    path = request.url.path
    for prefix, cc in _CACHE_RULES.items():
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            response.headers["Cache-Control"] = cc
            break
    return response

# ── Simple in-memory rate limiter ──
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120    # max requests per window per IP
_RATE_LIMIT_WRITE_MAX = 20  # stricter for POST endpoints

# ── Public API paths (no auth required) ──
_PUBLIC_PREFIXES = ("/api/health", "/api/auth/", "/api/admin/", "/api/dashboard", "/api/stats", "/api/football/")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if any(path == p or (p.endswith("/") and path.startswith(p)) for p in _PUBLIC_PREFIXES):
        return await call_next(request)

    from backend.auth import service
    token = request.cookies.get("osint_access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    payload = service.decode_token(token) if token else None

    if payload is None:
        # Access token missing or expired — try refresh token
        refresh_token = request.cookies.get("osint_refresh_token")
        if refresh_token:
            try:
                result = service.refresh_access_token(refresh_token)
                new_access = result["access_token"]
                new_refresh = result["refresh_token"]
                # Inject new access token so downstream Depends(get_current_user) can read it
                request._headers["authorization"] = f"Bearer {new_access}"
                response = await call_next(request)
                response.set_cookie(
                    "osint_access_token", new_access,
                    httponly=True, secure=False, samesite="lax",
                    max_age=3600, path="/",
                )
                response.set_cookie(
                    "osint_refresh_token", new_refresh,
                    httponly=True, secure=False, samesite="lax",
                    max_age=7 * 24 * 3600, path="/",
                )
                return response
            except ValueError:
                pass

        return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

    return await call_next(request)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    import time as _time
    client_ip = request.client.host if request.client else "unknown"
    now = _time.time()
    window = _rate_limit_store.get(client_ip, [])
    window = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    max_req = _RATE_LIMIT_WRITE_MAX if request.method in ("POST", "PUT", "DELETE") else _RATE_LIMIT_MAX
    if len(window) >= max_req:
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    window.append(now)
    _rate_limit_store[client_ip] = window
    if len(_rate_limit_store) > 4096:
        oldest = sorted(_rate_limit_store.keys(), key=lambda k: min(_rate_limit_store[k] or [0]))[:1024]
        for k in oldest:
            del _rate_limit_store[k]
    return await call_next(request)


STORAGE = Path(__file__).resolve().parent.parent / "bronze_storage"
_indexer: Indexer | None = None


def _get_indexer() -> Indexer:
    global _indexer
    if _indexer is None:
        _indexer = Indexer(STORAGE)
    return _indexer


def _init_indexer() -> None:
    """Build or verify the SQLite index. Runs synchronously in thread pool."""
    idx = _get_indexer()
    count = idx.count()
    if not should_start_background_workers():
        if count == 0:
            logging.getLogger("uvicorn").warning("Indexer is empty; start osint-worker.service to build it")
        return
    if count == 0:
        t0 = __import__("time").time()
        n = idx.build_index()
        elapsed = __import__("time").time() - t0
        logging.getLogger("uvicorn").info("Indexer built: %d docs in %.1fs", n, elapsed)
    else:
        n = idx.incremental_update()
        if n:
            logging.getLogger("uvicorn").info("Indexer incremental: %d new docs", n)

# ── Dashboard cache to avoid recomputing on every poll ──
_dashboard_cache: dict[str, tuple[float, object]] = {}
DASHBOARD_CACHE_TTL = 30  # seconds
DASHBOARD_CACHE_MAX_SIZE = 256  # prevent unbounded growth


def _evict_expired_cache() -> None:
    """Remove expired entries from the dashboard cache."""
    import time as _time
    now = _time.time()
    expired = [k for k, (ts, _) in _dashboard_cache.items() if now - ts >= DASHBOARD_CACHE_TTL]
    for k in expired:
        del _dashboard_cache[k]


def _cache_set(key: str, value: object) -> None:
    """Set cache entry with eviction of expired entries and LRU-like cap."""
    import time as _time
    _evict_expired_cache()
    if len(_dashboard_cache) >= DASHBOARD_CACHE_MAX_SIZE:
        oldest = min(_dashboard_cache.items(), key=lambda x: x[1][0])
        del _dashboard_cache[oldest[0]]
    _dashboard_cache[key] = (_time.time(), value)


def _resolve_source_name(doc) -> str:
    """Get the best source identifier for location lookup.

    Uses feed_name from horizon metadata (the actual publication name)
    instead of the author name stored in source_system.
    """
    ext = getattr(doc, "extensions", {}) or {}
    if isinstance(ext, dict):
        meta = ext.get("horizon_metadata", {})
        if isinstance(meta, dict) and meta.get("feed_name"):
            return meta["feed_name"]
    return doc.source_system


@app.get("/api/dashboard", response_model=DashboardData)
async def get_dashboard(start_date: str = "", end_date: str = "", date: str = "", page: int = 1, page_size: int = 100):
    import time as _time

    cache_key = f"{start_date}|{end_date}|{date}|{page}|{page_size}"
    cached = _dashboard_cache.get(cache_key)
    if cached:
        ts, data = cached
        if _time.time() - ts < DASHBOARD_CACHE_TTL:
            return data

    def _process() -> DashboardData:
        # When date is set, use it as both start and end for single-day view
        s_date = start_date
        e_date = end_date
        if date:
            s_date = date
            e_date = date
        all_items = _build_items(start_date=s_date, end_date=e_date)

        # Get available dates from SQLite index directly (fast)
        available_dates = _get_indexer().get_available_dates()

        # Build source_map and layer_counts from ALL items (aggregates are full)
        source_map: dict[str, dict] = {}
        now_ts = datetime.now(timezone.utc).isoformat()
        for item in all_items:
            for src_name in item.sources:
                if not src_name:
                    continue
                if src_name not in source_map:
                    seed = int.from_bytes(hashlib.md5(src_name.encode()).digest()[:4], "big")
                    cred = 0.5 + (seed / 0xFFFFFFFF) * 0.4
                    source_map[src_name] = {"credibility": round(cred, 2), "count": 0, "last": ""}
                source_map[src_name]["count"] += 1
                last = item.captured_at or now_ts
                if last > source_map[src_name]["last"]:
                    source_map[src_name]["last"] = last

        layer_counts: dict[IntelLayer, list[float]] = {l: [] for l in IntelLayer}
        for item in all_items:
            layer_counts[item.layer].append(item.confidence)

        layers = [
            LayerSummary(layer=layer, count=len(confs), avg_confidence=round(sum(confs) / len(confs), 3) if confs else 0.0)
            for layer, confs in layer_counts.items()
        ]

        sources = [
            SourceInfo(name=name, credibility=info["credibility"], document_count=info["count"], last_seen=info["last"])
            for name, info in sorted(source_map.items(), key=lambda x: x[1]["credibility"], reverse=True)
        ]

        # Paginate intel_items
        total = len(all_items)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = all_items[start:end]
        has_more = end < total

        return DashboardData(
            intel_items=paged_items,
            sources=sources,
            layers=layers,
            total_items=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
            available_dates=available_dates,
        )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _process)
    _cache_set(cache_key, result)
    return result


_health_count_cache: tuple[float, int] = (0.0, 0)


@app.get("/api/health")
async def health():
    import time as _time
    global _health_count_cache
    ts, count = _health_count_cache
    if _time.time() - ts < DASHBOARD_CACHE_TTL:
        return {"status": "ok", "bronze_docs": count}
    count = _get_indexer().count()
    _health_count_cache = (_time.time(), count)
    return {"status": "ok", "bronze_docs": count}


_collect_task: asyncio.Task | None = None

@app.post("/api/collect")
async def trigger_collect(hours: int = 48):
    """Run Horizon scrapers once in the background and return immediately."""
    global _collect_task

    if _collect_task and not _collect_task.done():
        return {"status": "running", "message": "采集任务正在进行中"}

    orch = AgentRegistry.create("orchestrator", callbacks=_ws_callbacks())
    task = AgentTaskModel(task_type="collect", params={"action": "collect", "hours": hours})
    _collect_task = asyncio.create_task(orch.run(task))
    return {"status": "started", "message": "采集任务已启动"}


@app.get("/api/collect/status")
async def collect_status():
    """Check the status of the background collection task."""
    global _collect_task
    if _collect_task is None:
        return {"status": "idle", "message": "暂无采集任务"}
    if _collect_task.done():
        exc = _collect_task.exception()
        if exc:
            log.exception("Background collection task failed")
            return {"status": "error", "message": "采集任务执行失败，请查看服务器日志"}
        result = _collect_task.result()
        return {"status": "completed", "results": result}
    return {"status": "running", "message": "采集中..."}


@app.post("/api/merge")
async def trigger_merge():
    """Manually trigger the daily content merge task."""
    _dashboard_cache.clear()
    result = await asyncio.get_running_loop().run_in_executor(
        None, lambda: build_merge_index(STORAGE)
    )
    return {"status": "ok", "groups": result.total_groups, "total_docs": result.total_docs}


@app.post("/api/reclassify")
async def trigger_reclassify(force: bool = Query(False)):
    """Re-classify all existing bronze documents using LLM.

    Reads every JSON file, runs LLM classification, and writes the
    layer back into extensions.horizon_metadata.layer. Documents that
    already have a stored layer are skipped unless force=true.
    """
    import time as _time

    idx = _get_indexer()
    docs = idx.get_all()

    # Build {raw_document_id: path} lookup from indexer
    conn = idx._get_conn()
    rows = conn.execute("SELECT raw_document_id, file_path FROM bronze_index").fetchall()
    id_to_path: dict[str, Path] = {r[0]: Path(r[1]) for r in rows if r[1]}

    total = len(docs)
    updated = 0
    skipped = 0
    failed = 0
    batch_size = 5

    sem = asyncio.Semaphore(3)

    async def _reclassify_one(doc) -> dict:
        """Reclassify a single document. Returns {"result": "updated"|"skipped"|"failed"}."""
        ext = doc.extensions or {}
        meta = ext.get("horizon_metadata", {}) if isinstance(ext, dict) else {}
        has_layer = isinstance(meta, dict) and meta.get("layer")
        has_location = isinstance(meta, dict) and meta.get("location_country")

        if has_layer and has_location and not force:
            return {"result": "skipped"}

        title = ""
        if isinstance(ext, dict):
            title = ext.get("horizon_title", "") or ext.get("summary", "") or ""

        async with sem:
            try:
                layer, country, city = await classify_with_llm(title, doc.text)
            except Exception:
                return {"result": "failed"}

        json_path = id_to_path.get(doc.raw_document_id)
        if json_path is None:
            return {"result": "failed"}

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            exts = data.get("extensions", {})
            if not isinstance(exts, dict):
                exts = {}
            h_meta = exts.get("horizon_metadata", {})
            if not isinstance(h_meta, dict):
                h_meta = {}
            h_meta["layer"] = layer.value
            if country:
                h_meta["location_country"] = country
            if city:
                h_meta["location_city"] = city
            exts["horizon_metadata"] = h_meta
            data["extensions"] = exts
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"result": "updated"}
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to update %s: %s", json_path, e)
            return {"result": "failed"}

    for i in range(0, total, batch_size):
        batch = docs[i:i + batch_size]
        results = await asyncio.gather(*[_reclassify_one(doc) for doc in batch])
        for r in results:
            if r["result"] == "updated":
                updated += 1
            elif r["result"] == "skipped":
                skipped += 1
            else:
                failed += 1
        if i + batch_size < total:
            await asyncio.sleep(0.1)

    _dashboard_cache.clear()
    return {
        "status": "ok",
        "total": total,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


@app.post("/api/reindex")
async def trigger_reindex():
    """Rebuild or incrementally update the SQLite index from bronze JSON files."""
    idx = _get_indexer()
    before = idx.count()
    new = idx.incremental_update()
    after = idx.count()
    _dashboard_cache.clear()
    return {
        "status": "ok",
        "before": before,
        "new": new,
        "after": after,
    }


# ═══════════════════════════════════════════════════════════════
# LLM helper — reusable DeepSeek call for Q&A and reports
# ═══════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════
# 1 — AI Analyst Q&A
# ═══════════════════════════════════════════════════════════════

@app.post("/api/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """AI尝识者问答 — 基于现有情报数据回答问题。"""
    agent = AgentRegistry.create("qa_analyst", indexer=_get_indexer())
    task = AgentTaskModel(task_type="qa", params={
        "question": req.question,
        "layer": req.layer,
        "start_date": req.start_date,
        "end_date": req.end_date,
    }, skills=req.skills)
    result = await agent.run(task)
    return AskResponse(
        answer=result.data.get("answer", "分析失败"),
        references=result.data.get("references", []),
    )


# ═══════════════════════════════════════════════════════════════
# 2 — Dashboard Stats & Visualizations
# ═══════════════════════════════════════════════════════════════


def _build_dashboard_stats_fast(start_date: str, end_date: str) -> DashboardStats:
    conn = _get_indexer()._get_conn()
    where: list[str] = ["1=1"]
    params: list[str] = []
    if start_date:
        where.append("captured_at >= ?")
        params.append(start_date)
    if end_date:
        where.append("captured_at <= ?")
        params.append(end_date + "Z")

    rows = conn.execute(
        f"""
        SELECT captured_at, source_system, layer, country, title
        FROM bronze_index
        WHERE {' AND '.join(where)}
        ORDER BY captured_at DESC
        """,
        params,
    ).fetchall()

    layer_counts: dict[IntelLayer, int] = {layer: 0 for layer in IntelLayer}
    date_counts: dict[str, int] = {}
    source_layers: dict[str, dict[str, int]] = {}
    geo_dist: dict[str, int] = {}
    word_counts: dict[str, int] = {}
    stopwords = {
        "的", "了", "在", "是", "和", "与", "及", "或", "但", "这", "那",
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "is",
        "are", "with", "from", "by",
    }

    import re as _re

    for row in rows:
        layer_value = row["layer"] or ""
        if layer_value in IntelLayer._value2member_map_:
            layer = IntelLayer(layer_value)
            layer_counts[layer] += 1

        d = (row["captured_at"] or "")[:10]
        if d:
            date_counts[d] = date_counts.get(d, 0) + 1

        source = row["source_system"] or "unknown"
        if source not in source_layers:
            source_layers[source] = {}
        if layer_value:
            source_layers[source][layer_value] = source_layers[source].get(layer_value, 0) + 1

        country = row["country"] or ""
        if country:
            geo_dist[country] = geo_dist.get(country, 0) + 1

        for word in _re.findall(r"[一-鿿\w]+", (row["title"] or "").lower()):
            if word not in stopwords and len(word) > 1:
                word_counts[word] = word_counts.get(word, 0) + 1

    by_layer = [
        LayerSummary(layer=layer, count=count, avg_confidence=0.55 if count else 0.0)
        for layer, count in layer_counts.items()
    ]
    source_matrix = [
        SourceMatrix(
            name=name,
            credibility=0.5 + (int.from_bytes(hashlib.md5(name.encode()).digest()[:4], "big") / 0xFFFFFFFF) * 0.4,
            document_count=sum(dist.values()),
            layer_distribution=dist,
        )
        for name, dist in sorted(source_layers.items(), key=lambda x: sum(x[1].values()), reverse=True)[:30]
    ]

    return DashboardStats(
        total_items=len(rows),
        total_sources=len(source_matrix),
        by_layer=by_layer,
        daily_trend=[TrendPoint(date=d, count=c) for d, c in sorted(date_counts.items())],
        source_matrix=source_matrix,
        geo_distribution=[{"country": c, "count": n} for c, n in sorted(geo_dist.items(), key=lambda x: -x[1])[:20]],
        top_keywords=sorted([{"word": w, "count": c} for w, c in word_counts.items()], key=lambda x: -x["count"])[:30],
    )


@app.get("/api/stats", response_model=DashboardStats)
async def dashboard_stats(start_date: str = "", end_date: str = ""):
    """Aggregated statistics for charts and visualizations."""
    import time as _time

    start_date, end_date = resolve_stats_window(start_date, end_date)
    cache_key = f"stats|{start_date}|{end_date}"
    cached = _dashboard_cache.get(cache_key)
    if cached:
        ts, data = cached
        if _time.time() - ts < DASHBOARD_CACHE_TTL:
            return data

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: _build_dashboard_stats_fast(start_date, end_date))
    _cache_set(cache_key, result)
    return result


@app.post("/api/football/analyze", response_model=FootballAnalysisResponse)
async def football_analyze(request: FootballAnalysisRequest):
    return analyze_football_match(request)


# ═══════════════════════════════════════════════════════════════
# 3 — Auto Situation Report
# ═══════════════════════════════════════════════════════════════

@app.post("/api/report", response_model=SituationReport)
async def generate_report(req: ReportRequest):
    """生成指定主题/地区的中文情报态势简报。"""
    agent = AgentRegistry.create("report_writer", indexer=_get_indexer())
    task = AgentTaskModel(task_type="report", params={
        "topic": req.topic,
        "country": req.country,
        "layer": req.layer,
        "days": req.days,
    }, skills=req.skills)
    result = await agent.run(task)
    data = result.data
    sections = [ReportSection(**s) for s in data.get("sections", [])]
    return SituationReport(
        title=data.get("title", "态势简报"),
        summary=data.get("summary", ""),
        sections=sections,
        item_count=data.get("item_count", 0),
        source_count=data.get("source_count", 0),
    )


@app.get("/api/collect/usgs")
async def collect_usgs():
    """Fetch latest USGS earthquake data (past 7 days, M2.5+)."""
    agent = AgentRegistry.create("usgs_collector")
    task = AgentTaskModel(task_type="collect")
    result = await agent.run(task)
    return result.data

@app.get("/api/collect/cisa")
async def collect_cisa():
    """Fetch latest CISA known exploited vulnerabilities."""
    agent = AgentRegistry.create("cisa_collector")
    task = AgentTaskModel(task_type="collect")
    result = await agent.run(task)
    return result.data

@app.get("/api/collect/opensky")
async def collect_opensky():
    """Fetch flight tracking stats from OpenSky Network."""
    agent = AgentRegistry.create("opensky_collector")
    task = AgentTaskModel(task_type="collect")
    result = await agent.run(task)
    return result.data

# ═══════════════════════════════════════════════════════════════
# Shared helper — build IntelItems from bronze docs
# ═══════════════════════════════════════════════════════════════

def _get_layer(doc) -> IntelLayer:
    ext = getattr(doc, "extensions", {}) or {}
    if isinstance(ext, dict):
        meta = ext.get("horizon_metadata", {})
        if isinstance(meta, dict) and meta.get("layer"):
            try:
                return IntelLayer(meta["layer"])
            except ValueError:
                pass
    return classify(doc.text)


def _build_items(
    start_date: str = "",
    end_date: str = "",
    layer_filter: str = "",
    country_filter: str = "",
    limit: int = 0,
) -> list[IntelItem]:
    """Scan bronze storage, deduplicate, classify, extract location, compute Bayesian.

    When a merge index exists, items are built from merged groups with
    multi-source ``sources`` lists. Otherwise falls back to 1:1 doc→item.
    """
    docs = _get_indexer().get_all()
    items: list[IntelItem] = []

    if not docs:
        return items

    # Try loading merge index for multi-source grouping
    merge_index = load_merge_index(STORAGE)
    use_merge = merge_index is not None and merge_index.groups

    def _make_item(
        text: str,
        doc: BronzeDocument,
        sources: list[str],
        item_id: str,
        captured_at: str,
        url: str,
    ) -> IntelItem | None:
        """Build a single IntelItem from a document + source list."""
        ext = doc.extensions or {}

        # Apply date filter early — before expensive operations
        captured = captured_at[:10] if captured_at else ""
        if start_date and captured < start_date:
            return None
        if end_date and captured > end_date:
            return None

        title = ext.get("summary", text[:80]).split("\n")[0] or f"Intel from {sources[0] if sources else doc.source_system}"
        summary = ext.get("summary") or text[:300]

        country, loc_name, lat, lng = extract_location_with_fallback(text, _resolve_source_name(doc), doc)

        layer = _get_layer(doc)
        src_name = sources[0] if sources else (doc.source_system or doc.collector_id)

        if layer_filter and layer.value != layer_filter:
            return None
        if country_filter and country_filter.lower() not in (country or "").lower():
            return None

        confidence, trace, verdict, bayes_method, prior_quality, prior_class, evidence_items = \
            compute_bayesian(text, src_name)

        return IntelItem(
            id=item_id,
            title=title,
            summary=summary,
            layer=layer,
            location=GeoPoint(lat=lat, lng=lng),
            location_name=loc_name,
            country=country,
            confidence=confidence,
            verdict=verdict,
            bayesian_trace=trace,
            evidence_count=len(trace) - 1,
            sources=sources,
            source_system=src_name,
            captured_at=captured_at,
            url=url,
            bayesian_method=bayes_method,
            bayesian_prior_quality=prior_quality,
            bayesian_prior_class=prior_class,
            bayesian_evidence_items=[BayesianEvidence(**ei) for ei in evidence_items],
        )

    if use_merge:
        # Index docs by raw_document_id
        doc_by_id: dict[str, BronzeDocument] = {}
        for d in docs:
            did = d.raw_document_id
            if did and did not in doc_by_id:
                doc_by_id[did] = d

        # Build from merged groups
        seen_docs: set[str] = set()
        for group in merge_index.groups:
            primary = doc_by_id.get(group.primary_doc_id)
            if primary is None or not primary.text:
                continue
            for gd in group.documents:
                did = gd.get("doc_id", "")
                if did:
                    seen_docs.add(did)

            item = _make_item(
                text=primary.text,
                doc=primary,
                sources=group.sources,
                item_id=group.group_id,
                captured_at=primary.captured_at,
                url=group.source_url or primary.source_url,
            )
            if item:
                items.append(item)
                if limit and len(items) >= limit:
                    return items

        # Build from orphaned (non-merged) docs
        for d in docs:
            did = d.raw_document_id
            if not d.text or did in seen_docs:
                continue
            # Also dedup by body hash within orphaned pass
            # (the merge index handles group dedup; MD5 is belt-and-suspenders)
            item = _make_item(
                text=d.text,
                doc=d,
                sources=[_resolve_source_name(d)],
                item_id=did or f"doc-{len(items)}",
                captured_at=d.captured_at,
                url=d.source_url,
            )
            if item:
                items.append(item)
                if limit and len(items) >= limit:
                    return items
    else:
        # Fallback: original 1:1 behavior with MD5 dedup
        seen_content: set[str] = set()
        for i, d in enumerate(docs):
            text = d.text
            if not text:
                continue
            body_hash = hashlib.md5(text.encode()).hexdigest()
            if body_hash in seen_content:
                continue
            seen_content.add(body_hash)

            src_name = _resolve_source_name(d)
            item = _make_item(
                text=text,
                doc=d,
                sources=[src_name],
                item_id=d.raw_document_id or f"doc-{i}",
                captured_at=d.captured_at,
                url=d.source_url,
            )
            if item:
                items.append(item)
                if limit and len(items) >= limit:
                    break

    items.sort(key=lambda x: x.captured_at or "", reverse=True)
    return items


async def _build_items_async(
    start_date: str = "",
    end_date: str = "",
    layer_filter: str = "",
    country_filter: str = "",
    limit: int = 0,
) -> list[IntelItem]:
    """Async wrapper: runs _build_items in thread pool with 30s cache."""
    import time as _time
    cache_key = f"build|{start_date}|{end_date}|{layer_filter}|{country_filter}|{limit}"
    cached = _dashboard_cache.get(cache_key)
    if cached:
        ts, data = cached
        if _time.time() - ts < DASHBOARD_CACHE_TTL:
            return data
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: _build_items(start_date, end_date, layer_filter, country_filter, limit)
    )
    _cache_set(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════
# 5 — Intelligence Analysis Endpoints
# ═══════════════════════════════════════════════════════════════


@app.get("/api/analysis/timeline", response_model=TimelineResult)
async def analysis_timeline(start_date: str = "", end_date: str = "", layer: str = "", country: str = ""):
    items = await _build_items_async(start_date=start_date, end_date=end_date, layer_filter=layer, country_filter=country)
    agent = AgentRegistry.create("timeline")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return TimelineResult(**result.data)


@app.get("/api/analysis/entities", response_model=EntityGraphResult)
async def analysis_entities():
    items = await _build_items_async()
    agent = AgentRegistry.create("entity_graph")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return EntityGraphResult(**result.data)


@app.get("/api/analysis/corroboration", response_model=CorroborationResult)
async def analysis_corroboration():
    items = await _build_items_async()
    agent = AgentRegistry.create("corroboration")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return CorroborationResult(**result.data)


@app.get("/api/analysis/anomalies", response_model=AnomalyResult)
async def analysis_anomalies(start_date: str = "", end_date: str = ""):
    items = await _build_items_async(start_date=start_date, end_date=end_date)
    agent = AgentRegistry.create("anomaly_detector")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return AnomalyResult(**result.data)


@app.get("/api/analysis/risk-heatmap", response_model=RiskHeatmapResult)
async def analysis_risk_heatmap():
    items = await _build_items_async()
    agent = AgentRegistry.create("risk_heatmap")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return RiskHeatmapResult(**result.data)


@app.get("/api/analysis/gaps", response_model=GapAnalysisResult)
async def analysis_gaps():
    items = await _build_items_async()
    agent = AgentRegistry.create("gap_analyzer")
    task = AgentTaskModel(task_type="analysis", params={"items": items})
    result = await agent.run(task)
    return GapAnalysisResult(**result.data)



# ── Processing API ──

from pydantic import BaseModel as PydanticBase, Field as PydanticField

class TranslateRequest(PydanticBase):
    text: str

class TranslateResponse(PydanticBase):
    translated: str

@app.post("/api/process/translate", response_model=TranslateResponse)
async def process_translate(req: TranslateRequest):
    agent = AgentRegistry.create("translator")
    task = AgentTaskModel(task_type="translate", params={"text": req.text})
    result = await agent.run(task)
    return TranslateResponse(translated=result.data.get("translated", req.text))


class SummarizeRequest(PydanticBase):
    text: str

class SummarizeResponse(PydanticBase):
    summary: str

@app.post("/api/process/summarize", response_model=SummarizeResponse)
async def process_summarize(req: SummarizeRequest):
    agent = AgentRegistry.create("summarizer")
    task = AgentTaskModel(task_type="summarize", params={"text": req.text})
    result = await agent.run(task)
    return SummarizeResponse(summary=result.data.get("summary", req.text))


class ClassifyRequest(PydanticBase):
    title: str = ""
    content: str

class ClassifyResponse(PydanticBase):
    layer: str
    country: str
    city: str

@app.post("/api/process/classify", response_model=ClassifyResponse)
async def process_classify(req: ClassifyRequest):
    agent = AgentRegistry.create("classifier")
    task = AgentTaskModel(task_type="classify", params={"title": req.title, "content": req.content})
    result = await agent.run(task)
    return ClassifyResponse(**result.data)


class LocateRequest(PydanticBase):
    text: str

class LocateResponse(PydanticBase):
    country: str
    city: str
    lat: float
    lng: float

@app.post("/api/process/locate", response_model=LocateResponse)
async def process_locate(req: LocateRequest):
    agent = AgentRegistry.create("location_extractor")
    task = AgentTaskModel(task_type="locate", params={"text": req.text})
    result = await agent.run(task)
    return LocateResponse(**result.data)


class BayesianScoreRequest(PydanticBase):
    text: str
    source_system: str = ""

class BayesianScoreResponse(PydanticBase):
    posterior: float
    verdict: str
    prior_quality: str
    prior_class: str
    evidence_items: list[dict]

@app.post("/api/process/bayesian-score", response_model=BayesianScoreResponse)
async def process_bayesian_score(req: BayesianScoreRequest):
    agent = AgentRegistry.create("bayesian_scorer")
    task = AgentTaskModel(task_type="bayesian_score", params={
        "text": req.text,
        "source_system": req.source_system,
    })
    result = await agent.run(task)
    return BayesianScoreResponse(**result.data)


class PipelineRequest(PydanticBase):
    text: str
    title: str = ""
    source_system: str = ""
    translate: bool = True
    summarize: bool = True
    classify: bool = True
    locate: bool = True
    bayesian: bool = True
    skills: list[str] = PydanticField(default_factory=list)

@app.post("/api/process/pipeline")
async def process_pipeline(req: PipelineRequest):
    """Run full processing pipeline: translate → summarize → classify → locate → bayesian."""
    agent = AgentRegistry.create("collection_pipeline", callbacks=_ws_callbacks())
    task = AgentTaskModel(task_type="pipeline", params={
        "text": req.text,
        "title": req.title,
        "source_system": req.source_system,
        "translate": req.translate,
        "summarize": req.summarize,
        "classify": req.classify,
        "locate": req.locate,
        "bayesian": req.bayesian,
    }, skills=req.skills)
    result = await agent.run(task)
    return result.data


@app.get("/api/skills")
async def list_skills():
    from backend.agents.skill import SkillLoader
    names = SkillLoader.list_all()
    result = []
    for name in names:
        try:
            s = SkillLoader.load(name)
            result.append({
                "name": s.name,
                "description": s.description,
                "agent_types": s.agent_types,
            })
        except Exception:
            pass
    return {"skills": result}


@app.get("/api/agent/status")
async def agent_status():
    from backend.agents.config import is_agent_mode
    from backend.agents.skill import SkillLoader
    agents = {}
    for aid in sorted(AgentRegistry.list_all()):
        cls = AgentRegistry.get(aid)
        agents[aid] = {
            "type": cls.agent_type.value,
            "model": cls.agent_id,  # placeholder — real config loaded at init
        }
    by_type = {}
    for aid, info in agents.items():
        t = info["type"]
        by_type.setdefault(t, []).append(aid)
    return {
        "agent_mode": is_agent_mode(),
        "total_agents": len(agents),
        "by_type": by_type,
        "skills_available": SkillLoader.list_all(),
    }

# ── WebSocket ──

@app.websocket("/ws/{channel}")
async def websocket_endpoint(ws: WebSocket, channel: str):
    await ws_manager.connect(channel, ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        ws_manager.disconnect(channel, ws)

@app.post("/api/analysis/interpret", response_model=AnalysisInterpretResponse)
async def analysis_interpret(req: AnalysisInterpretRequest):
    """Generate AI interpretation for any analysis view."""
    agent = AgentRegistry.create("interpretation")
    task = AgentTaskModel(task_type="interpret", params={
        "analysis_type": req.analysis_type,
        "context": req.context,
    })
    result = await agent.run(task)
    return AnalysisInterpretResponse(
        analysis_type=result.data.get("analysis_type", req.analysis_type),
        interpretation=result.data.get("interpretation", "分析失败"),
    )


@app.get("/api/super-analysis/progress")
async def super_analysis_progress():
    """获取超级分析的实时进度。"""
    from backend.processors.progress import get_progress
    return get_progress()


@app.post("/api/super-analysis", response_model=SuperAnalysisResponse)
async def super_analysis(req: SuperAnalysisRequest):
    """超级分析 — 结合贝叶斯框架对用户问题进行结构化情报分析。"""
    from backend.processors.progress import reset_progress, mark_finished, mark_error

    reset_progress()
    agent = AgentRegistry.create("super_analyst", storage_root=STORAGE)
    task = AgentTaskModel(task_type="super_analysis", params={
        "question": req.question,
        "start_date": req.start_date,
        "end_date": req.end_date,
    }, skills=req.skills)
    try:
        result = await agent.run(task)
    except Exception as e:
        mark_error(str(e))
        raise
    data = result.data
    items = [BayesianIntelItem(**item) for item in data.get("relevant_items", [])]
    mark_finished()
    return SuperAnalysisResponse(
        question=data.get("question", req.question),
        analysis=data.get("analysis", "分析失败"),
        relevant_items=items,
        web_results=data.get("web_results", []),
    )


# ═══════════════════════════════════════════════════════════════
# OpenCode Agent Proxy Routes (Phase 1)
# ═══════════════════════════════════════════════════════════════

OPENCODE_URL = os.getenv("OPENCODE_URL", "http://127.0.0.1:3001")
OPENCODE_BIN = os.getenv("OPENCODE_BIN", "/usr/local/bin/opencode")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse_opencode_output(stdout: str) -> str:
    """Parse opencode run --format json output, extracting all text parts."""
    parts: list[str] = []
    tool_results: list[str] = []
    for line in stdout.strip().split("\n"):
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "text":
                text = event.get("part", {}).get("text", "")
                if text:
                    parts.append(text)
            elif event.get("type") == "tool_use":
                part = event.get("part", {})
                state = part.get("state", {})
                output = state.get("output", "")
                if output and "Error executing" not in output:
                    tool_results.append(output[:200])
        except (json.JSONDecodeError, KeyError):
            continue
    if parts:
        return "\n".join(parts)
    if tool_results:
        return "工具调用结果:\n" + "\n---\n".join(tool_results[:5])
    return stdout[:500] if stdout.strip() else "Agent 未产生文本输出，请尝试重新提问。"


async def _run_opencode_agent(agent: str, prompt: str, timeout: int = 180) -> str:
    """Run an OpenCode agent via subprocess and return the text output."""
    env = os.environ.copy()
    # Ensure LLM credentials are passed (dotenv may have loaded them into os.environ)
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        if key not in env:
            env[key] = os.getenv(key, "")
    proc = await asyncio.create_subprocess_exec(
        OPENCODE_BIN, "run",
        "--agent", agent,
        "--format", "json",
        "--permission-mode", "acceptEdits",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=_PROJECT_ROOT,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
        if stderr_text:
            log.warning("opencode stderr [%s]: %s", agent, stderr_text[:500])
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        text_count = output.count('"type":"text"')
        log.info("opencode [%s] output=%d bytes, text_events=%d", agent, len(output), text_count)
        if not output.strip():
            log.warning("opencode produced no stdout for agent=%s prompt=%s", agent, prompt[:100])
        return _parse_opencode_output(output)
    except asyncio.TimeoutError:
        proc.kill()
        log.warning("opencode timeout for agent=%s after %ds", agent, timeout)
        raise


@app.post("/api/intel/ask", response_model=AskResponse)
async def intel_ask(req: AskRequest, request: Request, user: dict = Depends(get_current_user)):
    """Q&A via OpenCode QA Agent, with local fallback."""
    _ip = request.client.host if request.client else ""
    record_activity(user["id"], "ask_question", {"question": req.question[:200]}, ip_address=_ip)
    try:
        filters = []
        if req.layer:
            filters.append(f"layer={req.layer}")
        if req.start_date:
            filters.append(f"from {req.start_date}")
        if req.end_date:
            filters.append(f"to {req.end_date}")
        prompt = req.question
        if filters:
            prompt = f"{req.question}\n\nFilters: {', '.join(filters)}"
        answer = await _run_opencode_agent("qa-analyst", prompt)
        return AskResponse(answer=answer or "分析完成，暂无文本输出", references=[])
    except Exception:
        agent = AgentRegistry.create("qa_analyst", indexer=_get_indexer())
        task = AgentTaskModel(task_type="qa", params={
            "question": req.question,
            "layer": req.layer,
            "start_date": req.start_date,
            "end_date": req.end_date,
        }, skills=req.skills)
        result = await agent.run(task)
        return AskResponse(
            answer=result.data.get("answer", "分析失败"),
            references=result.data.get("references", []),
        )


@app.post("/api/intel/report", response_model=SituationReport)
async def intel_report(req: ReportRequest, request: Request, user: dict = Depends(get_current_user)):
    """Report generation via OpenCode Report Writer Agent, with local fallback."""
    _ip = request.client.host if request.client else ""
    record_activity(user["id"], "generate_report", {"topic": (req.topic or "")[:200]}, ip_address=_ip)
    try:
        prompt_parts = [f"请生成一份情报报告。主题：{req.topic or '综合情报'}", f"时间范围：最近{req.days or 7}天"]
        if req.country:
            prompt_parts.append(f"国家：{req.country}")
        if req.layer:
            prompt_parts.append(f"领域：{req.layer}")
        if req.detail_level:
            prompt_parts.append(f"详细程度：{req.detail_level}")
        answer = await _run_opencode_agent("report-writer", "\n".join(prompt_parts), timeout=180)
        return SituationReport(
            title=req.topic or "情报报告",
            summary=answer or "生成完成，暂无文本输出",
            sections=[],
            item_count=0,
            source_count=0,
        )
    except Exception:
        agent = AgentRegistry.create("report_writer", storage_root=STORAGE)
        task = AgentTaskModel(task_type="report", params={
            "topic": req.topic,
            "country": req.country,
            "days": req.days,
            "layer": req.layer,
            "detail_level": req.detail_level,
        }, skills=req.skills)
        result = await agent.run(task)
        return SituationReport(
            title=result.data.get("title", "报告"),
            summary=result.data.get("summary", "生成失败"),
            sections=result.data.get("sections", []),
            item_count=result.data.get("item_count", 0),
            source_count=result.data.get("source_count", 0),
        )


@app.post("/api/intel/super-analysis", response_model=SuperAnalysisResponse)
async def intel_super_analysis(req: SuperAnalysisRequest, request: Request, user: dict = Depends(get_current_user)):
    """Super analysis — Bayesian evidence evaluation + web search + LLM deep reasoning."""
    from backend.processors.progress import reset_progress, mark_finished, mark_error

    _ip = request.client.host if request.client else ""
    record_activity(user["id"], "super_analysis", {"question": req.question[:200]}, ip_address=_ip)

    reset_progress()
    try:
        agent = AgentRegistry.create("super_analyst", storage_root=STORAGE)
        task = AgentTaskModel(task_type="super_analysis", params={
            "question": req.question,
            "start_date": req.start_date,
            "end_date": req.end_date,
        }, skills=req.skills)
        result = await agent.run(task)
    except Exception as e:
        mark_error(str(e))
        raise
    data = result.data
    items = [BayesianIntelItem(**item) for item in data.get("relevant_items", [])]
    mark_finished()
    return SuperAnalysisResponse(
        question=data.get("question", req.question),
        analysis=data.get("analysis", "分析失败"),
        relevant_items=items,
        web_results=data.get("web_results", []),
    )


@app.post("/api/intel/build-embedding-index")
async def intel_build_embedding_index(request: Request, user: dict = Depends(get_current_user)):
    """Build/rebuilt the embedding semantic search index from all bronze documents."""
    from backend.bronze_reader import scan_bronze
    from backend.processors.embedding_index import EmbeddingIndex

    _ip = request.client.host if request.client else ""
    record_activity(user["id"], "build_embedding_index", {}, ip_address=_ip)

    docs = scan_bronze(STORAGE)
    if not docs:
        return {"status": "error", "message": "无文档可供索引"}

    index = EmbeddingIndex(STORAGE, index_dir="embedding_index")
    count = index.build(docs)
    return {"status": "ok", "message": f"索引构建完成，{count} 篇文档", "count": count}


@app.post("/api/intel/interpret", response_model=AnalysisInterpretResponse)
async def intel_interpret(req: AnalysisInterpretRequest, request: Request, user: dict = Depends(get_current_user)):
    """AI interpretation via OpenCode Intel Interpreter Agent, with local fallback."""
    _ip = request.client.host if request.client else ""
    record_activity(user["id"], "interpret_analysis", {"analysis_type": req.analysis_type}, ip_address=_ip)
    try:
        prompt = f"请解读以下分析结果。\n分析类型：{req.analysis_type}"
        if req.context:
            prompt += f"\n上下文：{json.dumps(req.context, ensure_ascii=False)}"
        answer = await _run_opencode_agent("intel-interpreter", prompt, timeout=180)
        return AnalysisInterpretResponse(
            analysis_type=req.analysis_type,
            interpretation=answer or "解读完成，暂无文本输出",
        )
    except Exception:
        agent = AgentRegistry.create("interpretation")
        task = AgentTaskModel(task_type="interpret", params={
            "analysis_type": req.analysis_type,
            "context": req.context,
        })
        result = await agent.run(task)
        return AnalysisInterpretResponse(
            analysis_type=result.data.get("analysis_type", req.analysis_type),
            interpretation=result.data.get("interpretation", "分析失败"),
        )

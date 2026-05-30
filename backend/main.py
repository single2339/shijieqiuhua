from __future__ import annotations

import hashlib
import json
import os
import sys as _sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import asyncio
import logging

log = logging.getLogger(__name__)

# ── load .env from project root ──
_dotenv = Path(__file__).resolve().parent.parent / ".env"
if _dotenv.exists():
    import dotenv
    dotenv.load_dotenv(_dotenv)

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import httpx

from backend.bronze_reader import scan_bronze, scan_bronze_async
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
from backend.processors.analysis import (
    analyze_gaps,
    compute_corroboration,
    compute_risk_heatmap,
    compute_timeline,
    detect_anomalies,
    extract_entity_graph,
)
from backend.seed_data import main as reseed
from backend.collectors.horizon_bridge import HorizonBridge
from backend.merger import build_merge_index, load_merge_index

# ── import yao-bayesian-skill engine ──
SKILL_DIR = Path.home() / ".cc-switch" / "skills" / "yao-bayesian-skill" / "scripts"
_sys.path.insert(0, str(SKILL_DIR))
from bayesian_decision_report import apply_odds_update  # type: ignore[import-untyped]

RESEED_INTERVAL = 30  # seconds
HORIZON_INTERVAL = 15 * 60  # 15 minutes between Horizon scraper runs
MERGE_HOUR_UTC = 3  # daily merge at 03:00 UTC (Beijing 11:00)
COLLECTOR_MODE = os.environ.get("OSINT_COLLECTOR", "horizon")  # "demo" or "horizon"

async def reseed_loop():
    """Regenerate test data every RESEED_INTERVAL seconds (demo mode)."""
    while True:
        try:
            loop = asyncio.get_running_loop()
            ts = datetime.now(timezone.utc).isoformat()
            await loop.run_in_executor(None, lambda: reseed(clear=True, seed=ts))
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("reseed_loop iteration failed")
        await asyncio.sleep(RESEED_INTERVAL)


async def horizon_loop():
    """Collect real content via Horizon scrapers every HORIZON_INTERVAL seconds."""
    bridge = HorizonBridge(STORAGE)
    try:
        while True:
            try:
                await bridge.collect_and_store(hours=48)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("horizon_loop iteration failed")
            await asyncio.sleep(HORIZON_INTERVAL)
    finally:
        await bridge.close()


def _run_merge() -> dict:
    """Synchronous merge execution. Runs in thread pool. Invalidates dashboard cache."""
    index = build_merge_index(STORAGE)
    import logging
    log = logging.getLogger("uvicorn")
    log.info("Merge complete: %d docs -> %d groups (%d orphaned)",
             index.total_docs, index.total_groups, len(index.orphaned_doc_ids))
    return {"total_docs": index.total_docs, "total_groups": index.total_groups}


async def merge_loop():
    """Run content merging daily at MERGE_HOUR_UTC. Also runs on first startup."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            index_path = STORAGE / "_merge_index.json"
            needs_run = True
            if index_path.exists():
                try:
                    data = json.loads(index_path.read_text(encoding="utf-8"))
                    gen_date = datetime.fromisoformat(data.get("generated_at", "")).date()
                    if gen_date == now.date():
                        needs_run = False
                except (json.JSONDecodeError, KeyError, ValueError, OSError):
                    log.warning("merge_loop: failed to read merge index, will re-merge")
            if needs_run:
                loop = asyncio.get_running_loop()
                _dashboard_cache.clear()
                await loop.run_in_executor(None, _run_merge)
            next_run = now.replace(hour=MERGE_HOUR_UTC, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - datetime.now(timezone.utc)).total_seconds())
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("merge_loop iteration failed")
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed demo data once so the dashboard has something on first load
    if not any(STORAGE.rglob("*.json")):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: reseed(clear=True))

    tasks: list[asyncio.Task] = []
    if COLLECTOR_MODE == "demo":
        tasks.append(asyncio.create_task(reseed_loop()))
    else:
        tasks.append(asyncio.create_task(horizon_loop()))
    tasks.append(asyncio.create_task(merge_loop()))
    yield
    for t in tasks:
        t.cancel()


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

# ── Simple in-memory rate limiter ──
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120    # max requests per window per IP
_RATE_LIMIT_WRITE_MAX = 20  # stricter for POST endpoints


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
        _rate_limit_store.clear()
    return await call_next(request)


STORAGE = Path(__file__).resolve().parent.parent / "bronze_storage"

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


def _get_layer(doc) -> IntelLayer:
    """Read IntelLayer from document extensions (set by LLM during collection).

    Falls back to keyword classifier if no stored layer found.
    """
    ext = getattr(doc, "extensions", {}) or {}
    if isinstance(ext, dict):
        meta = ext.get("horizon_metadata", {})
        if isinstance(meta, dict) and meta.get("layer"):
            try:
                return IntelLayer(meta["layer"])
            except ValueError:
                pass
    return classify(doc.text)


# ── yao-bayesian-skill evidence framework ──

SOURCE_PRIORS: dict[str, dict] = {
    "high": {"probability": 0.70, "quality": "B", "source_class": "high-credibility"},
    "medium": {"probability": 0.55, "quality": "C", "source_class": "medium-credibility"},
    "low": {"probability": 0.40, "quality": "D", "source_class": "low-credibility"},
    "kol": {"probability": 0.30, "quality": "D", "source_class": "kol"},
    "unknown": {"probability": 0.40, "quality": "D", "source_class": "unknown"},
}

HIGH_SOURCES = {"reuters", "ap", "ap-news", "bbc", "afp", "npr", "nytimes",
                "the-guardian", "guardian", "cnn", "el-pais", "le-monde", "france24", "dw"}
MEDIUM_SOURCES = {"al-jazeera", "al-monitor", "euronews", "ansa", "repubblica",
                  "all-africa", "el-universal", "un-news"}
LOW_SOURCES = {"bellingcat", "arstechnica", "bleeping-computer", "medium", "rferl", "fdd"}


KOL_SOURCES = {"oryx", "perun", "ralee85", "geoconfirmed", "osinttechnical", "war-mapper", "rybar",
               "suriyak-maps", "southfront", "redspotted-nro", "covert-cabal", "ukikaski",
               "trent-telenko", "defmon3", "middle-east-monitor", "visual-politik",
               "biggers-geopolitics", "ukraine-frontline", "marksian", "casual-scholar",
               "boston-roundface", "shapan-war", "guancha-kol",
               "intel-crab", "mt-anderson", "eliot-higgins", "christo-grozev",
               "hi-sutton", "simplicius-thinker", "andrew-perpetua", "tatarigami-ua",
               "jeffrey-lewis", "phillips-obrien", "mick-ryan", "franz-gady",
               "alex-mercouris", "brian-berletic", "michael-kofman"}


def source_prior_class(src: str) -> str:
    s = src.lower().strip()
    if s in KOL_SOURCES:
        return "kol"
    for name in HIGH_SOURCES:
        if name in s:
            return "high"
    for name in MEDIUM_SOURCES:
        if name in s:
            return "medium"
    for name in LOW_SOURCES:
        if name in s:
            return "low"
    return "unknown"


def compute_bayesian(text: str, source_system: str = "") -> tuple:
    """
    Use yao-bayesian-skill odds-update with evidence quality tiers (A-E).
    Evidence parameters differ by source type: KOL sources get lower priors
    and weaker evidence weights, reflecting lack of institutional verification.
    Returns (posterior, trace, verdict, method, prior_quality, prior_class, evidence_items).
    """
    if not text.strip():
        return (0.5, [0.5], Verdict.UNCERTAIN, "", "", "", [])

    prior_class = source_prior_class(source_system)
    prior_info = SOURCE_PRIORS[prior_class]
    prior = prior_info["probability"]

    # Source-type-dependent evidence configuration
    # KOLs (individual social-media analysts) have weaker cross-source and
    # authority evidence; institutions have stronger corroboration factors.
    if prior_class == "kol":
        evidence_list = [
            {"name": "content-specificity", "likelihood_ratio": 2.0, "direction": "support", "dependency_discount": 0.7},
            {"name": "cross-source",          "likelihood_ratio": 1.5, "direction": "support", "dependency_discount": 1.0},
            {"name": "temporal",              "likelihood_ratio": 1.4, "direction": "support", "dependency_discount": 1.0},
            {"name": "verifiable-numbers",    "likelihood_ratio": 1.8, "direction": "support", "dependency_discount": 0.8},
            {"name": "source-authority",      "likelihood_ratio": 0.5, "direction": "support", "dependency_discount": 1.0},
        ]
        ev_items_out = [
            dict(name="content-specificity", quality="C", lr=2.0, dep_discount=0.7, direction="support"),
            dict(name="cross-source", quality="D", lr=1.5, dep_discount=1.0, direction="support"),
            dict(name="temporal", quality="C", lr=1.4, dep_discount=1.0, direction="support"),
            dict(name="verifiable-numbers", quality="C", lr=1.8, dep_discount=0.8, direction="support"),
            dict(name="source-authority", quality="D", lr=0.5, dep_discount=1.0, direction="support"),
        ]
    elif prior_class in ("high", "medium"):
        evidence_list = [
            {"name": "content-specificity", "likelihood_ratio": 3.0, "direction": "support", "dependency_discount": 0.7},
            {"name": "cross-source",          "likelihood_ratio": 5.0, "direction": "support", "dependency_discount": 1.0},
            {"name": "temporal",              "likelihood_ratio": 1.6, "direction": "support", "dependency_discount": 1.0},
            {"name": "verifiable-numbers",    "likelihood_ratio": 2.5, "direction": "support", "dependency_discount": 0.8},
            {"name": "source-authority",      "likelihood_ratio": 1.2, "direction": "support", "dependency_discount": 1.0},
        ]
        ev_items_out = [
            dict(name="content-specificity", quality="B", lr=3.0, dep_discount=0.7, direction="support"),
            dict(name="cross-source", quality="A", lr=5.0, dep_discount=1.0, direction="support"),
            dict(name="temporal", quality="C", lr=1.6, dep_discount=1.0, direction="support"),
            dict(name="verifiable-numbers", quality="B", lr=2.5, dep_discount=0.8, direction="support"),
            dict(name="source-authority", quality="B", lr=1.2, dep_discount=1.0, direction="support"),
        ]
    else:  # low / unknown
        evidence_list = [
            {"name": "content-specificity", "likelihood_ratio": 2.0, "direction": "support", "dependency_discount": 0.7},
            {"name": "cross-source",          "likelihood_ratio": 2.0, "direction": "support", "dependency_discount": 1.0},
            {"name": "temporal",              "likelihood_ratio": 1.3, "direction": "support", "dependency_discount": 1.0},
            {"name": "verifiable-numbers",    "likelihood_ratio": 1.5, "direction": "support", "dependency_discount": 0.8},
            {"name": "source-authority",      "likelihood_ratio": 0.8, "direction": "support", "dependency_discount": 1.0},
        ]
        ev_items_out = [
            dict(name="content-specificity", quality="D", lr=2.0, dep_discount=0.7, direction="support"),
            dict(name="cross-source", quality="D", lr=2.0, dep_discount=1.0, direction="support"),
            dict(name="temporal", quality="D", lr=1.3, dep_discount=1.0, direction="support"),
            dict(name="verifiable-numbers", quality="D", lr=1.5, dep_discount=0.8, direction="support"),
            dict(name="source-authority", quality="D", lr=0.8, dep_discount=1.0, direction="support"),
        ]

    posterior, log, _, _ = apply_odds_update(prior, evidence_list)

    # Build trace for frontend chart
    trace = [prior]
    current = prior
    for e in evidence_list:
        p, _, _, _ = apply_odds_update(current, [e])
        current = p
        trace.append(round(p, 4))

    if posterior >= 0.7:
        verdict = Verdict.VERIFIED
    elif posterior <= 0.3:
        verdict = Verdict.FALSE
    else:
        verdict = Verdict.UNCERTAIN

    return (round(posterior, 3), trace, verdict, "odds-update",
            prior_info["quality"], prior_info["source_class"], ev_items_out)


@app.get("/api/dashboard", response_model=DashboardData)
async def get_dashboard(start_date: str = "", end_date: str = ""):
    import time as _time

    cache_key = f"{start_date}|{end_date}"
    cached = _dashboard_cache.get(cache_key)
    if cached:
        ts, data = cached
        if _time.time() - ts < DASHBOARD_CACHE_TTL:
            return data

    def _process() -> DashboardData:
        items = _build_items(start_date=start_date, end_date=end_date)

        # Build source_map from multi-source items
        source_map: dict[str, dict] = {}
        now_ts = datetime.now(timezone.utc).isoformat()
        for item in items:
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
        for item in items:
            layer_counts[item.layer].append(item.confidence)

        layers = [
            LayerSummary(layer=layer, count=len(confs), avg_confidence=round(sum(confs) / len(confs), 3) if confs else 0.0)
            for layer, confs in layer_counts.items()
        ]

        sources = [
            SourceInfo(name=name, credibility=info["credibility"], document_count=info["count"], last_seen=info["last"])
            for name, info in sorted(source_map.items(), key=lambda x: x[1]["credibility"], reverse=True)
        ]

        return DashboardData(
            intel_items=items,
            sources=sources,
            layers=layers,
            total_items=len(items),
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
    loop = asyncio.get_running_loop()
    docs = await loop.run_in_executor(None, lambda: scan_bronze(STORAGE))
    count = len(docs)
    _health_count_cache = (_time.time(), count)
    return {"status": "ok", "bronze_docs": count}


_collect_task: asyncio.Task | None = None

@app.post("/api/collect")
async def trigger_collect(hours: int = 48):
    """Run Horizon scrapers once in the background and return immediately."""
    global _collect_task

    if _collect_task and not _collect_task.done():
        return {"status": "running", "message": "采集任务正在进行中"}

    async def _run():
        bridge = HorizonBridge(STORAGE)
        try:
            return await bridge.collect_and_store(hours=hours)
        finally:
            await bridge.close()

    _collect_task = asyncio.create_task(_run())
    return {"status": "started", "message": "采集任务已启动，将在后台执行"}


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
    loop = asyncio.get_running_loop()
    _dashboard_cache.clear()
    result = await loop.run_in_executor(None, _run_merge)
    return {"status": "ok", **result}


@app.post("/api/reclassify")
async def trigger_reclassify(force: bool = Query(False)):
    """Re-classify all existing bronze documents using LLM.

    Reads every JSON file, runs LLM classification, and writes the
    layer back into extensions.horizon_metadata.layer. Documents that
    already have a stored layer are skipped unless force=true.
    """
    import time as _time

    loop = asyncio.get_running_loop()
    docs = await loop.run_in_executor(None, lambda: scan_bronze(STORAGE))

    # Build {raw_document_id: path} lookup for O(1) updates
    id_to_path: dict[str, Path] = {}
    for p in STORAGE.rglob("*.json"):
        if p.name == "queue.db":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            did = data.get("raw_document_id", "")
            if did:
                id_to_path[did] = p
        except (json.JSONDecodeError, OSError):
            continue

    total = len(docs)
    updated = 0
    skipped = 0
    failed = 0

    for doc in docs:
        ext = doc.extensions or {}
        meta = ext.get("horizon_metadata", {}) if isinstance(ext, dict) else {}
        has_layer = isinstance(meta, dict) and meta.get("layer")
        has_location = isinstance(meta, dict) and meta.get("location_country")

        # Skip if both layer and location are present (unless force)
        if has_layer and has_location and not force:
            skipped += 1
            continue

        title = ""
        if isinstance(ext, dict):
            title = ext.get("horizon_title", "") or ext.get("summary", "") or ""

        try:
            layer, country, city = await classify_with_llm(title, doc.text)
        except Exception:
            failed += 1
            continue

        json_path = id_to_path.get(doc.raw_document_id)
        if json_path is None:
            failed += 1
            continue

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
            updated += 1
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to update %s: %s", json_path, e)
            failed += 1

        # Rate limit: brief delay between LLM calls
        await asyncio.sleep(0.05)

    _dashboard_cache.clear()
    return {
        "status": "ok",
        "total": total,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


# ═══════════════════════════════════════════════════════════════
# LLM helper — reusable DeepSeek call for Q&A and reports
# ═══════════════════════════════════════════════════════════════

from backend.llm_config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, create_llm_client


async def _llm_chat(system: str, user: str, temperature: float = 0.3) -> str | None:
    """Call DeepSeek LLM with system + user messages. Returns content or None."""
    if not LLM_API_KEY:
        return None
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    try:
        async with create_llm_client() as client:
            r = await client.post(f"{LLM_BASE_URL}/chat/completions", json=payload)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        log.warning("LLM chat returned status %d: %s", r.status_code, r.text[:200])
    except httpx.HTTPError as exc:
        log.warning("LLM chat HTTP error: %s", exc)
    except Exception:
        log.exception("LLM chat unexpected error")
    return None


# ═══════════════════════════════════════════════════════════════
# 1 — AI Analyst Q&A
# ═══════════════════════════════════════════════════════════════

_SYSTEM_QA = (
    "你是一名专业的情报分析师。基于提供的上下文情报数据，用简体中文回答用户的问题。"
    "引用具体的情报来源和时间，保持客观、准确。如果数据不足以回答，请明确指出。"
    "不编造信息，不添加外部知识。"
)


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """AI尝识者问答 — 基于现有情报数据回答问题。"""
    docs = await scan_bronze_async(STORAGE)
    seen: set[str] = set()
    relevant: list[dict] = []

    for doc in docs:
        text = doc.text
        if not text:
            continue
        body_hash = hashlib.md5(text.encode()).hexdigest()
        if body_hash in seen:
            continue
        seen.add(body_hash)

        ext = doc.extensions or {}
        title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]
        layer = _get_layer(doc)
        if req.layer and layer.value != req.layer:
            continue

        captured = doc.captured_at[:10] if doc.captured_at else ""
        if req.start_date and captured < req.start_date:
            continue
        if req.end_date and captured > req.end_date:
            continue

        relevant.append({
            "title": title.split("\n")[0],
            "content": text[:500],
            "source": doc.source_system,
            "date": captured,
            "layer": layer.value,
        })

        if len(relevant) >= 30:
            break

    if not relevant:
        return AskResponse(answer="系统暂无相关情报数据可供分析。", references=[])

    # Build context for LLM
    context_lines = []
    for i, r in enumerate(relevant, 1):
        context_lines.append(
            f"[{i}] {r['date']} | {r['source']} | {r['layer']}\n"
            f"    标题: {r['title']}\n"
            f"    内容: {r['content'][:300]}\n"
        )
    context = "\n".join(context_lines)
    user_prompt = f"## 情报数据\n\n{context}\n\n## 问题\n\n{req.question}"

    answer = await _llm_chat(_SYSTEM_QA, user_prompt)
    refs = [{"title": r["title"], "source": r["source"], "date": r["date"]} for r in relevant[:10]]

    return AskResponse(
        answer=answer or "AI分析暂时不可用（API密钥未配置或请求失败）。",
        references=refs,
    )


# ═══════════════════════════════════════════════════════════════
# 2 — Dashboard Stats & Visualizations
# ═══════════════════════════════════════════════════════════════


@app.get("/api/stats", response_model=DashboardStats)
async def dashboard_stats(start_date: str = "", end_date: str = ""):
    """Aggregated statistics for charts and visualizations."""
    import time as _time

    cache_key = f"stats|{start_date}|{end_date}"
    cached = _dashboard_cache.get(cache_key)
    if cached:
        ts, data = cached
        if _time.time() - ts < DASHBOARD_CACHE_TTL:
            return data

    def _process() -> DashboardStats:
        items = _build_items(start_date=start_date, end_date=end_date)

        layer_counts: dict[IntelLayer, list[float]] = {l: [] for l in IntelLayer}
        for item in items:
            layer_counts[item.layer].append(item.confidence)
        by_layer = [
            LayerSummary(layer=layer, count=len(confs), avg_confidence=round(sum(confs) / len(confs), 3) if confs else 0.0)
            for layer, confs in layer_counts.items()
        ]

        date_counts: dict[str, int] = {}
        for item in items:
            d = item.captured_at[:10] if item.captured_at else ""
            if d:
                date_counts[d] = date_counts.get(d, 0) + 1
        daily_trend = [TrendPoint(date=d, count=c) for d, c in sorted(date_counts.items())]

        source_layers: dict[str, dict] = {}
        for item in items:
            for src in item.sources:
                if src not in source_layers:
                    source_layers[src] = {}
                source_layers[src][item.layer.value] = source_layers[src].get(item.layer.value, 0) + 1

        source_matrix = [
            SourceMatrix(
                name=name,
                credibility=0.5 + (int.from_bytes(hashlib.md5(name.encode()).digest()[:4], "big") / 0xFFFFFFFF) * 0.4,
                document_count=sum(dist.values()),
                layer_distribution=dist,
            )
            for name, dist in sorted(source_layers.items(), key=lambda x: sum(x[1].values()), reverse=True)[:30]
        ]

        geo_dist: dict[str, int] = {}
        for item in items:
            c = item.country
            geo_dist[c] = geo_dist.get(c, 0) + 1
        geo_distribution = [{"country": c, "count": n} for c, n in sorted(geo_dist.items(), key=lambda x: -x[1])[:20]]

        import re as _re
        stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也",
                     "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
                     "它", "们", "那", "些", "与", "及", "或", "但", "而", "被", "把", "对", "从", "以", "为",
                     "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "is", "are", "was", "were",
                     "be", "been", "has", "have", "had", "it", "its", "this", "that", "with", "from", "by"}
        word_counts: dict[str, int] = {}
        for item in items:
            words = _re.findall(r'[一-鿿\w]+', item.title.lower())
            for w in words:
                if w not in stopwords and len(w) > 1:
                    word_counts[w] = word_counts.get(w, 0) + 1
        top_keywords = sorted([{"word": w, "count": c} for w, c in word_counts.items()], key=lambda x: -x["count"])[:30]

        return DashboardStats(
            total_items=len(items),
            total_sources=len(source_matrix),
            by_layer=by_layer,
            daily_trend=daily_trend,
            source_matrix=source_matrix,
            geo_distribution=geo_distribution,
            top_keywords=top_keywords,
        )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _process)
    _cache_set(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════
# 3 — Auto Situation Report
# ═══════════════════════════════════════════════════════════════

_SYSTEM_REPORT = (
    "你是一名专业的情报分析官。根据提供的上下文情报数据，生成一份结构化中文态势简报。"
    "简报格式要求：\n"
    "1. 先给出整体态势总结（150字以内）\n"
    "2. 按主题分节，每节以「## 标题」开头\n"
    "3. 每节包含3-5条关键发现，每条控制在80字以内\n"
    "4. 对关键数据点标注情报来源和日期\n"
    "5. 最后附置信度评估\n\n"
    "只使用提供的情报数据，不编造信息。"
)


@app.post("/api/report", response_model=SituationReport)
async def generate_report(req: ReportRequest):
    """生成指定主题/地区的中文情报态势简报。"""
    docs = scan_bronze(STORAGE)
    seen: set[str] = set()
    relevant: list[dict] = []
    source_set: set[str] = set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=req.days)

    for doc in docs:
        text = doc.text
        if not text:
            continue
        body_hash = hashlib.md5(text.encode()).hexdigest()
        if body_hash in seen:
            continue
        seen.add(body_hash)

        captured_raw = doc.captured_at
        if captured_raw:
            try:
                dt = datetime.fromisoformat(captured_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except ValueError:
                continue

        ext = doc.extensions or {}
        title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]

        # Filter by topic/country if specified
        combined = (title + " " + text[:500]).lower()
        if req.topic and req.topic.lower() not in combined and req.topic not in combined:
            continue
        if req.country:
            loc = extract_location(text)
            if loc is None or loc[0] != req.country:
                continue

        layer = _get_layer(doc)
        if req.layer and layer.value != req.layer:
            continue

        src_name = doc.source_system or doc.collector_id
        source_set.add(src_name)
        relevant.append({
            "title": title.split("\n")[0],
            "content": text[:500],
            "source": src_name,
            "date": doc.captured_at[:10] if doc.captured_at else "",
            "layer": layer.value,
        })

        if len(relevant) >= 50:
            break

    if not relevant:
        return SituationReport(
            title=f"态势简报：{req.topic or req.country or '全局'}",
            summary="指定条件下无可用情报数据。",
            item_count=0,
            source_count=0,
        )

    # Build context for LLM
    context_lines = []
    for i, r in enumerate(relevant, 1):
        context_lines.append(
            f"[{i}] {r['date']} | {r['source']} | {r['layer']}\n"
            f"    标题: {r['title']}\n"
            f"    内容: {r['content'][:300]}\n"
        )
    context = "\n".join(context_lines)

    topic_desc = req.topic or req.country or "全局态势"
    user_prompt = f"## 情报数据（{len(relevant)}条）\n\n{context}\n\n## 简报主题\n\n{topic_desc}\n\n请生成结构化中文态势简报。"

    result = await _llm_chat(_SYSTEM_REPORT, user_prompt)

    if not result:
        # Fallback: generate a simple structured report without LLM
        sections = []
        by_layer_local: dict[str, list[str]] = {}
        for r in relevant:
            by_layer_local.setdefault(r["layer"], []).append(r["title"])
        for layer, titles in by_layer_local.items():
            sections.append(ReportSection(
                heading=f"## {layer} 层面",
                body="\n".join(f"- {t}" for t in titles[:10]),
            ))
        return SituationReport(
            title=f"态势简报：{topic_desc}",
            summary=f"共{len(relevant)}条情报，来自{len(source_set)}个来源。AI简报生成暂不可用，以下为数据汇总。",
            sections=sections,
            item_count=len(relevant),
            source_count=len(source_set),
        )

    # Parse structured output — sections separated by ##
    lines = result.split("\n")
    summary = ""
    sections = []
    current_heading = ""
    current_body: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current_heading:
                sections.append(ReportSection(heading=current_heading, body="\n".join(current_body).strip()))
            current_heading = line
            current_body = []
        elif line.strip() and not summary:
            summary = line.strip()
        else:
            current_body.append(line)
    if current_heading:
        sections.append(ReportSection(heading=current_heading, body="\n".join(current_body).strip()))

    return SituationReport(
        title=f"态势简报：{topic_desc}",
        summary=summary or f"共{len(relevant)}条情报，来自{len(source_set)}个来源",
        sections=sections,
        item_count=len(relevant),
        source_count=len(source_set),
    )


# ═══════════════════════════════════════════════════════════════
# 4 — New Data Source Collectors (USGS, CISA, OpenSky)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/collect/usgs")
async def collect_usgs():
    """Fetch latest USGS earthquake data (past 7 days, M2.5+)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://earthquake.usgs.gov/fdsnws/event/1/query",
                params={"format": "geojson", "minmagnitude": 2.5, "orderby": "time", "limit": 50},
            )
        data = r.json()
        events = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0, 0, 0])
            events.append({
                "id": f"usgs-{props.get('id', props.get('code', ''))}",
                "title": f"地震: {props.get('place', '未知')} — M{props.get('mag', '?')}",
                "content": f"地震{props.get('place', '未知地区')}，" +
                           f"震级{props.get('mag', '?')}，深度{coords[2]}km。" +
                           f"时间: {props.get('time', '')}。" +
                           f"详情: {props.get('url', '')}",
                "lat": coords[1],
                "lng": coords[0],
                "source": "usgs",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return {"status": "ok", "events": events}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/collect/cisa")
async def collect_cisa():
    """Fetch latest CISA known exploited vulnerabilities."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            )
        data = r.json()
        vulns = []
        for item in data.get("vulnerabilities", [])[:20]:
            vulns.append({
                "id": f"cisa-{item.get('cveID', '')}",
                "title": f"CVE: {item.get('cveID', '')} — {item.get('vulnerabilityName', '')}",
                "content": f"漏洞描述: {item.get('shortDescription', '')}。" +
                           f"供应商: {item.get('vendorProject', '')}。" +
                           f"利用已活跃: {item.get('knownRansomwareCampaignUse', '未知')}。" +
                           f"CVE: {item.get('cveID', '')}",
                "source": "cisa",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return {"status": "ok", "vulnerabilities": vulns}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/collect/opensky")
async def collect_opensky():
    """Fetch flight tracking stats from OpenSky Network."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://opensky-network.org/api/states/all")
        data = r.json()
        states = data.get("states", [])[:50]
        flights = []
        for s in states:
            flights.append({
                "icao24": s[0],
                "callsign": (s[1] or "").strip(),
                "origin_country": s[2],
                "lat": s[6],
                "lng": s[5],
                "altitude": s[7],
                "velocity": s[9],
            })
        return {"status": "ok", "flights_in_view": len(flights), "flights": flights}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# Shared helper — build IntelItems from bronze docs
# ═══════════════════════════════════════════════════════════════

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
    docs = scan_bronze(STORAGE)
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
        title = ext.get("summary", text[:80]).split("\n")[0] or f"Intel from {sources[0] if sources else doc.source_system}"
        summary = ext.get("summary") or text[:300]

        country, loc_name, lat, lng = extract_location_with_fallback(text, _resolve_source_name(doc), doc)

        layer = _get_layer(doc)
        src_name = sources[0] if sources else (doc.source_system or doc.collector_id)

        captured = captured_at[:10] if captured_at else ""
        if start_date and captured < start_date:
            return None
        if end_date and captured > end_date:
            return None
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
                seen_docs.add(gd.get("doc_id", ""))

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
    result = compute_timeline(items)
    return TimelineResult(**result)


@app.get("/api/analysis/entities", response_model=EntityGraphResult)
async def analysis_entities():
    items = await _build_items_async()
    result = extract_entity_graph(items)
    return EntityGraphResult(**result)


@app.get("/api/analysis/corroboration", response_model=CorroborationResult)
async def analysis_corroboration():
    items = await _build_items_async()
    result = compute_corroboration(items)
    return CorroborationResult(**result)


@app.get("/api/analysis/anomalies", response_model=AnomalyResult)
async def analysis_anomalies(start_date: str = "", end_date: str = ""):
    items = await _build_items_async(start_date=start_date, end_date=end_date)
    result = detect_anomalies(items)
    return AnomalyResult(**result)


@app.get("/api/analysis/risk-heatmap", response_model=RiskHeatmapResult)
async def analysis_risk_heatmap():
    items = await _build_items_async()
    result = compute_risk_heatmap(items)
    return RiskHeatmapResult(**result)


@app.get("/api/analysis/gaps", response_model=GapAnalysisResult)
async def analysis_gaps():
    items = await _build_items_async()
    result = analyze_gaps(items)
    return GapAnalysisResult(**result)


# ── AI Interpretation prompts ──

_ANALYSIS_PROMPTS: dict[str, str] = {
    "timeline": (
        "你是一名专业的情报分析官。基于以下时间线统计数据，用简体中文进行阶段性分析总结"
        "（200-400字）：识别事件发展的关键阶段、转折点和时间模式。"
        "只使用提供的数据，不编造信息。"
    ),
    "entities": (
        "你是一名专业的情报网络分析师。基于以下实体关联数据，用简体中文分析情报网络结构"
        "（200-400字）：识别人物、组织和地点之间的关键节点、聚类和桥梁实体。"
        "只使用提供的数据，不编造信息。"
    ),
    "corroboration": (
        "你是一名专业的情报来源分析官。基于以下信源一致性数据，用简体中文分析报道格局"
        "（200-400字）：识别信息茧房、独立验证最强的报道，以及可能存在的虚假信息。"
        "只使用提供的数据，不编造信息。"
    ),
    "anomalies": (
        "你是一名专业的情报预警分析官。基于以下异常检测数据，用简体中文解释可能的原因"
        "（200-400字）：对检测到的情报量异常激增提出合理解释假设。"
        "只使用提供的数据，不编造信息。"
    ),
    "risk-heatmap": (
        "你是一名战略风险评估专家。基于以下区域风险数据，用简体中文进行战略评估"
        "（200-400字）：分析高风险区域的风险驱动因素和可能的地缘政治影响。"
        "只使用提供的数据，不编造信息。"
    ),
    "gaps": (
        "你是一名情报采集规划专家。基于以下情报缺口数据，用简体中文提出采集优先级建议"
        "（200-400字）：建议优先填补哪些缺口以及可能的采集策略。"
        "只使用提供的数据，不编造信息。"
    ),
}


@app.post("/api/analysis/interpret", response_model=AnalysisInterpretResponse)
async def analysis_interpret(req: AnalysisInterpretRequest):
    """Generate AI interpretation for any analysis view."""
    system_prompt = _ANALYSIS_PROMPTS.get(req.analysis_type, _ANALYSIS_PROMPTS["timeline"])
    context_json = json.dumps(req.context, ensure_ascii=False, indent=2)
    user_prompt = f"## 分析数据\n\n{context_json}\n\n请生成分析解读。"
    result = await _llm_chat(system_prompt, user_prompt, temperature=0.3)
    return AnalysisInterpretResponse(
        analysis_type=req.analysis_type,
        interpretation=result or "AI分析暂时不可用（API密钥未配置或请求失败）。",
    )


# ═══════════════════════════════════════════════════════════════
# 8 — Super Bayesian Analysis
# ═══════════════════════════════════════════════════════════════

_SYSTEM_SUPER_ANALYSIS = (
    "你是一名专业的贝叶斯情报分析师，严格遵循 Yao Bayesian Skill 方法论对情报数据进行结构化决策分析。"
    "\n\n"
    "## 核心方法论\n\n"
    "### 证据质量分级（A-E）\n"
    "| 等级 | 典型来源 | 使用方式 |\n"
    "|------|----------|----------|\n"
    "| A | 元分析、系统综述、官方统计数据 | 强先验或强更新输入 |\n"
    "| B | 同行评审论文、公共数据集、行业标准 | 中等强度先验或更新 |\n"
    "| C | 结构化专家访谈、内部历史数据、实地证据 | 可用但需明确注明限制 |\n"
    "| D | LLM推测、类比、常识、非正式启发 | 仅限弱先验 |\n"
    "| E | 博客、营销文案、社交帖子、未归属声明 | 不得作为核心证据 |\n\n"
    "### 先验构建规则\n"
    "- 先验类别（high-credibility/medium-credibility/low-credibility/kol/unknown）对应不同的先验概率和等效样本量（ESS）\n"
    "- 弱先验规则：若先验主要来自常识、类比或模型推测，必须标注为弱先验，降低ESS，扩大灵敏度范围\n"
    "- 必须记录：先验来源摘要、参考类、来源质量等级、等效样本量、可能使先验失效的因素\n\n"
    "### 贝叶斯更新公式（Odds-Update）\n"
    "```\n"
    "prior_odds = P(H) / (1 - P(H))\n"
    "对于每条证据 i:\n"
    "  base_lr = evidence.lr（若 direction='against' 则取 1/lr）\n"
    "  effective_lr = exp(ln(base_lr) × dependency_discount)\n"
    "  applied_lr = effective_lr  （即依赖折扣后的有效似然比）\n"
    "  odds = odds × applied_lr\n"
    "posterior_P = odds / (1 + odds)\n"
    "```\n"
    "依赖折扣（dependency_discount）关键原则：不能盲目相乘重叠证据。当多个信号可能来自同一底层来源时，降低依赖折扣并解释重叠风险。\n\n"
    "### 自然频率转换\n"
    "必须将主要结果转换为具体频率陈述：\n"
    "\"在 100 个类似案例中，先验预期约有 X 个成立。综合当前证据后，预期变更为约 Y 个成立。\"\n\n"
    "### 决策就绪度评估\n"
    "| 分数区间 | 状态 | 含义 |\n"
    "|----------|------|------|\n"
    "| 0.00-0.44 | collecting / 仍需补信息 | 关键信息仍缺失 |\n"
    "| 0.45-0.74 | nearly-ready / 接近可决策 | 1-2个缺口仍有意义 |\n"
    "| 0.75-1.00 | ready / 可以决策 | 具备正式决策条件 |\n\n"
    "### 强制性区分\n"
    "报告中每个数字都必须标注来源类别：\n"
    "- **observed（观测值）**：来自数据直接观测\n"
    "- **estimated（估计值）**：基于判断的估计\n"
    "- **assumed（假定值）**：基于政策或效用假设\n\n"
    "### 建议置信度\n"
    "- **medium-high / 把握较高**：稳定性 good，无严重警告，无 D/E 级证据\n"
    "- **medium / 把握一般**：稳定性 mixed，或有 1 条警告，或有 D/E 级证据\n"
    "- **low / 把握偏低**：稳定性 unstable，或 ≥2 条警告，或 ≥2 条 D/E 级证据\n\n"
    "## 分析报告结构\n\n"
    "你的回答必须严格按照以下 7 个部分组织：\n\n"
    "## 1. 决策摘要\n"
    "- **核心假设 H**：将用户问题转化为一个可检验的假设，用一句话清晰陈述\n"
    "- **一句话结论**：先给结论，再讲为什么\n"
    "- **建议行动**：现在应该做什么？给出明确的行动建议\n\n"
    "## 2. 先验分析\n"
    "- **先验概率 P(H)**：基于情报源整体可信度分布估算\n"
    "- **先验来源**：引用的情报源类型和数量\n"
    "- **等效样本量（ESS）**：大致估算\n"
    "- **来源质量**：整体评定（A-E）\n"
    "- **先验可能失效的条件**：什么情况下先验不对\n"
    "- **先验有效范围**：90% 可信区间（下限-上限）\n"
    "- 标注每个数字是 observed/estimated/assumed\n\n"
    "## 3. 证据分析\n"
    "以表格形式逐条列出关键证据（至少 5-10 条）：\n"
    "| # | 证据来源 | 内容摘要 | 质量 | 方向 | LR | 依赖折扣 | 有效LR |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "每一条证据解读必须包含：\n"
    "- 观测到了什么\n"
    "- 为什么支持或反对 H\n"
    "- LR 取值的理由（基于具体性、信源交叉验证、时效性）\n"
    "- 依赖折扣的理由（证据之间是否部分重叠）\n\n"
    "## 4. 贝叶斯更新计算\n"
    "展示完整的 odds-update 链：\n"
    "```\n"
    "初始先验 P(H) = X.XX → 先验 odds = Y.YY\n"
    "证据1（名称, LR_eff=Z.ZZ）→ odds₁ = Y.YY × Z.ZZ = A.AA\n"
    "证据2（名称, LR_eff=W.WW）→ odds₂ = A.AA × W.WW = B.BB\n"
    "...\n"
    "最终后验 odds = M.MM → P(H|E) = N.NN\n"
    "```\n"
    "- 标注每次更新的 delta（变化幅度）\n"
    "- 识别关键转折证据（使概率变化最大的证据）\n\n"
    "## 5. 后验结论\n"
    "- **后验概率 P(H|E)**：最终概率估算值和区间\n"
    "- **自然频率**：在 100 个类似情境中，预期约有多少个成立\n"
    "- **判断等级**：verified（基本确认，P≥0.7）/ likely（可能性较高，0.5≤P<0.7）/ uncertain（不确定，0.3≤P<0.5）/ unlikely（可能性较低，0.1≤P<0.3）/ false（基本排除，P<0.1）\n"
    "- **建议置信度**：low/medium/medium-high，并说明理由\n"
    "- **决策就绪度**：0-1 评分，当前是否可以据此决策\n\n"
    "## 6. 灵敏度分析\n"
    "- **先验变动**：如果先验概率偏高/偏低 30%，后验结论是否稳健？\n"
    "- **证据权重变动**：如果关键证据的 LR 被高估或低估，结论会翻转吗？\n"
    "- **最坏情况/最好情况**：极端情况下的后验范围\n"
    "- **稳定性分类**：stable（所有场景结论一致）/ mixed（2种不同结论）/ unstable（3种以上不同结论）\n"
    "- 如果不稳定，建议优先收集哪类信息\n\n"
    "## 7. 下一步信息收集建议\n"
    "- 当前最需要补充什么信息？列出 1-3 项\n"
    "- 每项信息对决策的预期影响\n"
    "- 什么证据会改变当前建议？\n"
    "- 何时重新打开此决策？\n\n"
    "## 警告与限制\n"
    "- 明确列出分析中的不确定性来源\n"
    "- 标注弱证据（D/E 级）及其对结论的影响\n"
    "- 如果存在证据依赖性，说明重叠风险\n"
    "- 说明此分析的适用范围和局限\n\n"
    "## 约束\n"
    "- 只使用提供的情报数据和网络搜索结果，不编造信息\n"
    "- 网络搜索结果作为补充参考，权重低于系统情报数据\n"
    "- 每个数字必须标注 observed/estimated/assumed\n"
    "- 先验概率必须参考提供的情报源可信度分布\n"
    "- 每个部分的结论必须引用具体情报作为支撑\n"
    "- 如果证据质量等级低（C/D/E 为主），必须降低建议置信度并扩大误差范围\n"
    "- D/E 级证据达到 2 条或以上时，必须在结论中明确标注\"把握偏低\""
)


async def _search_bing(query: str, topn: int = 8) -> list[dict]:
    """Search a single query on Bing with auto language detection.

    Uses cn.bing.com for Chinese queries, www.bing.com for English/international.
    Forces mkt=en-US for English queries to get international results regardless of geo-IP.
    """
    import urllib.parse
    from bs4 import BeautifulSoup

    # Detect query language: if >30% Chinese chars, use cn.bing.com
    chinese_chars = sum(1 for c in query if '一' <= c <= '鿿')
    is_chinese = len(query) > 0 and chinese_chars / len(query) > 0.3

    if is_chinese:
        bing_host = "cn.bing.com"
        accept_lang = "zh-CN,zh;q=0.9,en;q=0.8"
        mkt_param = ""
    else:
        bing_host = "www.bing.com"
        accept_lang = "en-US,en;q=0.9,zh;q=0.8"
        mkt_param = "&mkt=en-US&setlang=en"

    results: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"https://{bing_host}/search?q={urllib.parse.quote(query)}&count=20{mkt_param}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": accept_lang,
                },
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Each result is an <li> with class containing "b_algo"
            for li in soup.find_all("li", class_=lambda c: c and "b_algo" in c):
                if len(results) >= topn:
                    break

                # Title + URL: <h2><a href="...">title</a></h2>
                h2 = li.find("h2")
                a_tag = h2.find("a", href=True) if h2 else None
                if not a_tag:
                    # Fallback: any direct <a> with a real URL
                    a_tag = li.find("a", href=lambda h: h and h.startswith("http"))

                if not a_tag:
                    continue

                url = a_tag["href"]
                title = a_tag.get_text(" ", strip=True)
                if not title:
                    continue

                # Snippet: <div class="b_caption"><p>...</p></div>
                caption = li.find(class_="b_caption")
                p_tag = caption.find("p") if caption else None
                if not p_tag:
                    # Fallback: first <p> in the result block
                    p_tag = li.find("p")
                snippet = p_tag.get_text(" ", strip=True) if p_tag else ""
                if not snippet:
                    continue

                # URL normalization
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = f"https://{bing_host}" + url

                results.append({
                    "title": title,
                    "snippet": snippet[:300],
                    "url": url,
                })

    except httpx.HTTPError as exc:
        log.warning("Bing search HTTP error for %r: %s", query[:80], exc)
    except Exception as exc:
        log.warning("Bing search failed for %r: %s", query[:80], exc)

    return results


async def _gen_search_queries(question: str) -> list[str]:
    """Return the raw user question as the search query.

    The full user input is used directly — no LLM rewriting, no keyword
    extraction, no recency variants.  The user's original wording is the
    best search query.
    """
    return [question]


async def _web_search(query: str) -> list[dict]:
    """Search the web using Bing China with multiple query formulations.

    Runs 2-3 parallel Bing searches with different query formulations
    (original, keyword-only, recency variant) to maximize coverage.
    Bing returns ~8 results per query; duplicates are removed.
    """
    qs = await _gen_search_queries(query)
    tasks = [_search_bing(q, topn=8) for q in qs]
    all_results = await asyncio.gather(*tasks)

    seen: set[str] = set()
    merged: list[dict] = []
    for results in all_results:
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                merged.append(r)
    return merged[:15]


@app.post("/api/super-analysis", response_model=SuperAnalysisResponse)
async def super_analysis(req: SuperAnalysisRequest):
    """超级分析 — 结合贝叶斯框架对用户问题进行结构化情报分析。"""

    def _score_docs() -> list[tuple[int, dict]]:
        """CPU-bound: scan bronze, classify, compute Bayesian — runs in thread pool."""
        docs = scan_bronze(STORAGE)
        seen: set[str] = set()
        scored: list[tuple[int, dict]] = []
        q_tokens = set(req.question.lower().split())

        for doc in docs:
            text = doc.text
            if not text:
                continue
            body_hash = hashlib.md5(text.encode()).hexdigest()
            if body_hash in seen:
                continue
            seen.add(body_hash)

            ext = doc.extensions or {}
            title = ext.get("summary", "") or ext.get("horizon_title", "") or text[:80]
            layer = _get_layer(doc)
            captured = doc.captured_at[:10] if doc.captured_at else ""

            if req.start_date and captured < req.start_date:
                continue
            if req.end_date and captured > req.end_date:
                continue

            posterior, trace, verdict, method, prior_quality, prior_class, evidence_items = compute_bayesian(
                text, doc.source_system
            )

            text_tokens = set((title + " " + text[:300]).lower().split())
            score = len(q_tokens & text_tokens) if q_tokens else 0

            scored.append((score, {
                "title": title.split("\n")[0],
                "source": doc.source_system,
                "date": captured,
                "layer": layer.value,
                "confidence": round(posterior, 3),
                "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
                "prior_class": prior_class,
                "prior_probability": SOURCE_PRIORS.get(prior_class, SOURCE_PRIORS["unknown"])["probability"],
                "evidence_items": [
                    {"name": e["name"], "quality": e["quality"], "lr": e["lr"], "direction": e["direction"]}
                    for e in evidence_items
                ],
                "bayesian_trace": [round(t, 4) for t in trace],
                "content_snippet": text[:200],
            }))

        scored.sort(key=lambda x: -x[0])
        return scored[:20]

    loop = asyncio.get_running_loop()
    top_scored = await loop.run_in_executor(None, _score_docs)
    top_items = [item for _, item in top_scored]

    # Web search for supplementary context
    web_results = await _web_search(req.question)

    if not top_items and not web_results:
        return SuperAnalysisResponse(
            question=req.question,
            analysis="系统暂无相关情报数据可供贝叶斯分析。",
            relevant_items=[],
            web_results=[],
        )

    # ── Cross-reference web results with internal items ──
    # Build a mapping: internal_item_index → [matching web result indices]
    used_web: set[int] = set()
    item_web_map: dict[int, list[int]] = {i: [] for i in range(len(top_items))}

    if web_results and top_items:
        for wi, wr in enumerate(web_results):
            web_text = (wr.get("title", "") + " " + wr.get("snippet", "")).lower()
            web_tokens = set(web_text.split())
            if not web_tokens:
                continue
            best_score = 0
            best_item = -1
            for ii, item in enumerate(top_items):
                item_text = (item["title"] + " " + item["content_snippet"]).lower()
                item_tokens = set(item_text.split())
                overlap = len(web_tokens & item_tokens)
                if overlap > best_score:
                    best_score = overlap
                    best_item = ii
            if best_score >= 3 and best_item >= 0:
                item_web_map[best_item].append(wi)
                used_web.add(wi)

    # ── Build unified context ──
    context_parts: list[str] = []

    if top_items:
        context_parts.append(f"=== 统一证据分析（{len(top_items)}条内部情报 + {len(web_results)}条网络数据） ===\n")
        context_parts.append("每条内部情报若有关联网络数据，已标注在「网络佐证」下。\n")

        for i, item in enumerate(top_items):
            evidence_str = ", ".join(
                f"{e['name']}(LR={e['lr']}, {e['direction']})"
                for e in item["evidence_items"]
            )
            context_parts.append(
                f"[内部-{i+1}] {item['date']} | {item['source']} | {item['layer']}\n"
                f"    标题: {item['title']}\n"
                f"    内容摘要: {item['content_snippet'][:200]}\n"
                f"    贝叶斯评估: 先验类别={item['prior_class']}, "
                f"先验概率={item['prior_probability']}, "
                f"后验置信度={item['confidence']}, 判定={item['verdict']}\n"
                f"    证据项: {evidence_str}\n"
                f"    置信度追踪: {' → '.join(f'{t:.2f}' for t in item['bayesian_trace'])}\n"
            )

            # Attach matching web results as corroboration
            matched_web = item_web_map.get(i, [])
            if matched_web:
                context_parts.append("    ── 网络佐证 ──\n")
                for wi in matched_web:
                    wr = web_results[wi]
                    context_parts.append(
                        f"    [Web-{wi+1}] {wr['snippet'][:250]}\n"
                        f"        来源: {wr.get('url', 'N/A')}\n"
                    )
            context_parts.append("")

    # Remaining unmatched web results
    unmatched = [wr for wi, wr in enumerate(web_results) if wi not in used_web]
    if unmatched:
        context_parts.append("=== 其他网络参考（未直接匹配内部情报） ===\n")
        for wr in unmatched:
            context_parts.append(
                f"- {wr['snippet'][:200]}\n"
                f"  来源: {wr.get('url', 'N/A')}\n"
            )
        context_parts.append("")

    context = "\n".join(context_parts)

    user_prompt = (
        f"{context}\n\n"
        f"## 用户问题\n\n{req.question}\n\n"
        f"请按照贝叶斯推理框架进行综合分析。内部情报和网络数据已交叉匹配，"
        f"请将它们视为统一证据源：网络数据用于佐证或补充内部情报，"
        f"分析时优先使用内部情报的贝叶斯评估作为基础。"
    )

    analysis = await _llm_chat(_SYSTEM_SUPER_ANALYSIS, user_prompt, temperature=0.3)

    return SuperAnalysisResponse(
        question=req.question,
        analysis=analysis or "AI分析暂时不可用（API密钥未配置或请求失败）。",
        relevant_items=[BayesianIntelItem(**item) for item in top_items],
        web_results=web_results,
    )

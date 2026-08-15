"""OSINT football prediction pipeline — job orchestration.

W1-W2 split per PRD §5.1 / decision Q5. This file is now thin orchestration:
- ``run_prediction_sync()`` — entry point that wires adapters / analysis /
  persistence into one synchronous call tree
- ``_job_id()`` / ``_profile_match()`` — small leaf utilities kept here
  because they're pure and coupling-free
- ``_collect_zero_config_sources()`` / ``_collect_farich_foot_sources()`` —
  W2.8 keeps these two as the collector hub; each delegates to adapters/
  and evidence.py, no longer owning subprocess or URL logic

Everything else lives in:
- adapters/        — data sources (lightpanda, dongqiudi, user_supplied, url_safety)
- analysis/        — prediction / confidence / intelligence / report
- factor_registry  — per-match factor scoring rules
- evidence         — evidence construction + classification
- storage          — bronze filesystem persistence
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

from backend import telemetry
from .adapters import lightpanda as lightpanda_adapter
from . import cache
from .adapters import user_supplied as user_supplied_adapter
from .adapters import dongqiudi as dongqiudi_adapter
from .adapters import dongqiudi_analysis as dongqiudi_analysis_adapter
from .adapters import dongqiudi_schedule as dongqiudi_schedule_adapter
from .analysis import confidence as confidence_module
from .analysis import intelligence as intelligence_module
from .analysis import prediction as prediction_module
from .analysis import report as report_module
from . import evidence as evidence_module
from . import data_quality as data_quality_module
from . import factor_registry as factor_registry_module
from . import market_service
from . import storage
from .models import (
    FootballOsintJob,
    FootballOsintJobRequest,
    FootballOsintJobStatus,
    MarketContext,
    MatchProfile,
    OsintEvidence,
    OsintMatch,
    OsintSourceStatus,
    SportteryMarket,
)
from .sources import DONGQIUDI_SOURCE_TEMPLATES, SEARCH_SOURCE_TEMPLATES
from .adapters import open_meteo as weather_adapter
from .adapters import rss_feed as rss_adapter
from .adapters import sporttery as sporttery_adapter
from .adapters import theoddsapi as theoddsapi_adapter
from .adapters import web_search as web_search_adapter


# ── public entry point ──

def run_prediction_sync(
    payload: dict[str, Any] | FootballOsintJobRequest,
    storage_root: str | Path | None = None,
    *,
    warm_window: str = "on-demand",
    cache_source: str = "on-demand",
) -> FootballOsintJob:
    request = payload if isinstance(payload, FootballOsintJobRequest) else FootballOsintJobRequest(**payload)
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    match_id = _job_id(request)
    match = OsintMatch(
        home_team=request.home_team,
        away_team=request.away_team,
        kickoff_at=request.kickoff_at,
        competition=request.competition,
        venue=request.venue,
        profile=_profile_match(request),
    )

    search_stats, market_context = _collect_zero_config_sources(request, evidence, sources)
    factors = factor_registry_module.build_factors(request, match.profile, evidence)
    prediction = prediction_module.predict(request, factors, factor_min=_read_factor_min())
    confidence = confidence_module.grade(match.profile, evidence, factors)
    data_quality = data_quality_module.build_data_quality(
        request, sources, evidence, factors, prediction, search_stats=search_stats,
    )
    cycle = intelligence_module.build_intelligence_cycle(sources, evidence)
    confirmed_findings = intelligence_module.confirmed_findings(match, evidence)
    assessments = intelligence_module.assessments(match, factors, prediction, confidence)
    alternatives = intelligence_module.alternative_explanations(match, sources, factors)
    next_steps = intelligence_module.next_steps(sources, factors)
    report = report_module.render_report(
        match, [source for source in sources if source.adapter != "theoddsapi"], evidence,
        factors, prediction, confidence,
        cycle, confirmed_findings, assessments, alternatives, next_steps,
    )

    job = FootballOsintJob(
        job_id=match_id,
        status=FootballOsintJobStatus.COMPLETED,
        phase="done",
        progress=100,
        match=match,
        sources=sources,
        evidence=evidence,
        factors=factors,
        prediction=prediction,
        market_context=market_context,
        confidence=confidence,
        data_quality=data_quality,
        intelligence_cycle=cycle,
        confirmed_findings=confirmed_findings,
        assessments=assessments,
        alternative_explanations=alternatives,
        next_steps=next_steps,
        report_markdown=report,
    )
    try:
        telemetry_payload = {
            "lean": job.prediction.lean if job.prediction else "",
            "insufficiency_reasons": job.data_quality.insufficiency_reasons if job.data_quality else [],
            "adapter_statuses": {source.adapter: source.status for source in job.sources},
            "fundamental_factor_count": job.data_quality.fundamental_factor_count if job.data_quality else 0,
            "relevant_search_results_count": job.data_quality.relevant_search_results_count if job.data_quality else 0,
            "dropped_search_results_count": job.data_quality.dropped_search_results_count if job.data_quality else 0,
            "extraction_status": job.data_quality.extraction_status if job.data_quality else "not_run",
        }
        telemetry.emit("research.analysis_completed", payload=telemetry_payload)
        telemetry.emit("research.dashboard_view", payload=telemetry_payload)
    except Exception:
        log.debug("analysis telemetry emit failed", exc_info=True)
    storage.persist_job(job, storage_root, request=request, warm_window=warm_window, cache_source=cache_source)
    return job


# ── internal helpers ──

def _read_factor_min() -> int:
    """Read info_insufficient_factor_min from system_config; default 1."""
    try:
        from backend.auth.db import get_db
        row = get_db().execute(
            "SELECT value FROM system_config WHERE key='info_insufficient_factor_min'"
        ).fetchone()
        return int(row[0]) if row else 1
    except Exception:
        return 1


def _job_id(request: FootballOsintJobRequest) -> str:
    payload = request.model_dump(mode="json")
    seed = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"fo_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{digest}"


def _profile_match(request: FootballOsintJobRequest) -> MatchProfile:
    text = " ".join([request.home_team, request.away_team, request.competition]).lower()
    competition_type = "u23" if "u23" in text or "u-23" in text else "club"
    if "friendly" in text or "友谊" in text:
        competition_type = "friendly_u23" if competition_type == "u23" else "friendly"
    factor_pack = "youth_match" if "u23" in competition_type else ("friendly" if "friendly" in competition_type else "default")
    return MatchProfile(
        competition_type=competition_type,
        time_to_kickoff_hours=None,
        data_density="medium" if request.user_supplied.notes else "low",
        factor_pack=factor_pack,
    )


# ── collector hub (W2.8: thin orchestrator, each leaf delegating to adapters/) ──

def _collect_zero_config_sources(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> tuple[data_quality_module.SearchQualityStats, MarketContext]:
    fixture_id = evidence_module.append_evidence(
        evidence,
        source="User request",
        source_type="fixture",
        claim=f"{request.home_team} vs {request.away_team} entered for OSINT verification",
        topic="fixture.query",
        side="both",
        confidence=0.55,
        raw_excerpt=f"{request.competition} {request.kickoff_at}".strip(),
    )
    sources.append(OsintSourceStatus(adapter="fixtures_public", label="公开赛程探测", status="ok", evidence_ids=[fixture_id]))

    sources.append(
        OsintSourceStatus(
            adapter="farich_foot_plan",
            label="farich/foot 数据源计划",
            status="skipped",
            reason="未抓取到结构化基本面，仅作为后续采集占位。",
        )
    )
    _collect_farich_foot_sources(request, evidence, sources)

    # ── weather / search / RSS / football-data / official market — parallel I/O ──
    search_stats = data_quality_module.SearchQualityStats()
    market: SportteryMarket | None = None
    licensed_snapshots = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_collect_one_weather, request, evidence): "weather",
            pool.submit(_collect_search_sources, request, evidence, sources): "search",
            pool.submit(rss_adapter.collect_all, request, evidence): "rss",
            pool.submit(_collect_football_data_stats, request, evidence, sources): "football_data",
            pool.submit(_collect_sporttery, request, evidence): "sporttery",
            pool.submit(theoddsapi_adapter.collect, request): "theoddsapi",
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result(timeout=60)
                if label == "weather":
                    weather_id, weather_reason = result
                    sources.append(OsintSourceStatus(
                        adapter="open_meteo", label="Open-Meteo 天气",
                        status="ok" if weather_id else "skipped",
                        evidence_ids=[weather_id] if weather_id else [],
                        reason=weather_reason if not weather_id else "",
                    ))
                elif label == "rss":
                    for adapter, status, count in result:
                        sources.append(OsintSourceStatus(
                            adapter=adapter, label="RSS 新闻",
                            status=status,
                            reason="" if status == "ok" else "未匹配到相关新闻",
                        ))
                elif label == "search" and isinstance(result, data_quality_module.SearchQualityStats):
                    search_stats = result
                elif label == "sporttery":
                    market, evidence_id, reason = result
                    sources.append(OsintSourceStatus(
                        adapter="sporttery",
                        label="中国体育彩票盘口",
                        status="ok" if evidence_id else "skipped",
                        evidence_ids=[evidence_id] if evidence_id else [],
                        reason="" if evidence_id else reason,
                    ))
                elif label == "theoddsapi":
                    licensed_snapshots, reason = result
                    sources.append(
                        market_service.licensed_market_source_status(licensed_snapshots, reason)
                    )
                # search / football_data append to evidence + sources internally
            except Exception:
                log.warning("%s phase failed or timed out", label)
                if label == "theoddsapi":
                    sources.append(
                        market_service.licensed_market_source_status(
                            [], "授权赔率数据服务请求失败",
                        )
                    )

    if request.user_supplied.notes:
        note_ids = []
        for note in request.user_supplied.notes:
            note_ids.append(
                evidence_module.append_evidence(
                    evidence,
                    source="User note",
                    source_type="note",
                    claim=note[:240],
                    topic="user.note",
                    side="neutral",
                    confidence=0.6,
                    raw_excerpt=note[:500],
                )
            )
        sources.append(OsintSourceStatus(adapter="user_supplied", label="用户补充基本面", status="ok", evidence_ids=note_ids))
    else:
        sources.append(OsintSourceStatus(adapter="user_supplied", label="用户补充基本面", status="skipped", reason="未提供伤病、首发或球队新闻补充"))
    return search_stats, market_service.build_market_context(market, licensed_snapshots)


def _collect_one_weather(request: FootballOsintJobRequest, evidence: list[OsintEvidence]) -> tuple[str, str]:
    """Tiny wrapper so weather can be submitted to ThreadPoolExecutor."""
    return weather_adapter.collect(request, evidence)


def _collect_sporttery(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
) -> tuple[SportteryMarket | None, str, str]:
    """Collect one official Sporttery snapshot and its traceable evidence row."""
    odds = sporttery_adapter.get_odds(
        request.home_team,
        request.away_team,
        request.kickoff_at,
        provider=request.provider,
        provider_match_id=request.provider_match_id,
    )
    if odds is None:
        return None, "", "体彩未覆盖该场比赛"
    market = sporttery_adapter.market_snapshot(odds, observed_at=datetime.now(timezone.utc).isoformat())
    if market is None:
        return None, "", "体彩赔率不完整"
    claim = f"体彩胜平负赔率: 主胜{odds.had_h:.2f} / 平{odds.had_d:.2f} / 客胜{odds.had_a:.2f}"
    if market.home_handicap is not None and odds.hhad_h is not None:
        claim += f"；让球({market.home_handicap:+d})赔率: 主胜{odds.hhad_h:.2f} / 平{odds.hhad_d:.2f} / 客胜{odds.hhad_a:.2f}"
    evidence_id = evidence_module.append_evidence(
        evidence,
        source=f"中国体育彩票 ({odds.league})",
        source_type="odds",
        claim=claim,
        topic="odds.sporttery.market",
        side="neutral",
        confidence=0.60,
        raw_excerpt=json.dumps(market.model_dump(mode="json"), ensure_ascii=False),
    )
    return market, evidence_id, ""




_DONGQIUDI_HTTP_ADAPTERS = {"dongqiudi_schedule", "dongqiudi_analysis"}


def _collect_farich_foot_sources(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> None:
    command = os.getenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", "lp-fetch-md")
    binary = command if Path(command).exists() else shutil.which(command)

    for source, urls in dongqiudi_adapter.candidate_urls(request):
        if not urls:
            sources.append(OsintSourceStatus(adapter=source.adapter, label=source.label, status="skipped", reason="缺少懂球帝 matchId 或历史赛程参数"))
            continue

        if source.adapter not in _DONGQIUDI_HTTP_ADAPTERS and not binary:
            sources.append(OsintSourceStatus(adapter=source.adapter, label=source.label, status="skipped", reason=f"{command} not available"))
            continue

        evidence_ids: list[str] = []
        failures: list[str] = []
        for url in urls:
            if source.adapter in _DONGQIUDI_HTTP_ADAPTERS:
                adapter_fn = dongqiudi_schedule_adapter.fetch_url if source.adapter == "dongqiudi_schedule" else dongqiudi_analysis_adapter.fetch_url
                evidence_id, failure = adapter_fn(url, source_type=source.source_type, topic=source.topic, source_label=source.label, request=request, evidence=evidence)
            else:
                evidence_id, failure = lightpanda_adapter.fetch_url(binary, url, source_type=source.source_type, topic=source.topic, source_label=source.label, request=request, evidence=evidence)
            if evidence_id:
                evidence_ids.append(evidence_id)
            elif failure:
                failures.append(failure)
        if evidence_ids:
            sources.append(
                OsintSourceStatus(
                    adapter=source.adapter,
                    label=source.label,
                    status="ok",
                    evidence_ids=evidence_ids,
                    reason="" if not failures else f"{len(failures)} 个页面未成功抓取",
                )
            )
        else:
            sources.append(
                OsintSourceStatus(
                    adapter=source.adapter,
                    label=source.label,
                    status="failed" if failures else "skipped",
                    reason="; ".join(failures[:2]) if failures else "未配置公开页面候选",
                )
            )

    manual_urls = user_supplied_adapter.candidate_urls(request)
    if manual_urls:
        if not binary:
            sources.append(OsintSourceStatus(adapter="manual_public_url", label="用户补充公开来源", status="skipped", reason=f"{command} not available"))
        else:
            evidence_ids = []
            failures = []
            for url in manual_urls[:3]:
                evidence_id, failure = lightpanda_adapter.fetch_url(binary, url, source_type="web", topic="collection.manual_url", source_label="用户补充公开来源", request=request, evidence=evidence)
                if evidence_id:
                    evidence_ids.append(evidence_id)
                elif failure:
                    failures.append(failure)
            sources.append(
                OsintSourceStatus(
                    adapter="manual_public_url",
                    label="用户补充公开来源",
                    status="ok" if evidence_ids else "failed",
                    evidence_ids=evidence_ids,
                    reason="" if evidence_ids else "; ".join(failures[:2]),
                )
            )


def _collect_search_sources(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> data_quality_module.SearchQualityStats:
    home = request.home_team
    away = request.away_team

    for source in SEARCH_SOURCE_TEMPLATES:
        if not source.default_enabled:
            continue
        if source.adapter == "ddg_search":
            _collect_ddg_search(source, home, away, request, evidence, sources)
            continue
        sources.append(OsintSourceStatus(adapter=source.adapter, label=source.label,
            status="skipped", reason="not implemented"))

    # Chinese domestic media search — runs after DDG so both English and
    # Chinese coverage contribute evidence independently.
    return _collect_chinese_search(request, evidence, sources)


def _contains_chinese(text: str) -> bool:
    """Return True if the text contains any CJK Unified Ideograph."""
    return any('一' <= c <= '鿿' for c in text)


def _fetch_page_text(url: str, timeout: float = 8.0) -> str:
    """Fetch a URL and extract readable text content. Returns '' on any failure."""
    if not url:
        return ""
    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    for selector in ("article", "main", '[class*="content"]', '[class*="article"]'):
        container = soup.select_one(selector)
        if container:
            text = container.get_text(separator="\n", strip=True)
            break
    else:
        text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""

    if len(text) > 2000:
        text = text[:2000] + "..."
    return text


def _fetch_top_pages(
    search_results: list[dict[str, str]],
    evidence: list[OsintEvidence],
    source_label: str,
    base_topic: str,
) -> list[str]:
    """Fetch full content of top 2 search result pages in parallel."""
    urls = [r["url"] for r in search_results[:2] if r.get("url")]
    if not urls:
        return []

    evidence_ids: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(_fetch_page_text, url): url for url in urls}
        for future in as_completed(futures):
            try:
                text = future.result(timeout=10)
            except Exception:
                continue
            if text and len(text) > 50:
                url = futures[future]
                evidence_ids.append(evidence_module.append_evidence(
                    evidence,
                    source=source_label,
                    source_type="web_page",
                    claim=f"Full page content from {url}",
                    topic=f"{base_topic}.fullpage",
                    side="neutral",
                    confidence=0.22,
                    raw_excerpt=text,
                    url=url,
                ))
    return evidence_ids


def _search_result_matches_match(result: dict[str, str], home: str, away: str) -> bool:
    """Keep match-specific results; discard country/profile pages that mention one side only."""
    haystack = " ".join(
        str(result.get(key, "")) for key in ("title", "snippet", "url")
    ).lower()

    def tokens(name: str) -> list[str]:
        return [part for part in re.split(r"[^a-z0-9]+", name.lower()) if len(part) >= 3]

    home_tokens = tokens(home)
    away_tokens = tokens(away)
    if not home_tokens or not away_tokens:
        return True
    return any(token in haystack for token in home_tokens) and any(token in haystack for token in away_tokens)


def _collect_ddg_search(
    source,
    home: str,
    away: str,
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> None:
    from .adapters import name_translation

    # Quality preview/stats sites are English — search the English originals,
    # not the translated Chinese display names.
    home_en = name_translation.to_english(home)
    away_en = name_translation.to_english(away)

    # Only build English queries when we have actual English names. If
    # to_english falls back to Chinese (uncached name), skip English search
    # — Chinese search will handle it.
    if _contains_chinese(home_en) or _contains_chinese(away_en):
        sources.append(OsintSourceStatus(
            adapter=source.adapter, label=source.label,
            status="skipped",
            reason="队名未翻译为英文（name_translation 缓存缺失），跳过英文搜索",
        ))
        return

    question = (request.question or "").strip()
    # Simple, focused queries. Disambiguate single-word names (e.g. "Jordan"
    # → Nike shoes) by appending "national football team".
    h = f"{home_en} national football team" if " " not in home_en else home_en
    a = f"{away_en} national football team" if " " not in away_en else away_en
    queries = [f"{h} {a} football match preview"]
    if question and len(question) > 2:
        queries.append(f"{h} {a} football {question}")
    queries.extend(_targeted_queries(question, h, a))

    evidence_ids = []
    primary_results: list[dict[str, str]] = []
    for i, query in enumerate(queries[:4]):
        sk = cache.search_key(query)
        results = cache.search_cache.get(sk)
        if results is None:
            # Primary query (i=0): with high-signal football domains.
            # Bing is the primary backend (Sogou anti-spider blocks the
            # server IP). Site: filter works on Bing for single domains
            # but the OR syntax is unreliable — apply only the first domain.
            if i == 0:
                results = web_search_adapter.search(
                    query, include_domains=web_search_adapter.PREVIEW_DOMAINS,
                )
                # If site: filter produced nothing, retry without it
                if not results:
                    results = web_search_adapter.search(query)
            else:
                results = web_search_adapter.search(query)
            cache.search_cache.set(sk, results)
        relevant_results = [r for r in results if _search_result_matches_match(r, home_en, away_en)]
        if i == 0:
            primary_results = relevant_results
        topic = source.topic if i == 0 else f"{source.topic}.q{i}"
        for result in relevant_results:
            evidence_ids.append(evidence_module.append_evidence(
                evidence,
                source=source.label,
                source_type=source.source_type,
                claim=result["title"],
                topic=topic,
                side="neutral",
                confidence=0.25,
                raw_excerpt=result["snippet"],
                url=result["url"],
            ))

    # Fetch full content of top 2 result pages for richer extraction
    full_page_ids = _fetch_top_pages(primary_results, evidence, source.label, source.topic)
    evidence_ids.extend(full_page_ids)

    sources.append(OsintSourceStatus(
        adapter=source.adapter, label=source.label,
        status="ok" if evidence_ids else "skipped",
        evidence_ids=evidence_ids,
        reason="" if evidence_ids else "无搜索结果",
    ))


def _targeted_queries(question: str, home: str, away: str) -> list[str]:
    """Return dimension-specific English search queries to fill data gaps.

    Detection keys stay Chinese (the user's question), but emitted queries are
    English so they hit international preview/stats sites.
    """
    q = question.lower()
    queries: list[str] = []

    if any(kw in q for kw in ["红黄牌", "黄牌", "红牌", "牌", "犯规", "裁判"]):
        queries.append(f"{home} {away} football cards fouls referee stats")

    if any(kw in q for kw in ["角球", "角"]):
        queries.append(f"{home} {away} football corners stats average")

    if any(kw in q for kw in ["进球", "总进球", "进球数", "大球", "小球", "比分"]):
        queries.append(f"{home} {away} football goals scored conceded form stats")

    if any(kw in q for kw in ["球员", "核心", "主力", "首发", "伤病", "缺席", "阵容"]):
        queries.append(f"{home} {away} football injuries suspensions predicted lineup")

    if any(kw in q for kw in ["半场", "上半", "下半"]):
        queries.append(f"{home} {away} football first half performance trends")

    if any(kw in q for kw in ["风险", "临场", "变数", "不确定"]):
        queries.append(f"{home} {away} football latest team news preview")

    return queries


# ── Chinese domestic media search ──

# High-signal Chinese sports media domains, applied as a Sogou site: filter.
CN_DOMAINS = [
    "sports.sina.com.cn",
    "sports.qq.com",
    "zhibo8.com",
    "hupu.com",
    "titansports.cn",
    "dongqiudi.com",
    "sohu.com",
    "163.com",
]

_LOW_SIGNAL_CN_TITLE_MARKERS = (
    "百度百科",
    "_百科",
    "百科",
    "国家概况",
    "国家简介",
    "国家概览",
    "外交部",
    "关于科特迪瓦的一切",
    "旅游",
    "签证",
    "地图",
    "人口",
    "经济",
    "地理",
)

_LOW_SIGNAL_CN_URL_MARKERS = (
    "baike.baidu.com",
    "mfa.gov.cn",
)

_FOOTBALL_CONTEXT_CN_MARKERS = (
    "足球",
    "比赛",
    "世界杯",
    "前瞻",
    "阵容",
    "伤停",
    "比分",
    "交锋",
    "战绩",
    "出线",
    "小组赛",
    "首发",
    "赛事",
    "赛前",
    "预测",
)
_GENERIC_TEAM_TOKENS = {
    "u23",
    "u21",
    "u20",
    "u19",
    "fc",
    "sc",
    "club",
    "football",
    "soccer",
    "national",
    "team",
}



def _cn_result_text(result: dict[str, str]) -> str:
    return " ".join(str(result.get(key, "")) for key in ("title", "snippet", "url"))


def _cn_result_mentions_side(text: str, team: str, other_team: str) -> bool:
    if _contains_chinese(team):
        return team in text
    tokens = [part for part in re.split(r"[^a-z0-9]+", team.lower()) if len(part) >= 2]
    other_tokens = {part for part in re.split(r"[^a-z0-9]+", other_team.lower()) if len(part) >= 2}
    unique_tokens = [token for token in tokens if token not in other_tokens and token not in _GENERIC_TEAM_TOKENS]
    if not unique_tokens:
        unique_tokens = [token for token in tokens if token not in _GENERIC_TEAM_TOKENS]
    haystack = text.lower()
    return bool(unique_tokens) and any(token in haystack for token in unique_tokens)


def _cn_search_result_matches_match(result: dict[str, str], home: str, away: str) -> bool:
    """Keep deterministic match-specific Chinese results before fetching pages."""
    text = _cn_result_text(result)
    title = str(result.get("title", ""))
    url = str(result.get("url", "")).lower()
    if any(marker in title for marker in _LOW_SIGNAL_CN_TITLE_MARKERS):
        return False
    if any(marker in text for marker in _LOW_SIGNAL_CN_TITLE_MARKERS):
        return False
    if any(marker in url for marker in _LOW_SIGNAL_CN_URL_MARKERS):
        return False

    has_home = _cn_result_mentions_side(text, home, away)
    has_away = _cn_result_mentions_side(text, away, home)
    has_football_context = any(marker in text for marker in _FOOTBALL_CONTEXT_CN_MARKERS)
    return has_home and has_away and has_football_context


def _targeted_cn_queries(question: str, home: str, away: str) -> list[str]:
    """Dimension-specific Chinese search queries for domestic media."""
    q = question.lower()
    queries: list[str] = []

    if any(kw in q for kw in ["进球", "总进球", "进球数", "大球", "小球", "比分"]):
        queries.append(f"{home} {away} 进球 数据 统计")

    if any(kw in q for kw in ["球员", "核心", "主力", "首发", "伤病", "缺席", "阵容"]):
        queries.append(f"{home} {away} 伤病 首发 阵容")

    if any(kw in q for kw in ["红黄牌", "黄牌", "红牌", "犯规", "裁判"]):
        queries.append(f"{home} {away} 红黄牌 裁判")

    if any(kw in q for kw in ["角球", "角"]):
        queries.append(f"{home} {away} 角球 统计")

    if any(kw in q for kw in ["风险", "临场", "变数", "不确定"]):
        queries.append(f"{home} {away} 最新消息 赛前")

    return queries


def _collect_chinese_search(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> data_quality_module.SearchQualityStats:
    home = request.home_team
    away = request.away_team

    # Primary: preview + team news; then question-specific; then dimension-targeted.
    queries = [f"{home} {away} 前瞻 分析 预测"]
    question = (request.question or "").strip()
    if question and len(question) > 2:
        queries.append(f"{home} {away} {question}")
    queries.extend(_targeted_cn_queries(question, home, away))
    queries = list(dict.fromkeys(queries))

    evidence_ids: list[str] = []
    seen_urls: set[str] = set()
    raw_count = 0
    relevant_count = 0
    dropped_count = 0
    for i, query in enumerate(queries[:4]):
        sk = cache.search_key(f"cn:{query}")
        results = cache.search_cache.get(sk)
        if results is None:
            # Try without domain filter first. Only add CN domain filter
            # as fallback if the broad query returns nothing useful.
            results = web_search_adapter.search(query)
            if not results:
                results = web_search_adapter.search(query, include_domains=CN_DOMAINS)
            cache.search_cache.set(sk, results)
        topic = "search.cn.preview" if i == 0 else f"search.cn.q{i}"
        for result in results:
            raw_count += 1
            url = str(result.get("url", "")).strip()
            if not url or url in seen_urls or not _cn_search_result_matches_match(result, home, away):
                dropped_count += 1
                continue
            seen_urls.add(url)
            relevant_count += 1
            evidence_ids.append(evidence_module.append_evidence(
                evidence,
                source="国内媒体搜索",
                source_type="search",
                claim=result["title"],
                topic=topic,
                side="neutral",
                confidence=0.28,
                raw_excerpt=result["snippet"],
                url=url,
            ))

    reason = ""
    if not evidence_ids:
        reason = "无相关中文搜索结果" if raw_count else "无中文搜索结果"
    sources.append(OsintSourceStatus(
        adapter="cn_search",
        label="国内媒体搜索",
        status="ok" if evidence_ids else "skipped",
        evidence_ids=evidence_ids,
        reason=reason,
    ))
    return data_quality_module.SearchQualityStats(
        relevant_count=relevant_count,
        dropped_count=dropped_count,
    )


def _collect_football_data_stats(
    request: FootballOsintJobRequest,
    evidence: list[OsintEvidence],
    sources: list[OsintSourceStatus],
) -> None:
    """Fetch structured form/H2H from football-data.org, add as fundamental evidence.

    Evidence text is formatted in the same Chinese pattern as dongqiudi's output
    so the existing regexes in factor_registry.py (_FORM_RE, _H2H_RE) parse it
    without any changes.
    """
    from .adapters import football_data_stats

    home = request.home_team
    away = request.away_team
    use_provider_ids = (
        request.provider == "football-data"
        and bool(request.home_provider_id)
        and bool(request.away_provider_id)
    )


    # Fetch form for both teams in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        if use_provider_ids:
            home_future = pool.submit(football_data_stats.fetch_team_form_by_id, request.home_provider_id, home)
            away_future = pool.submit(football_data_stats.fetch_team_form_by_id, request.away_provider_id, away)
        else:
            home_future = pool.submit(football_data_stats.fetch_team_form, home)
            away_future = pool.submit(football_data_stats.fetch_team_form, away)
        try:
            home_form = home_future.result(timeout=15)
        except Exception:
            home_form = None
        try:
            away_form = away_future.result(timeout=15)
        except Exception:
            away_form = None

    evidence_ids: list[str] = []
    if home_form is not None and away_form is not None:
        excerpt = (
            f"{home}近期战绩：{home_form.wins}胜{home_form.draws}平{home_form.losses}负"
            f"（近{home_form.recent_count}场）\n"
            f"{away}近期战绩：{away_form.wins}胜{away_form.draws}平{away_form.losses}负"
            f"（近{away_form.recent_count}场）"
        )
        evidence_ids.append(evidence_module.append_evidence(
            evidence,
            source="football-data.org",
            source_type="fundamental",
            claim=f"{home} {home_form.wins}W{home_form.draws}D{home_form.losses}L, "
                  f"{away} {away_form.wins}W{away_form.draws}D{away_form.losses}L",
            topic="fundamental.football_data.form",
            side="neutral",
            confidence=0.48,
            raw_excerpt=excerpt,
        ))

    if use_provider_ids:
        h2h = football_data_stats.fetch_h2h_by_ids(request.home_provider_id, request.away_provider_id, home, away)
    else:
        h2h = football_data_stats.fetch_h2h(home, away)
    if h2h is not None and h2h.total_matches > 0:
        # Format: "历史交锋：A X胜Y平Z负，B Z胜Y平X负"
        excerpt = (
            f"历史交锋：{h2h.home_team} {h2h.home_wins}胜{h2h.draws}平{h2h.away_wins}负，"
            f"{h2h.away_team} {h2h.away_wins}胜{h2h.draws}平{h2h.home_wins}负"
        )
        evidence_ids.append(evidence_module.append_evidence(
            evidence,
            source="football-data.org",
            source_type="fundamental",
            claim=f"H2H: {h2h.home_wins}W-{h2h.draws}D-{h2h.away_wins}L over {h2h.total_matches}",
            topic="fundamental.football_data.h2h",
            side="neutral",
            confidence=0.48,
            raw_excerpt=excerpt,
        ))

    if evidence_ids:
        sources.append(OsintSourceStatus(
            adapter="football_data_stats",
            label="football-data.org 结构化数据",
            status="ok",
            evidence_ids=evidence_ids,
        ))
    else:
        sources.append(OsintSourceStatus(
            adapter="football_data_stats",
            label="football-data.org 结构化数据",
            status="skipped",
            reason="未找到两队结构化数据（队名未匹配或无近期比赛记录）",
        ))

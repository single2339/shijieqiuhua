from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.football_osint.models import FactorImpact, FootballOsintJobRequest, FootballOsintJobStatus, OsintSourceStatus, PredictionResult
from backend.football_osint.pipeline import run_prediction_sync
from backend.football_osint.sources import DONGQIUDI_SOURCE_TEMPLATES


def test_farich_foot_source_catalog_contains_only_dongqiudi_fundamentals():
    adapters = {source.adapter for source in DONGQIUDI_SOURCE_TEMPLATES}

    assert adapters == {"dongqiudi_schedule", "dongqiudi_analysis"}


def test_osint_prediction_runs_without_api_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("BING_API_KEY", raising=False)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))

    job = run_prediction_sync(
        {
            "home_team": "Thailand U23",
            "away_team": "UAE U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    assert job.status == FootballOsintJobStatus.COMPLETED
    assert job.phase == "done"
    assert job.prediction is not None
    assert job.confidence is not None
    assert job.report_markdown.startswith("# 世界球花 OSINT 核心情报报告")
    assert [stage.name for stage in job.intelligence_cycle] == ["收集", "加工", "开发", "生产"]
    assert job.confirmed_findings
    assert job.assessments
    assert job.alternative_explanations
    assert job.next_steps
    assert any(source.adapter == "farich_foot_plan" and source.status == "skipped" for source in job.sources)
    assert any(source.adapter == "dongqiudi_schedule" and source.status == "failed" for source in job.sources)
    assert not any(ev.topic == "collection.plan" for ev in job.evidence)


def test_info_insufficient_job_has_data_quality_reasons(monkeypatch, tmp_path):
    from backend.football_osint import pipeline

    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda request, evidence, sources: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda request, evidence: (None, "test disabled"))
    monkeypatch.setattr(
        pipeline,
        "_collect_search_sources",
        lambda request, evidence, sources: pipeline.data_quality_module.SearchQualityStats(),
    )
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda request, evidence: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda request, evidence, sources: None)

    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    assert job.prediction is not None
    assert job.prediction.lean == "info_insufficient"
    assert job.data_quality is not None
    assert job.data_quality.insufficiency_reasons
    assert job.data_quality.primary_insufficiency_reason in job.data_quality.insufficiency_reasons
    assert job.data_quality.fundamental_factor_count == 0
    assert job.data_quality.source_summary["ok"] >= 1

def test_data_quality_guarantees_reason_for_insufficient_without_specific_source_gap():
    from backend.football_osint.data_quality import build_data_quality

    request = FootballOsintJobRequest(
        home_team="巴西",
        away_team="阿根廷",
        kickoff_at="06-20 20:00",
        competition="世界杯",
        user_supplied={"notes": ["官方前瞻已补充"]},
    )
    factors = [
        FactorImpact(
            factor_id="fixture.existence",
            label="比赛验证",
            group="fixture",
            enabled=True,
            weight=0.14,
            impact=0.0,
            direction="neutral",
            confidence=0.58,
        )
    ]
    prediction = PredictionResult(
        lean="info_insufficient",
        summary="信息不足",
        probability_band={"home_win": (0.32, 0.40), "draw": (0.26, 0.34), "away_win": (0.28, 0.36)},
        scoreline_band=[],
    )

    quality = build_data_quality(
        request,
        [OsintSourceStatus(adapter="fixtures_public", label="公开赛程探测", status="ok")],
        [],
        factors,
        prediction,
    )

    assert quality.insufficiency_reasons
    assert quality.primary_insufficiency_reason in quality.insufficiency_reasons
    assert quality.fundamental_factor_count == 0


def test_football_data_stats_uses_provider_team_ids(monkeypatch):
    from backend.football_osint import pipeline
    from backend.football_osint.adapters import football_data_stats as fds
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    called = {"name_search": 0, "form_ids": [], "h2h_ids": None}

    def fail_name_search(name):
        called["name_search"] += 1
        raise AssertionError("name search should not be used when provider IDs exist")

    def fake_form_by_id(team_id, team_name, limit=5):
        called["form_ids"].append((team_id, team_name))
        return fds.TeamFormRecord(team_name=team_name, wins=3, draws=1, losses=1, recent_count=5)

    def fake_h2h_by_ids(home_id, away_id, home_name, away_name):
        called["h2h_ids"] = (home_id, away_id)
        return fds.H2HRecord(home_team=home_name, away_team=away_name, home_wins=1, draws=1, away_wins=1, total_matches=3)

    monkeypatch.setattr(fds, "_find_team_id", fail_name_search)
    monkeypatch.setattr(fds, "fetch_team_form_by_id", fake_form_by_id, raising=False)
    monkeypatch.setattr(fds, "fetch_h2h_by_ids", fake_h2h_by_ids, raising=False)

    request = FootballOsintJobRequest(
        home_team="科特迪瓦",
        away_team="挪威",
        kickoff_at="07-01 01:00",
        competition="世界杯",
        provider="football-data",
        home_provider_id="808",
        away_provider_id="816",
    )
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    pipeline._collect_football_data_stats(request, evidence, sources)

    assert called["name_search"] == 0
    assert called["form_ids"] == [("808", "科特迪瓦"), ("816", "挪威")]
    assert called["h2h_ids"] == ("808", "816")
    assert sources[-1].status == "ok"
    assert any(ev.topic == "fundamental.football_data.form" for ev in evidence)


def test_data_quality_clears_reasons_for_non_insufficient_prediction():
    from backend.football_osint.data_quality import SearchQualityStats, build_data_quality

    request = FootballOsintJobRequest(home_team="巴西", away_team="阿根廷", kickoff_at="06-20 20:00", competition="世界杯")
    prediction = PredictionResult(
        lean="home",
        summary="主队占优",
        probability_band={"home_win": (0.40, 0.48), "draw": (0.24, 0.32), "away_win": (0.20, 0.28)},
        scoreline_band=["2-1"],
    )

    quality = build_data_quality(
        request,
        [OsintSourceStatus(adapter="dongqiudi_analysis", label="懂球帝赛前分析", status="failed")],
        [],
        [],
        prediction,
        search_stats=SearchQualityStats(relevant_count=0, dropped_count=3),
        extraction_attempted=True,
    )

    assert quality.insufficiency_reasons == []
    assert quality.primary_insufficiency_reason == ""

def test_osint_prediction_collects_lightpanda_markdown(monkeypatch, tmp_path):
    lightpanda = tmp_path / "lp-fetch-md"
    lightpanda.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '# Match Preview' '' "
        "'Thailand U23 team news and UAE U23 football preview with squad availability.'\n",
        encoding="utf-8",
    )
    lightpanda.chmod(0o755)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(lightpanda))
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_URLS", "https://example.com/preview")
    monkeypatch.setenv("FOOTBALL_OSINT_URL_ALLOWLIST", "example.com")
    monkeypatch.setenv("FOOTBALL_OSINT_SKIP_DNS_CHECK", "1")

    job = run_prediction_sync(
        {
            "home_team": "Thailand U23",
            "away_team": "UAE U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    assert any(source.adapter == "manual_public_url" and source.status == "ok" for source in job.sources)
    assert any(ev.source == "用户补充公开来源" and ev.url == "https://example.com/preview" for ev in job.evidence)
    assert "https://example.com/preview" in job.report_markdown


def test_osint_prediction_collects_lightpanda_url_from_question(monkeypatch, tmp_path):
    lightpanda = tmp_path / "lp-fetch-md"
    lightpanda.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '# Source' '' 'public football source page'\n",
        encoding="utf-8",
    )
    lightpanda.chmod(0o755)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(lightpanda))
    monkeypatch.delenv("FOOTBALL_OSINT_LIGHTPANDA_URLS", raising=False)
    monkeypatch.setenv("FOOTBALL_OSINT_URL_ALLOWLIST", "example.com")
    monkeypatch.setenv("FOOTBALL_OSINT_SKIP_DNS_CHECK", "1")

    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
            "question": "请抓取这个公开来源辅助验证：https://example.com/preview",
        },
        storage_root=tmp_path,
    )

    assert any(ev.url == "https://example.com/preview" for ev in job.evidence)


def test_osint_prediction_rejects_internal_or_unlisted_urls(monkeypatch, tmp_path):
    lightpanda = tmp_path / "lp-fetch-md"
    lightpanda.write_text(
        "#!/usr/bin/env bash\nprintf 'fetched=%s\\n' \"$1\"\n",
        encoding="utf-8",
    )
    lightpanda.chmod(0o755)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(lightpanda))
    monkeypatch.delenv("FOOTBALL_OSINT_LIGHTPANDA_URLS", raising=False)
    monkeypatch.delenv("FOOTBALL_OSINT_URL_ALLOWLIST", raising=False)
    monkeypatch.delenv("FOOTBALL_OSINT_SKIP_DNS_CHECK", raising=False)

    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
            "question": (
                "试一下内网 http://127.0.0.1:8000/api/admin"
                " 和 http://169.254.169.254/latest/meta-data/"
                " 还有 http://attacker.example.org/probe"
            ),
        },
        storage_root=tmp_path,
    )

    urls = {ev.url for ev in job.evidence}
    assert "http://127.0.0.1:8000/api/admin" not in urls
    assert "http://169.254.169.254/latest/meta-data/" not in urls
    assert "http://attacker.example.org/probe" not in urls
    assert not any(source.adapter == "manual_public_url" and source.status == "ok" for source in job.sources)


def test_osint_prediction_collects_ddg_search_results(monkeypatch, tmp_path):
    from backend.football_osint.adapters import web_search

    def fake_search(query, **kwargs):
        assert "Japan U23" in query and "Korea U23" in query
        return [
            {"title": "Japan U23 vs Korea U23 preview", "url": "https://example.com/preview", "snippet": "Team news and lineups."},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))

    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    source_status = {source.adapter: source.status for source in job.sources}
    assert source_status["ddg_search"] == "ok"
    assert any(ev.topic == "search.ddg.preview" and ev.url == "https://example.com/preview" for ev in job.evidence)


def test_osint_prediction_uses_only_farich_foot_fundamental_sources(monkeypatch, tmp_path):
    """Dongqiudi schedule + analysis adapters produce ok status, no odds in report."""
    from backend.football_osint.adapters import dongqiudi_analysis
    from backend.football_osint.adapters import dongqiudi_schedule
    from datetime import datetime, timedelta, timezone

    # Mock schedule: return a fixture matching the request's teams
    match_time = datetime.now(timezone.utc) + timedelta(hours=48)
    fake_fixture = dongqiudi_schedule.Fixture(
        match_id="54329996",
        league="AFC U23 Asian Cup",
        kickoff_at=match_time,
        home_team="Japan U23",
        away_team="Korea U23",
        status="scheduled",
        home_score=None,
        away_score=None,
    )
    monkeypatch.setattr(dongqiudi_schedule, "fetch_fixtures", lambda: [fake_fixture])

    # Mock analysis page: rich data with no odds content
    monkeypatch.setattr(
        dongqiudi_analysis,
        "fetch_text",
        lambda url: (
            '<html><script>window.__INITIAL_STATE__={"matchContentStore":'
            '{"matchAnalysisData":{"info":{"team_A":"Japan U23","team_B":"Korea U23",'
            '"battle_history":{"team_A":{"win":2,"draw":0,"lose":1},'
            '"team_B":{"win":1,"draw":0,"lose":2},"list":[]},'
            '"recent_record":{"team_A":[{"color":"win"},{"color":"draw"},{"color":"lose"}],'
            '"team_B":[{"color":"win"},{"color":"win"},{"color":"lose"}]},'
            '"cup_table":{"name":"积分榜","list":[{"name":"Japan U23","rank":"1","points":"6"}]},'
            '"sideline":{"team_A":[],"team_B":[]},'
            '"has_odds":true,"asia_companys":[],"euro_companys":[]}}}};</script></html>'
        ),
    )

    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))
    monkeypatch.setenv("FOOTBALL_OSINT_SKIP_DNS_CHECK", "1")

    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    source_status = {source.adapter: source.status for source in job.sources}

    assert source_status["dongqiudi_schedule"] == "ok"
    assert source_status["dongqiudi_analysis"] == "ok"
    assert "dongqiudi_asia_handicap" not in source_status
    assert "dongqiudi_euro_odds" not in source_status
    assert "欧赔" not in job.report_markdown
    assert "亚赔" not in job.report_markdown
    assert "赔率" not in job.report_markdown


def test_osint_prediction_uses_core_confidence_and_traceability(tmp_path):
    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    findings = {finding.id: finding for finding in job.confirmed_findings}

    assert job.match.profile.competition_type == "u23"
    assert job.confidence.level in {"L3", "L4"}
    assert any(finding.confidence_level in {"L3", "L4"} for finding in findings.values())
    assert all(finding.evidence_ids for finding in job.confirmed_findings)
    assert any("三方验证" in item for item in job.next_steps)


def _bypass_paywall(monkeypatch):
    """Stub the paid-tier gate so endpoint-behavior tests don't need real auth.

    Auth enforcement itself is covered by test_osint_prediction_rejects_anonymous.
    """
    from backend.football_osint import routes

    monkeypatch.setattr(routes, "_require_paid", lambda http_request: {"id": 1, "role": "user"})


def test_osint_prediction_rejects_anonymous(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/football/osint/predict-sync",
        json={
            "home_team": "Home U23",
            "away_team": "Away U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "Friendly U23",
        },
    )

    assert response.status_code == 401


def test_osint_prediction_returns_job_for_paid_user(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("BING_API_KEY", raising=False)
    _bypass_paywall(monkeypatch)

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/football/osint/predict-sync",
        json={
            "home_team": "Home U23",
            "away_team": "Away U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "Friendly U23",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["prediction"]["lean"] in {
        "home", "away", "draw", "home_or_draw", "away_or_draw", "info_insufficient",
    }
    assert data["confidence"]["level"] in {"L1", "L2", "L3", "L4"}
    assert data["intelligence_cycle"][0]["name"] == "收集"
    assert data["alternative_explanations"]


def test_osint_answer_rejects_unrelated_question(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    _bypass_paywall(monkeypatch)

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/football/osint/answer",
        json={
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
            "question": "今天晚饭吃什么？",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["related"] is False
    assert data["answer"] == "问题与比赛无关"
    assert data["analysis_started"] is False
    assert data["reasons"] == []


def test_osint_answer_handles_twelve_concurrent_related_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))
    _bypass_paywall(monkeypatch)

    from backend.football_osint.routes import answer_question
    from backend.football_osint.models import FootballOsintJobRequest

    async def run_all():
        async def ask(index: int):
            return await answer_question(
                FootballOsintJobRequest(
                    home_team="Japan U23",
                    away_team="Korea U23",
                    kickoff_at="2026-06-08 18:00",
                    competition="AFC U23 Asian Cup",
                    question=f"这场比赛日本队胜面怎么样 {index}",
                ),
                None,
            )

        return await asyncio.gather(*(ask(i) for i in range(12)))

    results = asyncio.run(run_all())

    assert len(results) == 12
    assert all(result.related for result in results)
    assert all(result.analysis_started for result in results)
    assert all(result.answer for result in results)
    assert all(len(result.reasons) <= 3 for result in results)


def test_warm_cache_lru_eviction(monkeypatch):
    """Unified warm_cache evicts oldest entries when over _CACHE_MAX."""
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import (
        FootballOsintAnswer,
        FootballOsintJob,
        FootballOsintJobStatus,
        OsintMatch,
    )

    monkeypatch.setattr(warm_cache, "_CACHE_MAX", 3)

    def _entry(jid: str) -> warm_cache.CacheEntry:
        job = FootballOsintJob(
            job_id=jid, status=FootballOsintJobStatus.COMPLETED,
            phase="done", progress=100,
            match=OsintMatch(home_team="A", away_team="B"),
        )
        answer = FootballOsintAnswer(related=True, analysis_started=True, answer=f"A {jid}")
        return warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source="on-demand")

    for i in range(10):
        warm_cache._store_entry(f"key_{i}", _entry(f"job_{i}"))

    assert len(warm_cache._cache) == 3
    assert "key_0" not in warm_cache._cache
    assert "key_6" not in warm_cache._cache
    assert "key_9" in warm_cache._cache
    # Secondary index works for retained entries
    assert warm_cache.get_cached_by_job_id("job_9") is not None
    # Evicted entries are removed from secondary index
    assert warm_cache.get_cached_by_job_id("job_0") is None


def test_warm_cache_job_id_lookup(monkeypatch):
    """get_cached_by_job_id finds a cached job via the secondary index."""
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import (
        FootballOsintAnswer,
        FootballOsintJob,
        FootballOsintJobStatus,
        OsintMatch,
    )

    monkeypatch.setattr(warm_cache, "_CACHE_MAX", 64)

    job = FootballOsintJob(
        job_id="fo_lookup_test",
        status=FootballOsintJobStatus.COMPLETED,
        phase="done", progress=100,
        match=OsintMatch(home_team="X", away_team="Y"),
    )
    answer = FootballOsintAnswer(related=True, analysis_started=True, answer="lookup answer")
    entry = warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source="on-demand")
    warm_cache._store_entry("lookup_key", entry)

    found = warm_cache.get_cached_by_job_id("fo_lookup_test")
    assert found is not None
    assert found.job_id == "fo_lookup_test"

    assert warm_cache.get_cached_by_job_id("nonexistent") is None


# ── warm_cache module tests ──

def test_cache_key_preset_question():
    """Preset questions produce stable, readable keys."""
    from backend.football_osint import warm_cache

    key1 = warm_cache.cache_key("皇马", "巴萨", "06-22 22:00", "全场比分预测是多少？")
    key2 = warm_cache.cache_key("皇马", "巴萨", "06-22 22:00", "全场比分预测是多少？")
    assert key1 == key2
    assert "全场比分预测是多少？" in key1
    assert "free:" not in key1


def test_cache_key_free_text():
    """Free-text questions are hashed; identical text gives the same key."""
    from backend.football_osint import warm_cache

    key1 = warm_cache.cache_key("皇马", "巴萨", "06-22 22:00", "梅西会进球吗")
    key2 = warm_cache.cache_key("皇马", "巴萨", "06-22 22:00", "梅西会进球吗")
    assert key1 == key2
    assert "free:" in key1

    # Different questions give different keys
    key3 = warm_cache.cache_key("皇马", "巴萨", "06-22 22:00", "C罗会进球吗")
    assert key1 != key3


def test_job_metadata_classifies_preset_and_free_text_without_public_raw_text():
    from backend.football_osint import job_metadata
    from backend.football_osint.models import FootballOsintJobRequest

    preset = FootballOsintJobRequest(
        home_team="巴西",
        away_team="日本",
        kickoff_at="06-30 01:00",
        competition="世界杯",
        question="全场比分预测是多少？",
    )
    preset_payload = job_metadata.record_request_metadata(
        preset, warm_window="t-2h", cache_source="t-2h"
    )
    assert preset_payload["match_key"] == "巴西|日本|06-30 01:00"
    assert preset_payload["question_kind"] == "preset"
    assert preset_payload["question_id"] == "fulltime_score"
    assert preset_payload["question"] == "全场比分预测是多少？"

    free_text = FootballOsintJobRequest(
        home_team="巴西",
        away_team="日本",
        kickoff_at="06-30 01:00",
        question="我的私有笔记里有伤病线索，帮我判断",
        user_supplied={"notes": ["private note"], "injuries": [{}]},
    )
    free_payload = job_metadata.record_request_metadata(free_text)
    assert free_payload["question_kind"] == "free_text"
    assert free_payload["question_id"] == "free_text"
    assert free_payload["question"] == ""
    assert free_payload["question_hash"]
    assert free_payload["user_supplied_summary"] == {
        "injuries_count": 1,
        "lineups_count": 0,
        "notes_count": 1,
    }


def test_run_prediction_sync_persists_request_metadata(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))
    job = run_prediction_sync(
        {
            "home_team": "巴西",
            "away_team": "日本",
            "kickoff_at": "06-30 01:00",
            "competition": "世界杯",
            "question": "全场比分预测是多少？",
            "user_supplied": {"notes": ["private note"], "injuries": [{}]},
        },
        storage_root=tmp_path,
        warm_window="t-2h",
        cache_source="t-2h",
    )

    payload = json.loads((tmp_path / job.job_id / "request.json").read_text(encoding="utf-8"))
    assert payload["match_key"] == "巴西|日本|06-30 01:00"
    assert payload["question_kind"] == "preset"
    assert payload["question_id"] == "fulltime_score"
    assert payload["warm_window"] == "t-2h"
    assert payload["cache_source"] == "t-2h"
    assert payload["locale"] == "zh-CN"
    assert payload["user_supplied_summary"] == {
        "injuries_count": 1,
        "lineups_count": 0,
        "notes_count": 1,
    }


def test_is_preset_question():
    from backend.football_osint import warm_cache

    assert warm_cache.is_preset_question("全场比分预测是多少？") is True
    assert warm_cache.is_preset_question("  全场比分预测是多少？  ") is True
    assert warm_cache.is_preset_question("梅西会进球吗") is False
    assert warm_cache.is_preset_question("") is False


@pytest.mark.asyncio
async def test_cache_or_compute_caches_and_returns_consistent(monkeypatch):
    """First call computes, second call returns cached — same answer for both."""
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import FootballOsintJobRequest

    # Avoid real pipeline runs
    async def fake_compute(request, *, source="on-demand"):
        from backend.football_osint.models import (
            FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus,
            OsintMatch,
        )
        job = FootballOsintJob(
            job_id=f"test_{source}_job",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done", progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
        )
        answer = FootballOsintAnswer(
            related=True, analysis_started=True,
            answer=f"Cached answer for {request.question}",
        )
        entry = warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=source)
        key = warm_cache.cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
        async with warm_cache._lock:
            warm_cache._store_entry(key, entry)
        return entry

    monkeypatch.setattr(warm_cache, "_compute_and_cache", fake_compute)

    request = FootballOsintJobRequest(
        home_team="皇马", away_team="巴萨",
        kickoff_at="06-22 22:00", competition="西甲",
        question="全场比分预测是多少？",
    )

    # First call — should compute
    entry1 = await warm_cache.cache_or_compute(request)
    assert entry1 is not None
    assert "Cached answer" in entry1.answer.answer

    # Second call — should return cached (same job_id)
    entry2 = await warm_cache.cache_or_compute(request)
    assert entry2 is not None
    assert entry2.job.job_id == entry1.job.job_id


def test_warm_cache_key_separates_provider_identity():
    from backend.football_osint import warm_cache

    legacy = warm_cache.cache_key("科特迪瓦", "挪威", "07-01 01:00", "全场比分预测是多少？")
    provider = warm_cache.cache_key(
        "科特迪瓦",
        "挪威",
        "07-01 01:00",
        "全场比分预测是多少？",
        provider="football-data",
        provider_match_id="537424",
        home_provider_id="808",
        away_provider_id="816",
    )

    assert legacy != provider


@pytest.mark.asyncio
async def test_warm_run_forwards_fixture_provider_identity(monkeypatch):
    from datetime import datetime, timezone

    from backend.football_osint import warm_cache
    from backend.football_osint.adapters import football_data_schedule

    seen: list[tuple[str, str, str, str]] = []

    async def fake_force_refresh(request, *, window):
        import time
        from backend.football_osint.models import (
            FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus, OsintMatch,
        )

        seen.append((request.provider, request.provider_match_id, request.home_provider_id, request.away_provider_id))
        job = FootballOsintJob(
            job_id=f"warm_provider_{len(seen)}",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done",
            progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
        )
        answer = FootballOsintAnswer(related=True, analysis_started=True, answer="ok")
        return warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=window)

    monkeypatch.setattr(warm_cache, "_force_refresh", fake_force_refresh)
    fixture = football_data_schedule.Fixture(
        match_id="537424",
        league="世界杯",
        kickoff_at=datetime(2026, 6, 30, 17, 0, tzinfo=timezone.utc),
        home_team="科特迪瓦",
        away_team="挪威",
        status="scheduled",
        home_score=None,
        away_score=None,
        provider="football-data",
        provider_match_id="537424",
        home_provider_id="808",
        away_provider_id="816",
    )

    await warm_cache._run_analysis_for_match(fixture, window="t-5h")

    assert seen
    assert set(seen) == {("football-data", "537424", "808", "816")}


@pytest.mark.asyncio
async def test_cache_or_compute_dedup_inflight(monkeypatch):
    """Concurrent requests for the same key only run one pipeline."""
    import asyncio
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import FootballOsintJobRequest

    call_count = 0

    async def fake_compute(request, *, source="on-demand"):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # simulate work
        from backend.football_osint.models import (
            FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus,
            OsintMatch,
        )
        job = FootballOsintJob(
            job_id="dedup_test_job",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done", progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
        )
        answer = FootballOsintAnswer(related=True, analysis_started=True, answer="dedup answer")
        entry = warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=source)

        key = warm_cache.cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
        async with warm_cache._lock:
            warm_cache._store_entry(key, entry)
        return entry

    monkeypatch.setattr(warm_cache, "_compute_and_cache", fake_compute)

    request = FootballOsintJobRequest(
        home_team="皇马", away_team="巴萨",
        kickoff_at="06-22 22:00", competition="西甲",
        question="全场比分预测是多少？",
    )

    # Fire 5 concurrent requests — should only compute once
    results = await asyncio.gather(*[
        warm_cache.cache_or_compute(request) for _ in range(5)
    ])

    assert call_count == 1
    assert len(results) == 5
    for r in results:
        assert r.answer.answer == "dedup answer"


@pytest.mark.asyncio
async def test_warm_run_records_partial_status_and_successful_job_ids(monkeypatch, tmp_path):
    import json
    import threading
    import time
    from datetime import datetime, timezone

    from backend.auth import db as auth_db
    from backend.football_osint import warm_cache
    from backend.football_osint.adapters import football_data_schedule
    from backend.football_osint.models import (
        FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus, OsintMatch,
    )

    storage = tmp_path / "bronze_storage"
    storage.mkdir()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    conn = auth_db.get_db()

    async def fake_force_refresh(request, *, window):
        if request.question == warm_cache.PRESET_QUESTIONS[-1]:
            raise RuntimeError("boom")
        job = FootballOsintJob(
            job_id=f"fo_20260630_{len(request.question):010x}"[-22:],
            status=FootballOsintJobStatus.COMPLETED,
            phase="done",
            progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
        )
        answer = FootballOsintAnswer(related=True, analysis_started=True, answer="ok")
        return warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=window)

    monkeypatch.setattr(warm_cache, "_force_refresh", fake_force_refresh)
    fixture = football_data_schedule.Fixture(
        match_id="m1",
        league="世界杯",
        kickoff_at=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
        home_team="巴西",
        away_team="日本",
        status="scheduled",
        home_score=None,
        away_score=None,
    )

    assert await warm_cache._run_analysis_for_match(fixture, window="t-2h") == 5
    row = conn.execute(
        "SELECT * FROM warm_cache_run WHERE match_key='巴西|日本|06-30 20:00' AND window='t-2h'"
    ).fetchone()
    assert row["status"] == "partial"
    assert row["successful_questions"] == 5
    assert len(json.loads(row["job_ids_json"])) == 5


@pytest.mark.asyncio
async def test_warm_due_matches_skips_durably_completed_windows(monkeypatch, tmp_path):
    import threading
    from datetime import datetime, timedelta, timezone

    from backend.auth import db as auth_db
    from backend.football_osint import job_metadata, warm_cache
    from backend.football_osint.adapters import football_data_schedule

    storage = tmp_path / "bronze_storage"
    storage.mkdir()
    monkeypatch.setattr(auth_db, "STORAGE_ROOT", storage)
    monkeypatch.setattr(auth_db, "DB_PATH", storage / "_auth.db")
    monkeypatch.setattr(auth_db, "_local", threading.local())
    conn = auth_db.get_db()

    kickoff = datetime.now(timezone.utc) + timedelta(hours=1)
    kickoff_str = kickoff.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M")
    mk = job_metadata.match_key("巴西", "日本", kickoff_str)
    for window in ("t-5h", "t-2h"):
        conn.execute(
            "INSERT INTO warm_cache_run(match_key, window, home_team, away_team, kickoff_at, competition, status, successful_questions, finished_at) "
            "VALUES (?, ?, '巴西', '日本', ?, '世界杯', 'completed', 6, datetime('now'))",
            (mk, window, kickoff_str),
        )
    conn.commit()

    calls: list[str] = []

    async def fake_run(fixture, *, window):
        calls.append(window)
        return 6

    monkeypatch.setattr(warm_cache, "_run_analysis_for_match", fake_run)
    fixture = football_data_schedule.Fixture(
        match_id="m1",
        league="世界杯",
        kickoff_at=kickoff,
        home_team="巴西",
        away_team="日本",
        status="scheduled",
        home_score=None,
        away_score=None,
    )

    await warm_cache._warm_due_matches([fixture])
    assert calls == []


# ── endpoint tests: no 503 + consistency ──

def test_preset_question_no_longer_503(monkeypatch):
    """Preset question returns 200 even when cache is empty (no 503)."""
    import asyncio
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import FootballOsintJobRequest

    # Pre-populate the cache with a fake entry so the endpoint returns immediately
    async def fake_compute(request, *, source="on-demand"):
        from backend.football_osint.models import (
            FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus,
            OsintMatch,
        )
        job = FootballOsintJob(
            job_id="no_503_job",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done", progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
            prediction=None, confidence=None,
        )
        answer = FootballOsintAnswer(
            related=True, analysis_started=True,
            answer="预设问题即时回答",
        )
        return warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=source)

    monkeypatch.setattr(warm_cache, "_compute_and_cache", fake_compute)

    request = FootballOsintJobRequest(
        home_team="皇马", away_team="巴萨",
        kickoff_at="06-22 22:00", competition="西甲",
        question="全场比分预测是多少？",
    )

    # This should return a job without raising 503
    import asyncio
    entry = asyncio.run(warm_cache.cache_or_compute(request))
    assert entry is not None
    assert entry.job is not None


def test_free_text_cached_and_consistent(monkeypatch):
    """Same free-text question returns the same cached answer."""
    import asyncio
    import time

    from backend.football_osint import warm_cache
    from backend.football_osint.models import FootballOsintJobRequest

    compute_count = [0]

    async def fake_compute(request, *, source="on-demand"):
        compute_count[0] += 1
        from backend.football_osint.models import (
            FootballOsintAnswer, FootballOsintJob, FootballOsintJobStatus,
            OsintMatch,
        )
        job = FootballOsintJob(
            job_id=f"ft_{compute_count[0]}_job",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done", progress=100,
            match=OsintMatch(home_team=request.home_team, away_team=request.away_team),
        )
        answer = FootballOsintAnswer(
            related=True, analysis_started=True,
            answer=f"自由提问回答 #{compute_count[0]}",
        )
        entry = warm_cache.CacheEntry(job=job, answer=answer, cached_at=time.time(), source=source)
        key = warm_cache.cache_key(request.home_team, request.away_team, request.kickoff_at, request.question)
        async with warm_cache._lock:
            warm_cache._store_entry(key, entry)
        return entry

    monkeypatch.setattr(warm_cache, "_compute_and_cache", fake_compute)

    request = FootballOsintJobRequest(
        home_team="皇马", away_team="巴萨",
        kickoff_at="06-22 22:00", competition="西甲",
        question="梅西这场比赛状态如何？",
    )

    # First call computes
    entry1 = asyncio.run(warm_cache.cache_or_compute(request))
    assert compute_count[0] == 1

    # Second call returns cached (consistent!)
    entry2 = asyncio.run(warm_cache.cache_or_compute(request))
    assert compute_count[0] == 1  # NOT incremented
    assert entry1.answer.answer == entry2.answer.answer
    """football-data payload parses, translates via cache, and drops finished/past."""
    from datetime import datetime, timedelta, timezone

    from backend.football_osint.adapters import football_data_schedule as fds

    # Stub translation so the test needs no LLM/disk.
    monkeypatch.setattr(fds.name_translation, "translate", lambda names: {n: n for n in names})

    future = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "matches": [
            {
                "id": 1, "utcDate": future, "status": "TIMED",
                "competition": {"name": "FIFA World Cup"},
                "homeTeam": {"name": "Brazil"}, "awayTeam": {"name": "Serbia"},
                "score": {"fullTime": {"home": None, "away": None}},
            },
            {
                "id": 2, "utcDate": "2020-01-01T00:00:00Z", "status": "FINISHED",
                "competition": {"name": "Premier League"},
                "homeTeam": {"name": "Arsenal"}, "awayTeam": {"name": "Chelsea"},
                "score": {"fullTime": {"home": 2, "away": 1}},
            },
        ]
    }

    fixtures = fds.parse_matches(payload)
    assert len(fixtures) == 2

    upcoming = fds.upcoming(fixtures)
    assert [f.match_id for f in upcoming] == ["1"]
    assert upcoming[0].status == "scheduled"


def test_football_data_fetch_returns_empty_without_key(monkeypatch):
    from backend.football_osint.adapters import football_data_schedule as fds

    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    assert fds.fetch_fixtures() == []


def test_name_translation_falls_back_to_english_without_llm(monkeypatch, tmp_path):
    from backend.football_osint.adapters import name_translation as nt

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(nt, "_CACHE_PATH", tmp_path / "names.json")

    result = nt.translate(["Real Madrid", "Barcelona"])
    assert result == {"Real Madrid": "Real Madrid", "Barcelona": "Barcelona"}


def test_cn_search_collects_evidence_with_correct_topics(monkeypatch, tmp_path):
    """Chinese search produces evidence with search.cn.* topics, DDG-only."""
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    call_count = {"n": 0}

    def fake_search(query, **kwargs):
        call_count["n"] += 1
        # Only 1 primary query with CN_DOMAINS (Sogou, DDG doesn't index Chinese well)
        if call_count["n"] == 1:
            assert "前瞻" in query
        return [
            {
                "title": f"巴西vs阿根廷世界杯前瞻 {call_count['n']}",
                "url": f"https://sports.sina.com.cn/article/{call_count['n']}",
                "snippet": "巴西近5场3胜1平1负，阿根廷近5场2胜2平1负，双方比赛阵容待定。",
            },
        ]

    monkeypatch.setattr(web_search, "search", fake_search)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    _collect_chinese_search(request, evidence, sources)

    assert len(evidence) >= 1
    assert evidence[0].topic == "search.cn.preview"
    assert evidence[0].source == "国内媒体搜索"
    assert sources[0].adapter == "cn_search"
    assert sources[0].status == "ok"


def test_cn_search_drops_country_encyclopedia_results(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    def fake_search(query, **kwargs):
        return [
            {"title": "科特迪瓦_百度百科", "url": "https://baike.baidu.com/item/x", "snippet": "科特迪瓦共和国位于西非。"},
            {"title": "国家概况_中华人民共和国外交部", "url": "https://www.mfa.gov.cn/x", "snippet": "科特迪瓦国家概况。"},
            {"title": "关于科特迪瓦的一切 - 知乎", "url": "https://zhuanlan.zhihu.com/p/x", "snippet": "科特迪瓦国土面积。"},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    request = FootballOsintJobRequest(home_team="科特迪瓦", away_team="挪威", kickoff_at="07-01 01:00", competition="世界杯")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    stats = _collect_chinese_search(request, evidence, sources)

    assert evidence == []
    assert stats.relevant_count == 0
    assert stats.dropped_count >= 3
    assert sources[0].adapter == "cn_search"
    assert sources[0].status == "skipped"
    assert "无相关中文搜索结果" in sources[0].reason


def test_cn_search_accepts_relevant_match_preview_and_dedupes(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    result = {
        "title": "巴西vs阿根廷世界杯前瞻：阵容伤停与历史交锋",
        "url": "https://sports.sina.com.cn/preview/bra-arg",
        "snippet": "巴西和阿根廷将在世界杯交锋，内马尔缺席，梅西领衔首发。",
    }

    def fake_search(query, **kwargs):
        return [result, dict(result)]

    monkeypatch.setattr(web_search, "search", fake_search)
    request = FootballOsintJobRequest(home_team="巴西", away_team="阿根廷", kickoff_at="06-20 20:00", competition="世界杯")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    stats = _collect_chinese_search(request, evidence, sources)

    assert len(evidence) == 1
    assert evidence[0].topic == "search.cn.preview"
    assert stats.relevant_count == 1
    assert stats.dropped_count >= 1
    assert sources[0].status == "ok"


def test_cn_search_drops_two_country_non_football_results(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    def fake_search(query, **kwargs):
        return [
            {
                "title": "科特迪瓦 挪威 旅游签证地图指南",
                "url": "https://example.com/country-guide",
                "snippet": "科特迪瓦和挪威人口、经济、历史、地理信息汇总。",
            },
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    request = FootballOsintJobRequest(home_team="科特迪瓦", away_team="挪威", kickoff_at="07-01 01:00", competition="世界杯")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    stats = _collect_chinese_search(request, evidence, sources)

    assert evidence == []
    assert stats.relevant_count == 0
    assert stats.dropped_count >= 1


def test_cn_form_regex_extracts_ppg_from_chinese_snippets():
    """_score_cn_form parses '近N场X胜Y平Z负' patterns from media text."""
    from backend.football_osint.factor_registry import _score_cn_form
    from backend.football_osint.models import FootballOsintJobRequest

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )

    # Brazil: 5 games, 4W 1D 0L → PPG = 2.6; Argentina: 5 games, 2W 1D 2L → PPG = 1.4
    text = "巴西近5场4胜1平0负，状态火热。阿根廷近5场2胜1平2负。"
    score = _score_cn_form(text, request)
    assert score > 0  # home advantage

    # Reversed: Argentina better
    text2 = "阿根廷最近5场4胜1平0负。巴西近5场1胜1平3负。"
    score2 = _score_cn_form(text2, request)
    assert score2 < 0  # away advantage


def test_cn_form_returns_zero_when_no_match():
    """_score_cn_form returns 0.0 when team names don't appear in text."""
    from backend.football_osint.factor_registry import _score_cn_form
    from backend.football_osint.models import FootballOsintJobRequest

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    assert _score_cn_form("这场比赛很精彩", request) == 0.0
    assert _score_cn_form("", request) == 0.0


def test_form_score_from_records_favours_better_ppg():
    from backend.football_osint.factor_registry import _form_score_from_records

    # Home: 4W1D0L → PPG 2.6; Away: 2W1D2L → PPG 1.4 → diff 1.2 * 0.10 = 0.12
    score = _form_score_from_records((4, 1, 0), (2, 1, 2))
    assert score == 0.12


def test_form_score_from_records_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _form_score_from_records

    assert _form_score_from_records(None, (2, 1, 2)) == 0.0
    assert _form_score_from_records((4, 1, 0), None) == 0.0


def test_h2h_score_from_counts_favours_home_wins():
    from backend.football_osint.factor_registry import _h2h_score_from_counts

    # 3 wins, 1 loss → advantage (3-1)/4 = 0.5 * 0.12 = 0.06
    score = _h2h_score_from_counts(3, 1)
    assert score == 0.06


def test_h2h_score_from_counts_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _h2h_score_from_counts

    assert _h2h_score_from_counts(None, 1) == 0.0
    assert _h2h_score_from_counts(3, None) == 0.0


def test_squad_score_from_absences_favours_fewer_absences():
    from backend.football_osint.factor_registry import _squad_score_from_absences

    # away has 2 more absences → (2)*0.03 = 0.06
    score = _squad_score_from_absences(1, 3)
    assert score == 0.06


def test_squad_score_from_absences_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _squad_score_from_absences

    assert _squad_score_from_absences(None, 3) == 0.0
    assert _squad_score_from_absences(1, None) == 0.0


def test_standings_score_from_ranks_favours_better_rank():
    from backend.football_osint.factor_registry import _standings_score_from_ranks

    # home rank 2, away rank 5 → (5-2)*0.015 = 0.045
    score = _standings_score_from_ranks(2, 5)
    assert score == 0.045


def test_standings_score_from_ranks_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _standings_score_from_ranks

    assert _standings_score_from_ranks(None, 5) == 0.0
    assert _standings_score_from_ranks(2, None) == 0.0


def test_media_cn_coverage_factor_enables_with_enough_evidence(monkeypatch, tmp_path):
    """media.cn_coverage factor enables when ≥3 Chinese search evidence items exist."""
    from backend.football_osint.adapters import web_search
    from backend.football_osint.models import FootballOsintJobStatus

    def fake_search(query, **kwargs):
        return [
            {"title": "巴西vs阿根廷赛前分析 1", "url": "https://sports.sina.com.cn/1", "snippet": "巴西和阿根廷世界杯比赛前瞻，巴西近5场3胜1平1负"},
            {"title": "巴西vs阿根廷赛前分析 2", "url": "https://sports.qq.com/2", "snippet": "巴西对阿根廷阵容预测，阿根廷近5场2胜2平1负"},
            {"title": "巴西vs阿根廷赛前分析 3", "url": "https://zhibo8.com/3", "snippet": "巴西与阿根廷历史交锋和世界杯赛前报道"},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))

    job = run_prediction_sync(
        {
            "home_team": "巴西",
            "away_team": "阿根廷",
            "kickoff_at": "2026-06-20 20:00",
            "competition": "世界杯",
        },
        storage_root=tmp_path,
    )

    assert job.status == FootballOsintJobStatus.COMPLETED
    # CN search adapter should appear in sources
    cn_source = next((s for s in job.sources if s.adapter == "cn_search"), None)
    assert cn_source is not None
    assert cn_source.status == "ok"
    # media.cn_coverage factor should be enabled (≥3 evidence items from fake_search)
    media_factor = next((f for f in job.factors if f.factor_id == "media.cn_coverage"), None)
    assert media_factor is not None
    assert media_factor.enabled is True
    # Chinese search evidence should exist
    cn_evidence = [ev for ev in job.evidence if ev.topic.startswith("search.cn.")]
    assert len(cn_evidence) >= 3


def test_targeted_cn_queries_generates_dimension_specific_searches():
    """_targeted_cn_queries produces Chinese queries for detected dimensions."""
    from backend.football_osint.pipeline import _targeted_cn_queries

    # Injury/lineup question
    queries = _targeted_cn_queries("主力球员伤病情况怎么样？", "巴西", "阿根廷")
    assert any("伤病" in q or "阵容" in q for q in queries)

    # Goals question
    queries = _targeted_cn_queries("这场比赛进球数会多吗？", "巴西", "阿根廷")
    assert any("进球" in q or "统计" in q for q in queries)

    # No dimension keywords → empty
    queries = _targeted_cn_queries("这场比赛谁会赢", "巴西", "阿根廷")
    assert queries == []


def test_cn_search_executes_question_and_targeted_queries_without_bare_team_fallback(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus
    from backend.football_osint.pipeline import _collect_chinese_search

    calls: list[str] = []

    def fake_search(query, **kwargs):
        calls.append(query)
        return []

    monkeypatch.setattr(web_search, "search", fake_search)

    request = FootballOsintJobRequest(
        home_team="巴西",
        away_team="阿根廷",
        kickoff_at="2026-06-20 20:00",
        competition="世界杯",
        question="角球和红黄牌怎么判断？",
    )

    _collect_chinese_search(request, [], [])

    assert calls
    assert "巴西 阿根廷" not in calls
    assert any("角球" in query for query in calls)
    assert any("红黄牌" in query or "犯规" in query for query in calls)


def test_ddg_queries_for_country_names_keep_football_context(monkeypatch):
    from backend.football_osint.adapters import name_translation, web_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus
    from backend.football_osint.pipeline import _collect_ddg_search
    from backend.football_osint.sources import SEARCH_SOURCE_TEMPLATES

    calls: list[str] = []

    def fake_search(query, **kwargs):
        calls.append(query)
        return []

    monkeypatch.setattr(name_translation, "to_english", lambda value: value)
    monkeypatch.setattr(web_search, "search", fake_search)

    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
        competition="AFC Asian Cup",
        question="角球和红黄牌怎么判断？",
    )
    _collect_ddg_search(SEARCH_SOURCE_TEMPLATES[0], "Jordan", "South Korea", request, [], [])

    assert calls
    assert all("football" in query.lower() or "soccer" in query.lower() for query in calls)


def test_english_targeted_queries_keep_football_context_for_multiword_teams():
    from backend.football_osint.pipeline import _targeted_queries

    queries = _targeted_queries("角球和红黄牌怎么判断？", "New Zealand", "Costa Rica")

    assert queries
    assert all("football" in query.lower() or "soccer" in query.lower() for query in queries)


def test_ddg_search_drops_results_that_only_match_one_country(monkeypatch):
    from backend.football_osint.adapters import name_translation, web_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus
    from backend.football_osint import pipeline
    from backend.football_osint.sources import SEARCH_SOURCE_TEMPLATES

    def fake_search(query, **kwargs):
        return [
            {
                "title": "Jordan country profile",
                "url": "https://example.com/jordan-country",
                "snippet": "Population and travel information.",
            },
            {
                "title": "Jordan vs South Korea football preview",
                "url": "https://example.com/jordan-south-korea-football",
                "snippet": "Lineups and recent form for both teams.",
            },
        ]

    monkeypatch.setattr(name_translation, "to_english", lambda value: value)
    monkeypatch.setattr(web_search, "search", fake_search)
    monkeypatch.setattr(pipeline, "_fetch_top_pages", lambda *args, **kwargs: [])

    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
        competition="AFC Asian Cup",
    )

    pipeline._collect_ddg_search(SEARCH_SOURCE_TEMPLATES[0], "Jordan", "South Korea", request, evidence, sources)

    urls = {item.url for item in evidence}
    assert "https://example.com/jordan-country" not in urls
    assert "https://example.com/jordan-south-korea-football" in urls


def test_cn_sports_rss_templates_loaded():
    """CN sports RSS templates are included in RSS_FEED_TEMPLATES."""
    from backend.football_osint.sources import RSS_FEED_TEMPLATES

    adapters = {source.adapter for source in RSS_FEED_TEMPLATES}
    expected = {"rss_hupu_soccer", "rss_dongqiudi_daily",
                "rss_dongqiudi_intl", "rss_dongqiudi_special"}
    assert expected <= adapters

    # All CN sports templates use the RSSHub base URL
    for source in RSS_FEED_TEMPLATES:
        if source.adapter in expected:
            assert "127.0.0.1:1200" in source.url_template or "rsshub" in source.url_template


def test_media_cn_coverage_counts_rss_evidence(monkeypatch, tmp_path):
    """media.cn_coverage factor enables when RSS + search evidence >= 3."""
    from backend.football_osint.adapters import web_search

    def fake_search(query, **kwargs):
        return [
            {"title": "巴西vs阿根廷国内媒体分析 1", "url": "https://sports.sina.com.cn/a", "snippet": "巴西和阿根廷世界杯赛前分析"},
            {"title": "巴西vs阿根廷国内媒体分析 2", "url": "https://sports.qq.com/b", "snippet": "巴西对阿根廷阵容预测"},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    monkeypatch.setenv("FOOTBALL_OSINT_LIGHTPANDA_BIN", str(tmp_path / "missing-lp-fetch-md"))

    # Inject synthetic CN RSS evidence via rss_adapter.collect_all mock
    from backend.football_osint.adapters import rss_feed

    orig_collect_all = rss_feed.collect_all

    def fake_rss_collect(request, evidence):
        from backend.football_osint.evidence import append_evidence
        # Call original first (may fail without RSSHub)
        try:
            orig_collect_all(request, evidence)
        except Exception:
            pass
        # Inject synthetic Chinese RSS evidence
        append_evidence(evidence, source="虎扑足球", source_type="news",
                        claim="巴西备战状态良好", topic="news.rss.hupu.soccer",
                        side="neutral", confidence=0.30,
                        raw_excerpt="巴西队近期训练状态出色。")
        append_evidence(evidence, source="懂球帝早报", source_type="news",
                        claim="阿根廷主力后卫疑似受伤", topic="news.rss.dongqiudi.daily",
                        side="neutral", confidence=0.30,
                        raw_excerpt="阿根廷主力后卫在训练中感到不适。")
        return [("rss_hupu_soccer", "ok", 1), ("rss_dongqiudi_daily", "ok", 1)]

    monkeypatch.setattr(rss_feed, "collect_all", fake_rss_collect)

    job = run_prediction_sync(
        {
            "home_team": "巴西",
            "away_team": "阿根廷",
            "kickoff_at": "2026-06-20 20:00",
            "competition": "世界杯",
        },
        storage_root=tmp_path,
    )

    assert job.status.value == "completed"

    # media.cn_coverage should be enabled: 2 search + 2 RSS = 4 total >= 3
    media_factor = next((f for f in job.factors if f.factor_id == "media.cn_coverage"), None)
    assert media_factor is not None
    assert media_factor.enabled is True

    # CN evidence should include both search and RSS
    cn_evidence = [ev for ev in job.evidence if (
        ev.topic.startswith("search.cn.")
        or ev.topic.startswith("news.rss.hupu.")
        or ev.topic.startswith("news.rss.dongqiudi.")
        or ev.topic.startswith("news.rss.weibo.")
    )]
    assert len(cn_evidence) >= 4


def test_build_factors_uses_llm_extraction_when_available(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.analysis import evidence_extraction as ee
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence

    fake_facts = ee.ExtractedFacts(
        home_form=(4, 1, 0), away_form=(2, 1, 2),
        h2h_home_wins=3, h2h_draws=1, h2h_home_losses=1,
        home_absences=1, away_absences=3,
        home_rank=2, away_rank=5,
    )
    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: fake_facts)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    # No fundamental.* evidence at all — this is the case that's broken today.
    evidence = [OsintEvidence(
        id="ev_001", source="国内媒体搜索", source_type="search",
        claim="赛前分析", topic="search.cn.preview", side="neutral",
        confidence=0.28, raw_excerpt="巴西近期表现出色",
    )]

    factors = fr.build_factors(request, profile, evidence)
    form_factor = next(f for f in factors if f.factor_id == "form.recent_signal")
    h2h_factor = next(f for f in factors if f.factor_id == "h2h.relevance")
    squad_factor = next(f for f in factors if f.factor_id == "squad.availability")

    assert form_factor.enabled is True
    assert form_factor.direction == "home"  # Brazil's PPG is higher
    assert h2h_factor.enabled is True
    assert h2h_factor.direction == "home"  # 3W1L for home in H2H
    assert squad_factor.enabled is True
    assert squad_factor.direction == "home"  # away has more absences


def test_build_factors_llm_extraction_attributes_evidence_ids_for_squad_and_h2h(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.analysis import evidence_extraction as ee
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence

    fake_facts = ee.ExtractedFacts(
        home_form=(4, 1, 0), away_form=(2, 1, 2),
        h2h_home_wins=3, h2h_draws=1, h2h_home_losses=1,
        home_absences=1, away_absences=3,
        home_rank=2, away_rank=5,
    )
    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: fake_facts)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    # Only search/news evidence — no fundamental.* evidence at all. The LLM
    # extraction can still pull absence/H2H facts out of this evidence, so
    # the resulting factors must trace back to it via evidence_ids.
    evidence = [
        OsintEvidence(
            id="ev_search_001", source="国内媒体搜索", source_type="search",
            claim="赛前分析：阿根廷多名主力缺席", topic="search.cn.preview", side="away",
            confidence=0.28, raw_excerpt="阿根廷因伤病多名主力缺席",
        ),
        OsintEvidence(
            id="ev_news_001", source="虎扑", source_type="news",
            claim="历史交锋：巴西近期占优", topic="news.rss.hupu.soccer", side="home",
            confidence=0.30, raw_excerpt="历史交锋巴西3胜1平1负",
        ),
    ]

    factors = fr.build_factors(request, profile, evidence)
    squad_factor = next(f for f in factors if f.factor_id == "squad.availability")
    h2h_factor = next(f for f in factors if f.factor_id == "h2h.relevance")

    assert squad_factor.enabled is True
    assert squad_factor.evidence_ids != []

    assert h2h_factor.enabled is True
    assert h2h_factor.evidence_ids != []


def test_build_factors_falls_back_to_regex_when_llm_extraction_fails(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence

    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: None)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    evidence = [OsintEvidence(
        id="ev_001", source="懂球帝赛前分析", source_type="fundamental",
        claim="赛前分析", topic="fundamental.dongqiudi.analysis", side="neutral",
        confidence=0.5,
        raw_excerpt="巴西近期战绩：4胜1平0负\n阿根廷近期战绩：2胜1平2负",
    )]

    factors = fr.build_factors(request, profile, evidence)
    form_factor = next(f for f in factors if f.factor_id == "form.recent_signal")
    assert form_factor.enabled is True
    assert form_factor.direction == "home"


def test_weather_score_from_raw_excerpt_penalises_heavy_rain():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt
    import json as _json

    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [90], "wind_speed_10m_max": [10],
        "temperature_2m_max": [22], "temperature_2m_min": [15], "weather_code": [65],
    }})
    score = _weather_score_from_raw_excerpt(raw)
    assert score < 0  # heavy rain → negative (lower-scoring, less predictable match)


def test_weather_score_from_raw_excerpt_neutral_for_calm_weather():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt
    import json as _json

    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [5], "wind_speed_10m_max": [8],
        "temperature_2m_max": [20], "temperature_2m_min": [12], "weather_code": [1],
    }})
    score = _weather_score_from_raw_excerpt(raw)
    assert score == 0.0


def test_weather_score_from_raw_excerpt_returns_zero_on_bad_json():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt

    assert _weather_score_from_raw_excerpt("not json") == 0.0
    assert _weather_score_from_raw_excerpt("") == 0.0


def test_weather_score_from_raw_excerpt_returns_zero_on_non_numeric_values():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt
    import json as _json

    raw = _json.dumps({"daily": {
        "precipitation_probability_max": ["heavy"], "wind_speed_10m_max": ["strong"],
    }})
    assert _weather_score_from_raw_excerpt(raw) == 0.0


def test_weather_score_from_raw_excerpt_returns_zero_on_top_level_list():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt

    assert _weather_score_from_raw_excerpt("[1,2,3]") == 0.0


def test_weather_factor_reflects_real_precipitation(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence
    import json as _json

    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: None)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [90], "wind_speed_10m_max": [10],
        "temperature_2m_max": [22], "temperature_2m_min": [15], "weather_code": [65],
    }})
    evidence = [OsintEvidence(
        id="ev_001", source="Open-Meteo", source_type="weather",
        claim="比赛日天气: 雨", topic="weather.open_meteo", side="neutral",
        confidence=0.55, raw_excerpt=raw,
    )]

    factors = fr.build_factors(request, profile, evidence)
    weather_factor = next(f for f in factors if f.factor_id == "weather.exposure")
    assert weather_factor.enabled is True
    assert weather_factor.impact == -0.03


@pytest.mark.asyncio
async def test_get_job_route_falls_back_to_bronze_status_when_cache_misses(monkeypatch, tmp_path):
    from backend.football_osint import routes, warm_cache, history as h_mod
    from backend.football_osint.models import (
        FootballOsintJob,
        FootballOsintJobStatus,
        OsintMatch,
        PredictionResult,
        ConfidenceRating,
    )

    job_id = "fo_20260630_abcdef1234"
    root = tmp_path / "football_osint"
    job_dir = root / job_id
    job_dir.mkdir(parents=True)
    job = FootballOsintJob(
        job_id=job_id,
        status=FootballOsintJobStatus.COMPLETED,
        progress=100,
        match=OsintMatch(home_team="巴西", away_team="日本", kickoff_at="06-30 01:00"),
        prediction=PredictionResult(lean="home", summary="主队占优", probability_band={}, scoreline_band=[]),
        confidence=ConfidenceRating(level="L2", reason="证据较充分"),
        report_markdown="# 报告\n",
    )
    (job_dir / "status.json").write_text(job.model_dump_json(), encoding="utf-8")
    (job_dir / "report.md").write_text("# 报告\n", encoding="utf-8")

    monkeypatch.setattr(warm_cache, "get_cached_by_job_id", lambda jid: None)
    monkeypatch.setattr(h_mod, "DEFAULT_STORAGE_ROOT", root)
    monkeypatch.setattr(routes, "_require_paid", lambda request: {"id": 1})

    loaded = await routes.get_job(job_id, object())
    report = await routes.get_report(job_id, object())

    assert loaded.job_id == job_id
    assert loaded.match.home_team == "巴西"
    assert report == "# 报告\n"


@pytest.mark.asyncio
async def test_compare_route_rejects_distinct_jobs_for_same_match(monkeypatch):
    from fastapi import HTTPException
    from backend.football_osint import routes

    first = "fo_20260630_aaaaaaaaaa"
    second = "fo_20260630_bbbbbbbbbb"
    monkeypatch.setattr(routes, "_require_paid", lambda request: {"id": 1})
    monkeypatch.setattr(
        routes.history_module,
        "match_keys_for_job_ids",
        lambda job_ids: {first: "巴西|日本|06-30 01:00", second: "巴西|日本|06-30 01:00"},
    )

    with pytest.raises(HTTPException) as exc:
        await routes.compare_matches(routes.CompareRequest(job_ids=[first, second]), object())

    assert exc.value.status_code == 422
    assert "同一场比赛" in exc.value.detail

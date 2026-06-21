from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.football_osint.models import FootballOsintJobStatus
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
    monkeypatch.setenv("OSINT_ROLE", "api")
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
    monkeypatch.setenv("OSINT_ROLE", "api")
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
    monkeypatch.setenv("OSINT_ROLE", "api")
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


def test_job_cache_evicts_old_entries_under_capacity():
    from backend.football_osint.routes import _JobCache
    from backend.football_osint.models import (
        FootballOsintJob,
        FootballOsintJobStatus,
        OsintMatch,
    )

    cache = _JobCache(max_size=3, ttl_seconds=3600)

    def _job(job_id: str) -> FootballOsintJob:
        return FootballOsintJob(
            job_id=job_id,
            status=FootballOsintJobStatus.COMPLETED,
            phase="done",
            progress=100,
            match=OsintMatch(home_team="A", away_team="B"),
        )

    for i in range(10):
        cache.set(f"fo_{i}", _job(f"fo_{i}"))

    assert len(cache) == 3
    assert cache.get("fo_0") is None
    assert cache.get("fo_6") is None
    assert cache.get("fo_9") is not None


def test_job_cache_drops_expired_entries():
    import time

    from backend.football_osint.routes import _JobCache
    from backend.football_osint.models import (
        FootballOsintJob,
        FootballOsintJobStatus,
        OsintMatch,
    )

    cache = _JobCache(max_size=8, ttl_seconds=1)
    cache.set(
        "fo_short",
        FootballOsintJob(
            job_id="fo_short",
            status=FootballOsintJobStatus.COMPLETED,
            phase="done",
            progress=100,
            match=OsintMatch(home_team="A", away_team="B"),
        ),
    )
    assert cache.get("fo_short") is not None
    time.sleep(1.1)
    assert cache.get("fo_short") is None


def test_football_data_parse_and_upcoming_filter(monkeypatch):
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
            {"title": f"搜索结果 {call_count['n']}", "url": f"https://sports.sina.com.cn/article/{call_count['n']}", "snippet": "巴西近5场3胜1平1负"},
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
            {"title": "赛前分析 1", "url": "https://sports.sina.com.cn/1", "snippet": "巴西近5场3胜1平1负"},
            {"title": "赛前分析 2", "url": "https://sports.qq.com/2", "snippet": "阿根廷近5场2胜2平1负"},
            {"title": "赛前分析 3", "url": "https://zhibo8.com/3", "snippet": "双方历史交锋巴西占优"},
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
            {"title": "国内媒体分析 1", "url": "https://sports.sina.com.cn/a", "snippet": "赛前分析"},
            {"title": "国内媒体分析 2", "url": "https://sports.qq.com/b", "snippet": "阵容预测"},
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

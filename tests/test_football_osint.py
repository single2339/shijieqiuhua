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
    assert data["prediction"]["lean"] in {"home", "away", "draw", "home_or_draw", "away_or_draw"}
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

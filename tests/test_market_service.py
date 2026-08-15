from __future__ import annotations

from datetime import datetime, timezone

from backend.football_osint import market_service
from backend.football_osint.analysis.prediction import predict
from backend.football_osint.models import (
    FactorImpact,
    FootballOsintJobRequest,
    MarketSourceSnapshot,
    OutcomeOdds,
    OutcomeProbabilities,
    SportteryMarket,
)


NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def _snapshot(source_id: str, *, home: float = 2.1) -> MarketSourceSnapshot:
    odds = OutcomeOdds(home_win=home, draw=3.4, away_win=3.8)
    return MarketSourceSnapshot(
        source_id=source_id,
        display_name=source_id,
        odds=odds,
        implied_probabilities=OutcomeProbabilities(
            home_win=0.46,
            draw=0.29,
            away_win=0.25,
        ),
        observed_at=NOW,
    )


def _sporttery_market() -> SportteryMarket:
    return SportteryMarket(
        had_odds=OutcomeOdds(home_win=2.0, draw=3.5, away_win=4.0),
        had_implied_probabilities=OutcomeProbabilities(
            home_win=0.48,
            draw=0.28,
            away_win=0.24,
        ),
        home_handicap=1,
        hhad_odds=OutcomeOdds(home_win=1.8, draw=3.8, away_win=4.2),
        hhad_implied_probabilities=OutcomeProbabilities(
            home_win=0.52,
            draw=0.25,
            away_win=0.23,
        ),
        observed_at=NOW.isoformat(),
    )


def test_build_context_uses_three_distinct_fresh_sources_and_preserves_handicap():
    context = market_service.build_market_context(
        _sporttery_market(),
        [_snapshot("pinnacle"), _snapshot("bet365", home=2.2)],
        now=NOW,
    )

    assert [snapshot.source_id for snapshot in context.snapshots] == [
        "sporttery", "pinnacle", "bet365",
    ]
    assert context.consensus is not None
    assert context.consensus.status == "consensus"
    assert context.consensus.fresh_source_count == 3
    assert context.handicap_snapshots[0].home_handicap == 1


def test_build_context_marks_two_sources_as_insufficient_without_probabilities():
    request = FootballOsintJobRequest(home_team="主队", away_team="客队")
    factors = [
        FactorImpact(
            factor_id="form", label="状态", group="form", enabled=True,
            weight=0.3, impact=0.2, direction="home", confidence=0.8,
        )
    ]
    prediction_without_market = predict(request, factors)
    context = market_service.build_market_context(
        _sporttery_market(),
        [_snapshot("pinnacle")],
        now=NOW,
    )

    assert context.consensus is not None
    assert context.consensus.status == "insufficient_sources"
    assert context.consensus.probabilities is None

    assert predict(request, factors) == prediction_without_market


def test_licensed_market_status_degrades_cleanly_when_key_is_not_configured():
    status = market_service.licensed_market_source_status(
        [],
        "未配置授权赔率数据服务",
    )

    assert status.adapter == "theoddsapi"
    assert status.status == "skipped"
    assert status.reason == "未配置授权赔率数据服务"


def test_market_provider_states_do_not_change_osint_artifacts(monkeypatch, tmp_path):
    from backend.football_osint import pipeline

    factors = [
        FactorImpact(
            factor_id="form", label="状态", group="form", enabled=True,
            weight=0.3, impact=0.2, direction="home", confidence=0.8,
        )
    ]
    monkeypatch.setattr(pipeline, "_collect_farich_foot_sources", lambda *args: None)
    monkeypatch.setattr(pipeline, "_collect_one_weather", lambda *args: ("", "disabled"))
    monkeypatch.setattr(
        pipeline,
        "_collect_search_sources",
        lambda *args: pipeline.data_quality_module.SearchQualityStats(),
    )
    monkeypatch.setattr(pipeline.rss_adapter, "collect_all", lambda *args: [])
    monkeypatch.setattr(pipeline, "_collect_football_data_stats", lambda *args: None)
    monkeypatch.setattr(pipeline, "_collect_sporttery", lambda *args: (None, "", "体彩未覆盖该场比赛"))
    monkeypatch.setattr(pipeline.factor_registry_module, "build_factors", lambda *args: factors)

    def run(snapshots, reason):
        monkeypatch.setattr(
            pipeline.theoddsapi_adapter,
            "collect",
            lambda request: (snapshots, reason),
        )
        return pipeline.run_prediction_sync(
            {"home_team": "主队", "away_team": "客队", "competition": "英超"},
            storage_root=tmp_path,
        )

    success = run([_snapshot("pinnacle"), _snapshot("bet365"), _snapshot("williamhill")], "")
    no_key = run([], "未配置授权赔率数据服务")
    timeout = run([], "授权赔率数据服务请求超时")

    for job in (no_key, timeout):
        assert job.prediction == success.prediction
        assert job.confidence == success.confidence
        assert job.data_quality == success.data_quality
        assert job.intelligence_cycle == success.intelligence_cycle
        assert job.report_markdown == success.report_markdown

    assert next(source for source in success.sources if source.adapter == "theoddsapi").status == "ok"
    assert next(source for source in no_key.sources if source.adapter == "theoddsapi").status == "skipped"
    assert next(source for source in timeout.sources if source.adapter == "theoddsapi").status == "failed"
    assert success.market_context is not None
    assert success.market_context.consensus is not None
    assert no_key.market_context != success.market_context

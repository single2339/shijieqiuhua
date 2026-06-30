"""Tests for the info_insufficient wording split by time-to-kickoff."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.football_osint.analysis.prediction import predict
from backend.football_osint.models import FactorImpact, FootballOsintJobRequest
from backend.football_osint.factor_registry import build_factors
from backend.football_osint.models import MatchProfile, OsintEvidence

_CST = timezone(timedelta(hours=8))

_NO_SIGNAL_FACTORS = [
    FactorImpact(
        factor_id="fixture.existence", label="比赛验证", group="fixture",
        enabled=True, weight=0.14, impact=0.0, confidence=0.58,
    ),
]


def _request(kickoff_at: str) -> FootballOsintJobRequest:
    return FootballOsintJobRequest(home_team="A队", away_team="B队", kickoff_at=kickoff_at)


def test_info_insufficient_far_from_kickoff_uses_softer_wording():
    far_kickoff = (datetime.now(_CST) + timedelta(days=5)).strftime("%Y-%m-%d %H:%M")

    result = predict(_request(far_kickoff), _NO_SIGNAL_FACTORS)

    assert result.lean == "info_insufficient"
    assert "暂未发布" in result.summary
    assert "开赛前 1-2 天" in result.summary


def test_info_insufficient_near_kickoff_uses_coverage_gap_wording():
    near_kickoff = (datetime.now(_CST) + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")

    result = predict(_request(near_kickoff), _NO_SIGNAL_FACTORS)

    assert result.lean == "info_insufficient"
    assert "懂球帝赛前分析未命中" in result.summary


def test_info_insufficient_unparseable_kickoff_defaults_to_softer_wording():
    result = predict(_request("not-a-date"), _NO_SIGNAL_FACTORS)

    assert result.lean == "info_insufficient"
    assert "暂未发布" in result.summary


def _direction_factor(*, impact: float, weight: float = 1.0, label: str = "近期状态信号") -> FactorImpact:
    return FactorImpact(
        factor_id="form.recent_signal",
        label=label,
        group="form",
        enabled=True,
        weight=weight,
        impact=impact,
        direction="home" if impact > 0 else "away",
        confidence=0.8,
    )


def _draw_risk_factor(*, impact: float = 0.10, weight: float = 0.18) -> FactorImpact:
    return FactorImpact(
        factor_id="uncertainty.draw_risk",
        label="平局风险",
        group="draw_risk",
        enabled=True,
        weight=weight,
        impact=impact,
        direction="draw",
        confidence=0.45,
    )


def test_draw_pressure_turns_tiny_favourite_into_draw():
    result = predict(
        _request("2026-06-20 20:00"),
        [_direction_factor(impact=0.02), _draw_risk_factor()],
    )

    assert result.lean == "draw"
    assert result.scoreline_band[:2] == ["1-1", "0-0"]


def test_draw_pressure_blocks_decisive_lean_for_moderate_edge():
    result = predict(
        _request("2026-06-20 20:00"),
        [_direction_factor(impact=0.04), _draw_risk_factor()],
    )

    assert result.lean == "home_or_draw"
    assert "0-0" in result.scoreline_band


def test_build_factors_adds_draw_risk_from_draw_heavy_records():
    evidence = [
        OsintEvidence(
            id="ev_draw",
            source="test",
            source_type="fundamental",
            claim="A队 1胜3平1负, B队 1胜3平1负, H2H 1胜3平1负",
            topic="fundamental.test",
            confidence=0.8,
            raw_excerpt=(
                "A队近期战绩：1胜3平1负\n"
                "B队近期战绩：1胜3平1负\n"
                "历史交锋：A队 1胜3平1负，B队 1胜3平1负"
            ),
        ),
    ]

    factors = build_factors(_request("2026-06-20 20:00"), MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is True
    assert draw_factor.direction == "draw"
    assert draw_factor.impact > 0


def test_build_factors_adds_draw_risk_from_hyphenated_english_h2h():
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_h2h_en",
            source="test",
            source_type="news",
            claim="Draw-heavy head-to-head record",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt="Jordan South Korea head-to-head record: 1 wins, 4 draws, 1 losses.",
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is True
    assert draw_factor.direction == "draw"
    assert draw_factor.impact > 0
    assert draw_factor.evidence_ids == ["ev_h2h_en"]


def test_build_factors_ignores_nearby_unrelated_english_h2h():
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_unrelated_h2h",
            source="test",
            source_type="news",
            claim="Mixed preview",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt=(
                "Jordan vs South Korea preview. "
                "Costa Rica New Zealand head-to-head record: 1 wins, 4 draws, 1 losses."
            ),
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is False
    assert draw_factor.evidence_ids == []

def test_build_factors_ignores_unpunctuated_nearby_unrelated_english_h2h():
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_nearby_unpunctuated",
            source="test",
            source_type="news",
            claim="Unrelated H2H after fixture preview",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt=(
                "Jordan vs South Korea preview Costa Rica New Zealand "
                "head-to-head record: 1 wins, 4 draws, 1 losses."
            ),
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is False
    assert draw_factor.evidence_ids == []


def test_build_factors_does_not_create_draw_risk_from_qualitative_extraction(monkeypatch):
    from backend.football_osint.analysis.evidence_extraction import ExtractedFacts

    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    monkeypatch.setattr(
        "backend.football_osint.factor_registry.evidence_extraction.extract",
        lambda evidence, request: ExtractedFacts(
            home_form=(1, 3, 1),
            away_form=(1, 3, 1),
            h2h_home_wins=1,
            h2h_draws=4,
            h2h_home_losses=1,
            home_absences=None,
            away_absences=None,
            home_rank=None,
            away_rank=None,
            qualitative_inference=True,
        ),
    )
    evidence = [
        OsintEvidence(
            id="ev_structured",
            source="test",
            source_type="news",
            claim="Qualitative extraction",
            topic="fundamental.form",
            confidence=0.8,
            raw_excerpt="Jordan are compact. South Korea are organized.",
        ),
        OsintEvidence(
            id="ev_unrelated",
            source="test",
            source_type="news",
            claim="Unrelated evidence",
            topic="search.cn.preview",
            confidence=0.8,
            raw_excerpt="This source does not mention a draw-heavy record.",
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is False
    assert draw_factor.evidence_ids == []


def test_build_factors_ignores_same_sentence_unrelated_english_h2h():
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_nearby",
            source="test",
            source_type="news",
            claim="Unrelated H2H after the requested fixture preview",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt=(
                "Jordan vs South Korea preview, "
                "Costa Rica New Zealand head-to-head record: 1 wins, 4 draws, 1 losses."
            ),
        )
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is False
    assert draw_factor.evidence_ids == []


def test_build_factors_scopes_qualitative_draw_evidence_to_raw_snippet(monkeypatch):
    from backend.football_osint.analysis.evidence_extraction import ExtractedFacts

    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    monkeypatch.setattr(
        "backend.football_osint.factor_registry.evidence_extraction.extract",
        lambda evidence, request: ExtractedFacts(
            home_form=(1, 3, 1),
            away_form=(1, 3, 1),
            h2h_home_wins=1,
            h2h_draws=4,
            h2h_home_losses=1,
            home_absences=None,
            away_absences=None,
            home_rank=None,
            away_rank=None,
            qualitative_inference=True,
        ),
    )
    evidence = [
        OsintEvidence(
            id="ev_fundamental",
            source="test",
            source_type="news",
            claim="Broad form note",
            topic="fundamental.form",
            confidence=0.8,
            raw_excerpt="Jordan are compact. South Korea are organized.",
        ),
        OsintEvidence(
            id="ev_cn",
            source="test",
            source_type="news",
            claim="Unrelated CN preview",
            topic="search.cn.preview",
            confidence=0.8,
            raw_excerpt="这只是赛前背景，没有平局重压记录。",
        ),
        OsintEvidence(
            id="ev_draw_h2h",
            source="test",
            source_type="news",
            claim="Draw-heavy H2H",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt="Jordan South Korea head-to-head record: 1 wins, 4 draws, 1 losses.",
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is True
    assert draw_factor.evidence_ids == ["ev_draw_h2h"]


def test_build_factors_ignores_english_h2h_without_requested_teams_nearby():
    request = FootballOsintJobRequest(
        home_team="Jordan",
        away_team="South Korea",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_unrelated_h2h",
            source="test",
            source_type="news",
            claim="Mixed preview",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt=(
                "Costa Rica New Zealand head-to-head record: 1 wins, 4 draws, 1 losses. "
                + "Preview filler. " * 40
                + "Jordan and South Korea squad news is still pending."
            ),
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is False
    assert draw_factor.evidence_ids == []


def test_build_factors_uses_english_names_for_draw_risk_form_matching(monkeypatch):
    monkeypatch.setattr(
        "backend.football_osint.adapters.name_translation.to_english",
        lambda name: {"约旦": "Jordan", "韩国": "South Korea"}[name],
    )
    request = FootballOsintJobRequest(
        home_team="约旦",
        away_team="韩国",
        kickoff_at="2026-06-20 20:00",
    )
    evidence = [
        OsintEvidence(
            id="ev_form_en",
            source="test",
            source_type="news",
            claim="Draw-heavy English team form",
            topic="search.preview",
            confidence=0.8,
            raw_excerpt=(
                "Jordan recent form: 1 win, 3 draws, 1 loss. "
                "South Korea recent form: 1 win, 3 draws, 1 loss."
            ),
        ),
    ]

    factors = build_factors(request, MatchProfile(), evidence)
    draw_factor = next(f for f in factors if f.factor_id == "uncertainty.draw_risk")

    assert draw_factor.enabled is True
    assert draw_factor.direction == "draw"
    assert draw_factor.impact > 0
    assert draw_factor.evidence_ids == ["ev_form_en"]


def test_scoreline_band_varies_by_edge_strength_not_only_direction():
    narrow_home = predict(_request("2026-06-20 20:00"), [_direction_factor(impact=0.03)])
    strong_home = predict(_request("2026-06-20 20:00"), [_direction_factor(impact=0.18)])
    strong_away = predict(_request("2026-06-20 20:00"), [_direction_factor(impact=-0.18)])

    assert narrow_home.lean in {"home_or_draw", "home"}
    assert strong_home.lean == "home"
    assert strong_away.lean == "away"
    assert narrow_home.scoreline_band != strong_home.scoreline_band
    assert "2-0" in strong_home.scoreline_band
    assert "0-2" in strong_away.scoreline_band


def test_assessment_uses_driver_labels_instead_of_falling_back_to_generic_source():
    from backend.football_osint.analysis.confidence import ConfidenceRating
    from backend.football_osint.analysis.intelligence import assessments
    from backend.football_osint.models import OsintMatch, PredictionResult

    factor = _direction_factor(impact=0.12, label="近期状态信号")
    prediction = PredictionResult(
        lean="home",
        summary="",
        probability_band={},
        scoreline_band=["2-0"],
        drivers=["近期状态信号"],
        uncertainties=[],
    )

    result = assessments(
        OsintMatch(home_team="A队", away_team="B队"),
        [factor],
        prediction,
        ConfidenceRating(level="L3", reason=""),
    )

    assert "近期状态信号" in result[0].statement
    assert "基础输入与公开源计划" not in result[0].statement

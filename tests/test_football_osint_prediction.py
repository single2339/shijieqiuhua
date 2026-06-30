"""Tests for the info_insufficient wording split by time-to-kickoff."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.football_osint.analysis.prediction import predict
from backend.football_osint.models import FactorImpact, FootballOsintJobRequest

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

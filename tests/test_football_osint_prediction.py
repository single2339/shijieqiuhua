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

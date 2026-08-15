from __future__ import annotations

import json

from backend.football_osint.analysis import evidence_extraction as ee
from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence


def _request() -> FootballOsintJobRequest:
    return FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )


def _evidence(topic: str, raw_excerpt: str) -> OsintEvidence:
    return OsintEvidence(
        id="ev_001", source="test", source_type="fundamental",
        claim=raw_excerpt[:50], topic=topic, side="neutral",
        confidence=0.5, raw_excerpt=raw_excerpt,
    )


def test_extract_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    result = ee.extract([_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")], _request())
    assert result is None


def test_extract_returns_none_without_useful_evidence(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    result = ee.extract([_evidence("fixture.query", "比赛已录入")], _request())
    assert result is None


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_extract_parses_llm_json_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    llm_json = json.dumps({
        "home_form": {"wins": 4, "draws": 1, "losses": 0},
        "away_form": {"wins": 2, "draws": 1, "losses": 2},
        "h2h_home_wins": 3, "h2h_draws": 1, "h2h_home_losses": 1,
        "home_absences": 1, "away_absences": 3,
        "home_rank": 2, "away_rank": 5,
    })

    def fake_post(*args, **kwargs):
        return _FakeResponse({"choices": [{"message": {"content": llm_json}}]})

    monkeypatch.setattr(ee.httpx, "post", fake_post)

    result = ee.extract(
        [_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")],
        _request(),
    )

    assert result == ee.ExtractedFacts(
        home_form=(4, 1, 0), away_form=(2, 1, 2),
        h2h_home_wins=3, h2h_draws=1, h2h_home_losses=1,
        home_absences=1, away_absences=3,
        home_rank=2, away_rank=5,
    )


def test_extract_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(ee.httpx, "post", fake_post)

    result = ee.extract(
        [_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")],
        _request(),
    )
    assert result is None

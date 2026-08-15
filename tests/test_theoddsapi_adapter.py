from __future__ import annotations

from datetime import timezone

import httpx

from backend.football_osint.adapters import theoddsapi
from backend.football_osint.models import FootballOsintJobRequest


def _request(**updates: str) -> FootballOsintJobRequest:
    values = {
        "home_team": "Manchester United",
        "away_team": "Arsenal",
        "kickoff_at": "2026-08-16T15:00:00Z",
        "competition": "Premier League",
    }
    values.update(updates)
    return FootballOsintJobRequest(**values)


def _event(**updates: object) -> dict:
    values = {
        "id": "event-123",
        "home_team": "Manchester United",
        "away_team": "Arsenal",
        "commence_time": "2026-08-16T15:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Manchester United", "price": 2.1},
                        {"name": "Draw", "price": 3.5},
                        {"name": "Arsenal", "price": 3.8},
                    ],
                }],
            },
            {
                "key": "bet365",
                "title": "Bet365",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Manchester United", "price": 2.15},
                        {"name": "Draw", "price": 3.4},
                        {"name": "Arsenal", "price": 3.7},
                    ],
                }],
            },
        ],
    }
    values.update(updates)
    return values


class _Response:
    def __init__(self, payload: object, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/")
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(self.status_code, request=request))

    def json(self) -> object:
        return self.payload


def test_collect_is_disabled_without_a_licensed_key(monkeypatch):
    monkeypatch.delenv("THEODDS_API_KEY", raising=False)

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "未配置授权赔率数据服务"


def test_collect_normalizes_named_bookmaker_quotes_and_request(monkeypatch):
    received: dict[str, object] = {}

    def fake_get(url, *, params, timeout):
        received.update(url=url, params=params, timeout=timeout)
        return _Response([_event()])

    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setenv("THEODDS_API_BOOKMAKERS", "pinnacle,bet365")
    monkeypatch.setattr(theoddsapi.httpx, "get", fake_get)

    snapshots, reason = theoddsapi.collect(_request())

    assert reason == ""
    assert [snapshot.source_id for snapshot in snapshots] == ["pinnacle", "bet365"]
    assert snapshots[0].display_name == "The Odds API · Pinnacle"
    assert snapshots[0].provider_event_id == "event-123"
    assert snapshots[0].observed_at.tzinfo == timezone.utc
    assert sum(snapshots[0].implied_probabilities.model_dump().values()) == 1.0
    assert received == {
        "url": "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/",
        "params": {
            "apiKey": "test-key",
            "regions": "uk",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "bookmakers": "pinnacle,bet365",
        },
        "timeout": 8.0,
    }


def test_collect_rejects_ambiguous_or_nonmatching_events(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([_event(), _event(id="event-456")]))

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "未找到唯一匹配的授权赔率赛事"


def test_collect_rejects_same_teams_when_kickoff_is_only_within_five_minutes(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(
        theoddsapi.httpx,
        "get",
        lambda *args, **kwargs: _Response([_event(commence_time="2026-08-16T15:04:00Z")]),
    )

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "未找到唯一匹配的授权赔率赛事"


def test_collect_rejects_incomplete_or_nonfinite_quotes(monkeypatch):
    invalid_event = _event(bookmakers=[{
        "key": "pinnacle",
        "markets": [{
            "key": "h2h",
            "outcomes": [
                {"name": "Manchester United", "price": 2.1},
                {"name": "Draw", "price": float("inf")},
                {"name": "Arsenal", "price": 3.8},
            ],
        }],
    }])
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([invalid_event]))

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "授权赔率数据服务未提供完整有效的胜平负赔率"


def test_collect_rejects_malformed_provider_containers(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([_event(bookmakers={})]))

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "授权赔率数据服务响应无效"


def test_collect_does_not_hide_unexpected_parser_failures(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([_event()]))

    for error_type in (RuntimeError, ValueError):
        def broken_parser(event, error_type=error_type):
            raise error_type("implementation regression")

        monkeypatch.setattr(theoddsapi, "_snapshots_from_event", broken_parser)
        try:
            theoddsapi.collect(_request())
        except error_type as exc:
            assert str(exc) == "implementation regression"
        else:
            raise AssertionError("unexpected parser failures must propagate")


def test_collect_rejects_date_only_kickoff_without_calling_provider(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call provider")))

    snapshots, reason = theoddsapi.collect(_request(kickoff_at="2026-08-16"))

    assert snapshots == []
    assert reason == "比赛开赛时间不完整，无法安全匹配授权赔率数据"


def test_collect_accepts_equivalent_offset_kickoff(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([_event()]))

    snapshots, reason = theoddsapi.collect(_request(kickoff_at="2026-08-16T23:00:00+08:00"))

    assert reason == ""
    assert len(snapshots) == 2


def test_collect_interprets_timezone_less_full_kickoff_as_cst(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")
    monkeypatch.setattr(theoddsapi.httpx, "get", lambda *args, **kwargs: _Response([_event()]))

    snapshots, reason = theoddsapi.collect(_request(kickoff_at="2026-08-16 23:00"))

    assert reason == ""
    assert len(snapshots) == 2


def test_collect_returns_chinese_timeout_reason(monkeypatch):
    monkeypatch.setenv("THEODDS_API_KEY", "test-key")

    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(theoddsapi.httpx, "get", timeout)

    snapshots, reason = theoddsapi.collect(_request())

    assert snapshots == []
    assert reason == "授权赔率数据服务请求超时"

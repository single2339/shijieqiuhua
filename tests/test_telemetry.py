"""Tests for backend.telemetry.

Use FOOTBALL_OSINT_TELEMETRY_DB to point at a tmp DB so we don't pollute the
real bronze_storage. Each test gets a fresh DB via reset_for_tests().
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from backend import telemetry


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    db = tmp_path / "telemetry.db"
    monkeypatch.setenv("FOOTBALL_OSINT_TELEMETRY_DB", str(db))
    telemetry.reset_for_tests()
    yield db
    telemetry.reset_for_tests()


def _rows(db: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(str(db)) as c:
        c.row_factory = sqlite3.Row
        return list(c.execute("SELECT * FROM telemetry_event ORDER BY id"))


def test_emit_persists_event(tmp_db):
    telemetry.emit("auth.login_success", user_id="u_test", payload={"foo": "bar"})
    rows = _rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["event_name"] == "auth.login_success"
    assert rows[0]["user_id"] == "u_test"
    assert json.loads(rows[0]["payload_json"]) == {"foo": "bar"}
    assert rows[0]["ts"].endswith("Z")
    assert rows[0]["event_id"]


def test_emit_swallows_errors(tmp_db, monkeypatch):
    """If the DB layer fails, emit() must not raise to the caller."""

    def boom(*_args, **_kwargs):
        raise sqlite3.OperationalError("simulated disk-full")

    monkeypatch.setattr(telemetry, "_get_conn", boom)
    # Must not raise
    telemetry.emit("system.error_5xx", payload={"path": "/x"})


def test_measure_records_duration_and_status(tmp_db):
    with telemetry.measure("research.dashboard_completed", user_id="u1", payload={"match_id": "m1"}) as m:
        m["payload"]["cache_hit"] = True
    rows = _rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["duration_ms"] is not None
    assert rows[0]["duration_ms"] >= 0
    payload = json.loads(rows[0]["payload_json"])
    assert payload == {"match_id": "m1", "cache_hit": True}


def test_measure_on_exception(tmp_db):
    with pytest.raises(ValueError):
        with telemetry.measure("research.dashboard_completed", user_id="u1"):
            raise ValueError("boom")
    rows = _rows(tmp_db)
    assert len(rows) == 1
    assert rows[0]["status"] == "error"
    assert rows[0]["error_code"] == "ValueError"
    assert rows[0]["duration_ms"] is not None


def test_hash_text_is_deterministic_and_short():
    assert telemetry.hash_text("alice@example.com") == telemetry.hash_text("alice@example.com")
    assert telemetry.hash_text("alice@example.com") != telemetry.hash_text("bob@example.com")
    assert len(telemetry.hash_text("x")) == 12
    assert telemetry.hash_text(None) == ""
    assert telemetry.hash_text("") == ""


def test_host_of_strips_path_and_query():
    assert telemetry.host_of("https://m.dongqiudi.com/matchDetail/54329996/analysis") == "m.dongqiudi.com"
    assert telemetry.host_of("not a url") == ""
    assert telemetry.host_of(None) == ""
    assert telemetry.host_of("https://EXAMPLE.com/") == "example.com"


def test_payload_does_not_persist_pii(tmp_db):
    """Caller is expected to pre-hash; this test documents the contract: emit
    does not magically scrub fields. It's the SDK user's job to pass hashes.
    """
    raw_email = "user@example.com"
    telemetry.emit("auth.register_attempt", payload={"email_hash": telemetry.hash_text(raw_email)})
    rows = _rows(tmp_db)
    payload = json.loads(rows[0]["payload_json"])
    assert raw_email not in rows[0]["payload_json"]
    assert payload["email_hash"] == telemetry.hash_text(raw_email)


def test_concurrent_emit_no_loss(tmp_db):
    n_threads = 8
    per_thread = 25

    def worker(idx: int):
        for i in range(per_thread):
            telemetry.emit("system.uptime_heartbeat", payload={"thread": idx, "i": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = _rows(tmp_db)
    assert len(rows) == n_threads * per_thread
    assert len({r["event_id"] for r in rows}) == n_threads * per_thread

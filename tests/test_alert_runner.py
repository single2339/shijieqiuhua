"""Tests for backend.alert_runner.

Covers:
- the simulate() bootstrap that lets us trigger a rule without real failures
- run_once() correctly fires P1/P2 alerts and respects cooldown
- dry-run mode never invokes SMTP and records 'skipped_dryrun'
- _approx_p95 returns None below the sample threshold

SMTP itself is not tested live — only the dry-run path is exercised. The
test-email subcommand is what you run manually after wiring real credentials.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend import alert_runner, telemetry


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    db = tmp_path / "telemetry.db"
    monkeypatch.setenv("FOOTBALL_OSINT_TELEMETRY_DB", str(db))
    # Ensure no SMTP creds are present — dry-run / unconfigured paths only.
    for key in ("ALERT_SMTP_HOST", "ALERT_SMTP_USER", "ALERT_SMTP_PASSWORD",
                "ALERT_FROM", "ALERT_TO"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("ALERT_POSTLAUNCH", raising=False)
    telemetry.reset_for_tests()
    yield db
    telemetry.reset_for_tests()


def _all_alerts(db: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(str(db)) as c:
        c.row_factory = sqlite3.Row
        return list(c.execute("SELECT * FROM alert_fired ORDER BY id"))


def test_simulate_alert1_fires_in_dry_run(tmp_db):
    msg = alert_runner.simulate("ALERT-1")
    assert "40" in msg
    fired = alert_runner.run_once(dry_run=True)
    rule_ids = {a.rule_id for a, _ in fired}
    assert "ALERT-1" in rule_ids

    rows = _all_alerts(tmp_db)
    alert1 = [r for r in rows if r["rule_id"] == "ALERT-1"]
    assert len(alert1) == 1
    assert alert1[0]["delivery_status"] == "skipped_dryrun"
    assert alert1[0]["sent_to"] == "(dry-run)"


def test_simulate_alert3_dashboard_p95(tmp_db):
    alert_runner.simulate("ALERT-3")
    fired = alert_runner.run_once(dry_run=True)
    assert any(a.rule_id == "ALERT-3" for a, _ in fired)


def test_simulate_alert6_url_blocked_surge(tmp_db):
    alert_runner.simulate("ALERT-6")
    fired = alert_runner.run_once(dry_run=True)
    assert any(a.rule_id == "ALERT-6" for a, _ in fired)


def test_simulate_alert11_info_insufficient(tmp_db):
    alert_runner.simulate("ALERT-11")
    fired = alert_runner.run_once(dry_run=True)
    assert any(a.rule_id == "ALERT-11" for a, _ in fired)


def test_alert11_reports_top_info_insufficient_reason(tmp_db):
    for _ in range(40):
        telemetry.emit("research.dashboard_view", payload={
            "lean": "info_insufficient",
            "insufficiency_reasons": ["detail_fixture_unmatched"],
        })
    for _ in range(10):
        telemetry.emit("research.dashboard_view", payload={"lean": "home"})

    fired = alert_runner.run_once(dry_run=True)
    alert = next(a for a, _ in fired if a.rule_id == "ALERT-11")

    assert alert.payload["top_reason"] == "detail_fixture_unmatched"
    assert "detail_fixture_unmatched" in alert.body


def test_cooldown_blocks_repeat_within_window(tmp_db):
    alert_runner.simulate("ALERT-1")

    first = alert_runner.run_once(dry_run=True)
    assert any(a.rule_id == "ALERT-1" for a, _ in first)

    # Re-seed the underlying signal AND run again — cooldown should suppress
    # the duplicate even though the condition still holds.
    alert_runner.simulate("ALERT-1")
    second = alert_runner.run_once(dry_run=True)
    assert not any(a.rule_id == "ALERT-1" for a, _ in second)


def test_run_once_with_no_data_fires_nothing(tmp_db):
    fired = alert_runner.run_once(dry_run=True)
    # Empty DB: no rule should match. ALERT-2 is silenced by missing-heartbeat
    # being treated as 'pre-launch' until ALERT_POSTLAUNCH=1 is set.
    assert fired == []


def test_alert9_silent_only_after_postlaunch(tmp_db, monkeypatch):
    # No events ever -> ALERT-9 should NOT fire while pre-launch
    fired_pre = alert_runner.run_once(dry_run=True)
    assert not any(a.rule_id == "ALERT-9" for a, _ in fired_pre)

    monkeypatch.setenv("ALERT_POSTLAUNCH", "1")
    # Cooldown table is empty for ALERT-9, so it should fire now
    fired_post = alert_runner.run_once(dry_run=True)
    assert any(a.rule_id == "ALERT-9" for a, _ in fired_post)


def test_test_email_fails_when_smtp_unconfigured(tmp_db):
    # ALERT_SMTP_* unset by fixture
    assert alert_runner.send_test_email() == "missing_smtp_config"


def test_approx_p95_below_min_samples_returns_none(tmp_db):
    for _ in range(5):
        telemetry.emit("research.dashboard_completed", duration_ms=1000, status="ok")
    conn = telemetry._get_conn()
    p95 = alert_runner._approx_p95(
        conn,
        event_name="research.dashboard_completed",
        window_minutes=10,
        min_samples=20,
    )
    assert p95 is None


def test_approx_p95_returns_high_value_when_data_present(tmp_db):
    for ms in [100] * 19 + [12_000] * 6:
        telemetry.emit("research.dashboard_completed", duration_ms=ms, status="ok")
    conn = telemetry._get_conn()
    p95 = alert_runner._approx_p95(
        conn,
        event_name="research.dashboard_completed",
        window_minutes=10,
        min_samples=20,
    )
    # 25 rows * 0.05 = 1 offset -> ORDER BY DESC LIMIT 1 OFFSET 1 = second-largest
    assert p95 is not None
    assert p95 >= 1000

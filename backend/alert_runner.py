"""P1/P2 alert runner for Shijieqiuhua v1 telemetry.

This is the cron-driven companion to backend/telemetry.py.

Modes:
- ``run-once``     : single check pass; cron uses this every minute.
- ``dry-run``      : run all rules but write `delivery_status='skipped_dryrun'`
                     instead of sending email; useful before SMTP is configured.
- ``test-email``   : send one synthetic email to verify SMTP works end-to-end.
- ``simulate``     : insert fake telemetry events to force a specific rule to
                     fire (W5 dry-run gate).

v1 keeps everything in this single file; rule logic and SMTP plumbing live
together because there are only ~16 rules. If we cross 30 rules, split into
``backend/alerts/rules/`` and dispatch on rule_id.

See docs/superpowers/specs/2026-06-13-telemetry/02-dashboards.md §4.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from backend import telemetry

log = logging.getLogger("alert_runner")

# ── config ──
COOLDOWN_P1_MIN = int(os.getenv("ALERT_COOLDOWN_P1_MIN", "15"))
COOLDOWN_P2_MIN = int(os.getenv("ALERT_COOLDOWN_P2_MIN", "1440"))  # 24h


def _smtp_config() -> dict[str, str]:
    return {
        "host": os.getenv("ALERT_SMTP_HOST", ""),
        "port": os.getenv("ALERT_SMTP_PORT", "587"),
        "user": os.getenv("ALERT_SMTP_USER", ""),
        "password": os.getenv("ALERT_SMTP_PASSWORD", ""),
        "from": os.getenv("ALERT_FROM", ""),
        "to": os.getenv("ALERT_TO", ""),  # comma-separated
        "use_tls": os.getenv("ALERT_SMTP_TLS", "1"),
    }


# ── rule dataclasses ──

@dataclass
class Alert:
    rule_id: str
    severity: str  # P1 | P2
    title: str
    body: str
    payload: dict = field(default_factory=dict)


# ── rule registry ──
# Each rule = (rule_id, severity, check_fn). check_fn returns Alert or None.
RuleFn = Callable[[sqlite3.Connection], "Alert | None"]
_RULES: list[tuple[str, str, RuleFn]] = []


def rule(rule_id: str, severity: str):
    def decorator(fn: RuleFn) -> RuleFn:
        _RULES.append((rule_id, severity, fn))
        return fn

    return decorator


# ── rules: P1 (real-time, email immediately) ──

@rule("ALERT-1", "P1")
def _r1_5xx_rate(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN event_name='system.error_5xx' THEN 1 ELSE 0 END) AS errors
        FROM telemetry_event
        WHERE ts >= datetime('now', '-10 minutes')
    """).fetchone()
    total = (row[0] or 0) if row else 0
    errors = (row[1] or 0) if row else 0
    if total < 20:
        return None  # too few samples to judge
    pct = 100.0 * errors / total
    if pct > 5.0:
        return Alert(
            rule_id="ALERT-1",
            severity="P1",
            title=f"5xx error rate {pct:.1f}% (last 10 min)",
            body=f"errors={errors}, total={total}, threshold=5%",
            payload={"pct": pct, "errors": errors, "total": total},
        )
    return None


@rule("ALERT-2", "P1")
def _r2_heartbeat_missing(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT (julianday('now') - julianday(MAX(ts))) * 24 * 60 AS minutes_since
        FROM telemetry_event WHERE event_name='system.uptime_heartbeat'
    """).fetchone()
    minutes = row[0] if row and row[0] is not None else None
    # If no heartbeat ever recorded, only alert when the deployment is past W5
    # (env var STARTED_AT set). Otherwise stay silent — we are in the bring-up.
    if minutes is None:
        return None
    if minutes > 3:
        return Alert(
            rule_id="ALERT-2",
            severity="P1",
            title=f"No heartbeat for {minutes:.1f} min",
            body="system.uptime_heartbeat missing — backend may be down",
            payload={"minutes_since_last": minutes},
        )
    return None


@rule("ALERT-3", "P1")
def _r3_dashboard_p95(conn: sqlite3.Connection) -> "Alert | None":
    p95 = _approx_p95(
        conn,
        event_name="research.dashboard_completed",
        window_minutes=5,
        min_samples=20,
    )
    if p95 is not None and p95 > 10_000:
        return Alert(
            rule_id="ALERT-3",
            severity="P1",
            title=f"dashboard P95 = {p95} ms (>10s, NFR-1)",
            body="research.dashboard_completed latency degraded",
            payload={"p95_ms": p95},
        )
    return None


@rule("ALERT-4", "P1")
def _r4_pipeline_p95(conn: sqlite3.Connection) -> "Alert | None":
    p95 = _approx_p95(
        conn,
        event_name="pipeline.job_completed",
        window_minutes=5,
        min_samples=10,
    )
    if p95 is not None and p95 > 90_000:
        return Alert(
            rule_id="ALERT-4",
            severity="P1",
            title=f"pipeline P95 = {p95} ms (>90s, NFR-2)",
            body="OSINT pipeline severely degraded",
            payload={"p95_ms": p95},
        )
    return None


@rule("ALERT-5", "P1")
def _r5_llm_failure_rate(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='error' OR status='timeout' THEN 1 ELSE 0 END) AS bad
        FROM telemetry_event
        WHERE event_name='llm.call_completed'
          AND ts >= datetime('now', '-10 minutes')
    """).fetchone()
    total = (row[0] or 0) if row else 0
    bad = (row[1] or 0) if row else 0
    if total < 10:
        return None
    pct = 100.0 * bad / total
    if pct > 50:
        return Alert(
            rule_id="ALERT-5",
            severity="P1",
            title=f"LLM failure rate {pct:.0f}% (last 10 min)",
            body="DeepSeek calls degraded — RISK-5 active; degrade-to-template path will absorb load",
            payload={"pct": pct, "bad": bad, "total": total},
        )
    return None


@rule("ALERT-6", "P1")
def _r6_url_blocked_surge(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT COUNT(*) FROM telemetry_event
        WHERE event_name='external.url_blocked'
          AND ts >= datetime('now', '-1 minute')
    """).fetchone()
    cnt = (row[0] or 0) if row else 0
    if cnt > 20:
        return Alert(
            rule_id="ALERT-6",
            severity="P1",
            title=f"url_blocked surge: {cnt}/min",
            body="Possible SSRF probing — review url_blocked payloads",
            payload={"count": cnt},
        )
    return None


@rule("ALERT-7", "P1")
def _r7_register_brute(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT ip_hash, COUNT(*) AS c FROM telemetry_event
        WHERE event_name='auth.register_attempt'
          AND ts >= datetime('now', '-1 minute')
          AND ip_hash IS NOT NULL
        GROUP BY ip_hash
        ORDER BY c DESC LIMIT 1
    """).fetchone()
    if row and (row[1] or 0) > 30:
        return Alert(
            rule_id="ALERT-7",
            severity="P1",
            title=f"register brute force: {row[1]}/min from one IP",
            body=f"ip_hash={row[0]}",
            payload={"ip_hash": row[0], "count": row[1]},
        )
    return None


@rule("ALERT-8", "P1")
def _r8_backup_failed(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT json_extract(payload_json, '$.kind') AS kind, status
        FROM telemetry_event
        WHERE event_name='system.backup_completed'
          AND ts >= datetime('now', '-25 hours')
        ORDER BY ts DESC LIMIT 1
    """).fetchone()
    if row and row[1] not in ("ok", None):
        return Alert(
            rule_id="ALERT-8",
            severity="P1",
            title=f"backup {row[0]} status={row[1]}",
            body="Latest backup did not succeed — data safety at risk",
            payload={"kind": row[0], "status": row[1]},
        )
    return None


@rule("ALERT-9", "P1")
def _r9_telemetry_silent(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT COUNT(*) FROM telemetry_event
        WHERE ts >= datetime('now', '-24 hours')
    """).fetchone()
    cnt = (row[0] or 0) if row else 0
    # Only meaningful after launch — guarded by env flag
    if os.getenv("ALERT_POSTLAUNCH", "").strip() != "1":
        return None
    if cnt == 0:
        return Alert(
            rule_id="ALERT-9",
            severity="P1",
            title="telemetry silent for 24h",
            body="No events recorded — emit pipeline likely broken",
            payload={},
        )
    return None


# ── rules: P2 (daily digest) ──

@rule("ALERT-11", "P2")
def _r11_info_insufficient_high(conn: sqlite3.Connection) -> "Alert | None":
    row = conn.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN json_extract(payload_json, '$.lean')='info_insufficient' THEN 1 ELSE 0 END) AS ii
        FROM telemetry_event
        WHERE event_name='research.dashboard_view'
          AND ts >= datetime('now', '-1 day')
    """).fetchone()
    total = (row[0] or 0) if row else 0
    ii = (row[1] or 0) if row else 0
    if total < 50:
        return None
    pct = 100.0 * ii / total
    reason_rows = conn.execute("""
        SELECT json_extract(payload_json, '$.insufficiency_reasons[0]') AS reason
        FROM telemetry_event
        WHERE event_name='research.dashboard_view'
          AND json_extract(payload_json, '$.lean')='info_insufficient'
          AND ts >= datetime('now', '-1 day')
    """).fetchall()
    reasons: dict[str, int] = {}
    for reason_row in reason_rows:
        reason = reason_row[0] or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    top_reason = max(reasons, key=reasons.get) if reasons else "unknown"
    if pct > 70:
        return Alert(
            rule_id="ALERT-11",
            severity="P2",
            title=f"info_insufficient = {pct:.0f}% (>70%)",
            body=f"Most matches lack data — RISK-3 active. Top reason: {top_reason}. Check adapter health.",
            payload={"pct": pct, "top_reason": top_reason},
        )
    return None


@rule("ALERT-13", "P2")
def _r13_dau_drop(conn: sqlite3.Connection) -> "Alert | None":
    cur_week = conn.execute("""
        SELECT COUNT(DISTINCT user_id) FROM telemetry_event
        WHERE user_id IS NOT NULL AND ts >= datetime('now', '-7 days')
    """).fetchone()
    prev_week = conn.execute("""
        SELECT COUNT(DISTINCT user_id) FROM telemetry_event
        WHERE user_id IS NOT NULL
          AND ts >= datetime('now', '-14 days')
          AND ts <  datetime('now', '-7 days')
    """).fetchone()
    cur = (cur_week[0] or 0) if cur_week else 0
    prev = (prev_week[0] or 0) if prev_week else 0
    if prev < 10:
        return None
    drop_pct = 100.0 * (prev - cur) / prev
    if drop_pct > 50:
        return Alert(
            rule_id="ALERT-13",
            severity="P2",
            title=f"WAU dropped {drop_pct:.0f}% week-over-week",
            body=f"this_week={cur} prev_week={prev}",
            payload={"current": cur, "previous": prev, "drop_pct": drop_pct},
        )
    return None


@rule("ALERT-10", "P2")
def _r10_llm_cost_estimate(conn: sqlite3.Connection) -> "Alert | None":
    # ponytail: no per-call token counts yet; approximate by call volume.
    # DeepSeek chat ~¥0.003/call avg (2k tokens). ¥500/month ≈ ¥17/day ≈ 5600 calls/day.
    # Warn at 3000 calls/day (~53% of monthly budget in one day).
    row = conn.execute("""
        SELECT COUNT(*) FROM telemetry_event
        WHERE event_name='llm.call_completed'
          AND ts >= datetime('now', '-24 hours')
    """).fetchone()
    cnt = (row[0] or 0) if row else 0
    threshold = int(os.getenv("ALERT_LLM_DAILY_CALL_LIMIT", "3000"))
    if cnt > threshold:
        est_cny = round(cnt * 0.003, 1)
        return Alert(
            rule_id="ALERT-10",
            severity="P2",
            title=f"LLM calls {cnt}/day (est. ¥{est_cny}, budget ¥17/day)",
            body=f"DeepSeek call count exceeds {threshold}/day threshold. Add token tracking for precise cost.",
            payload={"calls_24h": cnt, "est_cny": est_cny, "threshold": threshold},
        )
    return None


# ALERT-12/14/15/16 left as TODO: per-adapter aggregation (12), funnel views
# (14), filesystem stats (15), or systemd integration (16). All tractable
# but scoped out of the W5 dry-run skeleton.


# ── helpers ──

def _approx_p95(
    conn: sqlite3.Connection,
    *,
    event_name: str,
    window_minutes: int,
    min_samples: int,
) -> "int | None":
    row = conn.execute(
        """
        SELECT COUNT(*) FROM telemetry_event
        WHERE event_name=? AND status='ok' AND duration_ms IS NOT NULL
          AND ts >= datetime('now', ?)
        """,
        (event_name, f"-{window_minutes} minutes"),
    ).fetchone()
    n = (row[0] or 0) if row else 0
    if n < min_samples:
        return None
    offset = max(0, int(n * 0.05))
    row = conn.execute(
        """
        SELECT duration_ms FROM telemetry_event
        WHERE event_name=? AND status='ok' AND duration_ms IS NOT NULL
          AND ts >= datetime('now', ?)
        ORDER BY duration_ms DESC
        LIMIT 1 OFFSET ?
        """,
        (event_name, f"-{window_minutes} minutes", offset),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _is_in_cooldown(conn: sqlite3.Connection, rule_id: str, severity: str) -> bool:
    cooldown = COOLDOWN_P1_MIN if severity == "P1" else COOLDOWN_P2_MIN
    row = conn.execute(
        """
        SELECT (julianday('now') - julianday(MAX(fired_at))) * 24 * 60 AS minutes_ago
        FROM alert_fired
        WHERE rule_id=?
          AND delivery_status IN ('sent', 'pending', 'skipped_dryrun')
        """,
        (rule_id,),
    ).fetchone()
    minutes_ago = row[0] if row and row[0] is not None else None
    if minutes_ago is None:
        return False
    return minutes_ago < cooldown


def _record_fired(
    conn: sqlite3.Connection,
    alert: Alert,
    sent_to: str,
    delivery_status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO alert_fired (rule_id, severity, fired_at, payload_json,
                                 sent_to, delivery_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            alert.rule_id,
            alert.severity,
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            json.dumps(alert.payload, ensure_ascii=False),
            sent_to,
            delivery_status,
        ),
    )
    conn.commit()


# ── email ──

def _send_email(alert: Alert) -> tuple[str, str]:
    """Send alert via SMTP. Returns (sent_to, delivery_status)."""
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["from"] or not cfg["to"]:
        return ("", "failed")
    msg = EmailMessage()
    msg["Subject"] = f"[{alert.severity}] {alert.rule_id} {alert.title}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    body = (
        f"Rule: {alert.rule_id} ({alert.severity})\n"
        f"Title: {alert.title}\n\n"
        f"{alert.body}\n\n"
        f"Payload:\n{json.dumps(alert.payload, ensure_ascii=False, indent=2)}\n\n"
        f"-- alert_runner @ {datetime.now(timezone.utc).isoformat()}"
    )
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["host"], int(cfg["port"]), timeout=15) as smtp:
            smtp.ehlo()
            if cfg["use_tls"] == "1":
                smtp.starttls()
                smtp.ehlo()
            if cfg["user"] and cfg["password"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
        return (cfg["to"], "sent")
    except Exception as exc:  # noqa: BLE001
        log.error("SMTP send failed: %s", exc)
        return (cfg["to"], "failed")


# ── main loops ──

def run_once(*, dry_run: bool = False) -> list[tuple[Alert, str]]:
    """Single check pass. Returns list of (alert, delivery_status)."""
    conn = telemetry._get_conn()  # share the same DB
    fired: list[tuple[Alert, str]] = []
    for rule_id, severity, check in _RULES:
        try:
            alert = check(conn)
        except Exception:  # noqa: BLE001
            log.exception("rule %s check raised", rule_id)
            continue
        if alert is None:
            continue
        if _is_in_cooldown(conn, rule_id, severity):
            log.info("rule %s in cooldown, skip", rule_id)
            continue
        if dry_run:
            _record_fired(conn, alert, sent_to="(dry-run)", delivery_status="skipped_dryrun")
            fired.append((alert, "skipped_dryrun"))
            continue
        sent_to, delivery_status = _send_email(alert)
        _record_fired(conn, alert, sent_to=sent_to, delivery_status=delivery_status)
        fired.append((alert, delivery_status))
    return fired


def send_test_email() -> str:
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["from"] or not cfg["to"]:
        return "missing_smtp_config"
    test_alert = Alert(
        rule_id="TEST",
        severity="P1",
        title="alert_runner test email",
        body="If you can read this, SMTP is configured correctly.",
        payload={"now": datetime.now(timezone.utc).isoformat()},
    )
    sent_to, status = _send_email(test_alert)
    return status


def simulate(rule_id: str) -> str:
    """Insert synthetic telemetry rows so the named rule will fire on next run.

    Used in W5 dry-run to verify alerts end-to-end without waiting for real
    failures.
    """
    if rule_id == "ALERT-1":
        for i in range(40):
            telemetry.emit("system.error_5xx", payload={"path": "/api/sim", "i": i})
            telemetry.emit("research.dashboard_view", payload={"sim": True})
        return "inserted 40 errors + 40 views (>5% threshold)"
    if rule_id == "ALERT-2":
        # nothing to do — heartbeat just needs to be missing.
        return "ensure no system.uptime_heartbeat events recently"
    if rule_id == "ALERT-3":
        for i in range(25):
            telemetry.emit(
                "research.dashboard_completed",
                duration_ms=12_000,
                status="ok",
                payload={"sim": True},
            )
        return "inserted 25 slow dashboards (>10s)"
    if rule_id == "ALERT-6":
        for _ in range(25):
            telemetry.emit("external.url_blocked", payload={"reason": "host_not_allowed"})
        return "inserted 25 url_blocked events"
    if rule_id == "ALERT-11":
        # 50 dashboard views, 40 with info_insufficient
        for i in range(50):
            payload = {"lean": "info_insufficient" if i < 40 else "home"}
            telemetry.emit("research.dashboard_view", payload=payload)
        return "inserted 80% info_insufficient ratio"
    return f"unknown rule_id {rule_id}; supported: ALERT-1, ALERT-2, ALERT-3, ALERT-6, ALERT-11"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="alert_runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run-once", help="single check pass and exit")
    sub.add_parser("dry-run", help="run all checks but never send email")
    sub.add_parser("test-email", help="send one synthetic email to verify SMTP")
    sim = sub.add_parser("simulate", help="seed telemetry to make a rule fire")
    sim.add_argument("rule_id")
    args = parser.parse_args(argv)

    if args.cmd == "run-once":
        results = run_once(dry_run=False)
        for alert, status in results:
            log.info("FIRED %s %s -> %s", alert.severity, alert.rule_id, status)
        log.info("done; %d alerts processed", len(results))
        return 0
    if args.cmd == "dry-run":
        results = run_once(dry_run=True)
        for alert, status in results:
            log.info("DRY %s %s | %s", alert.severity, alert.rule_id, alert.title)
        log.info("done; %d alerts would have been sent", len(results))
        return 0
    if args.cmd == "test-email":
        result = send_test_email()
        log.info("test email status: %s", result)
        return 0 if result == "sent" else 1
    if args.cmd == "simulate":
        msg = simulate(args.rule_id)
        log.info("simulate: %s", msg)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

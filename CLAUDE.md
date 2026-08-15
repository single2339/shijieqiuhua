# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Security

- **DO NOT hardcode credentials.** The `.env` file at root holds `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `JWT_SECRET`, and `FOOTBALL_DATA_API_KEY` (free key from football-data.org, powers the upcoming-fixtures sidebar). Server passwords and SSH keys must be handled outside this file.
- If you discover exposed secrets (API keys, passwords), flag them immediately and stop — do not proceed with other work until they are rotated.

## Architecture

Two-part system: FastAPI backend (`backend/`), React SPA (`frontend/`). The product is **世界球花 — 足球情报研判** (football-match intelligence research): multi-source OSINT collection per fixture, factor-weighted analysis, and a confidence-graded direction call (never a betting tip).

```
backend/app_football.py  — production entry point (auth + admin + football_osint + billing routers)
backend/football_osint/  — pipeline: sources → evidence → factor scoring → prediction + confidence
backend/auth/, backend/billing/ — accounts, tiers/quota, entitlements
frontend/src/shijieqiuhua/ — the only tree App.tsx actually renders
```

- **Backend (local dev)**: `uvicorn backend.main:app --reload --port 8000` — `main.py` is a dev superset that also wires up `football_osint`/`auth`/`billing`, so it's interchangeable with `app_football.py` locally. **Production runs the leaner `backend.app_football:app`** (see Server Deployment) — when changing routes/startup behavior, keep both entry points consistent.
- **Frontend**: `cd frontend && npm run dev` — Vite dev server on `:5173`, proxies `/api` to `:8000`. Build: `npm run build` (= `tsc && vite build`)

Source layout:
- `backend/football_osint/` — `pipeline.py` (job orchestration), `sources.py` (adapters), `evidence.py`, `factor_registry.py` (scoring rules), `storage.py` (writes `bronze_storage/football_osint/{job_id}/`), `cache.py`, `warm_cache.py` (pre-warms today's matches hourly), `routes.py`, `models.py`
- `backend/auth/` — login/register/admin routes, `backend/billing/` — redeem codes, entitlements (`sql/003_billing_and_entitlements.sql`)
- `frontend/src/shijieqiuhua/` — `api.ts`, `types.ts`, `mockData.ts`, `plans.ts`, `useStagedProgress.ts`, `components/` (`LandingPage`, `AuthScreen`/`AuthGate`, `ReportView`, `PhaseTracker`, `AccountPanel`, `AdminPanel`, `PaywallModal`, `IdleHint`, `EvidenceStrength`)
- `frontend/src/App.tsx` — orchestrator (fixtures, job polling, tier gating); `frontend/src/shijieqiuhua.css` — all `sqh-*` styles (warm beige/brand-green palette, no CSS custom properties — literal hex values)

## Commands

| What | Command | From |
|------|---------|------|
| Run backend | `uvicorn backend.main:app --reload --port 8000` | root (`.venv` active) |
| Run frontend | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` (= `tsc && vite build`) | `frontend/` |
| Frontend test | `npm test` (vitest) | `frontend/` |
| Backend test | `pytest` | root (`.venv` active) |
| Deploy backend | `rsync -avz --exclude='__pycache__' --exclude='*.pyc' backend/ sqh-server:/opt/shijieqiuhua/backend/ && ssh sqh-server 'systemctl restart shijieqiuhua'` | root |
| Deploy frontend | `rsync -avz frontend/dist/ sqh-server:/opt/shijieqiuhua/frontend/dist/` | root (after `npm run build`) |
| Fixtures smoke test | `curl 'http://139.155.117.190/api/football/osint/fixtures?days=7'` | — |
| Service status | `ssh sqh-server 'systemctl status shijieqiuhua --no-pager -n 5'` | — |

Backend test files: `tests/test_football_osint.py`, `tests/test_football_analysis.py`, `tests/test_billing.py`, `tests/test_admin_cli.py`, `tests/test_audit.py`, `tests/test_evidence.py`, `tests/test_telemetry.py`, `tests/test_worker_isolation.py`, `tests/test_alert_runner.py`, `tests/test_cleaner.py`, `tests/test_summarizer.py`.
Frontend test files: `frontend/__tests__/shijieqiuhua-*.test.*`.

## Key Implementation Details

- **Python 3.11+**, `.venv` at root. Dependencies in `requirements.txt`
- **No traditional database for job content** — football OSINT jobs persist as JSON under `bronze_storage/football_osint/{job_id}/`. Accounts/billing/entitlements use the tables in `sql/` (see `backend/auth/db.py`)
- **No pre-commit, no lint config.** Python uses `from __future__ import annotations`; React uses inline `style={{}}` plus the `sqh-*` class system in `shijieqiuhua.css`

### Football OSINT pipeline (`backend/football_osint/`)

- `pipeline.py` orchestrates: fixture → adapter sources (`sources.py`) → evidence (`evidence.py`) → factor scoring (`factor_registry.py`) → prediction + confidence band → `IntelligenceFinding`s (confirmed / assessment) → next-steps
- Honest-uncertainty by design: when key facts (lineups, injuries) aren't released yet, the pipeline returns `lean: "info_insufficient"` rather than forcing a direction
- `warm_cache.py` pre-warms LLM answers for today's matches on startup and hourly while a match is live
- `cache.py` is a thread-safe TTL cache so concurrent requests for the same match reuse schedule/analysis work

### LLM Integration

- All LLM calls use DeepSeek API (`deepseek-chat`) via `LLM_API_KEY` + `LLM_BASE_URL` from `.env`

### Frontend report display

- `App.tsx` polls/creates `FootballOsintJob`s and renders `ReportView` once a job completes
- `ReportView.tsx`: `VerdictCard` (direction + confidence + probability bands) always visible; 情报循环/因子权重/证据链/确认事实+研判推断/替代解释+下一步 live behind a tab bar (`sqh-tabbar`/`sqh-tab`), one panel visible at a time, tabs only appear when their data is non-empty
- Paywall gating: `userTier !== 'paid'` blurs the tab area and shows `sqh-report-veil` with an unlock CTA
- React 19 + framer-motion. Warm beige/brand-green palette defined as literal hex in `shijieqiuhua.css` (no CSS variables)

## Server Deployment

Production server: use `ssh sqh-server` (`root@139.155.117.190`, configured in `~/.ssh/config`). **Do not confuse with `osint-server` (221.239.50.138) or `football-server` (221.239.50.142) — those are different systems.**

```
# Sync backend and restart
rsync -avz --exclude='__pycache__' --exclude='*.pyc' backend/ sqh-server:/opt/shijieqiuhua/backend/
ssh sqh-server 'systemctl restart shijieqiuhua'

# Sync frontend dist/ after local build
rsync -avz frontend/dist/ sqh-server:/opt/shijieqiuhua/frontend/dist/
```

Server stack:
- TencentOS VM, nginx on port 80 (`/etc/nginx/conf.d/shijieqiuhua.conf`: static `root /opt/shijieqiuhua/frontend/dist` + `/api/` proxy to `127.0.0.1:8002`)
- `shijieqiuhua.service` (systemd) — runs **`backend.app_football:app`** on `127.0.0.1:8002`, `WorkingDirectory=/opt/shijieqiuhua`, `EnvironmentFile=/opt/shijieqiuhua/.env`
- `.env` on server must hold `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `JWT_SECRET`, `FOOTBALL_DATA_API_KEY`
- No Node.js on server — frontend must be built locally

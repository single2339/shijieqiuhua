# ShijieQiuhua — AGENTS.md

## Architecture

Current product: FastAPI backend (`backend/`), React SPA (`frontend/`), and runtime state under `bronze_storage/`.

- **Backend**: `uvicorn backend.app_football:app --reload --port 8000` — current production composition root for auth/admin/billing plus football OSINT routes. `backend/main.py` remains only as a compatibility re-export of `backend.app_football.app`.
- **Football OSINT engine**: `backend/football_osint/` — schedules/fixtures, public-source collection, evidence extraction, factor registry, confidence grading, prediction result, Markdown report, history, compare, warm cache, and track-record backfill.
- **Frontend**: `cd frontend && npm run dev` — Vite dev server on `:5173`, proxies `/api` to `:8000`. Build: `npm run build` (`tsc && vite build`).
- **Runtime storage**: `bronze_storage/` — SQLite auth/telemetry DBs plus football job artifacts. Treat as local runtime data, not source. Do not delete without explicit data-loss approval.

## Commands

| What | Command | From |
|------|---------|------|
| Run backend | `uvicorn backend.app_football:app --reload --port 8000` | root (with `.venv` active) |
| Run frontend | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` (= `tsc && vite build`) | `frontend/` |
| Frontend test | `npm test` (vitest) | `frontend/` |
| Backend test | `pytest` | root (with `.venv` active, uses `asyncio_mode=auto`) |

Python deps in `requirements.txt`, frontend deps in `frontend/package.json`.

## Key Details

- **Python 3.11+** required. `.venv` already exists at root.
- **`.env`** at root sets `LLM_API_KEY`, `LLM_BASE_URL` (DeepSeek), `LLM_MODEL`.
- **`frontend/.env.local`** has `VITE_TIANDITU_KEY` for Tianditu map tiles.
- **Public football OSINT routes** live under `/api/football/osint/*`; the legacy simple analyzer remains at `/api/football/analyze`.
- **Auth/billing state** lives in `bronze_storage/_auth.db`; telemetry lives in `bronze_storage/_telemetry.db`; football reports live in `bronze_storage/football_osint/{job_id}/`.
- **Current SQL migrations**: `sql/002_telemetry.sql`, `sql/003_billing_and_entitlements.sql`, `sql/004_prediction_track_record.sql`.
- **Documentation**: `docs/runbook-v1.md`, `docs/football-analysis.md`, and `docs/superpowers/**`.
- **No pre-commit, no lint config** detected. Style is standard Python (`from __future__ import annotations` in many files) + React with framer-motion animations + CSS custom properties (warm beige palette).
- **Frontend tests**: `frontend/__tests__/`.
- **Backend tests**: `tests/test_*.py` (pytest).


# OSINT Network — AGENTS.md

## Architecture

Three-part system: Python collector pipeline (`src/`), FastAPI backend (`backend/`), React SPA (`frontend/`). Shared data lives in `bronze_storage/` (JSON files).

- **Pipeline**: `run.sh` → `python -m src.main` — polls SQLite job queue, fetches RSS feeds (BBC, NYT, Guardian, etc.), translates, summarizes, writes JSON to `bronze_storage/`
- **Backend**: `uvicorn backend.main:app --reload --port 8000` — reads bronze JSON, serves API endpoints. Two modes controlled by `OSINT_COLLECTOR` env var: `demo` (regenerates test data every 30s) or `horizon` (runs Horizon scrapers every 15min)
- **Frontend**: `cd frontend && npm run dev` — Vite dev server on `:5173`, proxies `/api` to `:8000`. Build: `npm run build` (runs `tsc && vite build`)

## Commands

| What | Command | From |
|------|---------|------|
| Run pipeline | `./run.sh` | root |
| Run backend | `uvicorn backend.main:app --reload --port 8000` | root (with `.venv` active) |
| Run frontend | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` (= `tsc && vite build`) | `frontend/` |
| Frontend test | `npm test` (vitest) | `frontend/` |
| Backend test | `pytest` | root (with `.venv` active, uses `asyncio_mode=auto`) |

Python deps in `requirements.txt`, frontend deps in `frontend/package.json`.

## Key Details

- **Python 3.11+** required. `.venv` already exists at root.
- **`.env`** at root sets `LLM_API_KEY`, `LLM_BASE_URL` (DeepSeek), `LLM_MODEL`
- **`frontend/.env.local`** has `VITE_TIANDITU_KEY` for Tianditu map tiles
- **8 Intel layers**: nature, commerce, finance, people, military, aviation, logistics, trade (bilingual keyword classification in `backend/processors/classifier.py`)
- **Bayesian analysis** via `yao-bayesian-skill` engine; source credibility classes: high/medium/low/kol/unknown (defined in `backend/main.py:139-162`)
- **`lib/horizon/`** is a vendored copy of the [Horizon](https://github.com/Thysrael/Horizon) project (AI news radar), used via `backend/collectors/horizon_bridge.py`
- **Schemas** in `schemas/` (JSON Schema for bronze/silver/entity/event/claim)
- **Documentation** in `docs/` covers compliance, collection contracts, medallion architecture, agent plane, roadmap
- **No pre-commit, no lint config** detected. Style is standard Python (`from __future__ import annotations` at top of many files) + React with framer-motion animations + CSS custom properties (warm beige palette)
- **Frontend test file**: `frontend/__tests__/mapview-regression.test.ts` (vitest)
- **Backend test files**: `tests/test_*.py` (pytest)

## Ongoing Tasks: iFairy Reproduction (`ifairy-repro/`)

Training a ComplexLlama model (L8 H1024, 408M params, fp32, FairyQuantizer {±1,±i}) on server **ubuntu@10.13.45.20**. See `ifairy-repro/TRAINING_STATE.md` for full context.

**On session start**: check if training is still running, report progress, and continue debugging.
- SSH: `sshpass -p 'zhangnanxin' ssh -o BindInterface=en0 ubuntu@10.13.45.20`
- Check: `tail -5 /tmp/train.log`
- Attach: `tmux attach -t ifairy`

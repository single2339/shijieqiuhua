# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Security

- **DO NOT hardcode credentials.** The `.env` file at root holds `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. Server passwords and SSH keys must be handled outside this file.
- If you discover exposed secrets (API keys, passwords), flag them immediately and stop — do not proceed with other work until they are rotated.

## Architecture

Three-part system: Python pipeline (`src/`), FastAPI backend (`backend/`), React SPA (`frontend/`). Shared data in `bronze_storage/` (JSON files keyed by date).

```
Collection (horizon_loop, every 15 min):
  RSS/Reddit/HN/Telegram/GitHub → translate → summarize → LLM classify → bronze JSON

Serving (FastAPI):
  bronze JSON → merger (union-find) → _build_items() → classify + location + bayesian → API

Frontend (React 19 + Vite):
  polls /api/dashboard every 10s → MessageFeed + MapView + IntelCard + analysis panels
```

- **Backend**: `uvicorn backend.main:app --reload --port 8000` — two modes via `OSINT_COLLECTOR` env var: `demo` (regenerates test data every 30s) or `horizon` (default — runs Horizon scrapers every 15min)
- **Frontend**: `cd frontend && npm run dev` — Vite dev server on `:5173`, proxies `/api` to `:8000`. Build: `npm run build` (= `tsc && vite build`)

Source layout:
- `src/` — legacy pipeline utilities: `processor/translator`, `processor/summarizer`, `processor/cleaner`, `bronze/writer`, `models/`
- `backend/` — API + live collection:
  - `main.py` — all routes, caching, `horizon_loop()`, `merge_loop()`, `_build_items()` (1771 lines — oversized)
  - `models.py` — Pydantic models + `IntelLayer` enum (12 layers) + analysis types
  - `merger.py` — union-find content merge engine, runs daily at 03:00 UTC
  - `collectors/horizon_bridge.py` — wires Horizon scrapers: translate → summarize → LLM classify → write
  - `collectors/horizon/` — vendored Horizon scraper implementations (RSS, Reddit, HN, Telegram, GitHub)
  - `processors/llm_classifier.py` — LLM-based layer classifier (primary, DeepSeek API)
  - `processors/classifier.py` — keyword-based layer classifier (fallback, 12 keyword groups)
  - `processors/location.py` — geo extraction
  - `processors/analysis.py` — timeline, entity graph, anomaly detection, risk heatmap
  - `osint_sources.py` — data source catalog with credibility scores
  - `bronze_reader.py` — `scan_bronze()` sync file scanner
  - `seed_data.py` — demo data generator (90+ source templates across 16 categories)
- `frontend/src/` — SPA: `App.tsx`, `api.ts`, `types.ts`, `index.css` (warm beige custom properties), `components/` (panels + `analysis/` subdir), `icons/` (12 layer SVG icons), `hooks/`

## Commands

| What | Command | From |
|------|---------|------|
| Run backend | `uvicorn backend.main:app --reload --port 8000` | root (`.venv` active) |
| Run frontend | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` (= `tsc && vite build`) | `frontend/` |
| Frontend test | `npm test` (vitest) | `frontend/` |
| Frontend single test | `npx vitest run -t "test name pattern"` | `frontend/` |
| Backend test | `pytest` | root (`.venv` active) |
| Deploy backend | `source .env && rsync -avz -e "ssh -p 9022" backend/ ubuntu@221.239.50.138:/opt/osint-network/backend/ && ssh osint-server "echo \$SERVER_SUDO_PASSWORD \| sudo -S systemctl restart osint-network.service"` | root |
| Deploy frontend | `source .env && rsync -avz -e "ssh -p 9022" frontend/dist/ ubuntu@221.239.50.138:/opt/osint-network/frontend/dist/` | root (after `npm run build`) |
| Trigger reclassify | `curl -X POST http://221.239.50.138/api/reclassify` | — |
| Trigger merge | `curl -X POST http://221.239.50.138/api/merge` | — |
| Trigger collect | `curl -X POST http://221.239.50.138/api/collect` | — |
| Health check | `curl http://221.239.50.138/api/health` | — |

Backend tests: `tests/test_cleaner.py`, `tests/test_summarizer.py`.
Frontend tests: `frontend/__tests__/api.test.ts`, `mapview-regression.test.ts`, `markdown.test.ts`, `types.test.ts`.

## Intel Layers (12 total)

| Layer | Key | Color | Label |
|-------|-----|-------|-------|
| 自然生态 | nature | `#2ecc71` | 自然生态 |
| 经济产业 | economy | `#3498db` | 经济产业 |
| 金融 | finance | `#f39c12` | 金融 |
| 政治外交 | politics | `#9b59b6` | 政治外交 |
| 军事 | military | `#e74c3c` | 军事 |
| 民航交通 | aviation | `#607d8b` | 民航交通 |
| 科技 | technology | `#ff4081` | 科技 |
| 社会民生 | society | `#e91e63` | 社会民生 |
| 能源资源 | energy | `#ff5722` | 能源资源 |
| 农业食品 | agriculture | `#4caf50` | 农业食品 |
| 公共卫生 | health | `#00bcd4` | 公共卫生 |
| 网络空间 | cyber | `#1a237e` | 网络空间 |

Layer definitions live in **four** places:
1. `backend/models.py` — `IntelLayer` enum
2. `backend/processors/llm_classifier.py` — **primary**: LLM classification via DeepSeek (SYSTEM_PROMPT defines all 12 layers with disambiguation rules)
3. `backend/processors/classifier.py` — **fallback**: keyword-based classifier (12 keyword groups)
4. `frontend/src/types.ts` — TypeScript type + `LAYER_META` (Chinese labels, colors)

Icons in `frontend/src/icons/`, layer panel in `frontend/src/components/LayerPanel.tsx`.

## Key Implementation Details

- **Python 3.11+**, `.venv` at root. Dependencies in `requirements.txt` (minimal) + full deps in `.venv`
- **No database** — all data flows through JSON files in `bronze_storage/`, organized by date subdirectories
- **No pre-commit, no lint config.** Python uses `from __future__ import annotations` + inline styles in React

### Layer Classification

- **Primary**: LLM classifier (`classify_with_llm()`) — called during collection in `horizon_bridge.py`, stores result in `extensions.horizon_metadata.layer`
- **Fallback**: Keyword classifier (`classify()`) — used when no stored layer exists or LLM is unavailable
- **Dashboard read**: `_get_layer(doc)` in `main.py` checks stored layer first, falls back to keyword
- **Reclassification**: `POST /api/reclassify` batch-updates all existing documents with LLM classification

### Content Merge Engine (`merger.py`)

- Union-find on three match keys: same `source_url` → same `content_sha256` → same normalized title
- Runs daily at 03:00 UTC via `merge_loop()` in main.py; manually via `POST /api/merge`
- Output: `bronze_storage/_merge_index.json` — `MergedGroup` objects with `sources: list[str]`
- `_build_items()` reads the merge index to produce multi-source `IntelItem.sources`

### Horizon Bridge (`collectors/horizon_bridge.py`)

- Wires vendored Horizon scrapers (RSS, Reddit, HN, Telegram, GitHub)
- Processing pipeline per item: `_translate_item()` → `_summarize_item()` → `_classify_item()` → `_to_raw_document()`
- `_DEFAULT_RSS_FEEDS` includes international news + Chinese feeds via RSSHub
- Chinese feeds (Weibo, CLS Telegraph, Zaobao) require RSSHub running on server at `127.0.0.1:1200`

### API Endpoints (all in `backend/main.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/dashboard` | Main dashboard data (paginated, cached 30s) |
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Aggregated stats (trends, source matrix, geo, keywords) |
| GET | `/api/collect/status` | Current collection run status |
| POST | `/api/collect` | Trigger collection (optional `hours` param) |
| POST | `/api/merge` | Trigger content merge |
| POST | `/api/reclassify` | Reclassify all documents with LLM |
| POST | `/api/ask` | AI Q&A over intel data |
| POST | `/api/report` | Generate situation report |
| POST | `/api/intel/super-analysis` | Authenticated hypothesis-level Bayesian analysis + web search |
| GET | `/api/super-analysis/progress` | Owner-scoped Super Analysis progress |
| GET | `/api/analysis/timeline` | Timeline analysis (filter by layer, country) |
| GET | `/api/analysis/entities` | Entity graph extraction |
| GET | `/api/analysis/corroboration` | Cross-source corroboration matrix |
| GET | `/api/analysis/anomalies` | Anomaly detection |
| GET | `/api/analysis/risk-heatmap` | Regional risk heatmap |
| GET | `/api/analysis/gaps` | Coverage gap analysis |
| GET | `/api/collect/usgs` | USGS earthquake data collection |
| GET | `/api/collect/cisa` | CISA alerts collection |
| GET | `/api/collect/opensky` | OpenSky flight tracking collection |

### Dashboard Caching

- 30s TTL in `_dashboard_cache`. All scans wrapped in `run_in_executor` to avoid blocking the async event loop
- Dashboard polled every 10s by frontend; `_build_items_async()` used by all analysis endpoints
- Cache invalidated on merge, reclassify, and collect triggers

### Bayesian Engine

- `assess_document_quality()` measures presentation/source quality only; it never emits truth probabilities
- Super Analysis uses a fixed 0.5 hypothesis prior and deterministic likelihood ratios for explicit `support` / `contradict` / `neutral` evidence relations
- Reposts and shared original sources are dependency-grouped before L1–L5 classification
- `/api/intel/super-analysis` is the single authenticated execution route; external search summaries remain neutral until verified

### LLM Integration

- All LLM calls use DeepSeek API (`deepseek-chat`) via `LLM_API_KEY` + `LLM_BASE_URL` from `.env`
- LLM consumers include translation, summarization, classification, Q&A/report generation, and Super Analysis relation/final-analysis passes
- Super Analysis computes probabilities locally; the LLM does not calculate priors or posterior probabilities

### Frontend

- React 19 + framer-motion + MapLibre GL + CSS custom properties
- Warm beige palette (`--bg-deep: #f5f2ed`). Fonts: Satoshi/Geist + JetBrains Mono
- Map tiles via Tianditu (key in `frontend/.env.local`)
- **Responsive**: `useIsMobile()` hook (breakpoint 767px). Mobile: hamburger menu, horizontal layer strip, full-screen overlays
- Components: `MessageFeed`, `MapView`, `IntelCard`, `LayerPanel`, `AskPanel`, `ReportPanel`, `StatsPanel`, `SourcePanel`, `IntelAnalysisPanel`, `SuperAnalysisPanel`, `SuperAnalysisSidebar`, `MobileMenu`, `StatusDot`
- Analysis sub-components: `TimelineView`, `EntityGraphView`, `CorroborationView`, `AnomalyView`, `RiskHeatmapView`, `GapAnalysisView`, `AIInterpretBadge`

## Adding a New Intel Layer

Files to touch (order matters):
1. `backend/models.py` — add to `IntelLayer` enum
2. `backend/processors/llm_classifier.py` — add to SYSTEM_PROMPT with disambiguation rules
3. `backend/processors/classifier.py` — add keyword rules to `_LAYER_RULES` (fallback)
4. `frontend/src/types.ts` — add to `IntelLayer` type + `LAYER_META` (label + color)
5. `frontend/src/icons/<NewIcon>.tsx` — create SVG icon component
6. `frontend/src/components/LayerPanel.tsx` — import and register in `iconMap`
7. `frontend/src/App.tsx`, `AskPanel.tsx`, `ReportPanel.tsx` — add to `ALL_LAYERS`
8. `frontend/src/components/analysis/TimelineView.tsx` — add to `LAYERS`
9. `backend/osint_sources.py` — add data sources with `layer_bias`
10. `backend/collectors/horizon_bridge.py` — add RSS feeds to `_DEFAULT_RSS_FEEDS`

## Performance Notes

- `scan_bronze()` reads thousands of JSON files synchronously. Never call it directly in an async handler — always wrap in `run_in_executor` or use `scan_bronze_async()`
- Dashboard is polled every 10s by frontend. The 30s cache prevents repeated full scans
- The merge index (`_merge_index.json`) reduces per-request computation by pre-computing document groups
- `backend/main.py` is 1771 lines — well over the 800-line guideline. Consider splitting routes into separate modules under `backend/routes/`

## Server Deployment

Production server: use `ssh osint-server` (configured in `~/.ssh/config` with ControlMaster multiplexing).

```
# Sync backend and restart
rsync -avz -e "ssh -p 9022" backend/ ubuntu@221.239.50.138:/opt/osint-network/backend/
ssh osint-server 'sudo systemctl restart osint-network.service'

# Sync frontend dist/ after local build
rsync -avz -e "ssh -p 9022" frontend/dist/ ubuntu@221.239.50.138:/opt/osint-network/frontend/dist/
```

Server stack:
- Ubuntu 24.04, nginx on port 80 (static files + `/api/` proxy to `127.0.0.1:8000`)
- `osint-network.service` (systemd) — the FastAPI backend
- RSSHub Docker container on `:1200` — provides RSS feeds for Weibo, CLS, Zaobao
- No Node.js on server — frontend must be built locally

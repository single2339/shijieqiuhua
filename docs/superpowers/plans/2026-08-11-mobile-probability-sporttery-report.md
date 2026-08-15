# Mobile Verdict, Distinct Probabilities, and Sporttery Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the football analysis usable on phones, present one concise and clearly differentiated verdict, and incorporate official China Sporttery 1X2/handicap information plus post-match handicap settlement into the analysis record.

**Architecture:** Keep the existing OSINT evidence pipeline as the source of football fundamentals. Add a typed Sporttery market snapshot extracted from the existing adapter, calculate a normalized model probability distribution from the score matrix, and blend it with de-margin Sporttery probabilities only when both sides have usable market data. The frontend receives one compact `PredictionResult` containing the primary outcome and, where available, the official handicap reference; all evidence/process views remain available behind collapsed disclosure sections.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, sqlite3, pytest; React 19, TypeScript, Vitest, existing CSS custom properties and Phosphor icons.

---

## Product decisions and assumptions

These decisions remove the ambiguous parts of the request before implementation:

1. **“受让球” means the official China Sporttery `HHAD` (让球胜平负) line.** The displayed line is always expressed from the home team's perspective: `+1` means the home team is receiving one goal; `-1` means the home team gives one goal.
2. **“实际体彩结果” means official 90-minute Sporttery settlement.** The history record stores both the ordinary 1X2 result and, when a valid HHAD line was available at prediction time, the derived handicap result. Extra time and penalties are excluded.
3. **The product remains an information/analysis product, not a betting product.** Do not show stake, payout, “recommended ticket”, or buy/sell language. Label the new block “体彩官方盘口参考” and retain the existing disclaimer.
4. **The primary probability is a point probability, not a ±4% interval.** The UI shows `主胜 48% / 平局 27% / 客胜 25%`, ranked high to low. A direction is “clear” only when the top outcome exceeds the runner-up by at least 5 percentage points; otherwise the summary must explicitly say “优势不足，存在接近结果”.
5. **Mobile compatibility targets modern mobile browsers from 320 CSS px wide upward.** It is responsive web design, not a separate native app. The verdict is always visible; long process content is collapsed by default at every screen width.

## Why the current implementation does not meet the request

- `backend/football_osint/adapters/sporttery.py` already fetches `HAD` and `HHAD`, but `backend/football_osint/pipeline.py` explicitly excludes it from the collection fan-out. Therefore the result shown to the user neither sees the official handicap nor records a handicap conclusion.
- `backend/football_osint/analysis/prediction.py` computes `home_mid = 0.36 + edge` and `away_mid = 0.32 - edge`; `draw_mid` consequently stays near `0.32`. The fixed `±0.04` display band makes modest differences look like the same 30%-range result.
- `frontend/src/shijieqiuhua/components/ReportView.tsx` renders the full verdict and then a tab bar. The existing CSS stacks grids at narrow widths but does not make the main conclusion shorter or make analysis-on-demand the default interaction.
- `frontend/src/shijieqiuhua.css` converts the main dashboard to one column below 1080 px, but the fixture rail remains a long vertical panel and report process controls still consume substantial above-the-fold space on a phone.

## File map

| File | Change | Responsibility |
| --- | --- | --- |
| `backend/football_osint/models.py` | Modify | Define typed market, handicap conclusion, and exact outcome probabilities in the job API contract. |
| `backend/football_osint/adapters/sporttery.py` | Modify | Parse the official handicap, preserve its odds, and expose a normalized snapshot for the pipeline. |
| `backend/football_osint/analysis/market.py` | Create | Convert odds to normalized probabilities and calculate outcomes from the score matrix, including handicap settlement. |
| `backend/football_osint/factor_registry.py` | Modify | Add a traceable market-reference factor without allowing odds alone to manufacture a fundamental verdict. |
| `backend/football_osint/analysis/prediction.py` | Modify | Replace fixed probability bands with normalized exact model/fused probabilities and an explicit conclusion margin. |
| `backend/football_osint/pipeline.py` | Modify | Collect Sporttery in parallel, produce the snapshot, and pass it to factor building and prediction. |
| `sql/005_sporttery_handicap_settlement.sql` | Create | Add immutable handicap prediction and settlement fields to `prediction_record`. |
| `backend/auth/db.py` | Modify | Load migration 005 for existing and new local SQLite databases. |
| `backend/football_osint/track_record.py` | Modify | Persist and settle official handicap outcomes; include them in history details without changing the primary WDL hit-rate denominator. |
| `backend/football_osint/history.py` | Modify | Return the handicap reference/result in a single-game history detail. |
| `frontend/src/shijieqiuhua/types.ts` | Modify | Mirror the API contract in TypeScript. |
| `frontend/src/shijieqiuhua/components/ReportView.tsx` | Modify | Render a concise verdict + Sporttery reference and use accessible collapsed detail sections. |
| `frontend/src/shijieqiuhua/components/PostMatchReview.tsx` | Modify | Show the actual handicap settlement where one was recorded. |
| `frontend/src/shijieqiuhua.css` | Modify | Establish phone-first verdict/process layout and touch-safe controls. |
| `tests/test_sporttery_market.py` | Create | Unit-test official odds parsing, handicap semantics, and no-coverage fallback. |
| `tests/test_football_osint_prediction.py` | Modify | Lock down normalized, distinct outcomes, fusion, and no-market behavior. |
| `tests/test_football_security.py` | Modify | Replace the obsolete test asserting that Sporttery must never be collected. |
| `tests/test_track_record.py` | Modify | Verify database persistence and 90-minute HHAD settlement. |
| `frontend/__tests__/reportview-verdict.test.tsx` | Create | Verify concise verdict, collapsed process, market reference, and history settlement text. |
| `docs/football-analysis.md` | Modify | Document the odds-as-reference policy, formula, and 90-minute settlement scope. |

## API contract to implement first

Add these models in `backend/football_osint/models.py`, above `PredictionResult`:

```python
class OutcomeProbabilities(BaseModel):
    home_win: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away_win: float = Field(ge=0.0, le=1.0)


class OutcomeOdds(BaseModel):
    home_win: float = Field(gt=0.0)
    draw: float = Field(gt=0.0)
    away_win: float = Field(gt=0.0)


class SportteryMarket(BaseModel):
    provider: Literal["sporttery"] = "sporttery"
    had_odds: OutcomeOdds | None = None
    had_implied_probabilities: OutcomeProbabilities
    home_handicap: int | None = None
    hhad_odds: OutcomeOdds | None = None
    hhad_implied_probabilities: OutcomeProbabilities | None = None
    observed_at: str


class HandicapConclusion(BaseModel):
    home_handicap: int
    outcome: Literal["home", "draw", "away"]
    probability: float = Field(ge=0.0, le=1.0)
    margin_to_runner_up: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "close"]
```

Replace `PredictionResult.probability_band` with the following fields. This is an intentional breaking change for the one internal frontend consumer; it avoids carrying a misleading range in the public job API.

```python
class PredictionResult(BaseModel):
    lean: Literal["home", "away", "draw", "home_or_draw", "away_or_draw", "info_insufficient"]
    summary: str
    outcome_probabilities: OutcomeProbabilities
    primary_probability: float = Field(ge=0.0, le=1.0)
    margin_to_runner_up: float = Field(ge=0.0, le=1.0)
    clarity: Literal["clear", "close", "insufficient"]
    scoreline_band: list[str]
    drivers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    sporttery_market: SportteryMarket | None = None
    handicap_conclusion: HandicapConclusion | None = None
```

Add this `@model_validator(mode="before")` to `PredictionResult` so existing `bronze_storage` jobs remain readable. It converts each former interval to its midpoint, normalizes the three values, derives `primary_probability`, `margin_to_runner_up`, and `clarity`, and then removes `probability_band` from the input dictionary. This compatibility path is for persisted historical jobs only; new prediction code must never produce `probability_band`.

The frontend counterpart has exactly the same field names, with `OutcomeProbabilities` as `{ home_win: number; draw: number; away_win: number }` and an `OutcomeOdds` interface with the same keys. Do not use anonymous `Record<string, number>` for these values; TypeScript must prevent a typo such as `home` from silently rendering `undefined`.

### Task 1: Lock down the contract and database migration

**Files:**
- Modify: `backend/football_osint/models.py`
- Modify: `frontend/src/shijieqiuhua/types.ts`
- Create: `sql/005_sporttery_handicap_settlement.sql`
- Modify: `backend/auth/db.py`
- Test: `tests/test_track_record.py`

- [ ] **Step 1: Write contract tests before changing the models.** Add a fixture that validates a completed job with exact outcomes and a `+1` home handicap. Assert that `model_dump(mode="json")` contains `outcome_probabilities`, `sporttery_market.home_handicap`, and `handicap_conclusion.outcome`; assert an invalid probability of `1.01` raises `ValidationError`.

- [ ] **Step 2: Add the Pydantic and TypeScript interfaces shown in “API contract”.** Add the legacy `probability_band` validator described above and tests that load a legacy status payload. Update new test fixtures to use all three exact outcome fields plus `primary_probability`, `margin_to_runner_up`, and `clarity`. For historical JSON without a Sporttery snapshot, the validator supplies `sporttery_market: null` and `handicap_conclusion: null`.

- [ ] **Step 3: Write migration `sql/005_sporttery_handicap_settlement.sql`.**

```sql
ALTER TABLE prediction_record ADD COLUMN sporttery_home_handicap INTEGER;
ALTER TABLE prediction_record ADD COLUMN predicted_hhad_outcome TEXT;
ALTER TABLE prediction_record ADD COLUMN predicted_hhad_probability REAL;
ALTER TABLE prediction_record ADD COLUMN actual_hhad_outcome TEXT;
ALTER TABLE prediction_record ADD COLUMN hhad_correct INTEGER;
```

Use this idempotent migration runner in `backend/auth/db.py`, immediately around the 005 script execution, because SQLite has no `ADD COLUMN IF NOT EXISTS` on all supported builds:

```python
try:
    _local.conn.executescript(sql_path.read_text(encoding="utf-8"))
except sqlite3.OperationalError as exc:
    if migration != "005_sporttery_handicap_settlement.sql" or "duplicate column name" not in str(exc):
        raise
```

Append `"005_sporttery_handicap_settlement.sql"` to `_EXTRA_MIGRATIONS` after 004. This only tolerates a partially applied 005 migration; any other migration error remains fatal.

- [ ] **Step 4: Run the focused RED/GREEN checks.**

```bash
pytest tests/test_track_record.py -v
cd frontend && npm test -- --run frontend/__tests__/shijieqiuhua-osint-api.test.ts
```

Expected after implementation: both commands pass and an existing `prediction_record` table exposes the five new columns through `PRAGMA table_info(prediction_record)`.

- [ ] **Step 5: Commit.**

```bash
git add backend/football_osint/models.py frontend/src/shijieqiuhua/types.ts sql/005_sporttery_handicap_settlement.sql backend/auth/db.py tests/test_track_record.py frontend/__tests__/shijieqiuhua-osint-api.test.ts
git commit -m "feat: add sporttery market and handicap result contract"
```

### Task 2: Make the existing Sporttery adapter a reliable market source

**Files:**
- Modify: `backend/football_osint/adapters/sporttery.py`
- Create: `backend/football_osint/analysis/market.py`
- Test: `tests/test_sporttery_market.py`

- [ ] **Step 1: Write failing adapter tests with a minimal official-style response.** Cover these fixtures:

```python
raw = {
    "success": True,
    "value": {"matchInfoList": [{"subMatchList": [{
        "matchId": "2040327", "matchDate": "2026-08-11", "matchTime": "20:00:00",
        "homeTeamAllName": "主队", "awayTeamAllName": "客队", "leagueAllName": "测试联赛",
        "had": {"h": "2.10", "d": "3.30", "a": "3.60"},
        "hhad": {"goalLine": "+1", "h": "1.52", "d": "3.80", "a": "4.50"},
    }]}]},
}
```

Assert that the adapter parses the three HAD odds, the three HHAD odds, and a home handicap of `1`. Add a second test for `"(-1)"` producing `-1`, and a third test for an unknown/malformed line producing `None` and suppressing the handicap conclusion rather than guessing.

- [ ] **Step 2: Add pure helpers in `analysis/market.py`.** Implement these exact functions so odds parsing and football maths are independently testable:

```python
from __future__ import annotations

import re
from typing import Literal

from ..models import OutcomeOdds, OutcomeProbabilities


def normalize_decimal_odds(odds: OutcomeOdds) -> OutcomeProbabilities:
    inverse = {
        "home_win": 1.0 / odds.home_win,
        "draw": 1.0 / odds.draw,
        "away_win": 1.0 / odds.away_win,
    }
    total = sum(inverse.values())
    return OutcomeProbabilities(**{key: value / total for key, value in inverse.items()})


def parse_home_handicap(raw: str) -> int | None:
    match = re.search(r"[（(]?\s*([+-]?\d+)\s*[）)]?", raw)
    return int(match.group(1)) if match else None


def score_matrix_probabilities(matrix: dict[tuple[int, int], float]) -> OutcomeProbabilities:
    total = sum(matrix.values())
    home = sum(value for (home_goals, away_goals), value in matrix.items() if home_goals > away_goals)
    draw = sum(value for (home_goals, away_goals), value in matrix.items() if home_goals == away_goals)
    away = total - home - draw
    return OutcomeProbabilities(home_win=home / total, draw=draw / total, away_win=away / total)


def settle_handicap(home_score: int, away_score: int, home_handicap: int) -> Literal["home", "draw", "away"]:
    adjusted_home_score = home_score + home_handicap
    if adjusted_home_score > away_score:
        return "home"
    if adjusted_home_score < away_score:
        return "away"
    return "draw"


def handicap_probabilities(matrix: dict[tuple[int, int], float], home_handicap: int) -> OutcomeProbabilities:
    buckets = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for (home, away), value in matrix.items():
        buckets[settle_handicap(home, away, home_handicap)] += value
    total = sum(buckets.values())
    return OutcomeProbabilities(
        home_win=buckets["home"] / total,
        draw=buckets["draw"] / total,
        away_win=buckets["away"] / total,
    )
```

`normalize_decimal_odds` must reject any non-positive input by returning `None` at its caller, not by emitting zero probabilities. `score_matrix_probabilities` and `handicap_probabilities` must normalize their three returned values so their sum is `1.0` within `1e-9`. `settle_handicap(1, 1, 1)` returns `"home"`; `settle_handicap(1, 2, 1)` returns `"draw"`; `settle_handicap(1, 3, 1)` returns `"away"`.

- [ ] **Step 3: Keep the adapter’s public lookup but make matching deterministic.** In `get_odds`, first match the official `matchId` when the request’s `provider_match_id` is a Sporttery ID; otherwise require normalized home team, away team, and same CST calendar date when `kickoff_at` parses. Only fall back to exact team names if the caller did not provide a parseable date. This avoids taking stale odds from a different meeting of the same teams.

- [ ] **Step 4: Return one typed `SportteryMarket` from raw adapter data.** Put this factory in `sporttery.py`:

```python
def market_snapshot(odds: SportteryOdds, *, observed_at: str) -> SportteryMarket | None:
    if odds.had_h <= 0 or odds.had_d <= 0 or odds.had_a <= 0:
        return None
    had = OutcomeOdds(home_win=odds.had_h, draw=odds.had_d, away_win=odds.had_a)
    hhad = None
    home_handicap = parse_home_handicap(odds.hhad_goal_line)
    if all(value is not None and value > 0 for value in (odds.hhad_h, odds.hhad_d, odds.hhad_a)) and home_handicap is not None:
        hhad = OutcomeOdds(home_win=odds.hhad_h, draw=odds.hhad_d, away_win=odds.hhad_a)
    return SportteryMarket(
        had_odds=had,
        had_implied_probabilities=normalize_decimal_odds(had),
        home_handicap=home_handicap if hhad else None,
        hhad_odds=hhad,
        hhad_implied_probabilities=normalize_decimal_odds(hhad) if hhad else None,
        observed_at=observed_at,
    )
```

The stored evidence `raw_excerpt` remains JSON for auditability, but all prediction code must use the typed snapshot, not regexes over the human-readable evidence claim.

- [ ] **Step 5: Run focused tests.**

```bash
pytest tests/test_sporttery_market.py -v
```

Expected: parsing, de-margin normalization, score settlement, malformed-line fallback, and date-aware match selection pass without real network access.

- [ ] **Step 6: Commit.**

```bash
git add backend/football_osint/adapters/sporttery.py backend/football_osint/analysis/market.py tests/test_sporttery_market.py
git commit -m "feat: normalize sporttery handicap market data"
```

### Task 3: Replace look-alike probability bands with score-matrix and market fusion

**Files:**
- Modify: `backend/football_osint/analysis/prediction.py`
- Modify: `backend/football_osint/factor_registry.py`
- Modify: `backend/football_osint/pipeline.py`
- Modify: `tests/test_football_osint_prediction.py`
- Modify: `tests/test_football_security.py`

- [ ] **Step 1: Write failing probability tests.** Add these assertions; they define the observable product behavior:

```python
def test_probability_distribution_is_normalized_and_has_a_clear_favourite():
    result = predict(_request("2026-08-11 20:00"), [_direction_factor(impact=0.18)])
    p = result.outcome_probabilities
    assert p.home_win > p.draw > 0
    assert p.home_win > p.away_win
    assert abs(p.home_win + p.draw + p.away_win - 1.0) < 1e-9
    assert result.clarity == "clear"
    assert result.margin_to_runner_up >= 0.05

def test_sporttery_market_moves_but_does_not_replace_a_fundamental_model():
    market = SportteryMarket(
        had_odds=OutcomeOdds(home_win=2.17, draw=3.45, away_win=4.00),
        had_implied_probabilities=OutcomeProbabilities(home_win=.46, draw=.29, away_win=.25),
        observed_at="2026-08-11T12:00:00+08:00",
    )
    model_only = predict(_request("2026-08-11 20:00"), [_direction_factor(impact=0.18)])
    result = predict(_request("2026-08-11 20:00"), [_direction_factor(impact=0.18)], market=market)
    assert result.outcome_probabilities.home_win > .46
    assert result.outcome_probabilities.home_win < model_only.outcome_probabilities.home_win

def test_close_distribution_is_explicitly_labelled_close():
    result = predict(_request("2026-08-11 20:00"), [_direction_factor(impact=0.01)])
    assert result.clarity == "close"
    assert "优势不足" in result.summary
```

The model-only intermediate probability is test-only information: return it from a private helper `_model_distribution`, not from the API response.

- [ ] **Step 2: Build a single normalized score matrix in `prediction.py`.** Refactor the existing Poisson loop so `_score_matrix(lean: str, edge: float, factors: list[FactorImpact], draw_pressure: float) -> dict[tuple[int, int], float]` creates scores from `0..6` for both teams, applies the current lean/draw/weather/youth multipliers, and normalizes all cells after weighting. Derive both `scoreline_band` and model W/D/L probabilities from this one matrix. Delete `band()` and `probability_band`; no fixed 32% draw midpoint remains.

- [ ] **Step 3: Fuse probabilities with fixed, auditable weights.** When a complete HAD market is available *and* at least one form/h2h/squad factor is active, calculate:

```text
fundamental coverage >= 2 factors:  65% model + 35% Sporttery HAD
fundamental coverage == 1 factor:   45% model + 55% Sporttery HAD
no complete HAD market:             100% model
```

Normalize once more after blending to eliminate rounding drift. Never use a Sporttery market by itself to change `info_insufficient` into a direction; attach it as a reference only. Derive `lean` from the highest fused W/D/L probability, except retain the existing cautious `home_or_draw` / `away_or_draw` behavior when draw-risk rules apply. Set `clarity="clear"` at a top-two difference of `>= 0.05`, otherwise `"close"`; use `"insufficient"` for no fundamental signal.

- [ ] **Step 4: Include Sporttery as a traceable, bounded factor.** Add a keyword-only `market: SportteryMarket | None = None` parameter to `factor_registry.build_factors(request: FootballOsintJobRequest, profile: MatchProfile, evidence: list[OsintEvidence], *, market: SportteryMarket | None = None)`. It adds `market.sporttery_had` only for a complete HAD snapshot, with label `体彩胜平负市场`, group `market`, weight `0.08`, direction equal to the highest official implied outcome, and impact equal to `top_probability - runner_up_probability` (clamped to `0.18`). Its presence may appear in `drivers`, but it is excluded from `active_factors` used to decide whether fundamentals exist.

- [ ] **Step 5: Collect Sporttery alongside the independent I/O.** Import `sporttery` in `pipeline.py`, add `_collect_one_sporttery`, and include it in the existing `ThreadPoolExecutor` fan-out. On success append `OsintSourceStatus(adapter="sporttery", label="中国体育彩票盘口", status="ok", evidence_ids=[sporttery_evidence_id])`; on no coverage use `skipped`, never `failed`. The collector returns `(SportteryMarket | None, sporttery_evidence_id, reason)` so the typed snapshot reaches factor building and `predict` without re-fetching the API.

- [ ] **Step 6: Replace the old security expectation.** Rename `test_zero_config_collection_does_not_attach_sporttery_odds` to assert the opposite scoped behavior: mocked Sporttery success produces exactly one `odds.sporttery.market` evidence item and source status; mocked no-coverage produces no odds evidence and a `skipped` source. Keep the test that third-party odds embedded in an unrelated Dongqiudi page are not parsed.

- [ ] **Step 7: Run focused regression tests.**

```bash
pytest tests/test_sporttery_market.py tests/test_football_osint_prediction.py tests/test_football_security.py -v
```

Expected: all probability totals are normalized, at least the strong-favourite case has a 5-point-or-greater lead, HHAD output only appears for a valid official line, and no external network is used by tests.

- [ ] **Step 8: Commit.**

```bash
git add backend/football_osint/analysis/prediction.py backend/football_osint/factor_registry.py backend/football_osint/pipeline.py tests/test_football_osint_prediction.py tests/test_football_security.py
git commit -m "feat: fuse sporttery market into distinct match probabilities"
```

### Task 4: Persist and display official handicap settlement after the match

**Files:**
- Modify: `backend/football_osint/track_record.py`
- Modify: `backend/football_osint/history.py`
- Modify: `frontend/src/shijieqiuhua/types.ts`
- Modify: `frontend/src/shijieqiuhua/components/PostMatchReview.tsx`
- Modify: `tests/test_track_record.py`
- Modify: `frontend/__tests__/reportview-verdict.test.tsx`

- [ ] **Step 1: Write failing track-record tests.** Create a completed job with `handicap_conclusion=HandicapConclusion(home_handicap=1, outcome="draw", probability=0.41, margin_to_runner_up=0.08, clarity="clear")`. Assert `record_if_definite` writes `sporttery_home_handicap=1`, `predicted_hhad_outcome="draw"`, and `predicted_hhad_probability=0.41`. Then settle it with the final score `1-2` and assert `actual_hhad_outcome="draw"`, `hhad_correct=1`; settle an unmatched prediction and assert `hhad_correct=0`.

- [ ] **Step 2: Persist snapshot-at-prediction values in `record_if_definite`.** Extend the INSERT columns and values with the three predicted handicap fields. When `job.prediction.handicap_conclusion is None`, store SQL `NULL` in all three fields. Do not fetch live odds during backfill: the historical evaluation must use the line the user saw when the analysis was created.

- [ ] **Step 3: Derive actual HHAD result in `settle_pending`.** Select `sporttery_home_handicap` and `predicted_hhad_outcome`; after obtaining the official 90-minute score, call `market.settle_handicap`. Update `actual_hhad_outcome` and set `hhad_correct` only if both a handicap and predicted HHAD outcome exist; otherwise leave both fields `NULL`.

- [ ] **Step 4: Add fields to one-match history only.** `history.get_history_detail` returns this optional object under `record.sporttery_handicap`:

```python
{
    "home_handicap": 1,
    "predicted_outcome": "draw",
    "predicted_probability": 0.41,
    "actual_outcome": "draw",
    "correct": True,
}
```

Do not add HHAD results to the landing-page aggregate hit rate in this release; its existing denominator is W/D/L and must remain comparable. The single-game detail makes the result auditable without blending two different markets into one metric.

- [ ] **Step 5: Render the history block in `PostMatchReview.tsx`.** When `record.sporttery_handicap` exists, show one compact row: `体彩让球（主队 +1）｜研判：让平（41%）｜赛果：让平｜命中`. When absent, render nothing. The labels are presentation-only mappings: `{ home: "让胜", draw: "让平", away: "让负" }`.

- [ ] **Step 6: Run settlement tests.**

```bash
pytest tests/test_track_record.py tests/test_history.py -v
cd frontend && npm test -- --run frontend/__tests__/reportview-verdict.test.tsx frontend/__tests__/shijieqiuhua-app.test.tsx
```

Expected: W/D/L statistics are unchanged; a stored HHAD decision is settled exactly from the 90-minute score and shows in the detail view.

- [ ] **Step 7: Commit.**

```bash
git add backend/football_osint/track_record.py backend/football_osint/history.py frontend/src/shijieqiuhua/types.ts frontend/src/shijieqiuhua/components/PostMatchReview.tsx tests/test_track_record.py tests/test_history.py frontend/__tests__/reportview-verdict.test.tsx
git commit -m "feat: settle sporttery handicap conclusions against final scores"
```

### Task 5: Deliver a phone-first concise verdict with optional analysis

**Files:**
- Modify: `frontend/src/shijieqiuhua/components/ReportView.tsx`
- Modify: `frontend/src/shijieqiuhua.css`
- Create: `frontend/__tests__/reportview-verdict.test.tsx`

- [ ] **Step 1: Write the rendering tests before the component change.** Render one paid report with outcomes `{ home_win: .48, draw: .27, away_win: .25 }`, clear primary home direction, and an HHAD `+1` conclusion. Assert the HTML contains all of the following exact user-visible strings:

```text
主胜 48%
平局 27%
客胜 25%
首选主胜 · 领先 21 个百分点
体彩官方盘口参考
主队受让 +1
让平 · 41%
查看完整分析过程
```

Render a close report (`.35/.33/.32`) and assert `优势不足，存在接近结果` instead of any “明确” wording. Render a no-market report and assert the Sporttery block is absent.

- [ ] **Step 2: Replace `ProbabilityBands` with ranked exact outcomes.** In `ReportView.tsx`, sort the three typed values descending and render each as `label + rounded percent`; add a lead sentence from `prediction.margin_to_runner_up`. The leading cell has `data-lead="true"`; all other cells are visually quieter. Never infer the leading item from `lean`, because a cautious double-chance lean and the highest exact W/D/L outcome are not necessarily the same concept.

- [ ] **Step 3: Make the top card a compact conclusion.** The always-visible card contains only: direction headline, confidence badge, one-sentence summary, ranked exact probabilities, primary scoreline chips, up to two driver labels, and the optional official Sporttery reference. Split/remove verbose wording from the existing summary: the backend summary must be at most 42 Chinese characters for a normal verdict and must use one of these templates:

```text
首选主胜，模型与公开信息支持主队，领先 21 个百分点。
首选主胜，但与平局接近，优势不足。
基础信息不足；仅展示官方市场参考，不形成方向结论。
```

- [ ] **Step 4: Replace the default tab panel with disclosures.** Use native `<details>` / `<summary>` elements inside the existing paid gate:

```tsx
<details className="sqh-analysis-disclosure">
  <summary><ListChecks size={16} weight="duotone" />查看完整分析过程</summary>
  <div className="sqh-analysis-disclosure-body">
    {/* existing tab buttons and active panel */}
  </div>
</details>
```

`details` is closed by default and persists no client state. Keep the existing tab behavior *inside* the disclosure so no current detailed content is removed. The locked teaser remains closed and does not leak paid evidence in server-rendered HTML.

- [ ] **Step 5: Add responsive CSS at the end of `shijieqiuhua.css`.** Implement these exact breakpoints and constraints:

```css
@media (max-width: 640px) {
  .sqh-shell { padding: 8px; gap: 8px; }
  .sqh-match-rail { max-height: 38dvh; }
  .sqh-verdict { padding: 16px; border-radius: 16px; }
  .sqh-verdict-headline { font-size: 24px; }
  .sqh-prob-grid { grid-template-columns: 1fr; gap: 8px; }
  .sqh-prob-cell { display: grid; grid-template-columns: 1fr auto; align-items: center; padding: 10px 12px; }
  .sqh-prob-bar { grid-column: 1 / -1; }
  .sqh-tabbar { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
  .sqh-tab { flex: 0 0 auto; min-height: 40px; }
  .sqh-analysis-disclosure summary { min-height: 44px; }
}
```

Add `padding-bottom: env(safe-area-inset-bottom)` to `.sqh-app`, retain a single vertical scroll owner (`.sqh-app` below 1080px), and verify there is no horizontal overflow. Do not add a mobile-only route or duplicate component tree.

- [ ] **Step 6: Manually verify at 320, 375, and 430 CSS px in browser devtools.** Check the selected fixture, verdict, one probability row, and the disclosure summary are visible without horizontal scrolling; tap targets are at least 40 px high; opening the disclosure does not jump the page; and the desktop three-column dashboard remains unchanged at 1280 px.

- [ ] **Step 7: Run frontend checks.**

```bash
cd frontend && npm test -- --run frontend/__tests__/reportview-verdict.test.tsx frontend/__tests__/reportview-data-quality.test.ts frontend/__tests__/shijieqiuhua-app.test.tsx
cd frontend && npm run build
```

Expected: tests pass and `tsc && vite build` exits 0.

- [ ] **Step 8: Commit.**

```bash
git add frontend/src/shijieqiuhua/components/ReportView.tsx frontend/src/shijieqiuhua.css frontend/__tests__/reportview-verdict.test.tsx
git commit -m "feat: prioritize concise mobile football verdicts"
```

### Task 6: Document the method and execute end-to-end verification

**Files:**
- Modify: `docs/football-analysis.md`
- Test: all affected backend and frontend suites

- [ ] **Step 1: Add a “体彩官方盘口参考” section to `docs/football-analysis.md`.** State the source (`sporttery.cn`), the de-margin normalization formula `p_i=(1/o_i)/Σ(1/o_j)`, the 65/35 and 45/55 fusion weights, the rule that odds alone cannot create a directional conclusion, the home-perspective handicap convention, and the 90-minute-only settlement rule.

- [ ] **Step 2: Add a “Probability presentation” section.** State that all three exact W/D/L probabilities sum to 100% after rounding correction, and that a conclusion is called clear only at a top-two difference of at least 5 percentage points. Document that process views are collapsed initially to keep the result scan-friendly on mobile.

- [ ] **Step 3: Run the full relevant verification set.**

```bash
pytest tests/test_sporttery_market.py tests/test_football_osint_prediction.py tests/test_football_osint.py tests/test_football_security.py tests/test_track_record.py tests/test_history.py -v
cd frontend && npm test
cd frontend && npm run build
```

Expected: all commands pass. If any fixture still supplies `probability_band`, update that fixture to the contract in Task 1; do not restore the old compatibility field.

- [ ] **Step 4: Run a local smoke test with Sporttery mocked.** Submit an authenticated OSINT job whose mocked adapter returns HAD and HHAD. Verify the job response contains a concise summary, three non-equal exact outcomes that total 1, `sporttery_market`, and `handicap_conclusion`; settle the stored record and verify the history response returns its actual HHAD outcome.

- [ ] **Step 5: Commit.**

```bash
git add docs/football-analysis.md
git commit -m "docs: describe sporttery probability and settlement policy"
```

## Acceptance criteria

1. At 320, 375, and 430 px the user can select a fixture, read the verdict, read all three exact W/D/L probabilities, and open “查看完整分析过程” without horizontal scrolling.
2. A completed, sufficiently evidenced prediction returns three exact probabilities that total 1.0 and uses `clarity="clear"` only when the lead is at least 5 percentage points; it never renders the former fixed ±4% bands.
3. When Sporttery covers a match, the response includes official HAD and valid HHAD data, displays a home-perspective handicap reference, and uses the specified fusion weights. When it does not cover a match, analysis completes normally with no market block.
4. Odds-only data is visible as a reference but does not convert `info_insufficient` into a directional conclusion.
5. A record with an HHAD conclusion stores the line seen at prediction time, resolves the official 90-minute handicap result after the match, and displays hit/miss in the single-game history detail. Existing W/D/L aggregate hit-rate semantics do not change.
6. Free users do not receive paid evidence/process HTML through the collapsed section, and the existing paid gate remains enforced server-side.

## Plan self-review

- **Coverage:** Tasks 5 covers mobile and concise/collapsed presentation; Task 3 covers differentiated probability; Tasks 2–4 cover Sporttery handicap input and final-result settlement.
- **No speculative scope:** No new betting workflow, payment change, new third-party account, native app, or broad scoring-model rewrite is included.
- **Compatibility:** API contract, persisted historical records, frontend types, unit tests, and documentation are changed together. The migration is additive and preserves existing runtime data.

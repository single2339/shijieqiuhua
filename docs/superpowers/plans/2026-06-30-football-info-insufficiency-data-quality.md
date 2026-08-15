# Football Info Insufficiency Data Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved PRD addendum so `info_insufficient` analyses are attributable, noisy search evidence is filtered, fixture provider identity is preserved, and football-data stats can use stable team IDs.

**Architecture:** Keep the existing FastAPI + Pydantic + React + bronze JSON architecture. Add a small data-quality layer to `backend/football_osint/`, make provider identity optional and backward-compatible, tighten Chinese search evidence before factor scoring, and expose data-quality signals through the existing job/report surfaces.

**Tech Stack:** Python 3.11+ / FastAPI / Pydantic / pytest; React + TypeScript + Vitest; no new runtime dependencies.

## Global Constraints

- Canonical PRD: `docs/superpowers/specs/2026-06-30-football-info-insufficiency-prd-addendum.md`.
- Do not lower `info_insufficient_factor_min` or relax the abstention rule to hide coverage failures.
- Do not introduce betting, odds, handicap, or wagering language.
- All new API fields must be optional and backward-compatible.
- All behavior changes must be test-first: write the failing test, run it red, implement minimal code, run green.
- Do not overwrite unrelated unstaged user changes; current workspace already contains pre-existing modifications.
- Keep `PredictionResult` focused on prediction output; put data-quality diagnostics on `FootballOsintJob.data_quality`.

---

## File Structure

- Modify `backend/football_osint/models.py`
  - Add optional provider identity fields to `FootballOsintJobRequest`.
  - Add `DataQualitySummary` model.
  - Add optional `data_quality` to `FootballOsintJob`.
- Create `backend/football_osint/data_quality.py`
  - Compute insufficiency reason codes from request, sources, evidence, factors, prediction, and search stats.
- Modify `backend/football_osint/pipeline.py`
  - Thread search relevance stats through collection.
  - Attach `data_quality` to completed jobs.
  - Filter Chinese search results before evidence insertion.
- Modify `backend/football_osint/adapters/football_data_schedule.py`
  - Preserve provider match/team IDs in fixtures.
- Modify `backend/football_osint/adapters/football_data_stats.py`
  - Add team-id-first form/H2H functions and detailed skip reasons.
- Modify `backend/football_osint/routes.py`
  - Include provider identity in `/fixtures` response.
- Modify `backend/alert_runner.py` and/or telemetry emission path
  - Emit and aggregate top `info_insufficient` reason codes.
- Modify `frontend/src/shijieqiuhua/types.ts`
  - Add optional provider identity and data-quality fields.
- Modify `frontend/src/shijieqiuhua/mockData.ts`
  - Preserve provider identity when converting fixtures.
- Modify `frontend/src/App.tsx`
  - Pass provider identity from selected fixture to API request payload.
- Modify `frontend/src/shijieqiuhua/components/ReportView.tsx`
  - Show actionable insufficient reason and gaps.
- Tests:
  - `tests/test_football_osint.py`
  - `tests/test_football_data_schedule_range.py`
  - `tests/test_alert_runner.py`
  - `frontend/__tests__/football-provider-identity.test.ts`
  - `frontend/__tests__/reportview-data-quality.test.ts`

---

### Task 1: Backend data-quality model and reason computation

**Files:**
- Modify: `backend/football_osint/models.py`
- Create: `backend/football_osint/data_quality.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Produces `DataQualitySummary` Pydantic model with fields:
  - `insufficiency_reasons: list[str]`
  - `primary_insufficiency_reason: str = ""`
  - `source_summary: dict[str, int]`
  - `fundamental_factor_count: int`
  - `relevant_search_results_count: int = 0`
  - `dropped_search_results_count: int = 0`
  - `extraction_status: str = "not_run"`
- Produces `SearchQualityStats` dataclass with `relevant_count: int` and `dropped_count: int`.
- Produces `build_data_quality(request, sources, evidence, factors, prediction, search_stats=None, extraction_attempted=False) -> DataQualitySummary`.
- Later tasks consume `SearchQualityStats` from `pipeline.py` and attach `DataQualitySummary` to `FootballOsintJob`.

**Steps:**

- [ ] **Step 1: Write failing tests for reason codes on an insufficient job**

Add to `tests/test_football_osint.py`:

```python
def test_info_insufficient_job_has_data_quality_reasons(tmp_path):
    job = run_prediction_sync(
        {
            "home_team": "Japan U23",
            "away_team": "Korea U23",
            "kickoff_at": "2026-06-08 18:00",
            "competition": "AFC U23 Asian Cup",
        },
        storage_root=tmp_path,
    )

    assert job.prediction is not None
    assert job.prediction.lean == "info_insufficient"
    assert job.data_quality is not None
    assert job.data_quality.insufficiency_reasons
    assert job.data_quality.primary_insufficiency_reason in job.data_quality.insufficiency_reasons
    assert job.data_quality.fundamental_factor_count == 0
    assert job.data_quality.source_summary["ok"] >= 1
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/pytest tests/test_football_osint.py::test_info_insufficient_job_has_data_quality_reasons -q`

Expected: FAIL with an attribute/model error because `FootballOsintJob` has no `data_quality` field.

- [ ] **Step 3: Add backend model fields**

In `backend/football_osint/models.py`, add after `ConfidenceRating`:

```python
class DataQualitySummary(BaseModel):
    insufficiency_reasons: list[str] = Field(default_factory=list)
    primary_insufficiency_reason: str = ""
    source_summary: dict[str, int] = Field(default_factory=dict)
    fundamental_factor_count: int = 0
    relevant_search_results_count: int = 0
    dropped_search_results_count: int = 0
    extraction_status: str = "not_run"
```

Then add to `FootballOsintJob`:

```python
    data_quality: DataQualitySummary | None = None
```

- [ ] **Step 4: Implement data-quality builder**

Create `backend/football_osint/data_quality.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from .models import (
    DataQualitySummary,
    FactorImpact,
    FootballOsintJobRequest,
    OsintEvidence,
    OsintSourceStatus,
    PredictionResult,
)

_REASON_PRIORITY = [
    "source_runtime_failure",
    "detail_fixture_unmatched",
    "structured_stats_unresolved",
    "irrelevant_search_results",
    "no_relevant_search_results",
    "llm_extraction_empty",
    "too_early",
    "no_user_supplied_context",
]

@dataclass(frozen=True)
class SearchQualityStats:
    relevant_count: int = 0
    dropped_count: int = 0


def build_data_quality(
    request: FootballOsintJobRequest,
    sources: list[OsintSourceStatus],
    evidence: list[OsintEvidence],
    factors: list[FactorImpact],
    prediction: PredictionResult | None,
    *,
    search_stats: SearchQualityStats | None = None,
    extraction_attempted: bool = False,
) -> DataQualitySummary:
    stats = search_stats or SearchQualityStats()
    source_summary = {"ok": 0, "skipped": 0, "failed": 0}
    for source in sources:
        source_summary[source.status] = source_summary.get(source.status, 0) + 1

    fundamental_factor_count = sum(
        1 for factor in factors
        if factor.group in {"form", "h2h", "squad"} and factor.enabled
    )

    reasons: list[str] = []
    if any(source.status == "failed" for source in sources):
        reasons.append("source_runtime_failure")
    if any(source.adapter == "dongqiudi_analysis" and source.status != "ok" for source in sources):
        reasons.append("detail_fixture_unmatched")
    if any(source.adapter == "football_data_stats" and source.status != "ok" for source in sources):
        reasons.append("structured_stats_unresolved")
    if stats.dropped_count > 0 and stats.relevant_count == 0:
        reasons.append("irrelevant_search_results")
    elif any(source.adapter in {"cn_search", "ddg_search"} and source.status != "ok" for source in sources):
        reasons.append("no_relevant_search_results")
    if extraction_attempted and fundamental_factor_count == 0:
        reasons.append("llm_extraction_empty")
    if not request.user_supplied.notes and not request.user_supplied.injuries and not request.user_supplied.lineups:
        reasons.append("no_user_supplied_context")

    if prediction is None or prediction.lean != "info_insufficient":
        reasons = []

    ordered = [reason for reason in _REASON_PRIORITY if reason in set(reasons)]
    return DataQualitySummary(
        insufficiency_reasons=ordered,
        primary_insufficiency_reason=ordered[0] if ordered else "",
        source_summary=source_summary,
        fundamental_factor_count=fundamental_factor_count,
        relevant_search_results_count=stats.relevant_count,
        dropped_search_results_count=stats.dropped_count,
        extraction_status=("empty" if extraction_attempted and fundamental_factor_count == 0 else ("ok" if extraction_attempted else "not_run")),
    )
```

- [ ] **Step 5: Attach data quality in pipeline**

In `backend/football_osint/pipeline.py`, import:

```python
from . import data_quality as data_quality_module
```

Before constructing `FootballOsintJob`, compute:

```python
    data_quality = data_quality_module.build_data_quality(
        request, sources, evidence, factors, prediction,
    )
```

Pass into job:

```python
        data_quality=data_quality,
```

- [ ] **Step 6: Run test and verify GREEN**

Run: `.venv/bin/pytest tests/test_football_osint.py::test_info_insufficient_job_has_data_quality_reasons -q`

Expected: PASS.

---

### Task 2: Chinese search relevance gate and media coverage correctness

**Files:**
- Modify: `backend/football_osint/pipeline.py`
- Modify: `backend/football_osint/factor_registry.py`
- Modify: `backend/football_osint/data_quality.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Produces `_cn_search_result_matches_match(result: dict[str, str], home: str, away: str, competition: str = "") -> tuple[bool, str]`.
- Produces `_dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]`.
- `_collect_chinese_search(...) -> SearchQualityStats` returns relevance counts.
- `factor_registry.build_factors()` only counts relevant `search.cn.*` evidence.

**Steps:**

- [ ] **Step 1: Write failing test that bad Chinese search results are dropped**

Add to `tests/test_football_osint.py`:

```python
def test_cn_search_drops_country_encyclopedia_results(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    def fake_search(query, **kwargs):
        return [
            {"title": "科特迪瓦_百度百科", "url": "https://baike.baidu.com/item/x", "snippet": "科特迪瓦共和国位于西非。"},
            {"title": "国家概况_中华人民共和国外交部", "url": "https://www.mfa.gov.cn/x", "snippet": "科特迪瓦国家概况。"},
            {"title": "关于科特迪瓦的一切 - 知乎", "url": "https://zhuanlan.zhihu.com/p/x", "snippet": "科特迪瓦国土面积。"},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)
    request = FootballOsintJobRequest(home_team="科特迪瓦", away_team="挪威", kickoff_at="07-01 01:00", competition="世界杯")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    stats = _collect_chinese_search(request, evidence, sources)

    assert evidence == []
    assert stats.relevant_count == 0
    assert stats.dropped_count >= 3
    assert sources[0].adapter == "cn_search"
    assert sources[0].status == "skipped"
    assert "无相关中文搜索结果" in sources[0].reason
```

- [ ] **Step 2: Write failing test that relevant Chinese football result is accepted and deduped**

Add:

```python
def test_cn_search_accepts_relevant_match_preview_and_dedupes(monkeypatch):
    from backend.football_osint.adapters import web_search
    from backend.football_osint.pipeline import _collect_chinese_search
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    result = {
        "title": "巴西vs阿根廷世界杯前瞻：阵容伤停与历史交锋",
        "url": "https://sports.sina.com.cn/preview/bra-arg",
        "snippet": "巴西和阿根廷将在世界杯交锋，内马尔缺席，梅西领衔首发。",
    }

    def fake_search(query, **kwargs):
        return [result, dict(result)]

    monkeypatch.setattr(web_search, "search", fake_search)
    request = FootballOsintJobRequest(home_team="巴西", away_team="阿根廷", kickoff_at="06-20 20:00", competition="世界杯")
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    stats = _collect_chinese_search(request, evidence, sources)

    assert len(evidence) == 1
    assert evidence[0].topic == "search.cn.preview"
    assert stats.relevant_count == 1
    assert stats.dropped_count >= 1
    assert sources[0].status == "ok"
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
.venv/bin/pytest \
  tests/test_football_osint.py::test_cn_search_drops_country_encyclopedia_results \
  tests/test_football_osint.py::test_cn_search_accepts_relevant_match_preview_and_dedupes \
  -q
```

Expected: FAIL because `_collect_chinese_search()` returns `None` and accepts all results.

- [ ] **Step 4: Implement relevance helpers**

In `backend/football_osint/pipeline.py`, add near Chinese search helpers:

```python
_CN_FOOTBALL_TERMS = ("足球", "比赛", "世界杯", "前瞻", "阵容", "伤停", "比分", "交锋", "战绩", "出线", "小组赛", "首发")
_CN_GENERIC_BLOCKLIST = ("百度百科", "百科", "国家概况", "外交部", "旅游", "地图", "签证", "人口", "经济", "历史", "地理")


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for result in results:
        key = (result.get("url") or result.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _cn_search_result_matches_match(
    result: dict[str, str],
    home: str,
    away: str,
    competition: str = "",
) -> tuple[bool, str]:
    haystack = " ".join(str(result.get(key, "")) for key in ("title", "snippet", "url")).lower()
    raw_haystack = " ".join(str(result.get(key, "")) for key in ("title", "snippet", "url"))
    if any(term in raw_haystack for term in _CN_GENERIC_BLOCKLIST):
        return False, "generic_page"
    home_hit = bool(home and home.lower() in haystack)
    away_hit = bool(away and away.lower() in haystack)
    competition_hit = bool(competition and competition.lower() in haystack)
    football_hit = any(term in raw_haystack for term in _CN_FOOTBALL_TERMS)
    if home_hit and away_hit and football_hit:
        return True, "both_teams_and_football_context"
    if home_hit and away_hit and competition_hit:
        return True, "both_teams_and_competition"
    return False, "missing_team_or_football_context"
```

- [ ] **Step 5: Update `_collect_chinese_search()` to return stats**

Import `data_quality_module` at top if not already imported, then change function tail to:

```python
    evidence_ids = []
    dropped = 0
    seen_results: list[dict[str, str]] = []
    ...
        for result in _dedupe_results(results):
            ok, _reason = _cn_search_result_matches_match(result, home, away, request.competition)
            if not ok:
                dropped += 1
                continue
            seen_results.append(result)
            evidence_ids.append(evidence_module.append_evidence(...))
    ...
    sources.append(OsintSourceStatus(
        adapter="cn_search",
        label="国内媒体搜索",
        status="ok" if evidence_ids else "skipped",
        evidence_ids=evidence_ids,
        reason="" if evidence_ids else "无相关中文搜索结果",
    ))
    return data_quality_module.SearchQualityStats(
        relevant_count=len(evidence_ids),
        dropped_count=dropped,
    )
```

Preserve the existing evidence append fields for accepted results.

- [ ] **Step 6: Update caller to collect stats**

In `_collect_search_sources()`, initialize:

```python
    cn_stats = _collect_chinese_search(request, evidence, sources)
    return cn_stats
```

In `_collect_zero_config_sources()`, capture future result for `search` and pass into data-quality builder in Task 1 wiring. If Task 1 initially ignored stats, update it now so `search_stats` is threaded through to `build_data_quality()`.

- [ ] **Step 7: Update `factor_registry` to rely on filtered evidence**

No extra code is required if only filtered evidence gets `search.cn.*` topics. Verify `cn_evidence` still reads from evidence list and therefore counts only accepted CN evidence.

- [ ] **Step 8: Run tests and verify GREEN**

Run the two focused tests from Step 3.

Expected: PASS.

---

### Task 3: Provider identity through fixtures and requests

**Files:**
- Modify: `backend/football_osint/models.py`
- Modify: `backend/football_osint/adapters/football_data_schedule.py`
- Modify: `backend/football_osint/routes.py`
- Modify: `frontend/src/shijieqiuhua/types.ts`
- Modify: `frontend/src/shijieqiuhua/mockData.ts`
- Modify: `frontend/src/App.tsx`
- Test: `tests/test_football_data_schedule_range.py`
- Test: `frontend/__tests__/football-provider-identity.test.ts`

**Interfaces:**
- `football_data_schedule.Fixture` gains `provider`, `provider_match_id`, `home_provider_id`, `away_provider_id`.
- `/fixtures` response includes these fields.
- `FootballOsintJobRequest` accepts matching optional fields.
- Frontend request payload includes provider identity from selected fixture.

**Steps:**

- [ ] **Step 1: Write failing backend fixture identity test**

In `tests/test_football_data_schedule_range.py`, extend or add:

```python
def test_parse_matches_preserves_provider_identity():
    from backend.football_osint.adapters import football_data_schedule as fds

    payload = {
        "matches": [{
            "id": 537424,
            "utcDate": "2026-06-30T17:00:00Z",
            "status": "TIMED",
            "competition": {"name": "FIFA World Cup"},
            "homeTeam": {"id": 808, "name": "Côte d'Ivoire"},
            "awayTeam": {"id": 816, "name": "Norway"},
            "score": {"fullTime": {"home": None, "away": None}},
        }]
    }

    fixture = fds.parse_matches(payload)[0]

    assert fixture.provider == "football-data"
    assert fixture.provider_match_id == "537424"
    assert fixture.home_provider_id == "808"
    assert fixture.away_provider_id == "816"
```

- [ ] **Step 2: Run backend test and verify RED**

Run: `.venv/bin/pytest tests/test_football_data_schedule_range.py::test_parse_matches_preserves_provider_identity -q`

Expected: FAIL because `Fixture` has no provider identity fields.

- [ ] **Step 3: Add provider fields to backend request model**

In `backend/football_osint/models.py`, add to `FootballOsintJobRequest`:

```python
    provider: str = ""
    provider_match_id: str = ""
    home_provider_id: str = ""
    away_provider_id: str = ""
    home_aliases: list[str] = Field(default_factory=list)
    away_aliases: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add provider fields to fixture dataclass and parser**

In `backend/football_osint/adapters/football_data_schedule.py`, extend `Fixture`:

```python
    provider: str = "football-data"
    provider_match_id: str = ""
    home_provider_id: str = ""
    away_provider_id: str = ""
```

In `parse_matches()`, set:

```python
            provider="football-data",
            provider_match_id=str(m.get("id", "")),
            home_provider_id=str((m.get("homeTeam") or {}).get("id") or ""),
            away_provider_id=str((m.get("awayTeam") or {}).get("id") or ""),
```

- [ ] **Step 5: Add fields to `/fixtures` route response**

In `backend/football_osint/routes.py:list_fixtures()`, add to returned dict:

```python
            "provider": getattr(f, "provider", "football-data"),
            "provider_match_id": getattr(f, "provider_match_id", f.match_id),
            "home_provider_id": getattr(f, "home_provider_id", ""),
            "away_provider_id": getattr(f, "away_provider_id", ""),
```

- [ ] **Step 6: Run backend test and verify GREEN**

Run: `.venv/bin/pytest tests/test_football_data_schedule_range.py::test_parse_matches_preserves_provider_identity -q`

Expected: PASS.

- [ ] **Step 7: Add frontend types and payload propagation test**

If existing frontend tests can import `fixtureToMatch`, add a new test file `frontend/__tests__/football-provider-identity.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { fixtureToMatch } from '../src/shijieqiuhua/mockData'

it('preserves provider identity when mapping fixture to match', () => {
  const match = fixtureToMatch({
    id: '537424',
    provider: 'football-data',
    provider_match_id: '537424',
    home_provider_id: '808',
    away_provider_id: '816',
    league: '世界杯',
    kickoff_at: '07-01 01:00',
    kickoff_iso: '2026-06-30T17:00:00+00:00',
    home_team: '科特迪瓦',
    away_team: '挪威',
    status: 'scheduled',
    home_score: null,
    away_score: null,
  })

  expect(match.provider).toBe('football-data')
  expect(match.provider_match_id).toBe('537424')
  expect(match.home_provider_id).toBe('808')
  expect(match.away_provider_id).toBe('816')
})
```

- [ ] **Step 8: Run frontend test and verify RED**

Run: `npm test -- football-provider-identity.test.ts` from `frontend/`.

Expected: FAIL because `FootballMatch`/`fixtureToMatch` do not preserve provider identity.

- [ ] **Step 9: Update frontend types and mapping**

In `frontend/src/shijieqiuhua/types.ts`, add optional fields to `FixtureStatus`, `FootballMatch`, and `FootballOsintJobRequest`:

```ts
provider?: string
provider_match_id?: string
home_provider_id?: string
away_provider_id?: string
home_aliases?: string[]
away_aliases?: string[]
```

In `frontend/src/shijieqiuhua/mockData.ts:fixtureToMatch()`, copy the fields:

```ts
    provider: fixture.provider,
    provider_match_id: fixture.provider_match_id,
    home_provider_id: fixture.home_provider_id,
    away_provider_id: fixture.away_provider_id,
```

In `frontend/src/App.tsx`, when building request payloads for `createFootballOsintJob()` / `askFootballQuestion()`, include selected match optional provider fields:

```ts
provider: match.provider,
provider_match_id: match.provider_match_id,
home_provider_id: match.home_provider_id,
away_provider_id: match.away_provider_id,
```

- [ ] **Step 10: Run frontend test and verify GREEN**

Run: `npm test -- football-provider-identity.test.ts` from `frontend/`.

Expected: PASS.

---

### Task 4: football-data stats team-ID path and precise reasons

**Files:**
- Modify: `backend/football_osint/adapters/football_data_stats.py`
- Modify: `backend/football_osint/pipeline.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Produces `fetch_team_form_by_id(team_id: str, team_name: str, limit: int = 5) -> TeamFormRecord | None`.
- Produces `fetch_h2h_by_ids(home_id: str, away_id: str, home_name: str, away_name: str) -> H2HRecord | None`.
- `_collect_football_data_stats()` uses ID path when request provider identity is present.

**Steps:**

- [ ] **Step 1: Write failing test that ID path avoids name search**

Add to `tests/test_football_osint.py`:

```python
def test_football_data_stats_uses_provider_team_ids(monkeypatch):
    from backend.football_osint import pipeline
    from backend.football_osint.adapters import football_data_stats as fds
    from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence, OsintSourceStatus

    called = {"name_search": 0, "form_ids": [], "h2h_ids": None}

    def fail_name_search(name):
        called["name_search"] += 1
        raise AssertionError("name search should not be used when provider IDs exist")

    def fake_form_by_id(team_id, team_name, limit=5):
        called["form_ids"].append((team_id, team_name))
        return fds.TeamFormRecord(team_name=team_name, wins=3, draws=1, losses=1, recent_count=5)

    def fake_h2h_by_ids(home_id, away_id, home_name, away_name):
        called["h2h_ids"] = (home_id, away_id)
        return fds.H2HRecord(home_team=home_name, away_team=away_name, home_wins=1, draws=1, away_wins=1, total_matches=3)

    monkeypatch.setattr(fds, "_find_team_id", fail_name_search)
    monkeypatch.setattr(fds, "fetch_team_form_by_id", fake_form_by_id, raising=False)
    monkeypatch.setattr(fds, "fetch_h2h_by_ids", fake_h2h_by_ids, raising=False)

    request = FootballOsintJobRequest(
        home_team="科特迪瓦",
        away_team="挪威",
        kickoff_at="07-01 01:00",
        competition="世界杯",
        provider="football-data",
        home_provider_id="808",
        away_provider_id="816",
    )
    evidence: list[OsintEvidence] = []
    sources: list[OsintSourceStatus] = []

    pipeline._collect_football_data_stats(request, evidence, sources)

    assert called["name_search"] == 0
    assert called["form_ids"] == [("808", "科特迪瓦"), ("816", "挪威")]
    assert called["h2h_ids"] == ("808", "816")
    assert sources[-1].status == "ok"
    assert any(ev.topic == "fundamental.football_data.form" for ev in evidence)
```

- [ ] **Step 2: Run test and verify RED**

Run: `.venv/bin/pytest tests/test_football_osint.py::test_football_data_stats_uses_provider_team_ids -q`

Expected: FAIL because `fetch_team_form_by_id` / `fetch_h2h_by_ids` do not exist and pipeline uses name path.

- [ ] **Step 3: Add ID-based adapter functions**

In `football_data_stats.py`, extract existing request logic into ID functions:

```python
def fetch_team_form_by_id(team_id: str, team_name: str, limit: int = 5) -> TeamFormRecord | None:
    if not _check_key():
        return None
    cache_key = f"fd_form:{team_id}:{limit}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        resp = httpx.get(
            f"{FOOTBALL_DATA_URL}/teams/{team_id}/matches",
            params={"status": "FINISHED", "limit": limit},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
    except Exception as e:
        log.warning("team %s form fetch failed: %s", team_id, e)
        return None
    wins = draws = losses = 0
    team_id_int = int(team_id)
    for m in matches:
        home = m.get("homeTeam", {})
        score = (m.get("score") or {}).get("fullTime") or {}
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue
        is_home = home.get("id") == team_id_int
        if home_goals > away_goals:
            wins += 1 if is_home else 0
            losses += 0 if is_home else 1
        elif home_goals < away_goals:
            losses += 1 if is_home else 0
            wins += 0 if is_home else 1
        else:
            draws += 1
    record = TeamFormRecord(team_name=team_name, wins=wins, draws=draws, losses=losses, recent_count=len(matches))
    cache.schedule_cache.set(cache_key, record)
    return record
```

Then make `fetch_team_form()` resolve name to ID and call `fetch_team_form_by_id(str(team_id), team_name_cn, limit)`.

Add:

```python
def fetch_h2h_by_ids(home_id: str, away_id: str, home_name: str, away_name: str) -> H2HRecord | None:
    if not _check_key():
        return None
    cache_key = f"fd_h2h:{home_id}:{away_id}"
    cached = cache.schedule_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        resp = httpx.get(
            f"{FOOTBALL_DATA_URL}/teams/{home_id}/matches",
            params={"status": "FINISHED", "limit": 30},
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
    except Exception as e:
        log.warning("h2h fetch for teams %s/%s failed: %s", home_id, away_id, e)
        return None
    home_id_int = int(home_id)
    away_id_int = int(away_id)
    home_wins = draws = away_wins = 0
    for m in matches:
        h = m.get("homeTeam", {})
        a = m.get("awayTeam", {})
        if h.get("id") != home_id_int or a.get("id") != away_id_int:
            continue
        score = (m.get("score") or {}).get("fullTime") or {}
        hg = score.get("home")
        ag = score.get("away")
        if hg is None or ag is None:
            continue
        if hg > ag:
            home_wins += 1
        elif hg < ag:
            away_wins += 1
        else:
            draws += 1
    record = H2HRecord(home_team=home_name, away_team=away_name, home_wins=home_wins, draws=draws, away_wins=away_wins, total_matches=home_wins + draws + away_wins)
    cache.schedule_cache.set(cache_key, record)
    return record
```

Then make `fetch_h2h()` resolve names and call `fetch_h2h_by_ids(str(home_id), str(away_id), home_cn, away_cn)`.

- [ ] **Step 4: Update pipeline stats collector to prefer IDs**

In `_collect_football_data_stats()`, branch:

```python
    use_provider_ids = (
        request.provider == "football-data"
        and request.home_provider_id
        and request.away_provider_id
    )
```

When true, call ID functions; otherwise keep existing name path.

- [ ] **Step 5: Run focused test and verify GREEN**

Run: `.venv/bin/pytest tests/test_football_osint.py::test_football_data_stats_uses_provider_team_ids -q`

Expected: PASS.

---

### Task 5: Frontend insufficient explanation display

**Files:**
- Modify: `frontend/src/shijieqiuhua/types.ts`
- Modify: `frontend/src/shijieqiuhua/components/ReportView.tsx`
- Test: `frontend/__tests__/reportview-data-quality.test.ts`

**Interfaces:**
- Frontend type `DataQualitySummary` mirrors backend.
- `ReportView` shows primary reason and up to three reason chips when `prediction.lean === 'info_insufficient'` and `osintJob.data_quality` exists.

**Steps:**

- [ ] **Step 1: Add frontend test for insufficient reason rendering**

Create `frontend/__tests__/reportview-data-quality.test.ts` and test a pure exported helper from `ReportView.tsx`:

```ts
export function dataQualityReasonLabel(code: string): string {
  const labels: Record<string, string> = {
    detail_fixture_unmatched: '赛前分析源暂未匹配到该场',
    structured_stats_unresolved: '结构化战绩源未解析到双方近期数据',
    irrelevant_search_results: '搜索结果多为百科或泛介绍',
    no_relevant_search_results: '未找到同时覆盖双方的赛前报道',
    llm_extraction_empty: '已有文本未抽取出关键基本面字段',
    source_runtime_failure: '部分数据源暂时不可用',
    too_early: '赛前信息可能尚未发布',
    no_user_supplied_context: '尚未收到用户补充信息',
  }
  return labels[code] || code
}
```

Test:

```ts
import { describe, expect, it } from 'vitest'
import { dataQualityReasonLabel } from '../src/shijieqiuhua/components/ReportView'

describe('dataQualityReasonLabel', () => {
  it('maps insufficient reason codes to user-facing Chinese copy', () => {
    expect(dataQualityReasonLabel('detail_fixture_unmatched')).toBe('赛前分析源暂未匹配到该场')
    expect(dataQualityReasonLabel('structured_stats_unresolved')).toBe('结构化战绩源未解析到双方近期数据')
  })
})
```

- [ ] **Step 2: Run frontend test and verify RED**

Run: `npm test -- reportview-data-quality.test.ts` from `frontend/`.

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Add types**

In `frontend/src/shijieqiuhua/types.ts`, add:

```ts
export interface DataQualitySummary {
  insufficiency_reasons: string[]
  primary_insufficiency_reason: string
  source_summary: Record<string, number>
  fundamental_factor_count: number
  relevant_search_results_count: number
  dropped_search_results_count: number
  extraction_status: string
}
```

Add to `FootballOsintJob`:

```ts
data_quality?: DataQualitySummary | null
```

- [ ] **Step 4: Add helper and render copy**

In `ReportView.tsx`, export `dataQualityReasonLabel()` as in Step 1.

Inside `VerdictCard`, accept optional `dataQuality` prop:

```ts
function VerdictCard({ prediction, confidence, dataQuality }: {
  prediction: NonNullable<FootballOsintJob['prediction']>
  confidence: FootballOsintJob['confidence']
  dataQuality?: FootballOsintJob['data_quality']
}) {
```

When rendering from parent, pass `osintJob.data_quality`.

Inside insufficient block, add:

```tsx
{insufficient && dataQuality?.primary_insufficiency_reason && (
  <div className="sqh-verdict-honest">
    <ShieldCheck size={16} weight="duotone" />
    主因：{dataQualityReasonLabel(dataQuality.primary_insufficiency_reason)}。
    {dataQuality.insufficiency_reasons.slice(1, 3).length > 0 && (
      <> 其它缺口：{dataQuality.insufficiency_reasons.slice(1, 3).map(dataQualityReasonLabel).join('、')}。</>
    )}
  </div>
)}
```

Keep existing fallback “我们没编...” copy when `dataQuality` is absent.

- [ ] **Step 5: Run frontend test and verify GREEN**

Run: `npm test -- reportview-data-quality.test.ts` from `frontend/`.

Expected: PASS.

---

### Task 6: Telemetry and ALERT-11 reason-code aggregation

**Files:**
- Modify: telemetry emission path in `backend/football_osint/pipeline.py` or route completion path if telemetry is centralized there
- Modify: `backend/alert_runner.py`
- Test: `tests/test_alert_runner.py`

**Interfaces:**
- Emits `research.analysis_completed` with `lean`, `insufficiency_reasons`, `adapter_statuses`, `fundamental_factor_count`, `relevant_search_results_count`, `dropped_search_results_count`, `extraction_status`.
- `ALERT-11` includes top reason code in payload/body.

**Steps:**

- [ ] **Step 1: Write failing alert aggregation test**

Add to `tests/test_alert_runner.py`:

```python
def test_alert11_reports_top_info_insufficient_reason(tmp_db):
    from backend import telemetry
    for _ in range(40):
        telemetry.emit("research.dashboard_view", payload={"lean": "info_insufficient", "insufficiency_reasons": ["detail_fixture_unmatched"]})
    for _ in range(10):
        telemetry.emit("research.dashboard_view", payload={"lean": "home"})

    fired = alert_runner.run_once(dry_run=True)
    alert = next(a for a, _ in fired if a.rule_id == "ALERT-11")

    assert alert.payload["top_reason"] == "detail_fixture_unmatched"
    assert "detail_fixture_unmatched" in alert.body
```

- [ ] **Step 2: Run test and verify RED**

Run: `.venv/bin/pytest tests/test_alert_runner.py::test_alert11_reports_top_info_insufficient_reason -q`

Expected: FAIL because alert payload lacks `top_reason`.

- [ ] **Step 3: Update ALERT-11 query logic**

In `backend/alert_runner.py:_r11_info_insufficient_high()`, after the existing percentage query, fetch recent payloads and count first reason:

```python
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
```

Add to alert:

```python
body=f"Most matches lack data — RISK-3 active. Top reason: {top_reason}. Check adapter health.",
payload={"pct": pct, "top_reason": top_reason},
```

- [ ] **Step 4: Ensure analysis emits reason codes into dashboard payload**

Where `research.dashboard_view` or analysis-completion telemetry is emitted, include:

```python
payload={
    "lean": job.prediction.lean if job.prediction else "",
    "insufficiency_reasons": job.data_quality.insufficiency_reasons if job.data_quality else [],
    "fundamental_factor_count": job.data_quality.fundamental_factor_count if job.data_quality else 0,
    "relevant_search_results_count": job.data_quality.relevant_search_results_count if job.data_quality else 0,
    "dropped_search_results_count": job.data_quality.dropped_search_results_count if job.data_quality else 0,
    "extraction_status": job.data_quality.extraction_status if job.data_quality else "not_run",
}
```

If no suitable telemetry emission exists for analysis completion, add it immediately after job construction in `pipeline.run_prediction_sync()` using existing `backend.telemetry.emit`, and keep it non-raising.

- [ ] **Step 5: Run focused alert test and verify GREEN**

Run: `.venv/bin/pytest tests/test_alert_runner.py::test_alert11_reports_top_info_insufficient_reason -q`

Expected: PASS.

---

### Task 7: Focused integration verification and review

**Files:**
- All files touched above.

**Steps:**

- [ ] **Step 1: Run backend focused suites**

Run:

```bash
.venv/bin/pytest \
  tests/test_football_osint.py \
  tests/test_football_data_schedule_range.py \
  tests/test_alert_runner.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests**

Run from `frontend/`:

```bash
npm test -- football-provider-identity.test.ts reportview-data-quality.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run frontend build if frontend files changed**

Run from `frontend/`:

```bash
npm run build
```

Expected: PASS; `tsc && vite build` completes.

- [ ] **Step 4: Scan changed files for forbidden placeholders/skips**

Use repository search tools, not shell grep, to confirm no new `TODO`, `test.skip`, `test.only`, or placeholder implementation was introduced in touched files.

Expected: no new blockers.

- [ ] **Step 5: Dispatch code review**

Use `code-reviewer` for the full diff. If review flags Critical or Important issues, fix them and re-run affected tests.

---

## Self-Review Notes

- Spec coverage: PRD requirements PR-1 through PR-10 are covered by Tasks 1 through 6.
- TDD coverage: every behavior-changing task starts with failing backend or frontend tests and specifies red/green commands.
- Compatibility: new API fields are optional; old request payloads remain valid.
- Scope boundary: no odds/betting logic, no threshold relaxation, no unrelated UI redesign.
- Known implementation risk: existing unstaged work touches several target files; implementers must read current file contents before each edit and avoid overwriting unrelated changes.

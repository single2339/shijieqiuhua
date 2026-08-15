# LLM 证据融合接入结构化打分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `factor_registry.build_factors()` 用 LLM 把懂球帝/搜索/RSS/用户笔记里的近期战绩、历史交锋、伤停、积分排名抽取成结构化字段，喂给现有打分公式；LLM 不可用时无损退回现有正则解析。同时把天气因子从固定 `+0.03` 改成按实际降水/风速数值打分。

**Architecture:** 新文件 `backend/football_osint/analysis/evidence_extraction.py` 暴露 `extract(evidence, request) -> ExtractedFacts | None`，对多源证据做一次 LLM 调用抽取结构化字段，失败时返回 `None`。`factor_registry.py` 先把现有的 4 个"正则解析"函数拆成"正则解析 + 纯打分"两层，纯打分层在 LLM 成功和正则兜底两条路径间复用，保证算术逻辑不重复、不漂移。

**Tech Stack:** Python 3.11, httpx（同步调用，复用 `name_translation.py` 的 DeepSeek 调用约定）, pytest + monkeypatch。

## Global Constraints

- LLM 调用走 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（`.env`，默认 `https://api.deepseek.com` / `deepseek-chat`），无 key 时直接跳过调用返回 `None`，不抛异常。
- 任何 LLM 调用失败（网络异常、超时、HTTP 错误、JSON 解析失败、字段类型错误）必须被 `except Exception` 捕获并 `log.warning`，对调用方表现为返回 `None`，绝不向上抛。
- 不改 `_score_recent_form` 等现有打分公式的系数和上下限（`±0.15`/`±0.12`/`±0.10`/`±0.06`），只重组代码结构。
- 不改 `confidence.py`、`match_report.py`、`llm_qa.py`。
- 不接入 SofaScore/FBref/Transfermarkt（出此 plan 范围）。

---

### Task 1: `ExtractedFacts` 数据结构 + LLM 抽取函数

**Files:**
- Create: `backend/football_osint/analysis/evidence_extraction.py`
- Test: `tests/test_evidence_extraction.py`

**Interfaces:**
- Produces: `ExtractedFacts` dataclass，字段：`home_form: tuple[int, int, int] | None`、`away_form: tuple[int, int, int] | None`、`h2h_home_wins: int | None`、`h2h_draws: int | None`、`h2h_home_losses: int | None`、`home_absences: int | None`、`away_absences: int | None`、`home_rank: int | None`、`away_rank: int | None`。
- Produces: `extract(evidence: list[OsintEvidence], request: FootballOsintJobRequest) -> ExtractedFacts | None`。

- [ ] **Step 1: Write the failing test for "no API key → None"**

```python
# tests/test_evidence_extraction.py
from __future__ import annotations

from backend.football_osint.analysis import evidence_extraction as ee
from backend.football_osint.models import FootballOsintJobRequest, OsintEvidence


def _request() -> FootballOsintJobRequest:
    return FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )


def _evidence(topic: str, raw_excerpt: str) -> OsintEvidence:
    return OsintEvidence(
        id="ev_001", source="test", source_type="fundamental",
        claim=raw_excerpt[:50], topic=topic, side="neutral",
        confidence=0.5, raw_excerpt=raw_excerpt,
    )


def test_extract_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    result = ee.extract([_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")], _request())
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evidence_extraction.py::test_extract_returns_none_without_api_key -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.football_osint.analysis.evidence_extraction'`

- [ ] **Step 3: Write the module (skeleton + no-key short-circuit)**

```python
# backend/football_osint/analysis/evidence_extraction.py
"""LLM-driven structured fact extraction from multi-source OSINT evidence.

factor_registry.py's scoring formulas (_form_score_from_records etc.) need
home/away recent-form W/D/L, H2H counts, absence counts, and standings rank
as plain numbers. Today those numbers only ever come from a handful of
regexes matched against dongqiudi's own structured text — search snippets,
RSS news, and user notes carry the same facts in free-text form that the
regexes never match. This module reads ALL of it in one LLM call and
extracts the same fields the regexes were trying to find, so the scoring
formulas get fed regardless of which source happened to phrase it.

Returns ``None`` on any failure (no key, network error, bad JSON, timeout)
so the caller can fall back to the existing regex path unchanged.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx

from ..models import FootballOsintJobRequest, OsintEvidence

log = logging.getLogger(__name__)

_TIMEOUT = 45.0
_USEFUL_PREFIXES = ("fundamental.", "search.", "news.rss.", "user.note")

_SYSTEM = (
    "你是足球数据抽取助手。给定一场比赛的多条赛前情报文本，抽取以下结构化字段，"
    "只返回一个 JSON 对象，不要任何额外文字：\n"
    '{"home_form": {"wins": int, "draws": int, "losses": int} 或 null,\n'
    ' "away_form": {"wins": int, "draws": int, "losses": int} 或 null,\n'
    ' "h2h_home_wins": int 或 null, "h2h_draws": int 或 null, "h2h_home_losses": int 或 null,\n'
    ' "home_absences": int 或 null, "away_absences": int 或 null,\n'
    ' "home_rank": int 或 null, "away_rank": int 或 null}\n'
    "home_form/away_form 是该队近期比赛的胜/平/负场次。h2h_* 是双方历史交锋中主队的胜/平/负场次。"
    "home_absences/away_absences 是因伤/停赛缺席的人数。home_rank/away_rank 是当前联赛或赛事积分榜排名。\n"
    "严格规则：只抽取证据文本中明确出现的数字，绝不推测或编造。某个字段在任何一条证据里都没有明确数字，"
    "就填 null。"
)


@dataclass
class ExtractedFacts:
    home_form: tuple[int, int, int] | None
    away_form: tuple[int, int, int] | None
    h2h_home_wins: int | None
    h2h_draws: int | None
    h2h_home_losses: int | None
    home_absences: int | None
    away_absences: int | None
    home_rank: int | None
    away_rank: int | None


def extract(
    evidence: list[OsintEvidence],
    request: FootballOsintJobRequest,
) -> ExtractedFacts | None:
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None

    body = _format_evidence(evidence)
    if not body:
        return None

    return _call_llm(api_key, body, request)


def _format_evidence(evidence: list[OsintEvidence], limit: int = 30) -> str:
    lines = []
    for ev in evidence:
        if not ev.topic.startswith(_USEFUL_PREFIXES):
            continue
        text = (ev.raw_excerpt or ev.claim or "").strip()
        if not text:
            continue
        lines.append(f"[{ev.source}] {text[:400]}")
    return "\n".join(lines[:limit])


def _call_llm(api_key: str, body: str, request: FootballOsintJobRequest) -> ExtractedFacts | None:
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    user = (
        f"主队：{request.home_team}，客队：{request.away_team}\n\n"
        f"赛前情报（每条：[来源] 正文）：\n{body}"
    )
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return _parse(data)
    except Exception as e:
        log.warning("evidence extraction failed: %s", e)
        return None


def _parse(data: dict) -> ExtractedFacts:
    def _form(key: str) -> tuple[int, int, int] | None:
        v = data.get(key)
        if not isinstance(v, dict):
            return None
        try:
            return (int(v["wins"]), int(v["draws"]), int(v["losses"]))
        except (KeyError, TypeError, ValueError):
            return None

    def _int(key: str) -> int | None:
        v = data.get(key)
        return int(v) if isinstance(v, (int, float)) else None

    return ExtractedFacts(
        home_form=_form("home_form"),
        away_form=_form("away_form"),
        h2h_home_wins=_int("h2h_home_wins"),
        h2h_draws=_int("h2h_draws"),
        h2h_home_losses=_int("h2h_home_losses"),
        home_absences=_int("home_absences"),
        away_absences=_int("away_absences"),
        home_rank=_int("home_rank"),
        away_rank=_int("away_rank"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evidence_extraction.py::test_extract_returns_none_without_api_key -v`
Expected: PASS

- [ ] **Step 5: Write failing test for "no useful evidence → None"**

```python
def test_extract_returns_none_without_useful_evidence(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    result = ee.extract([_evidence("fixture.query", "比赛已录入")], _request())
    assert result is None
```

Run: `pytest tests/test_evidence_extraction.py::test_extract_returns_none_without_useful_evidence -v`
Expected: PASS immediately (already covered by the `if not body: return None` branch in Step 3) — confirms the guard works, no code change needed.

- [ ] **Step 6: Write failing test for successful extraction (mocked httpx)**

```python
class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_extract_parses_llm_json_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    llm_json = json.dumps({
        "home_form": {"wins": 4, "draws": 1, "losses": 0},
        "away_form": {"wins": 2, "draws": 1, "losses": 2},
        "h2h_home_wins": 3, "h2h_draws": 1, "h2h_home_losses": 1,
        "home_absences": 1, "away_absences": 3,
        "home_rank": 2, "away_rank": 5,
    })

    def fake_post(*args, **kwargs):
        return _FakeResponse({"choices": [{"message": {"content": llm_json}}]})

    monkeypatch.setattr(ee.httpx, "post", fake_post)

    result = ee.extract(
        [_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")],
        _request(),
    )

    assert result == ee.ExtractedFacts(
        home_form=(4, 1, 0), away_form=(2, 1, 2),
        h2h_home_wins=3, h2h_draws=1, h2h_home_losses=1,
        home_absences=1, away_absences=3,
        home_rank=2, away_rank=5,
    )
```

Add `import json` to the top of `tests/test_evidence_extraction.py`.

Run: `pytest tests/test_evidence_extraction.py::test_extract_parses_llm_json_response -v`
Expected: PASS (code already handles this — confirms parsing logic)

- [ ] **Step 7: Write failing test for malformed JSON → None**

```python
def test_extract_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    def fake_post(*args, **kwargs):
        return _FakeResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(ee.httpx, "post", fake_post)

    result = ee.extract(
        [_evidence("fundamental.dongqiudi", "巴西近期战绩：4胜1平0负")],
        _request(),
    )
    assert result is None
```

Run: `pytest tests/test_evidence_extraction.py -v`
Expected: all 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/football_osint/analysis/evidence_extraction.py tests/test_evidence_extraction.py
git commit -m "feat: add LLM-based structured fact extraction from OSINT evidence"
```

---

### Task 2: Split `factor_registry.py` scoring functions into parse-layer + pure-score-layer

**Files:**
- Modify: `backend/football_osint/factor_registry.py`
- Test: `tests/test_football_osint.py` (existing tests in this file must keep passing unchanged — they exercise `_score_cn_form` and the regex path end-to-end)

**Interfaces:**
- Consumes: nothing new.
- Produces: pure functions `_form_score_from_records(home_rec, away_rec) -> float`, `_h2h_score_from_counts(home_wins, home_losses) -> float`, `_squad_score_from_absences(home_abs, away_abs) -> float`, `_standings_score_from_ranks(home_rank, away_rank) -> float`. Existing `_score_recent_form`, `_score_h2h`, `_score_squad`, `_score_standings` keep their current signatures and behavior, now implemented by parsing then delegating to the pure functions above.

- [ ] **Step 1: Write failing tests for the new pure functions**

Add to `tests/test_football_osint.py` (near the existing `test_cn_form_*` tests, after line 536):

```python
def test_form_score_from_records_favours_better_ppg():
    from backend.football_osint.factor_registry import _form_score_from_records

    # Home: 4W1D0L → PPG 2.6; Away: 2W1D2L → PPG 1.4 → diff 1.2 * 0.10 = 0.12
    score = _form_score_from_records((4, 1, 0), (2, 1, 2))
    assert score == 0.12


def test_form_score_from_records_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _form_score_from_records

    assert _form_score_from_records(None, (2, 1, 2)) == 0.0
    assert _form_score_from_records((4, 1, 0), None) == 0.0


def test_h2h_score_from_counts_favours_home_wins():
    from backend.football_osint.factor_registry import _h2h_score_from_counts

    # 3 wins, 1 loss → advantage (3-1)/4 = 0.5 * 0.12 = 0.06
    score = _h2h_score_from_counts(3, 1)
    assert score == 0.06


def test_h2h_score_from_counts_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _h2h_score_from_counts

    assert _h2h_score_from_counts(None, 1) == 0.0
    assert _h2h_score_from_counts(3, None) == 0.0


def test_squad_score_from_absences_favours_fewer_absences():
    from backend.football_osint.factor_registry import _squad_score_from_absences

    # away has 2 more absences → (2)*0.03 = 0.06
    score = _squad_score_from_absences(1, 3)
    assert score == 0.06


def test_squad_score_from_absences_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _squad_score_from_absences

    assert _squad_score_from_absences(None, 3) == 0.0
    assert _squad_score_from_absences(1, None) == 0.0


def test_standings_score_from_ranks_favours_better_rank():
    from backend.football_osint.factor_registry import _standings_score_from_ranks

    # home rank 2, away rank 5 → (5-2)*0.015 = 0.045
    score = _standings_score_from_ranks(2, 5)
    assert score == 0.045


def test_standings_score_from_ranks_returns_zero_when_missing():
    from backend.football_osint.factor_registry import _standings_score_from_ranks

    assert _standings_score_from_ranks(None, 5) == 0.0
    assert _standings_score_from_ranks(2, None) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_football_osint.py -k "form_score_from_records or h2h_score_from_counts or squad_score_from_absences or standings_score_from_ranks" -v`
Expected: FAIL with `ImportError: cannot import name '_form_score_from_records'` (and similarly for the other three)

- [ ] **Step 3: Refactor `factor_registry.py` to extract the pure functions**

Replace the body of `_score_recent_form` (lines 164-191 in the current file) through `_score_standings` (lines 248-268) with:

```python
def _form_score_from_records(
    home_rec: tuple[int, int, int] | None,
    away_rec: tuple[int, int, int] | None,
) -> float:
    """Compare home vs away recent form PPG. Positive favours home.

    Pure arithmetic, no parsing — shared by the regex path (_score_recent_form)
    and the LLM extraction path in build_factors.
    """
    if not home_rec or not away_rec:
        return 0.0
    games = sum(home_rec)
    if games == 0:
        return 0.0
    home_ppg = (home_rec[0] * 3 + home_rec[1]) / games
    away_games = sum(away_rec)
    away_ppg = (away_rec[0] * 3 + away_rec[1]) / away_games if away_games else 0.0
    raw = (home_ppg - away_ppg) * 0.10
    return max(-0.15, min(0.15, round(raw, 3)))


def _score_recent_form(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '{name}近期战绩：W胜D平L负' from dongqiudi text, then score it."""
    home_name = request.home_team
    away_name = request.away_team
    records: dict[str, tuple[int, int, int]] = {}
    for m in _FORM_RE.finditer(text):
        name = m.group(1)
        w, d, l = int(m.group(2)), int(m.group(3)), int(m.group(4))
        records[name] = (w, d, l)
    return _form_score_from_records(records.get(home_name), records.get(away_name))


def _h2h_score_from_counts(home_wins: int | None, home_losses: int | None) -> float:
    """Compare H2H win/loss counts for the home side. Positive favours home."""
    if home_wins is None or home_losses is None:
        return 0.0
    total = home_wins + home_losses
    if total == 0:
        return 0.0
    advantage = (home_wins - home_losses) / total
    return max(-0.12, min(0.12, round(advantage * 0.12, 3)))


def _score_h2h(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '历史交锋：A W胜D平L负，B W胜D平L负' from dongqiudi text, then score it."""
    home_name = request.home_team
    away_name = request.away_team
    m = _H2H_RE.search(text)
    if not m:
        return 0.0

    name_a, wa, da, la = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    name_b, wb, db, lb = m.group(5), int(m.group(6)), int(m.group(7)), int(m.group(8))

    if home_name not in (name_a, name_b) or away_name not in (name_a, name_b):
        return 0.0

    if name_a == home_name:
        home_w, home_l = wa, la
    else:
        home_w, home_l = wb, lb
    return _h2h_score_from_counts(home_w, home_l)


def _squad_score_from_absences(home_abs: int | None, away_abs: int | None) -> float:
    """Compare absence counts: fewer absences = advantage. Positive favours home."""
    if home_abs is None or away_abs is None:
        return 0.0
    raw = (away_abs - home_abs) * 0.03
    return max(-0.10, min(0.10, round(raw, 3)))


def _score_squad(text: str, request: FootballOsintJobRequest) -> tuple[float, bool]:
    """Parse '伤停信息：A N人缺席，B M人缺席' from dongqiudi text, then score it."""
    m = _SIDELINE_RE.search(text)
    if not m:
        return 0.0, False

    name_a, abs_a = m.group(1), int(m.group(2))
    name_b, abs_b = m.group(3), int(m.group(4))
    home_name = request.home_team
    away_name = request.away_team

    if home_name not in (name_a, name_b) or away_name not in (name_a, name_b):
        return 0.0, True

    home_abs = abs_a if name_a == home_name else abs_b
    away_abs = abs_b if name_a == home_name else abs_a
    return _squad_score_from_absences(home_abs, away_abs), True


def _standings_score_from_ranks(home_rank: int | None, away_rank: int | None) -> float:
    """Compare standings rank: lower number (better rank) = advantage. Positive favours home."""
    if not home_rank or not away_rank:
        return 0.0
    raw = (away_rank - home_rank) * 0.015
    return max(-0.06, min(0.06, round(raw, 3)))


def _score_standings(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '{name} 第N名' from dongqiudi text, then score it."""
    home_name = request.home_team
    away_name = request.away_team

    def _find_rank(name: str) -> int | None:
        m = re.search(re.escape(name) + r"\s*第(\d+)名", text)
        return int(m.group(1)) if m else None

    return _standings_score_from_ranks(_find_rank(home_name), _find_rank(away_name))
```

Leave `_score_cn_form`, `_direction`, `build_factors`, and the regex constants (`_FORM_RE` etc.) untouched in this task.

- [ ] **Step 4: Run tests to verify everything passes**

Run: `pytest tests/test_football_osint.py -v`
Expected: all tests PASS, including the new pure-function tests and every pre-existing test in the file (`_score_cn_form`, `media.cn_coverage`, etc. — these never touched the functions you just split, so they should be unaffected)

- [ ] **Step 5: Commit**

```bash
git add backend/football_osint/factor_registry.py tests/test_football_osint.py
git commit -m "refactor: split factor_registry scoring into parse + pure-score layers"
```

---

### Task 3: Wire `evidence_extraction.extract()` into `build_factors`

**Files:**
- Modify: `backend/football_osint/factor_registry.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Consumes: `evidence_extraction.extract(evidence, request) -> ExtractedFacts | None` (Task 1); `_form_score_from_records`, `_h2h_score_from_counts`, `_squad_score_from_absences`, `_standings_score_from_ranks` (Task 2).
- Produces: `build_factors` keeps its existing signature `(request, profile, evidence) -> list[FactorImpact]`.

- [ ] **Step 1: Write failing test — LLM extraction path drives the factors**

Add to `tests/test_football_osint.py`:

```python
def test_build_factors_uses_llm_extraction_when_available(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.analysis import evidence_extraction as ee
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence

    fake_facts = ee.ExtractedFacts(
        home_form=(4, 1, 0), away_form=(2, 1, 2),
        h2h_home_wins=3, h2h_draws=1, h2h_home_losses=1,
        home_absences=1, away_absences=3,
        home_rank=2, away_rank=5,
    )
    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: fake_facts)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    # No fundamental.* evidence at all — this is the case that's broken today.
    evidence = [OsintEvidence(
        id="ev_001", source="国内媒体搜索", source_type="search",
        claim="赛前分析", topic="search.cn.preview", side="neutral",
        confidence=0.28, raw_excerpt="巴西近期表现出色",
    )]

    factors = fr.build_factors(request, profile, evidence)
    form_factor = next(f for f in factors if f.factor_id == "form.recent_signal")
    h2h_factor = next(f for f in factors if f.factor_id == "h2h.relevance")
    squad_factor = next(f for f in factors if f.factor_id == "squad.availability")

    assert form_factor.enabled is True
    assert form_factor.direction == "home"  # Brazil's PPG is higher
    assert h2h_factor.enabled is True
    assert h2h_factor.direction == "home"  # 3W1L for home in H2H
    assert squad_factor.enabled is True
    assert squad_factor.direction == "home"  # away has more absences
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_football_osint.py::test_build_factors_uses_llm_extraction_when_available -v`
Expected: FAIL — `form_factor.enabled` is `False` today because there's no `fundamental.*` evidence and no CN-form regex match, so `has_form_signal` is `False`.

- [ ] **Step 3: Write failing test — LLM extraction fails, regex fallback still works**

```python
def test_build_factors_falls_back_to_regex_when_llm_extraction_fails(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence

    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: None)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    evidence = [OsintEvidence(
        id="ev_001", source="懂球帝赛前分析", source_type="fundamental",
        claim="赛前分析", topic="fundamental.dongqiudi.analysis", side="neutral",
        confidence=0.5,
        raw_excerpt="巴西近期战绩：4胜1平0负\n阿根廷近期战绩：2胜1平2负",
    )]

    factors = fr.build_factors(request, profile, evidence)
    form_factor = next(f for f in factors if f.factor_id == "form.recent_signal")
    assert form_factor.enabled is True
    assert form_factor.direction == "home"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_football_osint.py::test_build_factors_falls_back_to_regex_when_llm_extraction_fails -v`
Expected: FAIL with `AttributeError: module 'backend.football_osint.factor_registry' has no attribute 'evidence_extraction'` (build_factors doesn't import or call it yet)

- [ ] **Step 5: Modify `factor_registry.py` to call extraction and branch on its result**

Add the import near the top of the file (after the existing imports):

```python
from .analysis import evidence_extraction
```

Replace the body of `build_factors` from the `# Parse the fundamental evidence text...` comment (current line 33) down through the `combined_form = max(-0.18, min(0.18, combined_form))` line (current line 53) with:

```python
    fundamental_text = "\n".join(ev.raw_excerpt for ev in evidence if ev.topic.startswith("fundamental."))

    # Chinese search + RSS evidence: enriches form scoring when dongqiudi is sparse,
    # and feeds the media.cn_coverage factor below regardless of which path wins.
    cn_evidence = [ev for ev in evidence if (
        ev.topic.startswith("search.cn.")
        or ev.topic.startswith("news.rss.hupu.")
        or ev.topic.startswith("news.rss.dongqiudi.")
        or ev.topic.startswith("news.rss.weibo.")
    )]

    extracted = evidence_extraction.extract(evidence, request)

    if extracted is not None:
        form_score = _form_score_from_records(extracted.home_form, extracted.away_form)
        h2h_score = _h2h_score_from_counts(extracted.h2h_home_wins, extracted.h2h_home_losses)
        has_sideline = extracted.home_absences is not None and extracted.away_absences is not None
        squad_score = _squad_score_from_absences(extracted.home_absences, extracted.away_absences)
        standings_score = _standings_score_from_ranks(extracted.home_rank, extracted.away_rank)
        combined_form = max(-0.18, min(0.18, form_score + standings_score))

        has_form_signal = extracted.home_form is not None and extracted.away_form is not None
        has_h2h = extracted.h2h_home_wins is not None and extracted.h2h_home_losses is not None
        form_evidence_ids = fundamental_evidence + [ev.id for ev in cn_evidence]
        form_weight = (0.12 if youth else 0.16) if has_form_signal else 0.0
        form_confidence = 0.42 if has_form_signal else 0.0
        form_missing_reason = "" if has_form_signal else "LLM 未能从多源证据中抽取近期战绩，无法形成近期状态信号"
        h2h_enabled = has_h2h
        h2h_weight = ((0.05 if youth else 0.10) if has_h2h else 0.0)
        h2h_confidence = 0.25 if has_h2h else 0.0
        h2h_missing_reason = "" if has_h2h else "LLM 未能从多源证据中抽取历史交锋数据，h2h 因子不启用"
        squad_enabled = has_sideline
        squad_weight = 0.10 if has_sideline else 0.0
        squad_confidence = 0.35 if has_sideline else 0.0
        squad_missing_reason = "" if has_sideline else "LLM 未能从多源证据中抽取伤停/缺席数据，阵容因子不启用"
    else:
        cn_text = "\n".join(ev.raw_excerpt for ev in cn_evidence)
        cn_form_score = _score_cn_form(cn_text, request)

        form_score = _score_recent_form(fundamental_text, request)
        h2h_score = _score_h2h(fundamental_text, request)
        squad_score, has_sideline = _score_squad(fundamental_text, request)
        standings_score = _score_standings(fundamental_text, request)
        combined_form = max(-0.18, min(0.18, form_score + standings_score + cn_form_score))

        has_cn_form = cn_form_score != 0.0
        has_form_signal = has_fundamental or has_cn_form
        form_evidence_ids = fundamental_evidence + ([ev.id for ev in cn_evidence] if cn_evidence else [])
        form_weight = (0.12 if youth else 0.16) if has_fundamental else (0.08 if has_cn_form else 0.0)
        form_confidence = 0.42 if has_fundamental else (0.22 if has_cn_form else 0.0)
        form_missing_reason = "" if has_form_signal else "未抓取到懂球帝赛前分析或国内媒体近期战绩，无法形成近期状态信号"
        h2h_enabled = has_fundamental
        h2h_weight = (0.05 if youth else 0.10) if has_fundamental else 0.0
        h2h_confidence = 0.25 if has_fundamental else 0.0
        h2h_missing_reason = "" if has_fundamental else "缺历史交锋证据，h2h 因子不启用"
        squad_enabled = has_fundamental and has_sideline
        squad_weight = 0.10 if squad_enabled else 0.0
        squad_confidence = 0.35 if has_sideline else 0.0
        squad_missing_reason = "" if has_sideline else "暂无伤病/缺席数据，阵容因子不启用"
```

Then update the returned `FactorImpact` list (current lines 61-148) so the `form.recent_signal`, `squad.availability`, and `h2h.relevance` entries use the branch-computed variables instead of the old inline conditionals:

```python
        FactorImpact(
            factor_id="form.recent_signal",
            label="近期状态信号",
            group="form",
            enabled=has_form_signal,
            weight=form_weight,
            impact=combined_form,
            direction=_direction(combined_form),
            confidence=form_confidence,
            evidence_ids=form_evidence_ids,
            missing_reason=form_missing_reason,
        ),
        FactorImpact(
            factor_id="squad.availability",
            label="阵容可用性",
            group="squad",
            enabled=squad_enabled,
            weight=squad_weight,
            impact=squad_score,
            direction=_direction(squad_score),
            confidence=squad_confidence,
            evidence_ids=fundamental_evidence,
            missing_reason=squad_missing_reason,
        ),
        FactorImpact(
            factor_id="uncertainty.youth_volatility",
            label="青年赛事波动",
            group="uncertainty",
            enabled=youth,
            weight=0.20 if youth else 0.04,
            impact=-0.10 if youth else 0.0,
            direction="neutral",
            confidence=0.82 if youth else 0.0,
            evidence_ids=fixture_evidence,
            missing_reason="" if youth else "非青年赛事，青年波动因子不启用",
        ),
        FactorImpact(
            factor_id="h2h.relevance",
            label="历史交锋参考性",
            group="h2h",
            enabled=h2h_enabled,
            weight=h2h_weight,
            impact=h2h_score,
            direction=_direction(h2h_score),
            confidence=h2h_confidence,
            evidence_ids=fundamental_evidence,
            missing_reason=h2h_missing_reason,
        ),
```

(The `fixture.existence`, `weather.exposure`, and `media.cn_coverage` entries stay exactly as they are in this task — `weather.exposure` changes in Task 4.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_football_osint.py -v`
Expected: all tests PASS, including the two new ones from this task and every test from Task 2 and pre-existing tests (`test_media_cn_coverage_factor_enables_with_enough_evidence` exercises the full `run_prediction_sync` → `build_factors` path with no `LLM_API_KEY` set in CI, so it takes the `extracted is None` branch and must produce identical output to before)

- [ ] **Step 7: Commit**

```bash
git add backend/football_osint/factor_registry.py tests/test_football_osint.py
git commit -m "feat: wire LLM evidence extraction into build_factors with regex fallback"
```

---

### Task 4: Weather factor scores by actual precipitation/wind values

**Files:**
- Modify: `backend/football_osint/factor_registry.py`
- Test: `tests/test_football_osint.py`

**Interfaces:**
- Consumes: `OsintEvidence.raw_excerpt` for `topic == "weather.open_meteo"` — this is the raw Open-Meteo JSON response string (set in `adapters/open_meteo.py:137`), containing `data["daily"]["precipitation_probability_max"][0]` and `data["daily"]["wind_speed_10m_max"][0]`.
- Produces: `_weather_score_from_raw_excerpt(raw_excerpt: str) -> float`, used inside `build_factors` for the `weather.exposure` factor's `impact`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_football_osint.py`:

```python
def test_weather_score_from_raw_excerpt_penalises_heavy_rain():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt
    import json as _json

    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [90], "wind_speed_10m_max": [10],
        "temperature_2m_max": [22], "temperature_2m_min": [15], "weather_code": [65],
    }})
    score = _weather_score_from_raw_excerpt(raw)
    assert score < 0  # heavy rain → negative (lower-scoring, less predictable match)


def test_weather_score_from_raw_excerpt_neutral_for_calm_weather():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt
    import json as _json

    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [5], "wind_speed_10m_max": [8],
        "temperature_2m_max": [20], "temperature_2m_min": [12], "weather_code": [1],
    }})
    score = _weather_score_from_raw_excerpt(raw)
    assert score == 0.0


def test_weather_score_from_raw_excerpt_returns_zero_on_bad_json():
    from backend.football_osint.factor_registry import _weather_score_from_raw_excerpt

    assert _weather_score_from_raw_excerpt("not json") == 0.0
    assert _weather_score_from_raw_excerpt("") == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_football_osint.py -k weather_score_from_raw_excerpt -v`
Expected: FAIL with `ImportError: cannot import name '_weather_score_from_raw_excerpt'`

- [ ] **Step 3: Add the function to `factor_registry.py`**

Add near the bottom of the file, after `_score_cn_form`:

```python
def _weather_score_from_raw_excerpt(raw_excerpt: str) -> float:
    """Score weather exposure from Open-Meteo's raw JSON response.

    Heavy rain or high wind makes the match harder to predict and tends to
    suppress scoring/tempo — small negative, neutral direction (it affects
    both sides, not home vs away). Calm weather → 0.0 (no signal either way).
    Capped at [-0.05, 0.0]: this factor nudges confidence, it doesn't pick a
    winner.
    """
    try:
        data = json.loads(raw_excerpt)
        daily = data.get("daily") or {}
        precip = (daily.get("precipitation_probability_max") or [None])[0]
        wind = (daily.get("wind_speed_10m_max") or [None])[0]
    except (json.JSONDecodeError, TypeError, IndexError):
        return 0.0

    if precip is None and wind is None:
        return 0.0

    penalty = 0.0
    if precip is not None and precip >= 70:
        penalty -= 0.03
    if wind is not None and wind >= 30:
        penalty -= 0.02
    return round(penalty, 3)
```

Add `import json` to the top of `factor_registry.py` (alongside the existing `import re`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_football_osint.py -k weather_score_from_raw_excerpt -v`
Expected: PASS

- [ ] **Step 5: Wire it into `build_factors`**

In `build_factors`, before the `weather_evidence` list comprehension, add:

```python
    weather_score = 0.0
    for ev in evidence:
        if ev.topic == "weather.open_meteo" and ev.raw_excerpt:
            weather_score = _weather_score_from_raw_excerpt(ev.raw_excerpt)
            break
```

Then replace the `weather.exposure` `FactorImpact` entry's `impact=0.03 if has_weather else 0.0` with `impact=weather_score`.

- [ ] **Step 6: Write a test that the factor reflects real weather data through the full pipeline**

Add to `tests/test_football_osint.py`:

```python
def test_weather_factor_reflects_real_precipitation(monkeypatch):
    from backend.football_osint import factor_registry as fr
    from backend.football_osint.models import FootballOsintJobRequest, MatchProfile, OsintEvidence
    import json as _json

    monkeypatch.setattr(fr.evidence_extraction, "extract", lambda evidence, request: None)

    request = FootballOsintJobRequest(
        home_team="巴西", away_team="阿根廷",
        kickoff_at="2026-06-20 20:00", competition="世界杯",
    )
    profile = MatchProfile(competition_type="club", time_to_kickoff_hours=None,
                            data_density="low", factor_pack="default")
    raw = _json.dumps({"daily": {
        "precipitation_probability_max": [90], "wind_speed_10m_max": [10],
        "temperature_2m_max": [22], "temperature_2m_min": [15], "weather_code": [65],
    }})
    evidence = [OsintEvidence(
        id="ev_001", source="Open-Meteo", source_type="weather",
        claim="比赛日天气: 雨", topic="weather.open_meteo", side="neutral",
        confidence=0.55, raw_excerpt=raw,
    )]

    factors = fr.build_factors(request, profile, evidence)
    weather_factor = next(f for f in factors if f.factor_id == "weather.exposure")
    assert weather_factor.enabled is True
    assert weather_factor.impact == -0.03
```

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/test_football_osint.py tests/test_evidence_extraction.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add backend/football_osint/factor_registry.py tests/test_football_osint.py
git commit -m "feat: score weather.exposure from actual precipitation/wind instead of a flat constant"
```

---

### Task 5: Full regression pass

**Files:**
- None modified — verification only.

- [ ] **Step 1: Run the entire backend test suite**

Run: `pytest -v` (from repo root, `.venv` active)
Expected: all tests PASS, including `tests/test_football_osint.py`, `tests/test_football_osint_prediction.py`, `tests/test_evidence_extraction.py`, and every other existing test file untouched by this plan (`test_billing.py`, `test_admin_cli.py`, etc.)

- [ ] **Step 2: Confirm no `LLM_API_KEY` leakage into test environment**

Run: `grep -rn "LLM_API_KEY" tests/test_evidence_extraction.py tests/test_football_osint.py`
Expected: every occurrence is inside a `monkeypatch.setenv`/`monkeypatch.delenv` call — no real key is read from `.env` during tests (the existing `monkeypatch.setenv("LLM_API_KEY", "fake-key")` pattern from Task 1/3 already guarantees this; this step is just a manual confirmation, not a code change).

- [ ] **Step 3: Manually smoke-test one real job against the running backend (optional, requires `.env` with a real `LLM_API_KEY`)**

```bash
curl -s -X POST http://localhost:8000/api/football/osint/jobs \
  -H "Content-Type: application/json" \
  -d '{"home_team":"巴西","away_team":"阿根廷","kickoff_at":"2026-06-20 20:00","competition":"世界杯"}' \
  | python3 -m json.tool | grep -A6 '"factor_id": "form.recent_signal"'
```

Expected: `"enabled": true` with a non-zero `"weight"` even though this match has no dongqiudi `matchId` resolvable yet — proof the LLM extraction path is now feeding the factor that used to need dongqiudi's own structured text.

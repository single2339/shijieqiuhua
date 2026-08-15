---
title: 世界球花“信息不足”归因与数据覆盖 PRD 修订补丁
version: 1.2.0-prd-addendum
status: review-ready
created: 2026-06-30
authors:
  - 产品负责人
  - Codex PRD整理
canonical_for:
  - football_osint data coverage
  - info_insufficient attribution
  - football source identity handoff
  - search relevance gates
amends:
  - docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md
  - docs/superpowers/specs/2026-06-30-football-cache-track-record-prd-addendum.md
source_audit:
  - backend/football_osint/analysis/prediction.py
  - backend/football_osint/factor_registry.py
  - backend/football_osint/pipeline.py
  - backend/football_osint/adapters/football_data_schedule.py
  - backend/football_osint/adapters/football_data_stats.py
  - backend/football_osint/adapters/dongqiudi_schedule.py
  - backend/football_osint/adapters/dongqiudi_analysis.py
  - backend/football_osint/analysis/evidence_extraction.py
  - bronze_storage/football_osint local job sample on 2026-06-30
---

# 世界球花“信息不足”归因与数据覆盖 PRD 修订补丁

## 0. 结论

本补丁把“信息不足”从一个不可解释的单一输出，升级为可归因、可统计、可恢复的数据覆盖状态。

现状不是模型单纯保守，而是结构化基本面链路覆盖不足：前端 fixture 多来自 football-data.org，赛前 detail 又依赖懂球帝 matchId；football-data stats 阶段丢失了 fixture 阶段已有的 provider identity，只能按中文队名反查；中文搜索缺相关性闸门，会把国家百科、外交部国家概况等泛页面作为 evidence；最终 `form` / `h2h` / `squad` 三类基本面因子没有任一启用，于是 `prediction.lean = info_insufficient`。

本补丁要求：

1. `info_insufficient` 必须带机器可统计的原因码和用户可读主因。
2. 从 `/fixtures` 到 `/predict-sync` / `/answer` 必须传递 provider identity，优先用稳定 ID 获取结构化 stats。
3. 中文搜索必须经过比赛相关性过滤和 URL 去重，不能把泛国家/百科页面算作媒体覆盖。
4. 结构化基本面优先于搜索；搜索只补充 vetted evidence，不直接制造方向判断。
5. 监控必须能按 adapter、factor、search relevance、extraction yield 归因，而不只看总 `info_insufficient` 比例。

---

## 1. Capability

已付费用户选择一场比赛后，系统能明确区分“真的缺数据”“数据源暂未发布”“provider 匹配失败”“搜索结果不相关”“抽取失败”等状态；当存在可靠结构化基本面时，系统应给出低/中/高置信度方向；当仍不足时，用户看到的是具体原因和可操作下一步，而不是泛泛的“信息不足”。

运营和工程侧能用指标定位不足来源：是 fixture/detail provider 不一致、team ID 解析失败、搜索噪声、LLM 抽取空、还是比赛确实过早。

---

## 2. 背景与已观察事实

### 2.1 现有产品红线仍然有效

主 PRD 已规定：

- 不输出投注建议。
- 不在缺证据时编造倾向。
- 缺数据时显式“信息不足”。

本补丁不推翻“诚实不足”的原则。它修的是“不足过宽、不可解释、不可恢复”的问题。

### 2.2 本地历史样本

2026-06-30 本地 `bronze_storage/football_osint` 抽样统计：

| 指标 | 数值 |
|---|---:|
| 已落盘 football_osint job | 60 |
| `info_insufficient` job | 42 |
| 2026-06-29 job | 15/15 为 `info_insufficient` |
| 2026-06-30 job | 13/13 为 `info_insufficient` |

2026-06-30 当前样本多为 `Japan U23 vs Korea U23` 或测试式 `Home U23 vs Away U23`，其典型状态为：

- `fixtures_public = ok`
- `dongqiudi_schedule = failed`
- `dongqiudi_analysis = skipped`
- `ddg_search = skipped`
- `cn_search = skipped`
- `form.recent_signal = disabled`
- `h2h.relevance = disabled`
- `squad.availability = disabled`

### 2.3 真实链路复现样本

加载项目 `.env` 后，当前 `/fixtures` 源返回未来比赛，例如：

```text
世界杯 科特迪瓦 vs 挪威 2026-06-30T17:00:00+00:00 scheduled
```

对 `科特迪瓦 vs 挪威` 跑 `全场比分预测是多少？` 后，结果为：

```text
lean = info_insufficient
confidence = L3
evidence_count = 17
```

其中 15 条中文搜索证据为泛页面，例如：

- `科特迪瓦_百度百科`
- `关于科特迪瓦的一切 - 知乎`
- `国家概况_中华人民共和国外交部`
- `走进非洲 | 科特迪瓦——从前的“象牙海岸”...`

这些页面不是足球比赛赛前情报，不能支持近期战绩、H2H 或阵容因子。

---

## 3. 当前根因

### R1. `info_insufficient` 判定依赖基本面因子

当前 `prediction.predict()` 的决策入口：

```python
active_factors = [
    f for f in factors
    if f.group in ("form", "h2h", "squad") and f.enabled
]
has_fundamental_signal = len(active_factors) >= factor_min

if not has_fundamental_signal:
    lean = "info_insufficient"
```

默认 `factor_min = 1`。因此只要 `form` / `h2h` / `squad` 没有任一启用，就必然输出 `info_insufficient`。

天气、fixture existence、中文媒体覆盖、青年赛事波动都不能单独避免 `info_insufficient`。

### R2. fixture provider 和 detail provider 不一致

前端赛事列表来自 `football_data_schedule.py`；懂球帝赛前分析来自 `dongqiudi_schedule.py` + `dongqiudi_analysis.py`。

当前真实样本中，football-data 返回未来世界杯比赛；懂球帝 schedule 只返回到 06-30 早场和部分历史/近场赛事，未包含 `科特迪瓦 vs 挪威`，导致：

```text
dongqiudi_schedule failed: no fixture
dongqiudi_analysis skipped: 缺少懂球帝 matchId
```

### R3. football-data stats 阶段没有复用 fixture identity

`football_data_schedule.parse_matches()` 读取了 football-data match payload，但当前对外 request 只保留中文展示名、开赛时间和赛事名。

后续 `football_data_stats.py` 需要重新执行：

```text
中文队名 -> name_translation.to_english -> /v4/teams?name=... -> team_id
```

这比直接复用 fixture 阶段的 `homeTeam.id` / `awayTeam.id` 更脆弱。

### R4. 中文搜索缺相关性闸门

英文搜索已有 `_search_result_matches_match()`，要求 home/away 双方命中。中文搜索 `_collect_chinese_search()` 当前直接接收搜索返回结果，没有：

- 主客双方同时命中校验；
- 足球/比赛/赛前语境校验；
- 百科/国家概况/旅游/外交页面排除；
- URL 去重；
- dropped result 计数。

结果是无关页面能进入 evidence，并可能启用 `media.cn_coverage`。

### R5. LLM extraction 不是源头保障

`evidence_extraction.py` 负责把 `fundamental.*`、`search.*`、`news.rss.*`、`user.note` 文本抽取成结构化字段。它可以从可靠文本中抽取，但不能把百科页面变成球队基本面。

因此修复顺序必须是：先过滤/补强 evidence，再抽取，不应靠 prompt 让 LLM 从无关材料中猜结论。

---

## 4. Scope

### 4.1 本补丁范围

| ID | 能力 | 范围 |
|---|---|---|
| C1 | 信息不足原因码 | 为 `info_insufficient` job 生成机器可统计原因码和用户可读主因 |
| C2 | fixture identity 传递 | `/fixtures` 到分析请求传递 provider match/team identity |
| C3 | football-data stats 直连 ID | 能用 team IDs 时不再按中文名反查 |
| C4 | 中文搜索相关性闸门 | 过滤无关搜索结果，去重，避免虚假 media coverage |
| C5 | evidence / factor 数据质量摘要 | 在 job/report/frontend 中展示哪些源可用、哪些因子缺失 |
| C6 | 不足率可观测性 | telemetry 按 adapter、factor、search、extraction 归因 |

### 4.2 非目标

| 非目标 | 原因 |
|---|---|
| 降低 `factor_min` 来强行减少不足 | 会违反“不编造倾向”红线 |
| 直接把泛媒体覆盖算作方向因子 | 搜到网页不等于基本面可用 |
| 引入投注/赔率/盘口判断 | 违反主 PRD R1 |
| 重做前端视觉设计 | 本补丁只改信息架构和展示内容 |
| 引入 Redis/Postgres | 当前单机 SQLite + bronze files 足够 |
| 一次接入多个新商业数据源 | 先修现有数据链路和归因，再扩源 |

---

## 5. Product Requirements

### PR-1. `info_insufficient` 必须可归因

每个 `prediction.lean == "info_insufficient"` 的 job 必须生成至少一个原因码。

建议原因码：

| Code | 含义 | 用户文案 |
|---|---|---|
| `too_early` | 距开赛较远，赛前情报常未发布 | “赛前分析通常在临近开赛前发布，系统会复扫。” |
| `detail_fixture_unmatched` | detail provider 找不到 matchId | “已确认比赛，但赛前分析源暂未匹配到该场。” |
| `structured_stats_unresolved` | football-data stats 未解析出 team/form/H2H | “结构化战绩源未解析到双方近期数据。” |
| `no_relevant_search_results` | 搜索无相关比赛结果 | “搜索未找到同时覆盖双方的赛前报道。” |
| `irrelevant_search_results` | 搜索有结果但被过滤为无关 | “搜索结果多为百科/泛介绍，未纳入判断。” |
| `llm_extraction_empty` | 有 vetted 文本但抽取为空 | “已有文本未抽取出近期战绩、交锋或阵容字段。” |
| `source_runtime_failure` | 源运行失败或超时 | “部分数据源暂时不可用，稍后自动重试。” |
| `no_user_supplied_context` | 用户未补充伤停/首发/URL | “可以补充官方预览、伤停或首发信息提高覆盖。” |

默认主因选择顺序：

1. `source_runtime_failure`
2. `detail_fixture_unmatched`
3. `structured_stats_unresolved`
4. `irrelevant_search_results`
5. `no_relevant_search_results`
6. `llm_extraction_empty`
7. `too_early`
8. `no_user_supplied_context`

### PR-2. Job 需携带数据质量摘要

新增或等价表达 `data_quality`，最小字段：

```json
{
  "insufficiency_reasons": ["detail_fixture_unmatched", "structured_stats_unresolved"],
  "primary_insufficiency_reason": "detail_fixture_unmatched",
  "source_summary": {
    "ok": 3,
    "skipped": 12,
    "failed": 1
  },
  "fundamental_factor_count": 0,
  "relevant_search_results_count": 0,
  "dropped_search_results_count": 15,
  "extraction_status": "empty"
}
```

如果实现时为避免模型破坏 API，可先放入现有 `next_steps` / `assessments` / `report_markdown`，但 telemetry 和后端内部必须有结构化字段。

### PR-3. `/fixtures` 必须保留 provider identity

`FixtureStatus` 需要携带可选 provider 字段：

```ts
interface FixtureStatus {
  id: string
  provider: 'football-data' | 'dongqiudi' | 'sporttery' | 'manual'
  provider_match_id?: string
  home_provider_id?: string
  away_provider_id?: string
  league: string
  kickoff_at: string
  kickoff_iso: string
  home_team: string
  away_team: string
  status: 'scheduled' | 'live' | 'finished'
  home_score?: number | null
  away_score?: number | null
}
```

兼容要求：现有字段不删除；新增字段 optional，以免破坏前端旧调用。

### PR-4. 分析请求必须可接收 provider identity

`FootballOsintJobRequest` 需要可选字段：

```python
provider: str = ""
provider_match_id: str = ""
home_provider_id: str = ""
away_provider_id: str = ""
home_aliases: list[str] = []
away_aliases: list[str] = []
```

前端从 fixture 点击进入分析时，应把这些字段带回后端。

兼容要求：手动输入比赛仍可只传 `home_team` / `away_team` / `kickoff_at`。

### PR-5. football-data stats 优先用 provider team IDs

当 `home_provider_id` / `away_provider_id` 存在且 `provider == "football-data"` 时：

- `fetch_team_form` 必须支持直接使用 team ID；
- `fetch_h2h` 必须支持直接使用 team IDs；
- 禁止先走中文名反查；
- 失败 reason 必须区分 `team_id_missing`、`api_empty_matches`、`api_error`、`h2h_empty`。

### PR-6. 中文搜索必须过滤无关结果

中文搜索 evidence 入库前必须通过 relevance gate。

通过条件：

1. 命中主队和客队之一的强别名组合；优先要求双方同时命中。
2. 命中至少一个足球语境词：`足球`、`比赛`、`世界杯`、`前瞻`、`阵容`、`伤停`、`比分`、`交锋`、`战绩`、`出线`、`小组赛`、`首发`。
3. URL 不在已收录集合中。
4. 不属于明确泛页面类型。

默认排除标题/URL/来源包含：

- `百度百科`
- `百科`
- `国家概况`
- `外交部`
- `旅游`
- `地图`
- `签证`
- `人口`
- `经济`
- `历史`
- `地理`

排除项要计数，不进入 evidence。

### PR-7. `media.cn_coverage` 只能统计相关且去重后的中文 evidence

`media.cn_coverage.enabled` 的判定不能再使用原始 `cn_evidence` 数量。

新规则：

```text
enabled = relevant_cn_evidence_count >= 3
```

重复 URL 只计 1 条。

### PR-8. LLM extraction 只消费 vetted evidence

LLM 抽取输入应优先包括：

1. `fundamental.*`
2. 通过 relevance gate 的 `search.*`
3. 通过 match relevance 的 `news.rss.*`
4. `user.note`

不应消费已判定为 irrelevant 的搜索结果。

如果 LLM 返回空，必须记录 `llm_extraction_empty`，而不是静默降级。

### PR-9. UI 文案升级为“可操作不足”

前端在 `info_insufficient` 时仍显示“信息不足”，但必须补充：

- 主因一句话；
- 缺失清单最多 3 条；
- 下一次系统动作或用户可操作动作。

示例：

```text
信息不足
主因：已确认比赛，但赛前分析源暂未匹配到该场；football-data 未解析出双方近期战绩。
缺口：近期状态、历史交锋、阵容伤停。
下一步：系统将在 T-5h/T-2h 自动复扫；你也可以补充官方前瞻或伤停 URL。
```

### PR-10. Telemetry 必须支持归因

新增或扩展分析完成事件：

```json
{
  "event_name": "research.analysis_completed",
  "lean": "info_insufficient",
  "match_key": "科特迪瓦|挪威|07-01 01:00",
  "question_id": "fulltime_score",
  "insufficiency_reasons": ["detail_fixture_unmatched", "structured_stats_unresolved"],
  "adapter_statuses": {
    "dongqiudi_schedule": "failed",
    "dongqiudi_analysis": "skipped",
    "football_data_stats": "skipped",
    "cn_search": "ok"
  },
  "fundamental_factor_count": 0,
  "relevant_search_results_count": 0,
  "dropped_search_results_count": 15,
  "extraction_status": "empty"
}
```

现有 `ALERT-11` 仍保留，但告警内容应能列出 top reason codes。

---

## 6. Interface and Data Implications

### 6.1 Backend models

修改 `backend/football_osint/models.py`：

- `FootballOsintJobRequest` 增加 provider identity optional 字段。
- 新增 `DataQualitySummary` Pydantic model，并在 `FootballOsintJob` 顶层增加 optional `data_quality: DataQualitySummary | None = None`。
- `OsintSourceStatus` 保持现有 shape；adapter 状态继续放在 `sources`，原因码由 `DataQualitySummary` 汇总。
- `PredictionResult` 不承载 data quality；它继续只表达方向、概率、比分带、drivers 和 uncertainties，避免预测结果与采集诊断耦合。

### 6.2 Frontend types

修改 `frontend/src/shijieqiuhua/types.ts`：

- `FixtureStatus` 增加 optional provider identity。
- `FootballOsintJobRequest` 增加 optional provider identity。
- `FootballOsintJob` 增加 optional `data_quality` 字段；`PredictionResult` 不增加 data quality 字段。

### 6.3 API compatibility

不得破坏：

- `POST /api/football/osint/predict-sync`
- `POST /api/football/osint/jobs`
- `POST /api/football/osint/answer`
- `GET /api/football/osint/fixtures`
- `GET /api/football/osint/jobs/{job_id}`
- `GET /api/football/osint/jobs/{job_id}/report.md`

所有新增字段为 optional；旧 request 仍可运行。

### 6.4 Storage compatibility

Bronze `status.json` 可以多出字段；旧 reader 应容忍缺失。

`request.json` 可保存 provider identity，但不能泄露非公开 user notes 到公开 history。

---

## 7. Acceptance Criteria

### AC-1. 当前坏样本不再制造假证据

输入：`科特迪瓦 vs 挪威`，搜索返回：

- `科特迪瓦_百度百科`
- `国家概况_中华人民共和国外交部`
- `关于科特迪瓦的一切 - 知乎`

期望：

- 这些结果不进入 `job.evidence`；
- `dropped_search_results_count >= 3`；
- `media.cn_coverage.enabled == false`；
- 如无其它基本面，仍可 `info_insufficient`，但原因包含 `irrelevant_search_results` 或 `no_relevant_search_results`。

### AC-2. 相关中文赛前报道能进入 evidence

输入：`巴西 vs 阿根廷`，搜索返回：

```text
巴西vs阿根廷世界杯前瞻：内马尔缺席，梅西领衔首发
```

期望：

- 结果进入 `search.cn.preview` evidence；
- URL 去重；
- `relevant_search_results_count >= 1`。

### AC-3. football-data fixture ID 透传

从 `/fixtures` 返回的 football-data 比赛必须包含：

- `provider = "football-data"`
- `provider_match_id`
- `home_provider_id`，如果 upstream payload 有该字段
- `away_provider_id`，如果 upstream payload 有该字段

前端调用 `/predict-sync` 或 `/answer` 时必须把这些字段传回。

### AC-4. football-data stats 用 ID 优先

当 request 含 `provider == "football-data"` 且双方 provider IDs 存在：

- stats adapter 不调用 `_search_team_api(name)`；
- 直接调用 team-id form/H2H 路径；
- 失败 reason 精确到 `api_empty_matches` 或 `h2h_empty`。

### AC-5. 每个信息不足 job 都有原因码

任意 `prediction.lean == "info_insufficient"` 的 job：

- `data_quality.insufficiency_reasons` 非空；
- `data_quality.primary_insufficiency_reason` 非空；
- report 或 answer 中能显示用户可读主因。

### AC-6. 监控可归因

触发 `research.analysis_completed` 后，telemetry payload 至少含：

- `lean`
- `insufficiency_reasons`
- `adapter_statuses`
- `fundamental_factor_count`
- `relevant_search_results_count`
- `dropped_search_results_count`
- `extraction_status`

`ALERT-11` 告警能展示 top reason code。

### AC-7. 不通过放松阈值解决覆盖率

测试必须证明：只有 fixture/weather/media coverage、但没有 `form` / `h2h` / `squad` 或其它明确新增结构化基本面时，系统仍然可以 abstain，不强行给方向。

---

## 8. Rollout Plan

### Phase 1 — Diagnosis and relevance gates

目标：先让不足变得可解释，清理假 evidence。

交付：

- data quality summary；
- 中文搜索 relevance filter；
- URL 去重；
- `media.cn_coverage` 只统计相关结果；
- telemetry reason codes；
- 前端 insufficient 主因展示。

### Phase 2 — Provider identity handoff

目标：减少 provider mismatch 和中文名反查失败。

交付：

- `/fixtures` 返回 provider identity；
- 前端 request 透传 identity；
- football-data stats 支持 team IDs；
- 失败 reason 精细化。

### Phase 3 — Source coverage expansion

目标：在现有链路稳定后，再接入新的结构化 football detail/stats source。

候选：SofaScore、FotMob、官方赛事页、可靠国家队 stats source。

Phase 3 需单独 PRD 或设计补丁；本补丁只为其留接口。

---

## 9. Test Requirements

所有行为变化必须 test-first。

必须新增或更新：

1. `tests/test_football_osint.py`
   - 中文搜索过滤坏样本；
   - 中文搜索接受好样本；
   - info_insufficient 原因码；
   - 不因 weather/media coverage 强行出方向。
2. `tests/test_football_data_schedule_range.py` 或新增 schedule tests
   - fixture provider identity 从 football-data payload 提取。
3. stats adapter tests
   - team ID path 不调用 name search；
   - API empty 和 h2h empty reason 区分。
4. frontend vitest
   - fixtureToMatch/request payload 透传 provider identity；
   - ReportView insufficient 主因展示。
5. alert runner tests
   - ALERT-11 可以统计 top reason codes。

---

## 10. Open Decisions with Defaults

| ID | 决策 | 默认值 | 是否阻塞实现 |
|---|---|---|---|
| OD-01 | `DataQualitySummary` 放在 job 顶层还是 prediction 内 | job 顶层 `data_quality` | 不阻塞 |
| OD-02 | 中文 relevance 是否要求双方同时命中 | 默认要求双方；若权威 sports domain 且标题命中赛事名可放宽 | 不阻塞 |
| OD-03 | `media.cn_coverage` 阈值是否仍为 3 | 保持 3，但只统计相关去重结果 | 不阻塞 |
| OD-04 | football-data payload 若没有 team ID 怎么办 | 回退现有 name search，并记录 `team_id_missing` | 不阻塞 |
| OD-05 | 旧 bronze job 是否回填 data_quality | 不回填；只对新 job 生成 | 不阻塞 |

---

## 11. Handoff

本文为 review-ready PRD。用户确认后，下一步使用 `writing-plans` 生成实施计划，再按 TDD 执行。

实施时必须遵守：

- 先写失败测试，再写生产代码；
- 不降低 `factor_min` 作为主修复；
- 不引入投注/赔率判断；
- 不改无关 UI 视觉；
- 不覆盖现有未提交改动；
- 所有新增 API 字段保持 optional 兼容。

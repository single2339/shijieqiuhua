---
title: 世界球花缓存与战绩统计 PRD 修订补丁
version: 1.1.0-prd-addendum
status: implementation-ready
created: 2026-06-30
authors:
  - 产品负责人
  - Codex PRD整理
canonical_for:
  - football_osint warm cache
  - prediction_record / track_record
  - post-match history data quality
supersedes:
  - docs/superpowers/specs/2026-06-22-prediction-track-record-design.md
  - docs/superpowers/plans/2026-06-22-prediction-track-record.md
amends:
  - docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md
  - docs/superpowers/specs/2026-06-27-shijieqiuhua-prd-v2-draft.md
source_audit:
  - agent://PrdDocAudit
  - agent://CodeContractAudit
---

# 世界球花缓存与战绩统计 PRD 修订补丁

## 0. 结论

本补丁把“缓存预热、job 落盘、赛后回看、公开命中率”重新划边界。实施前以本文为 `football_osint` 缓存/战绩统计的准入 PRD；原 `2026-06-22-prediction-track-record-design.md` 与对应 implementation plan 作为历史资料，不再作为实现依据。

核心决策：

1. **job 是问题级产物**：一次 match + question 计算产生一个 `FootballOsintJob`，持久化到 `bronze_storage/football_osint/{job_id}/`。
2. **公开命中率是比赛级统计**：同一场比赛无论跑了几个预设问题、几次重启补跑，只能贡献最多一条 `stats_primary` 样本。
3. **赛后历史是审计视图**：可包含 `home_or_draw`、`away_or_draw`、`info_insufficient` 等历史记录；公开命中率只统计明确方向 `home|away|draw`。
4. **warm cache 是性能优化，不是事实源**：内存 LRU 可丢；T-5h/T-2h 窗口完成状态必须持久化，避免重启重复预热。
5. **question/window metadata 必须落盘**：否则无法解释、去重、迁移、审计已生成 job。

---

## 1. 背景与问题

### 1.1 已观察事实

- 当前 v1 PRD 已把生产入口、warm cache、track record 纳入范围：`docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md:275-299`。
- 当前 `warm_cache` 明确按 `home_team|away_team|kickoff_at|question` 缓存，且 6 个预设问题都会被 T-5h/T-2h 预热：`backend/football_osint/warm_cache.py:25-32`, `backend/football_osint/warm_cache.py:68-82`, `backend/football_osint/warm_cache.py:226-260`。
- 当前 `prediction_record` 以 `job_id` 为主键：`sql/004_prediction_track_record.sql:2-16`。
- 当前 `track_record.record_if_definite()` 对每个完成 job 插入一行，`job_id` 重复才会跳过：`backend/football_osint/track_record.py:33-63`。
- 当前 `request.json` 只写 match 字段，不写 `question`、`locale`、`user_supplied` 或 warm window：`backend/football_osint/storage.py:49-58`。
- 当前 `/jobs/{job_id}` 与 `/jobs/{job_id}/report.md` 只查内存缓存，miss 后 404；`history.compare_jobs()` 另有 bronze fallback：`backend/football_osint/routes.py:126-143`, `backend/football_osint/history.py:155-176`。

### 1.2 根因

旧设计默认“一个 job 等于一场比赛的一次预测”。当前实现实际是“一个 job 等于一场比赛下某个问题的一次回答”。两者没有在数据模型中分开，导致：

- 6 个预设问题可能变成 6 条 `prediction_record`；
- 重启后 T-5h/T-2h 窗口可能重复跑，生成更多 job；
- `prediction_record` 缺少 `question_kind` / `warm_window` / `record_role`，无法解释样本来源；
- v2 赛后回看草稿误判为“只缺前端视图”，实际还缺数据质量基础。

---

## 2. Capability

已付费用户可以在赛前稳定看到同一场比赛的预热研判；赛后可以回看当时系统如何判断；公开首页可以展示经过去重、可审计、不会被问题级 job 污染的比赛级命中率。

成功后，系统必须满足：

- 同一比赛最多一条公开统计样本；
- 同一比赛的多个问题回答仍可保留为审计/历史细节；
- 服务重启不会把已完成 T-5h/T-2h 预热窗口当成没跑过；
- 旧数据迁移后能明确区分“可统计”“仅历史”“不可判定”；
- 前端历史/对比功能只能展示经过数据质量门控的记录。

---

## 3. 范围

### 3.1 本补丁范围

| ID | 能力 | 范围 |
|---|---|---|
| C1 | match-level stats identity | 为公开命中率建立比赛级唯一语义 |
| C2 | question/window metadata | 让每个 job 可解释其来源、问题类型、窗口 |
| C3 | durable warm-window state | T-5h/T-2h 完成状态持久化 |
| C4 | history/stat split | 历史记录与公开统计 denominator 分离 |
| C5 | bronze fallback consistency | job/report/history/compare 对落盘数据的读取边界一致 |
| C6 | migration/data quality gate | 已有污染数据迁移、去重、排除规则 |

### 3.2 非目标

| 非目标 | 原因 |
|---|---|
| 改预测算法本身 | 本补丁只修数据语义、缓存、统计口径 |
| 接真实支付 | v1 仍为付费码模式 |
| 做实时滚球/赔率建议 | 违反 PRD v1 红线 R1 |
| 做个人命中率 | v2.1；需要 user-session 到 match 的绑定 |
| 扩展到 200 场/日全量预计算 | 旧 v1.5 容量目标，先解决单场语义正确性 |
| 引入 Redis/Postgres | 当前单机 SQLite + 文件系统足够；先用最小改动 |

---

## 4. Canonical 决策

### D1. Canonical 文档优先级

| 优先级 | 文档 | 状态 |
|---|---|---|
| 1 | 本文 | 缓存/战绩/历史数据质量的当前准入 PRD |
| 2 | `2026-06-13-shijieqiuhua-prd-v1.md` | v1 产品主 PRD；缓存/track record 相关段落由本文修订 |
| 3 | `2026-06-27-shijieqiuhua-prd-v2-draft.md` | v2 UX 草稿；必须等待本文完成后才能实现 |
| 历史 | `2026-06-22-prediction-track-record-design.md` | 被本文 supersede |
| 历史 | `2026-06-22-prediction-track-record.md` | 被本文 supersede |
| 历史 | `2026-06-12-prd-redo/*` | 需求推导材料；不直接约束当前实现 |

### D2. job 与 match 的边界

- `FootballOsintJob`：问题级计算产物，仍以 `job_id` 标识。
- `match_key`：比赛级身份，用于窗口、历史分组、公开统计去重。
- `prediction_record`：结算/历史索引表，不再被解释为“命中率表”。公开命中率是该表上的过滤视图。

推荐 `match_key` 规则：

```text
normalized_home_team|normalized_away_team|kickoff_at
```

若后续可拿到稳定 provider fixture id，则升级为：

```text
provider:fixture_id
```

但 v1.1 不阻塞在 provider id 上。

### D3. 统计样本选择

同一 `match_key` 最多一条 `stats_primary=1`。默认选择规则：

1. 优先 `question_id = fulltime_score`（预设问题：“全场比分预测是多少？”）。
2. 同一问题多窗口时，优先 `warm_window = t-2h`。
3. 无 T-2h 时用 T-5h。
4. 无预热窗口时用最新 `on-demand` 的 `fulltime_score`。
5. 没有 `fulltime_score` job 时，该 match 不进入公开统计；可进入历史细节。

公开统计 denominator：

```sql
stats_primary = 1
AND settled_at IS NOT NULL
AND predicted_lean IN ('home', 'away', 'draw')
```

`home_or_draw`、`away_or_draw`、`info_insufficient`：

- 可进入历史/赛后回看；
- 不进入公开命中率 denominator；
- `info_insufficient` 的 correctness 为空，展示为“系统 abstain / 证据不足”。

### D4. warm cache 事实源

- 内存 LRU 只负责性能；不得作为“是否已预热”的唯一事实源。
- T-5h/T-2h 窗口完成状态写入 SQLite。
- 服务启动 catch-up 只补跑未成功持久化的窗口。
- 如果窗口只部分成功，状态必须可见，不得日志显示假 `6/6`。

### D5. bronze artifact fidelity

`request.json` 必须能解释 job 来源。最小新增字段：

```json
{
  "home_team": "巴西",
  "away_team": "日本",
  "kickoff_at": "06-30 01:00",
  "competition": "世界杯",
  "venue": "",
  "locale": "zh-CN",
  "question": "全场比分预测是多少？",
  "question_kind": "preset",
  "question_id": "fulltime_score",
  "question_hash": null,
  "warm_window": "t-2h",
  "cache_source": "t-2h",
  "match_key": "巴西|日本|06-30 01:00",
  "user_supplied_summary": {
    "injuries_count": 0,
    "lineups_count": 0,
    "notes_count": 0
  }
}
```

隐私边界：

- preset/on-demand 系统问题可以保存原文；
- free-text 用户问题保存原文前须确认无敏感输入策略；v1.1 默认保存 `question_hash` 和 `question_kind='free_text'`，不把 raw free-text 作为公开历史字段；
- `user_supplied.notes` 不进入公开历史，除非未来增加用户私有历史功能。

---

## 5. 数据模型修订

### 5.1 `prediction_record` 语义调整

现有表保留，增加列；避免大迁移。

建议新增字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `match_key` | TEXT | ✅ | 比赛级身份 |
| `question_kind` | TEXT | ✅ | `primary` / `preset` / `free_text` / `legacy` |
| `question_id` | TEXT | ✅ | preset id；free text 为 `free_text`；legacy 为 `legacy_unknown` |
| `question_hash` | TEXT | ❌ | free-text 或全部 question 的 sha1 前缀 |
| `warm_window` | TEXT | ✅ | `t-5h` / `t-2h` / `on-demand` / `legacy_unknown` |
| `cache_source` | TEXT | ✅ | `t-5h` / `t-2h` / `on-demand` / `migration` |
| `record_role` | TEXT | ✅ | `stats_primary` / `history_detail` / `legacy_pending` / `excluded` |
| `stats_primary` | INTEGER | ✅ | 0/1；公开统计唯一样本 |
| `excluded_reason` | TEXT | ❌ | 如 `duplicate_question_job`、`legacy_missing_question` |
| `created_from_job_id` | TEXT | ❌ | 保留源 job id；现有 `job_id` 仍是主键 |

SQLite 约束：

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_record_one_stats_primary
ON prediction_record(match_key)
WHERE stats_primary = 1;

CREATE INDEX IF NOT EXISTS idx_prediction_record_match_key
ON prediction_record(match_key);

CREATE INDEX IF NOT EXISTS idx_prediction_record_role_settled
ON prediction_record(record_role, settled_at);
```

### 5.2 新增 `warm_cache_run`

```sql
CREATE TABLE IF NOT EXISTS warm_cache_run (
  match_key TEXT NOT NULL,
  window TEXT NOT NULL,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  kickoff_at TEXT NOT NULL,
  competition TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,              -- running | completed | partial | failed
  expected_questions INTEGER NOT NULL DEFAULT 6,
  successful_questions INTEGER NOT NULL DEFAULT 0,
  job_ids_json TEXT NOT NULL DEFAULT '[]',
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT,
  error TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (match_key, window)
);
```

语义：

- `completed`：6/6 成功；
- `partial`：至少 1 个成功但未满 6；
- `failed`：0 个成功或 pipeline 全失败；
- catch-up 只跳过 `completed`，`partial/failed` 可按策略补跑；
- UI 不直接读取该表，先作为运维和去重依据。

### 5.3 `question_id` 枚举

| `question_id` | 原文 | 角色 |
|---|---|---|
| `first_half_score` | 上半场比分预计是多少？ | preset/history_detail |
| `cards_total` | 全场红黄牌的预测数量是多少？ | preset/history_detail |
| `corners_total` | 全场角球数预测是多少？ | preset/history_detail |
| `fulltime_score` | 全场比分预测是多少？ | preset/stats candidate |
| `key_player_state` | 核心球员状态会怎样影响比赛？ | preset/history_detail |
| `late_risk` | 这场比赛最大的临场风险是什么？ | preset/history_detail |
| `free_text` | 任意用户输入 | free_text/history_detail |
| `legacy_unknown` | 历史数据缺失 | legacy/excluded 或 migration candidate |

---

## 6. API 行为修订

### 6.1 `/track-record`

保持公开，但查询必须使用比赛级主样本：

```sql
WHERE stats_primary = 1
  AND settled_at IS NOT NULL
  AND predicted_lean IN ('home', 'away', 'draw')
```

返回结构保持兼容：

```json
{
  "settled": 42,
  "lean_accuracy": 0.643,
  "scoreline_accuracy": 0.214,
  "recent": []
}
```

新增可选字段：

```json
{
  "sample_policy": "one_stats_primary_per_match",
  "excluded_duplicates": 18
}
```

### 6.2 `/history`

历史列表默认按 `match_key` 分组，不直接暴露重复 question rows。每场返回主记录 + 可选 `detail_count`：

```json
{
  "match_key": "巴西|日本|06-30 01:00",
  "primary_job_id": "fo_...",
  "home_team": "巴西",
  "away_team": "日本",
  "predicted_lean": "home_or_draw",
  "actual_outcome": "draw",
  "detail_count": 6,
  "settled_at": "2026-06-30 04:48:03"
}
```

### 6.3 `/history/{job_id}`

可继续按 job_id 查详情，但返回中必须包含：

```json
{
  "record": {
    "job_id": "fo_...",
    "match_key": "巴西|日本|06-30 01:00",
    "question_id": "fulltime_score",
    "warm_window": "t-2h",
    "record_role": "stats_primary"
  }
}
```

### 6.4 `/compare`

`/compare` 接受 job_id 维持兼容，但前端应优先传 `primary_job_id`。同一 `match_key` 重复选择必须拒绝或自动去重。

### 6.5 `/jobs/{job_id}` 与 `/jobs/{job_id}/report.md`

目标行为：

1. 先查 `warm_cache.get_cached_by_job_id(job_id)`。
2. miss 时读取 `bronze_storage/football_osint/{job_id}/status.json`。
3. report miss 时读取 `report.md`。
4. 仍无数据才 404。

这样 LRU eviction / 服务重启不会让已落盘报告消失。

---

## 7. 迁移策略

### 7.1 新数据

所有新 job 写入：

- full/sanitized `request.json` metadata；
- `prediction_record.match_key`；
- `question_kind/question_id/question_hash`；
- `warm_window/cache_source`；
- `record_role/stats_primary`。

### 7.2 旧数据

旧数据缺少 `question` 和 `warm_window`，不能盲目当成可统计样本。

默认迁移规则：

1. 计算 `match_key = normalized(home_team)|normalized(away_team)|kickoff_at`。
2. 标记 `question_kind='legacy'`、`question_id='legacy_unknown'`、`warm_window='legacy_unknown'`。
3. 同一 `match_key` 只选择一条作为 `stats_primary`：
   - 优先 `predicted_lean IN ('home','away','draw')`；
   - 再按 `created_at DESC`；
   - 其余标记 `record_role='history_detail'`、`stats_primary=0`、`excluded_reason='duplicate_legacy_match'`。
4. 如果该 match 全部是 `home_or_draw/away_or_draw/info_insufficient`，全部不进入公开统计；历史可展示。
5. 迁移报告输出计数：`matches_total`、`stats_primary_selected`、`duplicates_excluded`、`legacy_unknown_question_count`。

### 7.3 不删除旧记录

v1.1 不物理删除污染行。通过字段和查询语义排除，保留审计可回滚能力。

---

## 8. Functional Requirements

| ID | Requirement | Source / rationale |
|---|---|---|
| FR-CACHE-01 | 系统必须为每场比赛生成稳定 `match_key`。 | warm cache 现有 `match_prefix` 仅内存使用 |
| FR-CACHE-02 | T-5h/T-2h 预热窗口完成状态必须写入 `warm_cache_run`。 | 服务重启会清空 `_completed_windows` |
| FR-CACHE-03 | warm 计数必须反映真实成功数；失败不能被计入 `6/6`。 | `_force_refresh()` 当前吞异常 |
| FR-CACHE-04 | `cache_or_compute(force_refresh=True)` 要么实现明确窗口语义，要么从公共路径移除/标 internal。 | 现在参数与 `_force_refresh()` 语义不一致 |
| FR-TRACK-01 | `prediction_record` 必须支持 `match_key`、question metadata、warm window、record role。 | 去重和审计需要 |
| FR-TRACK-02 | 同一 `match_key` 最多一条 `stats_primary=1`。 | 公开命中率比赛级统计 |
| FR-TRACK-03 | public stats 只统计 `stats_primary=1` 且 lean 为 `home|away|draw`。 | 防止 double-chance/abstain 污染命中率 |
| FR-TRACK-04 | `home_or_draw`、`away_or_draw`、`info_insufficient` 可进入历史，但不进入公开命中率。 | v2 history 需要回看系统 abstain/不败判断 |
| FR-STORAGE-01 | `request.json` 必须包含或可推导 question/window/cache metadata。 | 旧 request.json 无法解释 job 来源 |
| FR-STORAGE-02 | bronze `status.json` 继续作为完整 job 事实源。 | 当前 history/compare 已依赖 |
| FR-ROUTE-01 | `/jobs/{job_id}` 和 `/jobs/{job_id}/report.md` 必须支持 bronze fallback。 | 服务重启不应让落盘 job 404 |
| FR-HISTORY-01 | `/history` 默认按 `match_key` 分组。 | 防止同一场多 question 重复展示 |
| FR-HISTORY-02 | `/history/{job_id}` 返回 record metadata：match_key/question_id/warm_window/record_role。 | 用户/运营可解释当时看到的内容 |
| FR-MIGRATION-01 | 旧数据迁移不删除行，通过 role/excluded_reason 排除。 | 审计与可回滚 |

---

## 9. Non-Functional Requirements

| ID | Requirement | Acceptance |
|---|---|---|
| NFR-CACHE-01 | warm-window 判定不依赖进程内存。 | 服务重启后不会重复跑已 `completed` 的窗口 |
| NFR-STATS-01 | 公开命中率可解释。 | API 返回或日志能说明 denominator、excluded duplicates |
| NFR-HISTORY-01 | history 读取不能因 malformed `predicted_scoreline_band` 500。 | malformed band 降级为 `[]` 并记录 warning |
| NFR-PRIVACY-01 | free-text question 不默认公开展示原文。 | 历史列表不返回 raw free-text；详情遵循权限策略 |
| NFR-COMPAT-01 | 现有 `/track-record` 返回字段兼容前端。 | 原字段名不破坏；新增字段 optional |
| NFR-OPS-01 | 迁移可重复执行。 | 第二次运行不改变已完成迁移结果 |

---

## 10. Acceptance Criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | 同一场比赛 6 个预设问题全部完成 | backfill 写入 `prediction_record` | 该 `match_key` 最多 1 行 `stats_primary=1`，其余为 `history_detail` |
| AC-02 | 同一场比赛 T-5h 已成功完成 | 服务重启后 warm loop catch-up | 不重复跑 T-5h；`warm_cache_run` 保持 completed |
| AC-03 | T-2h 6 个问题中 1 个失败 | warm loop 完成 | `warm_cache_run.status='partial'`，`successful_questions=5`，日志不得显示 `6/6` |
| AC-04 | `prediction_record` 中同一 match 有旧重复 rows | 迁移执行 | 选出最多 1 条 `stats_primary=1`；其他行有 `excluded_reason` |
| AC-05 | `predicted_lean='info_insufficient'` 的 settled row | `/track-record` 统计 | 不进入 denominator；history 仍可展示“证据不足” |
| AC-06 | `predicted_lean='home_or_draw'` 的 settled row | `/track-record` 统计 | 不进入 public accuracy；history 显示实际是否落在不败范围 |
| AC-07 | 服务重启后请求旧 job 报告 | GET `/jobs/{job_id}/report.md` | 内存 miss 后从 bronze `report.md` 返回 200 |
| AC-08 | malformed `predicted_scoreline_band` 历史记录 | GET `/history` 或 `/history/{job_id}` | 返回 `[]` scoreline_band，不 500 |
| AC-09 | 用户选择多场对比时传入同一 match 的两个 job_id | POST `/compare` | 返回 422 或自动去重；不能重复展示同一比赛 |
| AC-10 | free-text question job 进入历史 | GET `/history` | 不公开 raw free-text；仅展示 `question_kind='free_text'` 与 hash/摘要策略 |

---

## 11. Traceability Matrix

| Goal | Requirement | Acceptance | Tests to write |
|---|---|---|---|
| G1 去重命中率 | FR-TRACK-01/02/03 | AC-01/04/05/06 | track_record migration + stats tests |
| G2 重启不重复预热 | FR-CACHE-01/02/03 | AC-02/03 | warm_cache_run scheduler tests |
| G3 job 可解释 | FR-STORAGE-01/02 | AC-10 | storage metadata tests |
| G4 报告不因内存丢失 404 | FR-ROUTE-01 | AC-07 | route bronze fallback tests |
| G5 history 不被 question rows 污染 | FR-HISTORY-01/02 | AC-08/09 | history grouping + malformed JSON tests |
| G6 旧数据可迁移 | FR-MIGRATION-01 | AC-04 | idempotent migration tests |

---

## 12. Implementation Handoff

建议开工顺序：

1. **Schema + migration**
   - 新增 `prediction_record` metadata columns。
   - 新增 `warm_cache_run`。
   - 写 idempotent migration/backfill helper。
2. **Storage metadata**
   - `request.json` 写入 question/window/cache metadata。
   - 定义 `question_id` helper。
3. **Warm scheduler durability**
   - `_completed_windows` 改为 DB-backed check；内存 set 只做加速。
   - `_force_refresh()` 返回 success/job_id。
4. **Track record semantics**
   - record all trackable history rows。
   - select exactly one `stats_primary` per `match_key`。
   - public stats filter `stats_primary=1 AND lean in home/away/draw`。
5. **Route/read model cleanup**
   - `/jobs` report bronze fallback。
   - `/history` match grouping。
   - `/compare` same-match guard。
6. **Tests**
   - 先写 migration/warm/track/history route tests，再实现。

开发模式：TDD，小步提交。不要修改预测算法权重、搜索策略、UI 视觉，除非测试暴露依赖。

---

## 13. Open Decisions with Defaults

| ID | Decision | Default for implementation |
|---|---|---|
| OD-01 | `match_key` 是否使用 provider fixture id | v1.1 用 normalized teams + kickoff；后续可迁移 |
| OD-02 | legacy duplicate 中选哪条为 primary | 优先明确方向，其次最新 created_at |
| OD-03 | partial warm window 是否补跑 | 默认补跑直到 completed；失败记录保留 |
| OD-04 | free-text raw question 是否落盘 | 默认不公开；request.json 可保存 hash/metadata，raw text 需权限策略后再展示 |
| OD-05 | `/compare` 同 match 多 job 处理 | 默认 422，提示“同一比赛只能选择一次” |

这些默认不阻塞开工；除非产品负责人明确覆盖，实施按默认走。

---

## 14. PRD Readiness Verdict

**Ready for implementation after this document is linked from the v1 PRD.**

阻塞已清除：核心口径、数据模型、迁移、验收标准已明确。剩余 OD-01..OD-05 有默认值，不需要再开产品会。

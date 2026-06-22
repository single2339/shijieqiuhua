# 预测战绩统计（命中率公示）设计

## 目标

给整个系统的预测能力提供可公示的统计证据，用于首页/获客场景的广告语，例如"近 124 场比赛方向命中率 68%"。统计口径必须经得起推敲，避免小样本或模糊判断（如 `home_or_draw`）冒充"命中"。

## 范围

- 只统计有明确方向的预测：`prediction.lean` ∈ {home, away, draw}。`home_or_draw`/`away_or_draw`/`info_insufficient` 不计入命中率统计（系统主动放弃判断时不应被算作"猜对"或拉低命中率）。
- 统计两个口径：胜负方向命中率（lean 与实际结果一致）、比分区间命中率（`scoreline_band` 覆盖实际比分）。
- 首页展示：汇总数字 + 最近 20 场已结算比赛的明细列表（可展开），不做独立翻页页面。
- 样本量 < 20 时不展示具体数字/明细（避免小样本可信度问题）。

## 数据模型

新增 `sql/004_prediction_track_record.sql`，复用现有共享 SQLite（`backend/auth/db.py` 的 `_auth.db`，通过 `_EXTRA_MIGRATIONS` 加载，与 `003_billing_and_entitlements.sql` 同模式）：

```sql
CREATE TABLE IF NOT EXISTS prediction_record (
    job_id TEXT PRIMARY KEY,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    kickoff_at TEXT NOT NULL DEFAULT '',
    competition TEXT NOT NULL DEFAULT '',
    predicted_lean TEXT NOT NULL,              -- home / away / draw
    predicted_scoreline_band TEXT NOT NULL,    -- JSON list, e.g. ["1-1","1-0","2-1"]
    actual_home_score INTEGER,
    actual_away_score INTEGER,
    actual_outcome TEXT,                       -- home / away / draw
    lean_correct INTEGER,                      -- 0/1，未结算前为 NULL
    scoreline_hit INTEGER,                     -- 0/1，未结算前为 NULL
    settled_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

只有满足"明确方向"条件的 job 才会插入一行（插入时立即写入，`actual_*`/`settled_at` 留空表示待结算）。

## 回填机制

### 数据来源与已知限制

- `dongqiudi_schedule` 只提供滚动 ~6 天窗口，无法按历史日期查询，**不适合回填**。
- `football_data_schedule`（football-data.org）原本只支持"今天起 N 天"的前向查询（`fetch_fixtures(days_ahead)`）。需扩展为支持任意 `date_from`/`date_to`（新增函数或加可选参数），复用现有 `parse_matches` 解析逻辑。
- football-data.org 免费层对历史日期范围的实际限制未完全验证 —— **历史回填是最佳努力（best-effort）**：最近几周的比赛大概率能回填成功，更久远的记录可能始终停留在"未结算"状态。这是已知且可接受的折衷，不阻塞上线。

### 匹配策略

- 用 job 的 `home_team`/`away_team`（标准化：去空格、统一大小写）与 football-data 返回的中文译名做精确匹配。
- 时间窗口：以 job 的 `kickoff_at`（若有）±1 天，或缺失时以 `created_at` 起 5 天内，查询该窗口的 fixtures。
- 命中且 `status == finished` 才写入实际比分；找不到匹配或未结束则保持未结算，下次回填周期再试。

### 触发方式

- 复用 `warm_cache.py` 已有的每小时循环，新增一步：`track_record.backfill_due()`。
  - 扫描 `bronze_storage/football_osint/*/status.json`，筛选：`status == COMPLETED`、`lean` 为明确方向、`kickoff_at` 早于当前时间 3 小时以上、且 `job_id` 不在 `prediction_record` 中 → 插入待结算行。
  - 对 `prediction_record` 中 `settled_at IS NULL` 的行，逐条尝试通过上述匹配策略解析实际比分并结算。
- 一次性历史回填脚本：`python -m backend.football_osint.track_record --seed-history`，对 `bronze_storage` 中所有历史 job 跑一遍同样的插入+结算逻辑，用于上线时立刻获得历史样本量（受上述 best-effort 限制）。

## 统计接口

`GET /api/football/osint/track-record`（`backend/football_osint/routes.py`）：

- SQL：`SELECT COUNT(*), SUM(lean_correct), SUM(scoreline_hit) FROM prediction_record WHERE settled_at IS NOT NULL`。
- 若 `settled < 20`：仅返回 `{"settled": N}`，不返回 accuracy 字段和 `recent` 列表。
- 若 `settled >= 20`：

```json
{
  "settled": 124,
  "lean_accuracy": 0.68,
  "scoreline_accuracy": 0.21,
  "recent": [
    {
      "home_team": "曼城", "away_team": "利物浦", "kickoff_at": "2026-06-15T19:00:00Z",
      "predicted_lean": "home", "predicted_scoreline_band": ["1-1", "2-1", "1-0"],
      "actual_home_score": 2, "actual_away_score": 1,
      "lean_correct": true, "scoreline_hit": true
    }
  ]
}
```

  `recent` 取 `settled_at` 最新的 20 条，按 `settled_at DESC`。

无需缓存层 —— 这是单次轻量聚合查询，每次请求直接查库即可。

## 前端展示

`frontend/src/shijieqiuhua/components/LandingPage.tsx`：

- 挂载时 fetch `/api/football/osint/track-record`。
- `settled < 20`：不渲染该模块（数据积累中，不展示半成品统计）。
- `settled >= 20`：渲染一个统计条，例如"近 124 场比赛 · 方向命中率 68% · 比分命中率 21%"，下方一个默认收起的"查看最近战绩明细 ▾"展开区，表格列：对阵 | 预测方向/比分 | 实际比分 | 命中 ✓/✗。纯展示组件，复用同一份 fetch 结果，不二次请求。

## 测试要点

- 后端：`track_record.py` 的插入/结算/聚合逻辑单测（明确方向才插入、`home_or_draw` 等不插入、`lean_correct`/`scoreline_hit` 计算正确、`settled < 20` 时接口裁剪字段）。
- 回填匹配逻辑单测：team name 标准化匹配、时间窗口匹配、找不到匹配时保持未结算。
- 不要求前端新增 E2E，覆盖到组件渲染的两种分支（有数据/无数据）即可。

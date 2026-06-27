---
title: 世界球花 PRD v2（草稿）
version: 2.0.0-draft
status: draft
date: 2026-06-27
authors:
  - 产品负责人
depends_on:
  - docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md
---

# 世界球花 PRD v2（草稿）

> **v2 核心命题**：让用户看到"我当时判断对了吗"——把赛前研判和赛后事实连起来，形成可回溯的判断闭环，驱动 7 天留存。

---

## 1. 背景

v1 解决了"赛前看什么"（主判断 + 证据链 + 追问）。用户付费后会重复回来的动力是**验证感**：我上次的判断准不准，哪个因子起作用了。

现有基础：
- `prediction_record` 表已落盘每次预测的 `predicted_lean` + `actual_outcome` + `lean_correct`
- `track_record.py` 的 `backfill_loop()` 已在开赛后自动回填比分
- `GET /api/football/osint/track-record` 已返回聚合胜率统计（Landing 展示用）

**缺的只是前端视图**：用户无法按比赛查自己当时看到的研判结论，也无法对比多场。

### 1.1 v2 成功指标（来自 PRD v1 §2.4）

| 时点 | 指标 |
|---|---|
| v2 上线 + 4 周 | 已付费用户 7 天留存 ≥ 30% |
| v2 上线 + 8 周 | 已付费用户人均每周回访 ≥ 2 次 |

---

## 2. 范围

### 2.1 v2 范围（本 PRD 主体）

| 功能 | 说明 |
|---|---|
| **赛后回看** | 比赛结束后，已付费用户可查看当时的研判结论与实际结果对照 |
| **多场对比** | 已付费用户可同时查看并横向对比 2–3 场比赛的研判摘要 |

### 2.2 v2 范围外

| 项 | 原因 |
|---|---|
| 赛中实时滚球 | 与红线 R1 冲突 |
| 用户个人命中率统计 | v2.1；需要绑定用户 session 到具体比赛 |
| 社区对比（看别人的判断） | v2.1；隐私和法律风险待评估 |
| 导出报告 PDF | v1.1 已规划，与 v2 并行 |

---

## 3. 核心功能

### 3.1 赛后回看（Post-Match Review）

**触发条件**：`prediction_record.settled_at IS NOT NULL`（比分已回填）

**页面入口**：赛事队列中已结束的比赛显示"查看回顾"按钮（仅已付费可见）

**内容结构**：

```
┌─────────────────────────────────────────┐
│  [赛事] 主队 2 - 1 客队  [已结束]       │
├─────────────────────────────────────────┤
│  研判结论         │  实际结果            │
│  ─────────────── │  ──────────────────  │
│  主队占优 (L2)   │  ✓ 主队赢（命中）   │
│  1-0, 1-1, 2-1  │  比分 2-1（命中）    │
├─────────────────────────────────────────┤
│  关键因子回顾                            │
│  ● 近期状态 → 主队主场 4 连胜 [✓ 应验]  │
│  ● 历史交锋 → 主队近 5 场 4 胜 [✓ 应验] │
│  ● 客队阵容缺阵 → 实际首发正常 [✗ 偏差] │
├─────────────────────────────────────────┤
│  系统注记（自动生成）                    │
│  "赛前识别的 3 个风险因子中，1 个出现。" │
└─────────────────────────────────────────┘
```

**字段来源**：

| 展示内容 | 来源 |
|---|---|
| 预测结论 / 置信度 | `prediction_record.predicted_lean` + job 的 `report.md` |
| 实际比分 | `prediction_record.actual_home_score` / `actual_away_score` |
| 命中标记 | `prediction_record.lean_correct` / `scoreline_hit` |
| 关键因子 | job 的 `factors` 字段（需从 bronze_storage 读取） |
| 系统注记 | LLM 后处理（可选，v2 先用规则生成） |

**命中判定规则**（已在 track_record.py 实现）：

| predicted_lean | 命中条件 |
|---|---|
| home | actual_outcome = 'home_win' |
| away | actual_outcome = 'away_win' |
| draw | actual_outcome = 'draw' |
| home_or_draw | actual_outcome in ('home_win', 'draw') |
| away_or_draw | actual_outcome in ('away_win', 'draw') |
| info_insufficient | 不参与命中统计 |

### 3.2 多场对比（Multi-Match Comparison）

**场景**：用户想同时看"今晚 3 场英超"的研判摘要，横向对比置信度和倾向。

**交互**：赛事队列支持多选（最多 3 场），点击"对比"后展开对比面板。

**对比维度**：

| 维度 | 说明 |
|---|---|
| 研判倾向 | lean + 可信度等级 L1–L4 |
| 证据密度 | 强证据数 / 弱信号数 / 样本不足数 |
| 关键风险 | uncertainties 前 2 条 |
| 信息完整度 | enabled 因子数 / 总因子数 |

**约束**：只能对比"已有缓存研判"的比赛（已付费 + 已触发过 OSINT pipeline）；无缓存的比赛不可选入对比。

---

## 4. 数据模型变化

### 4.1 现有表无需改动

`prediction_record` 表结构已满足赛后回看需求。

### 4.2 新增 API 端点

| 路径 | 方法 | 用途 | 权限 |
|---|---|---|---|
| `/api/football/osint/history` | GET | 已结束比赛列表（含 lean_correct）| 已付费 |
| `/api/football/osint/history/{job_id}` | GET | 单场回顾：预测 + 实际 + 因子 | 已付费 |
| `/api/football/osint/compare` | POST | 多场对比（最多 3 个 job_id）| 已付费 |

#### `GET /api/football/osint/history` 响应摘要

```json
[
  {
    "job_id": "fo_20260620_abc123",
    "home_team": "曼城", "away_team": "阿森纳",
    "kickoff_at": "2026-06-20 21:00",
    "competition": "英超",
    "predicted_lean": "home",
    "actual_outcome": "home_win",
    "lean_correct": true,
    "scoreline_hit": true,
    "settled_at": "2026-06-20 23:10"
  }
]
```

#### `GET /api/football/osint/history/{job_id}` 响应摘要

```json
{
  "record": { /* prediction_record 行 */ },
  "factors": [ /* 来自 bronze_storage job 的 factors */ ],
  "report_excerpt": "...",  /* report.md 前 500 字 */
  "retrospective": {
    "hit_factors": ["近期状态", "历史交锋"],
    "miss_factors": ["客队阵容缺阵"],
    "note": "赛前识别的 3 个风险因子中，1 个出现。"
  }
}
```

`retrospective` 的 `hit_factors`/`miss_factors` v2 先用**规则**生成（不调 LLM）：因子方向与实际结果吻合 → hit，否则 → miss；`info_insufficient` 因子不参与。

### 4.3 bronze_storage 读取

`history/{job_id}` 需要从 `bronze_storage/football_osint/{job_id}/status.json` 读 factors。`storage.py` 已有 `load_job()` 骨架（或直接读 JSON）。v2 不改落盘格式。

---

## 5. 前端设计

### 5.1 赛后回看入口

- 左栏赛事队列：已结束比赛显示灰色状态 + "回顾 →" 链接（仅付费可见）
- 点击后中栏切换为 `PostMatchReview` 组件（复用 `ReportView` 样式）
- 标题区显示实际比分 + 命中/未命中徽章（绿色勾 / 红色叉）

### 5.2 多场对比

- 赛事队列支持 checkbox 多选（最多 3 场，超出提示"最多同时对比 3 场"）
- 右下角浮现"对比 N 场"按钮
- 点击后底部抽屉或全屏展开对比表格（`ComparePanel` 组件）

### 5.3 新增组件

| 组件 | 职责 |
|---|---|
| `PostMatchReview` | 赛后回看主视图（预测 vs 实际 + 因子回顾） |
| `RetroFactorList` | 因子命中/偏差列表（带颜色标注） |
| `ComparePanel` | 多场对比面板（最多 3 列） |
| `MatchCheckbox` | 赛事队列中的多选控件 |

---

## 6. 非功能需求

| ID | 要求 |
|---|---|
| NFR-v2-1 | `GET /history` < 200ms（仅查 SQLite prediction_record，无 LLM） |
| NFR-v2-2 | `GET /history/{job_id}` < 500ms（读 SQLite + 一次 bronze JSON 读取） |
| NFR-v2-3 | `/compare` < 1s（最多 3 个 job 的内存拼合，无 LLM） |
| NFR-v2-4 | history 列表默认返回最近 30 天、最多 50 条 |

---

## 7. 实施计划（估算）

**前提**：v1 已上线，track_record 数据已积累 ≥ 2 周。

| 周 | 里程碑 |
|---|---|
| W1 | `GET /history` + `GET /history/{job_id}` 后端（规则生成 retrospective） |
| W2 | `PostMatchReview` + `RetroFactorList` 前端组件 |
| W3 | `POST /compare` 后端 + `ComparePanel` 前端 |
| W4 | 多选 UI + 集成测试 + 内测验收 |

总工期：**4 周**单人节奏。无新外部依赖，无新 LLM 调用（retrospective 用规则）。

---

## 8. 开放问题

| ID | 问题 | 默认建议 |
|---|---|---|
| Q-v2-1 | 赛后回看是否对"未付费"用户展示摘要？ | 不展示；回看是留存钩子，不开放给未付费 |
| Q-v2-2 | `/history` 列表是否绑定到当前登录用户，还是全局？ | v2 全局（所有付费用户看同一份历史），个人命中率统计 v2.1 |
| Q-v2-3 | 因子命中/偏差的判定逻辑是否足够准确？ | 先上规则版本，收集用户反馈后看是否需要 LLM 辅助解读 |
| Q-v2-4 | `info_insufficient` 的比赛在历史列表怎么展示？ | 显示但标注"证据不足，未作方向判断"，不计入命中率 |
| Q-v2-5 | bronze_storage 里 job 的 factors 可能因缓存清理丢失，降级策略？ | 降级展示"因子数据已过期"，不影响命中标记的展示 |

---

## 9. 关键路径依赖

```
v1 正式上线
  └─→ track_record 数据积累 ≥ 2 周（有足够已结束比赛）
        └─→ v2 开发启动
```

v2 不依赖 v1.5（微信小程序），可并行推进。

---

*本文档为草稿，待 v1 上线后根据实际运营数据校准范围。Q-v2-1 至 Q-v2-5 需产品负责人在 v2 开发启动前确认。*

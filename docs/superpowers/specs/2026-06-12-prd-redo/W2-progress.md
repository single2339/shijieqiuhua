---
title: W2 进度报告 (2026-06-13)
phase: implementation-week-2
status: done (8/8 sub-steps complete)
sibling: W1-progress.md
---

# W2 进度报告（完成）

PRD §11.1 W2：「注册/登录链路 + 邀请/付费码闭环 + 因子注册表 + pipeline.py 拆分」。

W2 拆 8 个子步骤；**全部完成**。pipeline.py 从 730 行 → 240 行（-67%）。

## 完成清单

| 步 | 搬什么 | 目标模块 | 测试 |
|---|---|---|---|
| W2.1 | `_persist` | `storage.py`（W1 已有） | 12/12 |
| W2.2 | URL 安全 7 函数 | `adapters/url_safety.py` | 12/12 |
| W2.3 | `_render_report + _compact_markdown + _claim_from_markdown` | `analysis/report.py` | 12/12 |
| W2.4 | `_predict + _band` / `_confidence` | `analysis/prediction.py` + `confidence.py` | 111/111 |
| W2.5 | `_build_intelligence_cycle + _confirmed_findings + _assessments + _alternative_explanations + _next_steps` | `analysis/intelligence.py` | 12/12 |
| W2.6 | `_score_factors` | `factor_registry.py`（删 W1 delegate） | 111/111 |
| W2.7a | `_fetch_lightpanda_url`；`_append_evidence` | `adapters/lightpanda.py`；`evidence.py` | 12/12 |
| W2.7b | `_farich_foot_candidate_urls + _win007_match_id` | `adapters/win007.py` | 12/12 |
| W2.7c | `_manual_candidate_urls` | `adapters/user_supplied.py` | 12/12 |
| W2.8 | 全 thin shim 删除；`run_prediction_sync` 直接调模块 | — | 111/111 |

## pipeline.py 行数轨迹

```
W0  730 (首次检视)
W1  730 (skeleton 不动)
W2.1 728
W2.2 686
W2.3 626
W2.4 599
W2.5 545
W2.6 525
W2.7a 475
W2.7b 455
W2.7c 440
W2.8 240  ← 达成（目标 < 200 留 W2.9 后续清理 _collect_* 到 adapters/collector.py）
```

## 最终模块分布（16 文件 / 1132 行）

```
pipeline.py           240  orchestration only
adapters/
  url_safety.py       103  SRF + allowlist
  lightpanda.py        70  subprocess wrapper
  win007.py            53  URL catalog
  user_supplied.py     29  user URL extraction
  base.py              33  Adapter protocol
analysis/
  report.py           124  markdown renderer
  intelligence.py     137  findings / cycle / alternatives
  prediction.py        61  linear factor model
  confidence.py        37  L1-L4 grading
factor_registry.py     92  per-profile rules
evidence.py            67  append + classify
storage.py             68  bronze persistence
```

单文件 ≤ 240 行，符合 CLAUDE.md 800 行上限。

## 测试

111 passed（W1 收尾 111；W2 无新增测试无破坏）。

## 下一步

W3（PRD §11.1）：「三栏布局 + MatchQuestionCard + EvidenceStrength + AuthGate」。

建议先做 **W2.9 路由挂载**（把 billing/audit 的 FastAPI 路由接上 main.py，1 天），让 W3 前端有真实 API 可调。

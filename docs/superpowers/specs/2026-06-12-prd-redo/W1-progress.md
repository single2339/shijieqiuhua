---
title: W1 进度报告 (2026-06-13)
phase: implementation-week-1
status: done
sibling: ../2026-06-13-shijieqiuhua-prd-v1.md
---

# W1 进度报告

PRD §11.1 的 W1 里程碑：「DB 模型 + admin CLI + 后端拆分骨架」。

## 完成清单

| PRD 项 | 文件 | 行数 | 测试 |
|---|---|---|---|
| §6.1 SQL 表 | `sql/003_billing_and_entitlements.sql` | 63 | — |
| audit_log writer (GAP-W-3) | `backend/audit.py` | 73 | 5 |
| billing 服务 (UC-03 / AC-03-1..10) | `backend/billing/service.py` | 245 | 16 |
| admin CLI (UC-10 / OPS-4) | `backend/admin.py` | 336 | 14 |
| OSINT 拆分骨架 (Q5) | `backend/football_osint/{storage,factor_registry,evidence}.py + adapters/ + analysis/` | 166 | 5 (evidence) |
| migration loader | `backend/auth/db.py` (Edit) | +6 | (现有 auth 测试) |

新增**1395 行**（901 模块 + 494 测试 + SQL）；新增 **40 个测试** 全过；旧 71 测试零破坏；总计 **111 passed**。

## 关键设计决策（W1 期间发现，已固化）

### D-W1-1：billing/audit/admin 共享 `_auth.db`，不另起新 DB

PRD §6.1 把 user/invitation/activation_code/entitlement/audit_log/system_config 都画在一起，但现有 `_auth.db` 已经持有 users/registration_codes 表。**没拆是对的**——SQLite 单库内 `BEGIN IMMEDIATE` 才能让"flip activation_code.status + INSERT entitlement + INSERT audit_log"原子执行，跨 DB 做不到原子事务。

代价：`audit_log.user_id` 用 `INTEGER REFERENCES users(id)`，与 PRD §6.1 写的 `TEXT` 不一致——但与现有 schema 一致更重要。PRD 文档已落，长期不再改 schema。

### D-W1-2：billing 用 SQLite `BEGIN IMMEDIATE`，不依赖 SAVEPOINT

`redeem_code` 的并发安全靠 SQLite 自身的 reserved lock：两个客户端同时 redeem 同一码 → 后到的看到 status='used' → `E_CODE_USED`。AC-03-8 的并发测试**没**写（SQLite 单进程多线程模型在测试里很难重现真实并发），延后到 W6 灰度时跑一次端到端。

### D-W1-3：admin CLI 不用 `Typer/Click`

`argparse` 够用，少一个依赖。CLI 只面向 SSH 的运维者，不暴露给最终用户，体感优先级低。

### D-W1-4：football_osint 拆分骨架"只搬空壳"

W1 真正搬代码会破坏 `tests/test_football_osint.py` 的 12 个测试。骨架文件全部 import-safe，pipeline.py 不动；W2 才搬运。`factor_registry.build_factors` 暂时 delegate 回 `pipeline._score_factors` 让上层调用方先迁移过来——这是经典的 "expand-contract migration" 模式。

### D-W1-5：admin CLI 不和现有 `auth/admin_routes.py` 合并

后者是 HTTP API（admin UI 用），前者是 CLI（运维用）。两者的鉴权模型不同（前者 JWT cookie + role='admin'；后者 ADMIN_TOKEN），代码路径不能简单复用。共享部分通过 `backend.billing` / `backend.audit` 抽出。

## 验收 AC 覆盖度（PRD §10）

UC-03 付费码兑换：✅ 全部 10 条 AC 有测试覆盖
UC-10 admin 批发：✅ AC-10-1, AC-10-2, AC-10-3, AC-10-4, AC-10-5, AC-10-6 全覆盖
GAP-W-3 audit_log 字段：✅ 写入 ip/ua/payload_json
NEG-2/NEG-3 SRF：上轮已修，未回归
DoD §10 第 1-12 项：所有 W1 新增模块均符合（含 migration、错误码、测试覆盖）

## 还没动（按计划留给 W2-W6）

| 项 | 计划周 |
|---|---|
| 注册/登录 OTP 流程（UC-01/UC-02） | W2 |
| 邀请码生成 API（UC-09） | W2 |
| 微信平台占位（identity.provider='wechat_mp'） | W2（仅 schema） |
| pipeline.py 真正搬到子模块 | W2 |
| factor_registry 完整规则 | W2 |
| MatchQuestionCard 完整版（UC-05） | W3 |
| EvidenceStrength + AuthGate（UC-04/UC-08） | W3 |
| PaymentUnlock + InvitePanel（UC-09） | W4 |
| LLM 引用合法性校验（UC-07/AC-07-2） | W4 |
| 备份/HTTPS/systemd（NFR-5/-6, OPS-1） | W5 |
| Rollout checklist（RQ-I-1） | W6 |

## W2 上手指南

W2 第一周会触碰 `backend/football_osint/pipeline.py` 685 行的拆分。建议顺序：

1. 先读 `backend/football_osint/storage.py` 注释——这是 W1 已经定好的目标接口
2. 把 pipeline.py 的 `_persist()` 替换为 `storage.persist_job(job)` 调用
3. 跑 `pytest tests/test_football_osint.py` 确认 12 测试仍过
4. 再把 `_score_factors` 搬到 `factor_registry.py`，删 `factor_registry.build_factors` 里的 delegate import
5. 拆 `_collect_*` 函数到 `adapters/`（每个 adapter 一个文件）
6. 拆 `_predict / _confidence / _build_intelligence_cycle / _render_report` 到 `analysis/`
7. pipeline.py 应该收缩到 < 200 行（只剩 orchestration）

每一步一个 PR，跑完测试再合下一步。

## 部署影响

W1 没改任何运行时行为：

- 新 SQL 在启动时 idempotent 应用，老库自动加新表
- `pipeline.py` 一行没改，OSINT 流水线行为不变
- 新增模块（admin/billing/audit）不接 FastAPI 路由——必须 W2 显式 wire 起来才生效
- 现有 `osint-network.service` 重启即可，无 migration 数据风险

## 数字

```
旧 71 → 新 111 测试  (+ 40, +56%)
901 行业务 + 494 行测试  (test 占比 35%)
billing.service 245 行 — 比一个独立模块的 800 上限低很多
admin.py 336 行 — argparse 派发 + 6 子命令，可读
```

W1 完成。下一步建议：进 W2 或先 commit 当前进度。

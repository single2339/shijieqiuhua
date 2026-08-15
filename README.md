# 世界球花（ShijieQiuhua）— 足球 OSINT 赛前研判

世界球花是一个面向足球赛前情报研判的产品：后端采集公开足球信息并生成可解释情报报告，前端提供选赛、提问、历史记录、赛后复盘、胜平负倾向和置信等级展示。

## 当前架构

| 模块 | 路径 | 说明 |
|------|------|------|
| FastAPI 入口 | `backend/app_football.py` | 当前生产应用，组合 auth/admin/billing/football OSINT 路由，并启动缓存预热与赛果回填后台任务 |
| 兼容入口 | `backend/main.py` | 仅 re-export `backend.app_football.app`，保留旧部署/import 路径 |
| 足球 OSINT 引擎 | `backend/football_osint/` | 赛程、公开源采集、因子构建、置信评级、预测倾向、报告、历史与 track record |
| Auth / Billing | `backend/auth/`, `backend/billing/` | 用户、会话、邀请码、权益、审计日志 |
| 遥测与运维 | `backend/telemetry.py`, `backend/alert_runner.py`, `scripts/run-dashboard.sh` | SQLite telemetry、告警、Datasette 仪表盘 |
| React SPA | `frontend/src/shijieqiuhua/` | Warm beige 风格产品界面：落地页、主工作台、报告、历史、对比、账号与后台 |
| 运行数据 | `bronze_storage/` | 本地 SQLite 与 football job artifacts；这是运行时状态，不是源码 |

## 常用命令

| What | Command | From |
|------|---------|------|
| Run backend | `uvicorn backend.app_football:app --reload --port 8000` | root（激活 `.venv` 后） |
| Run frontend | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` | `frontend/` |
| Frontend test | `npm test` | `frontend/` |
| Backend test | `pytest` | root（激活 `.venv` 后） |

Python 依赖在 `requirements.txt`，前端依赖在 `frontend/package.json`。

## 关键文档

- `docs/football-analysis.md`：早期足球分析接口说明
- `docs/runbook-v1.md`：生产运维与故障处理
- `docs/superpowers/specs/`：PRD、验收标准、telemetry、track record、情报不足等规格
- `docs/superpowers/plans/`：已执行/进行中的实现计划

## 设计产物

- `designs/osint-network-intro/`：项目介绍 PPTX/HTML deck
- `designs/shijieqiuhua-product/`：产品 UI 原型与预览图

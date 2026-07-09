# 世界球花 / OSINT Network 项目介绍 — slide outline

Audience: 10分钟通用介绍。Design: 沿用 warm beige 情报面板；参考 `designs/shijieqiuhua-product`，无正式 design system 绑定。

## Evidence anchors
- `README.md` describes the original global OSINT collection network: compliance, collection contracts, medallion architecture, agent plane, A-D roadmap.
- `backend/main.py` is now a compatibility entrypoint to `backend.app_football`, so the implemented product is currently ShijieQiuhua football OSINT.
- `backend/app_football.py` exposes FastAPI with auth/admin/football/billing routers, warm cache + track-record background tasks, CORS, rate limiting, health.
- `backend/football_osint/routes.py` exposes prediction jobs, answer, fixtures, track record, history, match detail, compare.
- `backend/football_osint/pipeline.py` orchestrates collection, normalization, factor scoring, confidence, prediction, report persistence.
- `backend/football_osint/warm_cache.py` caches match+question answers and scheduled T-5h/T-2h rescans.
- `backend/football_osint/analysis/confidence.py` maps evidence/factors to L1-L4.
- `backend/football_osint/factor_registry.py` scores fixture/form/squad/youth/draw-risk/H2H/weather/media factors.
- `backend/football_osint/storage.py` persists bronze artifacts under `bronze_storage/football_osint/{job_id}/`.
- `frontend/src/App.tsx` surfaces landing/auth/app views, fixture rail, history, compare, paywall/admin.
- `frontend/src/shijieqiuhua/components/ReportView.tsx` renders cycle/factors/evidence/findings/next tabs.
- `frontend/src/shijieqiuhua/components/LandingPage.tsx` markets 7 source classes, 4 confidence levels, 5-step cycle, T-2h rescan, public track record.
- `docs/01...04` define compliance boundaries, collection contracts, Bronze/Silver/Gold, claim verification, agent plane.

## Title sequence
1. 世界球花：把公开赛事情报变成可复核判断
2. 项目从通用 OSINT 网络收敛到足球研判产品
3. 用户看到的是三层工作台：赛程、提问、报告
4. 后台把一次提问拆成采集、评分、报告与留痕
5. 数据模型坚持 Bronze 留证、Silver 清洗、Gold 产出
6. 判断不是裸结论：它由信源、因子和置信度组成
7. 产品把不确定性显性化，而不是强行预测
8. 权限、缓存和战绩回填让系统可运营
9. 代码已经覆盖关键风险：鉴权、去重、赛后结算、数据不足
10. 下一步是从单垂直产品扩展回可复用 OSINT 平台

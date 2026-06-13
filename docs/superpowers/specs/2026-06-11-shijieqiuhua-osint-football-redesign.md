# 世界球花 OSINT 足球预测重设计

## 目标

把当前“世界球花”从前端本地 mock 问答，升级为可部署的 OSINT 足球预测系统。系统默认不依赖 Bing、赔率商或付费足球 API；有额外密钥时可以增强采集，没有密钥时正常降级运行。

## 设计原则

- 零配置可运行：服务器只要能联网，基础预测链路就能跑。
- 不硬套固定七维：七维框架保留为默认因子包，但实际分析使用动态因子注册表。
- 证据优先：每个预测结论都能追溯到证据、来源、时间和置信度。
- 缺数据要明说：没有赔率、伤病、首发时不填中性分，而是返回 `missing_reason`。
- 前后端解耦：前端只依赖 job 状态、证据、因子、预测和报告契约，不依赖后端内部采集方式。
- LLM 不直接预测：LLM 只做自然语言解析和报告润色；预测核心由证据、规则、概率和动态因子模型完成。

## 后端架构

新增模块：

```text
backend/football_osint/
  __init__.py
  models.py
  routes.py
  pipeline.py
  storage.py
  factor_registry.py
  evidence.py
  adapters/
    base.py
    fixtures_public.py
    ddg_search.py
    official_site.py
    open_meteo.py
    geo_distance.py
    local_poisson.py
    user_supplied.py
    optional_bing.py
    optional_odds.py
  analysis/
    profiling.py
    factor_scoring.py
    confidence.py
    prediction.py
    report.py
```

现有 `backend/football.py` 保留，继续服务 `/api/football/analyze`，作为“已知赔率和近况数据”的快速 Poisson 模型。

新增 OSINT API：

```text
POST /api/football/osint/jobs
GET  /api/football/osint/jobs/{job_id}
GET  /api/football/osint/jobs/{job_id}/report.md
POST /api/football/osint/predict-sync
```

`predict-sync` 只用于测试和低流量同步调用；前端生产路径使用 job API。

## 后端数据契约

创建任务请求：

```json
{
  "home_team": "Thailand U23",
  "away_team": "UAE U23",
  "kickoff_at": "2026-06-08 18:00",
  "competition": "AFC U23 Asian Cup",
  "venue": "",
  "locale": "zh-CN",
  "question": "上半场角球会不会偏多？",
  "user_supplied": {
    "market_odds": null,
    "injuries": [],
    "lineups": [],
    "notes": []
  }
}
```

任务结果：

```json
{
  "job_id": "fo_20260611_abc123",
  "status": "queued",
  "phase": "verify",
  "progress": 15,
  "match": {
    "home_team": "Thailand U23",
    "away_team": "UAE U23",
    "kickoff_at": "2026-06-08 18:00",
    "competition": "AFC U23 Asian Cup",
    "profile": {
      "competition_type": "u23",
      "time_to_kickoff_hours": 8,
      "data_density": "medium",
      "market_available": false,
      "factor_pack": "youth_match"
    }
  },
  "sources": [],
  "evidence": [],
  "factors": [],
  "prediction": null,
  "confidence": null,
  "report_markdown": ""
}
```

证据单元：

```json
{
  "id": "ev_001",
  "source": "SofaScore public page",
  "source_type": "fixture",
  "url": "https://example.com/match",
  "observed_at": "2026-06-11T15:00:00Z",
  "claim": "比赛存在，开球时间与用户输入一致",
  "topic": "fixture.existence",
  "side": "both",
  "confidence": 0.78,
  "freshness": 0.9,
  "raw_excerpt": "..."
}
```

动态因子：

```json
{
  "factor_id": "squad.availability",
  "label": "阵容可用性",
  "group": "squad",
  "enabled": true,
  "weight": 0.18,
  "impact": 0.12,
  "direction": "home",
  "confidence": 0.71,
  "evidence_ids": ["ev_004", "ev_008"],
  "missing_reason": ""
}
```

缺失因子：

```json
{
  "factor_id": "market.liquidity",
  "label": "盘口流动性",
  "group": "market",
  "enabled": false,
  "weight": 0,
  "impact": 0,
  "direction": "neutral",
  "confidence": 0,
  "evidence_ids": [],
  "missing_reason": "未配置赔率 API，且免费公开源未采集到可验证盘口"
}
```

预测结果：

```json
{
  "lean": "home_or_draw",
  "summary": "主队不败倾向，但 U23 信息不确定性较高",
  "probability_band": {
    "home_win": [0.36, 0.44],
    "draw": [0.25, 0.31],
    "away_win": [0.27, 0.35]
  },
  "scoreline_band": ["1-1", "2-1", "1-0"],
  "drivers": ["squad.availability", "travel.distance"],
  "uncertainties": ["U23 阵容公开度低", "缺少结构化盘口来源"]
}
```

## 动态因子模型

原七维不再作为写死表格，而是作为默认因子包的一部分。系统先生成 match profile，再启用适合本场的因子。

基础因子组：

- `fixture.*`：比赛存在性、时间一致性、赛事归属。
- `form.*`：进攻状态、防守状态、近期波动。
- `squad.*`：伤病、停赛、轮换、首发可信度。
- `motivation.*`：积分压力、淘汰赛压力、友谊赛不确定性。
- `market.*`：赔率变化、盘口流动性、异常资金信号。
- `h2h.*`：历史交锋，但对青年赛和长期跨度自动降权。
- `schedule.*`：休息天数、连续客场、赛程密度。
- `geo.*`：主场优势、旅行距离、时区。
- `weather.*`：天气、场地、极端条件。
- `tactical.*`：风格匹配、强弱项冲突。
- `uncertainty.*`：数据源不足、青年队波动、信息透明度。

比赛 profile 规则：

- U23/青年赛：提高 `squad.*`、`uncertainty.youth_volatility`、`motivation.*`；降低 `h2h.*`。
- 国家队：提高旅行、赛程、阵容征召；降低俱乐部长周期战绩。
- 友谊赛：提高不确定性；降低盘口和战意结论强度。
- 临场两小时内：若有首发，首发权重大幅提高。
- 缺盘口：跳过盘口因子，不硬补中性分。

## 零配置采集策略

默认启用，无需 API key：

- `fixtures_public`：访问公开赛程/比分页面，验证比赛存在性。
- `ddg_search`：免费搜索，返回标题、摘要、URL。
- `official_site`：赛事官网、俱乐部官网可访问性探测。
- `open_meteo`：天气数据，无需密钥。
- `geo_distance`：基于本地球场/城市缓存和距离计算。
- `local_poisson`：沿用本地 Poisson/市场模型能力；有输入就用，没有就跳过。
- `user_supplied`：用户手动提供赔率、伤病、首发、新闻链接。
- `bronze_osint_search`：复用项目已有 bronze storage 中的足球相关情报。

可选增强，有密钥才启用：

- `optional_bing`：`BING_API_KEY` 存在时启用。
- `optional_odds`：`ODDS_API_KEY` 或其他 provider key 存在时启用。
- `optional_fixture_provider`：未来付费足球数据源。

adapter 不允许因为缺少 key 让任务失败。它必须返回 `skipped` 和原因。

## 任务存储

每个 job 落盘，便于审计：

```text
bronze_storage/football_osint/{job_id}/
  request.json
  status.json
  verify.json
  raw/
    fixtures_public.json
    ddg_search.json
    open_meteo.json
  normalized.json
  factors.json
  prediction.json
  report.md
  provenance.json
```

缓存策略：

- 同一比赛验证结果缓存 6 小时。
- 搜索结果缓存 30 分钟。
- 天气缓存到比赛结束后 2 小时。
- 用户手动输入永远优先于自动采集结果。

## 前端重设计

当前 `frontend/src/App.tsx` 是单文件 mock。重设计后拆分为世界球花专用模块：

```text
frontend/src/shijieqiuhua/
  api.ts
  types.ts
  useFootballOsintJob.ts
  components/
    MatchInputPanel.tsx
    MatchRail.tsx
    PredictionProgress.tsx
    PredictionSummary.tsx
    FactorImpactPanel.tsx
    EvidenceRail.tsx
    MissingEvidencePanel.tsx
    ReportViewer.tsx
    AccountPanel.tsx
```

`App.tsx` 只负责布局、账户状态、选中比赛和 job 生命周期。

前端流程：

1. 用户选择 mock 今日赛事或输入新比赛。
2. 未开通用户只看到公开倾向和创建分析的引导。
3. 已开通用户点击“开始 OSINT 分析”。
4. 前端 `POST /api/football/osint/jobs`。
5. `useFootballOsintJob` 每 1.5 秒轮询 `GET /jobs/{job_id}`。
6. UI 展示阶段进度：比赛验证、情报采集、证据归一化、动态因子、报告生成。
7. 完成后展示预测摘要、关键因子、缺失证据、证据链和 Markdown 报告。

UI 不再展示固定七维评分表。默认展示本场影响最大的 5-8 个启用因子，并单独展示跳过的高价值因子。

## 前端 API 类型

```ts
export type OsintJobStatus = 'queued' | 'running' | 'needs_review' | 'completed' | 'failed'

export interface FootballOsintJob {
  job_id: string
  status: OsintJobStatus
  phase: 'verify' | 'collect' | 'normalize' | 'score' | 'report' | 'done'
  progress: number
  match: OsintMatch
  sources: OsintSourceStatus[]
  evidence: EvidenceItem[]
  factors: FactorImpact[]
  prediction: PredictionResult | null
  confidence: ConfidenceRating | null
  report_markdown: string
  error?: string
}
```

## 前端视觉结构

主屏保持三栏：

- 左栏：比赛列表、输入比赛、历史 job。
- 中栏：比赛概览、预测摘要、动态因子影响。
- 右栏：账户权限、证据链、缺失证据、报告下载。

移动端改成 tabs：

- 比赛
- 分析
- 证据
- 报告
- 账号

## 错误和降级

- 比赛无法验证：返回 `needs_review`，前端提示用户修改队名/时间/赛事。
- 部分 adapter 失败：job 继续，source 状态显示 `failed`。
- 缺 API key：source 状态显示 `skipped`，不算错误。
- 数据太少：返回 L4 或 L5，并列出缺失证据。
- 后端 job 异常：保留已采集证据和错误消息，前端可重试。

## 测试策略

后端测试：

- 无 API key 时 job 能完成到 L4/L5，不抛异常。
- 用户提供赔率时 `user_supplied` 因子启用。
- U23 profile 会提高青年波动和阵容权重。
- 缺盘口时 `market.liquidity` 返回 `missing_reason`。
- report.md 包含预测、证据、缺失项和免责声明。

前端测试：

- 未开通用户不能创建完整分析 job。
- 已开通用户创建 job 后显示进度。
- completed job 显示预测摘要、因子、证据和报告。
- skipped source 显示为“未启用”而不是错误。
- failed job 显示错误和重试入口。

## 实施顺序

1. 新建后端 `football_osint` 模型、存储和 mock pipeline。
2. 新增 job API，并接入 `backend/main.py`。
3. 实现动态因子注册表、profile 和基础 scoring。
4. 接入零配置 adapters：user_supplied、local_poisson、open_meteo、ddg_search、fixtures_public。
5. 实现 Markdown 报告。
6. 前端新增 `api.ts`、job hook 和类型。
7. 拆分 `App.tsx`，做进度、因子、证据、报告 UI。
8. 补测试并保证 `npm run build`、`npm test`、`pytest` 通过。
9. 部署到足球服务器，验证 `http://221.239.50.142:31080/`。

## 非目标

- 第一版不做付费数据源强依赖。
- 第一版不强制配置 Bing 或 odds API。
- 第一版不承诺投注建议，只给研究型预测和风险声明。
- 第一版不删除旧 OSINT 前端文件，只继续保持世界球花入口。

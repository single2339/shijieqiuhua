---
title: 世界球花 PRD v1
version: 1.0.1
status: code-aligned
date: 2026-06-27
authors:
  - 产品负责人（你）
supersedes:
  - docs/superpowers/specs/2026-06-11-shijieqiuhua-frontend-design.md (前端设计被本文档覆盖更新)
  - docs/superpowers/specs/2026-06-11-shijieqiuhua-osint-football-redesign.md (后端设计被本文档覆盖更新)
trace_root: docs/superpowers/specs/2026-06-12-prd-redo/
---

# 世界球花 PRD v1

> **一句话产品定义**：世界球花是一个"带证据链的足球研判工作台"——给懂球但不擅长读数据的用户，提供赛前判断、可追问的维度分析和证据强弱标注，**不输出投注建议**。

---

## 0. 阅读指引

| 角色 | 必读 | 选读 |
|---|---|---|
| 产品负责人 | §1, §2, §3, §10, §11 | 全部 |
| 工程实现 | §3, §4, §5, §6, §7, §8 | §10 |
| 设计 | §3, §4, §6, §9 | §1 |
| 法务/合规 | §1.4, §2.3, §10 | §6 |
| 运维 | §7, §8 | §3 |

完整推导过程在 `docs/superpowers/specs/2026-06-12-prd-redo/` 目录的 10 份阶段文档中（01-10），本 PRD 是终态；如有歧义以本 PRD 为准。

---

## 1. 背景与定位

### 1.1 业务情境

`shijieqiuhua` 子项目从 OSINT 网络分支而来，目标是为"懂球但不擅长读数据"的用户提供赛前研判工作台。当前代码已形成可运行闭环：React 19 + Vite 前端、FastAPI 后端、SQLite 鉴权/权益、`backend/football_osint/` 研判流水线、公开赛程和公开战绩、付费码解锁完整研判。生产轻量入口为 `backend/app_football.py`；`backend/main.py` 仍是 OSINT Network 总入口，也挂载足球路由但不负责足球预热任务。

本次 PRD 重梳触发于 commit `8c09e12`：前端从"多组件 + 访问控制"压回"单页 mock"，后端出现哈希伪造的"近期状态信号"和被当成证据的"采集计划"占位项。已通过修复 PR 解决 SRF / 资源耗尽 / 内存泄漏 / 伪造证据等技术债，但暴露出**产品方向、范围与交付优先级未对齐**的根本问题。

### 1.2 核心定位（一句话）

> **带证据链的足球研判工作台**：默认主判断 + 可追问的 6 个维度 + 强/弱/不足三级证据标注；缺数据时显式声明，绝不编造倾向。

### 1.3 目标用户

| ID | 画像 | v1 是否优化 |
|---|---|---|
| **U1 核心**：懂球的研判型球迷，看球 5+ 年 | 主用户，承载 USP | ✅ |
| **U2 边缘**：偶尔看大赛 | 接受门槛拒绝 | ❌ |
| **U3 反例**：盘口/投注用户 | 红线 R1 明确不服务 | ❌ |
| **U4 邀请发起人**：已付费 U1 的二度网络 | 增长杠杆 | ✅ |

### 1.4 红线（不可妥协）

| 红线 | 含义 |
|---|---|
| **R1** | 不输出投注建议；文案使用"倾向、压力、风险、证据强弱" |
| **R2** | 不在缺证据时编造倾向；缺数据 → 显式"信息不足" |
| **R3** | 不绕过付费；客户端"成功"提示不开通权益；只信服务端校验 |
| **R4** | 不在前端硬编码秘密 |
| **R5** | 邀请关系仅用于注册准入和增长统计，不影响预测结论 |

---

## 2. 范围与版本规划

### 2.1 v1 范围（本 PRD 主体）

| 模块 | 内容 |
|---|---|
| 用户与权限 | 邀请码注册、用户名密码登录、付费码兑换、3 级权限 |
| 核心研判 | 默认主判断 + 自由提问 + 6 维快捷追问 + 信息不足显式 |
| 证据系统 | 强/弱/不足三级 + 来源回溯 + "缺什么"清单 |
| 后端 OSINT | `football_osint` 模块化流水线；零配置采集；动态因子注册表；按需缓存 + 定时预热 |
| Web 工作台 | Landing + 三栏研判台；赛程轮询；问答、证据、因子、账号与管理面板 |
| 运维 | `app_football.py` 轻量服务 + warm cache + track record backfill；HTTPS / 备份 / runbook 按部署环境补齐 |

### 2.2 v1 范围外（延后）

| 项 | 时点 | 原因 |
|---|---|---|
| 微信小程序 4 Tab | v1.5 | 单人节奏 |
| 真实微信支付接入 | v1.5 | 商户号申请 |
| 订阅消息 / 跨端账号合并 / 分享海报 | v1.5 | 依赖小程序 |
| 手机号登录 | v1.5 | 短信服务商待选 |
| 赛后回看与对照 | v2 | 工程量大 |
| 多场对比 | v2 | 非核心 |
| 实时滚球 / 真实赔率盘口 | 不规划 | 与 R1 冲突 |

### 2.3 商业模式（v1 锁定）

- **访问门**：邀请码注册 + 付费码兑换权益
- **不接微信支付**：v1 仅"付费码"通道，运营手动发码
- **3 级权限**：访客 / 已注册未付费 / 已付费
- **邀请码发放**：当前实现为 admin 生成邀请码；已付费用户自助生成邀请码延后

### 2.4 成功标准

| 时点 | 标准 |
|---|---|
| v1 上线 | 已付费用户从打开赛事到看到主判断 < 5s（缓存命中）或可接受的同步等待；缺证据时明示"信息不足"；邀请-注册-兑换链路端到端通跑 |
| v1 上线 + 4 周 | 5 人真实用户访谈完成；F1 ≥ 0.85 校验集就绪；DeepSeek 月成本 < ¥500 |
| v1.5 时 | 微信小程序壳 + 跨端账号合并跑通 |
| v2 时 | 已付费用户 7 天留存 ≥ 30% |

---

## 3. 用户角色与权限

### 3.1 角色定义

| 角色 | 标识 | 进入路径 |
|---|---|---|
| 访客 | 无 cookie | 直接访问 |
| 已注册未付费 | 持有 access_token；entitlement 表无 active full_analysis 记录 | 邀请码注册成功 |
| 已付费 | entitlement(type='full_analysis', expires_at>now()) | 付费码兑换成功（默认 30 天权益） |
| admin | `users.role='admin'`；CLI 另可使用 `.env` 中的管理凭据/本机环境 | 管理员账号或服务器本地 CLI |

### 3.2 权限矩阵

| 行为 | 访客 | 已注册未付费 | 已付费 | admin |
|---|---|---|---|---|
| 看赛事列表 | ✅ | ✅ | ✅ | ✅ |
| 看简单胜负倾向（公开摘要） | ✅ | ✅ | ✅ | ✅ |
| 看默认主判断完整版 | ❌ | ❌ | ✅ | — |
| 看完整证据列表 | ❌ | ❌ | ✅ | — |
| 6 维快捷追问 | ❌ | ❌ | ✅ | — |
| 自由提问 | ❌ | ❌ | ✅ | — |
| 提交补充 URL/笔记 | ❌ | ❌ | ✅（后端字段支持，前端入口未完整暴露） | — |
| 注册新账号 | ✅（持邀请码） | — | — | — |
| 兑换付费码 | ❌ | ✅ | ❌（已持有，会被 A4 拒绝） | — |
| 生成邀请码 | ❌ | ❌ | ❌（延后） | ✅ |
| 批发邀请/付费码 | ❌ | ❌ | ❌ | ✅ |
| 调阈值 / 封禁用户 | ❌ | ❌ | ❌ | ✅ |

### 3.3 服务端权限边界

- 公开接口当前仅包括 `GET /api/football/osint/fixtures`、`GET /api/football/osint/track-record` 以及登录/注册/管理路由自身的公开部分。
- `/api/football/osint/jobs`、`/answer`、`/predict-sync`、`/jobs/{id}`、`/jobs/{id}/report.md` 均在路由内调用 `_require_paid()`，要求登录且拥有有效 `full_analysis` 权益。
- `backend/main.py` 的全局中间件仍把 `/api/football/` 作为公开前缀放行，但足球路由自身会再次做付费校验；不能依赖前端 AuthGate 的"隐藏"做权限。

---

## 4. 核心研判系统

### 4.1 默认主判断契约

```ts
interface PredictionResult {
  lean: 'home' | 'away' | 'draw' | 'home_or_draw' | 'away_or_draw' | 'info_insufficient'
  summary: string                  // 文案约束 R1
  probability_band: { home_win: [number, number]; draw: [number, number]; away_win: [number, number] }
  scoreline_band: string[]
  drivers: string[]                // factor_id 列表
  uncertainties: string[]
}

interface ConfidenceRating {
  level: 'L1' | 'L2' | 'L3' | 'L4'
  reason: string
}
```

### 4.2 信息不足判定（R2）

`form` / `h2h` / `squad` 三组基本面因子中，**没有任何一个**同时满足「enabled = true 且 |impact| > 0.005」→ `lean = 'info_insufficient'`。

这三组因子的取值来自懂球帝赛前分析页解析（命中即 enabled），缺懂球帝时由国内媒体近期战绩信号兜底（`form` 组）。enabled 只代表抓到了原始文本，不代表正则真的从里面解出了分数——所以额外要求 impact 非零，否则"页面格式我们没适配"会被误判成"有真实信号但恰好是中性"。

判定逻辑硬编码在 `prediction.py::predict()`，未走 `system_config` 阈值表，目前不可通过 admin CLI 调整。

UI 表现（UC-08）：
- **不显示**胜负箭头
- 显示大字"信息不足" + confidence_level（多半 L4）
- 显示 `missing_data` 清单（最多 5 条），来自 disabled 因子的 missing_reason
- 已付费用户：提供"我有补充信息"入口

### 4.3 6 维快捷追问（模板路径）

| 维度 | 因子选用 |
|---|---|
| 半场 (first_half) | form / motivation / tactical |
| 红黄牌 (cards) | referee / tactical / motivation |
| 角球 (corners) | form / tactical / weather / referee |
| 进球数 (goals) | form / tactical / weather |
| 球员 (player) | squad / form |
| 风险 (risk) | uncertainty / squad / market |

每维度以预设问题文本进入统一问答接口：前端点击 chip 后调用 `/api/football/osint/answer`，同时并发调用 `/api/football/osint/jobs` 取得完整 job 供报告视图展示。后端优先命中 `warm_cache`；缓存未命中时会按需运行完整流水线并缓存结果。LLM 综合报告可用时优先使用；不可用时降级到 `osint_qa` 模板 / 短问答 / prediction summary。

**重要**：6 维快捷追问仍是预热对象。`warm_cache.py` 会在 T-5h 和 T-2h 对 6 个预设问题做 force refresh，保证临场前有共享缓存；但当前实现不是"仅读缓存"，缓存缺失不会返回 503，而是实时计算。

### 4.4 自由提问（LLM 路径 + 降级）

接口：`POST /api/football/osint/answer`（已实现）

流程：
1. `_is_match_related()` 判定（目标 F1 ≥ 0.85，校验集 v1 上线后构建）
2. 不相关 → `{ related: false, answer: '问题与比赛无关' }`
3. 相关 → 进入 `_ANSWER_SEMAPHORE`（默认 4 并发）→ `warm_cache.cache_or_compute()`
4. cache miss 时在后台线程运行 `pipeline.run_prediction_sync()`，完成采集、因子、预测、置信度、情报循环和 Markdown 报告
5. `_answer_from_job()` 优先调用 `analysis.match_report.synthesize()` 生成综合回答
6. 若综合回答不可用，则降级到 `analysis.osint_qa.analyze()`；仍无维度命中时再尝试 `analysis.llm_qa.answer_question()`；最终降级到 prediction summary

### 4.5 证据系统

`OsintEvidence` 字段（已实现）：
- `id, source, source_type, url, observed_at, claim, topic, side, confidence, freshness, raw_excerpt`

三级阈值：
- **强证据** ≥ 0.50
- **弱信号** [0.25, 0.50)
- **样本不足** < 0.25

当前由 `ReportView` 的证据 tab 展示，每条带：来源标签、可点击 URL、observed_at、claim 摘要、置信度可视化；证据强弱排序逻辑在 `frontend/src/shijieqiuhua/components/evidence.ts`。

### 4.6 文案规则

允许：倾向 / 压力偏高 / 压力偏低 / 风险 / 证据强弱 / 信息不足
**禁词清单**（文案审计目标；当前代码未接 CI 自动审计）：
- 必胜、稳赢、保赢、稳红
- 推荐、推单、跟单、内部消息
- 大胆、稳胆、稳串、专家、料、爆料
- 投注、押注、买注、单关、串关、过关

---

## 5. 后端架构

### 5.1 模块拆分（按当前代码）

实际拆分结果与本节早期草案不同（搜索/赛程信源的选型在实现中变了，详见下方真实目录）：

```
backend/football_osint/
  __init__.py
  models.py
  routes.py               # API 路由、付费门控、并发限制
  pipeline.py             # 编排：fixture → 信源 → 证据 → 因子打分 → 预测
  storage.py              # bronze 落盘抽象
  factor_registry.py      # 动态因子注册
  evidence.py             # 证据构建/校验
  cache.py                # 线程安全 TTL 缓存
  sources.py              # FootballSourceTemplate 定义（adapter → URL 模板）
  warm_cache.py           # match+question 统一缓存、in-flight 去重、T-5h/T-2h 预热
  adapters/
    __init__.py
    base.py
    dongqiudi.py            # 懂球帝候选 URL
    dongqiudi_analysis.py   # 懂球帝赛前分析页解析
    dongqiudi_schedule.py   # 懂球帝赛程对齐 + 球队名归一化
    football_data_schedule.py  # football-data.org 赛程兜底
    web_search.py           # 搜索适配器；英文/中文搜索由 pipeline 编排
    rss_feed.py              # hupu/dongqiudi/weibo RSSHub 聚合
    name_translation.py
    open_meteo.py
    lightpanda.py
    url_safety.py
    user_supplied.py
  analysis/
    __init__.py
    confidence.py
    prediction.py
    intelligence.py
    match_report.py
    report.py
    osint_qa.py
    llm_qa.py
```

未落地/已废弃的草案项：`fixtures_public.py`、`official_site.py`、`geo_distance.py`、`local_poisson.py`、`optional_bing.py`、`optional_odds.py`、`profiling.py`、`factor_scoring.py` ——这些规划文件名最终没有对应实现，对应能力分散合并进了上面列出的实际文件。

服务入口：
- `backend/app_football.py`：世界球花生产/轻量入口，挂载 auth/admin/billing/football 路由，启动 `warm_cache.warm_loop()` 和 `track_record.backfill_loop()`。
- `backend/main.py`：OSINT Network 总入口，挂载足球路由供一体化运行；后台采集由 `OSINT_ROLE` 控制，但不启动足球 warm loop。

### 5.2 比赛 profile 规则

- U23 / 青年 → 提高 `squad.*`、`uncertainty.youth_volatility`；降低 `h2h.*`
- 国家队 → 提高旅行、赛程、阵容
- 友谊赛 → 提高不确定性；降低盘口/战意权重
- 临场 ≤ 2h → 首发权重大幅提高
- 缺盘口 → 跳过盘口因子，**不补中性默认值**（R2）

### 5.3 缓存策略

**预设问题（6 维快捷追问）采用定时预热 + 按需兜底模式：**

- **T-5h**：比赛开赛前 5 小时，后台自动运行完整 OSINT 流水线（采集 → 证据 → 因子打分 → 预测 → LLM 综合研判），结果写入内存缓存
- **T-2h**：比赛开赛前 2 小时，再次自动运行（此时首发阵容通常已公布，数据密度更高），覆盖更新缓存
- **T-5h 到 T-2h 之间**：所有用户看到的都是 T-5h 的缓存结果
- **T-2h 到开赛**：所有用户看到的都是 T-2h 的缓存结果
- **开赛前 T-5h 之前或缓存未命中**：`/jobs`、`/answer`、`/predict-sync` 会调用 `cache_or_compute()` 按需实时运行；同一 key 的并发请求通过 `_inflight` 去重，只有一个 runner 真正计算，其余等待缓存结果
- **缓存 key**：`home_team|away_team|kickoff_at|question`；预设问题使用原文，非预设问题使用问题文本 sha1 前 16 位
- **缓存容量**：内存 LRU，默认 `FOOTBALL_OSINT_CACHE_MAX=512`，最小 64

**自由提问（非预设问题）**同样进入统一缓存。完全相同的 match+question 会复用缓存，不同措辞会形成新的 free-text key。

**子组件缓存（搜索/赛程/天气等 adapter 级别）：**

| 类别 | TTL | 说明 |
|---|---|---|
| 赛程（football-data.org） | 由 adapter / 请求控制 | warm loop 每 15 min 重扫未来 3 天，前端每 60s 拉取 fixtures |
| 搜索/抓取结果 | adapter 内存缓存 | 英文高信号域搜索 + 中文媒体搜索 |
| 天气 | 1 hour | Open-Meteo |
| 用户输入（笔记、URL） | 跟随 match+question 结果缓存 | 后端请求模型支持 `user_supplied.notes` / URL，前端尚未完整暴露 |

### 5.4 落盘约定（bronze）

每 job 落盘到 `bronze_storage/football_osint/{job_id}/`：

| 文件 | v1 必须 | 内容 |
|---|---|---|
| `request.json` | ✅ | 入参 |
| `status.json` | ✅ | 当前状态（FootballOsintJob 序列化） |
| `report.md` | ✅ | Markdown 报告 |
| `provenance.json` | ✅ | adapter 调用历史 |
| `verify.json` | ❌（v1.1） | fixture 验证细节 |
| `raw/*` | ❌（v1.1） | 各 adapter 原始返回 |
| `normalized.json` | ❌（v1.1） | 标准化中间产物 |
| `factors.json` | ❌（v1.1） | factor_registry 输出 |
| `prediction.json` | ❌（v1.1） | 预测明细 |

### 5.5 API 契约

| 路径 | 方法 | 用途 | 公开度 | 当前状态 |
|---|---|---|---|---|
| `/api/auth/register` | POST | 邀请码注册，返回 token + user | 公开 | 已实现 |
| `/api/auth/login` | POST | 用户名 + 密码登录，返回 token + user | 公开 | 已实现 |
| `/api/auth/logout` | POST | 注销当前 refresh session | 已登录 | 已实现 |
| `/api/auth/me` | GET | 拉当前用户 + entitlements | 已登录 | 已实现 |
| `/api/billing/redeem` | POST | 付费码兑换 | 已注册 | 已实现 |
| `/api/admin/invite-codes` | GET/POST | 管理员生成/查看邀请码 | admin | 已实现 |
| `/api/admin/payment-codes` | GET/POST | 管理员生成/查看付费码 | admin | 已实现 |
| `/api/admin/users` | GET | 管理员查看用户 | admin | 已实现 |
| `/api/football/osint/fixtures` | GET | 公开赛事列表（赛程/比分/状态） | 公开 | 已实现 |
| `/api/football/osint/track-record` | GET | 公开战绩统计 | 公开 | 已实现 |
| `/api/football/osint/jobs` | POST | 运行/读取 match+question job；当前同步返回 completed job | 已付费 | 已实现 |
| `/api/football/osint/jobs/{id}` | GET | 从内存缓存按 job_id 取任务 | 已付费 | 已实现 |
| `/api/football/osint/jobs/{id}/report.md` | GET | Markdown 报告 | 已付费 | 已实现 |
| `/api/football/osint/predict-sync` | POST | 同步预测（测试/兼容用） | 已付费 | 已实现 |
| `/api/football/osint/answer` | POST | 比赛问答；预设和自由问题共用 | 已付费 | 已实现 |
| `/api/auth/otp/send` | POST | 发邮箱 OTP | 公开 | 未实现，延后 |
| `/api/invitation/create` | POST | 已付费用户生成邀请码 | 已付费 | 未实现，延后 |
| `/api/invitation/list` | GET | 我生成的邀请码列表 | 已付费 | 未实现，延后 |
| `/api/matches` | GET | 公开赛事列表旧草案路径 | 公开 | 废弃，用 `/fixtures` |
| `/api/football/osint/match/{id}/dashboard` | GET | 比赛详情旧草案路径 | 公开 | 未实现 |
| `/api/football/osint/dimension` | POST | 6 维快捷追问旧草案路径 | 已付费 | 废弃，并入 `/answer` |

### 5.6 错误响应

当前只有 billing 域稳定返回结构化错误码；auth / football 路由多数返回 FastAPI `detail: string`。前端 `readError()` 会优先读取 `detail.message_zh`，其次读取 `detail.error_code`，最后回退到字符串。

```json
{
  "detail": {
    "error_code": "E_CODE_USED",
    "message_zh": "该付费码已被使用"
  }
}
```

已实现清单：
- `E_CODE_INVALID` / `E_CODE_USED` / `E_CODE_EXPIRED` / `E_ENTITLEMENT_DUPLICATE`
- `E_DB_TRANSIENT`

目标清单（延后统一）：
- `E_INVITE_INVALID` / `E_INVITE_USED` / `E_INVITE_EXPIRED`
- `E_AUTH_FAILED` / `E_AUTH_LOCKED`
- `E_EMAIL_TAKEN` / `E_FORBIDDEN` / `E_QUOTA_EXCEEDED`
- `E_LLM_DOWN`

---

## 6. 数据模型

### 6.1 SQLite 表（auth + billing 域，按当前代码）

当前 SQLite 位于 `bronze_storage/_auth.db`。表名沿用早期 auth 实现：`users`、`registration_codes`、`sessions`、`user_activities`、`login_attempts`，而不是草案中的 `user` / `identity` / `invitation`。billing 和公开战绩通过 `sql/003_billing_and_entitlements.sql`、`sql/004_prediction_track_record.sql` 追加。

```sql
-- users
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',         -- admin | user
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_login_at TEXT NOT NULL DEFAULT ''
);

-- registration_codes (邀请码)
CREATE TABLE registration_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  created_by INTEGER NOT NULL REFERENCES users(id),
  max_uses INTEGER NOT NULL DEFAULT 1,
  current_uses INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL DEFAULT ''
);

-- sessions (refresh token jti)
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  token_jti TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  ip_address TEXT NOT NULL DEFAULT '',
  user_agent TEXT NOT NULL DEFAULT ''
);

-- activation_code (付费码)
CREATE TABLE activation_code (
  code TEXT PRIMARY KEY,                     -- [A-Z2-9]{16}
  status TEXT NOT NULL,                      -- unused | used
  granted_to_user_id INTEGER REFERENCES users(id),
  redeemed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  validity_days_after_redeem INTEGER,        -- NULL = permanent entitlement
  note TEXT NOT NULL DEFAULT ''
);

-- entitlement
CREATE TABLE entitlement (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  type TEXT NOT NULL,                        -- full_analysis
  granted_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT,                           -- NULL = permanent
  source TEXT NOT NULL,                      -- code:<code> | admin:<admin_id>
  UNIQUE(user_id, type)                      -- v1 强制：单 user 单类型
);

-- audit_log
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  user_id INTEGER REFERENCES users(id),
  actor TEXT NOT NULL,                       -- user | admin | system
  event TEXT NOT NULL,                       -- registration.consumed | billing.code_redeemed | ...
  payload_json TEXT NOT NULL DEFAULT '{}',
  ip TEXT,
  user_agent TEXT
);

-- system_config (admin CLI 可调)
CREATE TABLE system_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_by TEXT
);

CREATE TABLE prediction_record (
  job_id TEXT PRIMARY KEY,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  kickoff_at TEXT NOT NULL DEFAULT '',
  competition TEXT NOT NULL DEFAULT '',
  predicted_lean TEXT NOT NULL,
  predicted_scoreline_band TEXT NOT NULL DEFAULT '[]',
  actual_home_score INTEGER,
  actual_away_score INTEGER,
  actual_outcome TEXT,
  lean_correct INTEGER,
  scoreline_hit INTEGER,
  settled_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 6.2 Bronze JSON（OSINT 域）

仍采用文件系统：`bronze_storage/football_osint/{job_id}/*.json`。当前 GET by job_id 优先查 `warm_cache` 内存索引 `_by_job_id`；`_index.json` 尚未实现。

### 6.3 数据约束

- 付费码字符集：`ABCDEFGHJKMNPQRSTUVWXYZ23456789`，长度 16（去除易混 0/O/1/I/L）
- 邀请码由 admin API 生成，当前字符集为 `A-Z0-9`，默认长度 16
- email 可选；当前只校验基本邮箱格式，未强制小写，也未禁止 `+` 别名
- 用户名：2-50 字符；密码：6-128 字符
- 默认有效期：邀请码默认 30 天 / 付费码兑换窗口默认 90 天 / 兑换后权益默认 30 天

---

## 7. 非功能需求（NFR）

| ID | 要求 | 验收 |
|---|---|---|
| NFR-1 | 已付费看主判断：缓存命中 < 200ms；缓存未命中为同步等待，需单独观测 | 上线前 5 比赛实测 + 上线后埋点 P95 |
| NFR-2 | OSINT pipeline P95 < 30s（无 lp-fetch-md），P99 < 60s | 自动化测试 + 上线埋点（当前未完整接埋点） |
| NFR-3 | 月可用性 99% | 自建 uptime 监控 |
| NFR-4 | 单进程内存 < 1.8GB（systemd MemoryMax 强制） | systemd + 监控 |
| NFR-5 | 备份每日；保留 7 天；季度恢复演练 | rsync cron + 文档 |
| NFR-6 | 全 API HTTPS（含 nginx + HSTS） | curl -I |
| NFR-7 | 速率限制：单 IP 20 写/min（已实现） | 自动化测试 |
| NFR-8 | URL 抓取经白名单 + 公网 DNS 检查（已实现） | NEG-2/3 测试 |

---

## 8. 运维需求

| ID | 项 | 说明 |
|---|---|---|
| OPS-1 | systemd unit + MemoryMax=1.8G + 自动重启 | 世界球花建议跑 `backend.app_football:app`；总平台可跑 `backend.main:app` |
| OPS-2 | runbook 简版：DeepSeek 503 / 数据源全挂 / bronze 写失败 | `docs/runbook-v1.md` |
| OPS-3 | 故障 5 分钟定位：日志按 `request_id` 索引 | 日志查询脚本 |
| OPS-4 | admin CLI（详见 §8.1） | `python -m backend.admin` |
| OPS-5 | 采集触发：`app_football.py` 启动 warm_loop，按赛程自动在 T-5h / T-2h 触发；所有问题均可按需实时触发 | warm_cache.py |
| OPS-6 | 缓存策略：预设问题 T-5h + T-2h 定时预热；缓存未命中按需计算并写入 LRU | warm_cache + routes 门控 |
| OPS-7 | 错误码命名 + 文案分离 | 错误码字典 |
| OPS-8 | 数据库唯一约束（见 §6.1） | migration 脚本 |

### 8.1 admin CLI 命令

```bash
# 邀请/付费码批发
python -m backend.admin invite_codes --count N [--validity-days 30] [--output codes.csv]
python -m backend.admin payment_codes --count N [--validity-days 90] [--note "..."]

# 用户管理
python -m backend.admin list_users [--paid] [--limit 100]
python -m backend.admin ban_user --user-id u_xxx --reason "..."

# 配置（写入 system_config；当前信息不足判定仍由 prediction.py 硬编码，未读取 system_config）
python -m backend.admin set_threshold --key <key> --value <value>
python -m backend.admin list_config

# 列表
python -m backend.admin list_codes --type invite|payment [--status unused|used]
```

鉴权：`ADMIN_TOKEN` 在 `.env` 中，CLI 仅服务器本地能跑（依赖文件系统读 .env）。

---

## 9. 前端设计

### 9.1 信息架构

Web 当前为 Landing + 三栏研判台：

```
┌─────────────┬───────────────────────────┬─────────────────────┐
│             │                           │                     │
│  赛事队列   │    比赛问答卡             │   账号 / 管理面板   │
│  (左栏)     │    (中栏)                 │   (右栏)            │
│             │                           │                     │
│  联赛       │    联赛/时间/双方         │   问答历史          │
│  时间       │    默认主判断             │   推荐追问          │
│  公开状态   │    (lean+L+风险)          │   研判历史          │
│             │    因子折叠               │   报告生成          │
│             │    ReportView tabs        │                     │
│             │    6 维 chips             │                     │
│             │    自由提问输入           │                     │
└─────────────┴───────────────────────────┴─────────────────────┘
```

移动端（< 768px）：单栏堆叠（赛事队列 → 比赛卡 → Ask），不强求"小程序级"体验。

### 9.2 视觉系统

| 项 | 值 |
|---|---|
| 主色 | 深绿 `#143c2d` |
| 辅色 | 草金 `#c9a86a`（待最终确定） |
| 背景 | 暖纸 `#f7f3e7` |
| 字体（西文） | Satoshi / Geist |
| 字体（中文） | system-ui / 思源黑体 |
| 图标 | `@phosphor-icons/react` |

### 9.3 当前组件清单

| 组件 | 职责 |
|---|---|
| `LandingPage` | 首屏产品说明、公开战绩、价格与注册入口 |
| `AuthScreen` | 登录 / 注册表单 |
| `AuthGate` | 包裹受限内容，触发注册/登录或付费引导 |
| `PaywallModal` | 付费码兑换面板 |
| `AccountPanel` | 账号状态、权益、临时问答历史 |
| `ReportView` | 方向研判、情报循环、因子、证据、确认/推断、替代解释 tabs |
| `PhaseTracker` | 同步等待时的阶段进度动效 |
| `AdminPanel` | 管理面板：用户列表、批量生成邀请码/付费码（仅 admin 角色可见） |

`MatchQuestionCard` 目前是 `frontend/src/App.tsx` 内部的 `MatchCard` 函数组件；`EvidenceStrength` 没有作为独立文件落地，证据强弱逻辑在 `ReportView` / `components/evidence.ts` 中实现。

延后到 v1.1：已付费用户自助 `InvitePanel`、问答历史持久化、导出报告按钮。

延后到 v1.5：`SharePoster`、`SubscribeButton`、跨端账号合并 UI。

### 9.4 文案锚点

- 信息不足时 RQ-E-13："我们没编。这场缺关键数据，等开赛前 2 小时还会再扫一遍。"
- 访客升级提示："使用邀请码注册后继续"
- 已注册未付费提示："开通完整功能后可使用自由提问、6 维追问、完整证据链"

---

## 10. 用例与验收标准

完整 10 个用例 + 53 条 AC + 8 条负向 AC + 8 条 NFR AC + 12 项 DoD + 12 项 Rollout Checklist 见：

- `docs/superpowers/specs/2026-06-12-prd-redo/09-use-cases.md`
- `docs/superpowers/specs/2026-06-12-prd-redo/10-acceptance-criteria.md`

10 个用例（按用户旅程）：

| ID | 名称 |
|---|---|
| UC-01 | 邀请码注册新用户 |
| UC-02 | 用户名密码登录 |
| UC-03 | 付费码兑换权益 |
| UC-04 | 访客查看赛事列表与简单倾向 |
| UC-05 | 已付费查看默认主判断 |
| UC-06 | 6 维快捷追问（统一 `/answer` 路径 + 预热缓存） |
| UC-07 | 自由提问（统一 `/answer` 路径 + 降级） |
| UC-08 | 信息不足展示 |
| UC-09 | 已付费用户邀请新用户（未实现，延后） |
| UC-10 | admin CLI 批发邀请码/付费码 |

---

## 11. 实施计划

### 11.1 工期估算

总工期：**5-6 周**（单人节奏）+ 1 周风险缓冲。

| 周 | 里程碑 |
|---|---|
| W1 | 已完成：DB 模型、admin API/CLI、后端拆分骨架 |
| W2 | 已完成：注册/登录链路、付费码闭环、因子注册表 |
| W3 | 已完成：Landing + 三栏研判台 + AuthGate + ReportView |
| W4 | 已完成：PaywallModal + AdminPanel；待补：已付费用户自助邀请、文案审计自动化 |
| W5 | 待补：备份/HTTPS/systemd/runbook 简版 + 内测 5 人 |
| W6 | 待补：Rollout checklist + 上线灰度 |
| W7（缓冲） | 灰度修复 |

### 11.2 关键路径

```
DB 模型 → admin 管理 → 注册/登录 → 付费码 → AuthGate/PaywallModal → 研判缓存/战绩回填 → Rollout
```

并行：后端拆分（D-1..D-3）/ 视觉调整 / 文案审计 / runbook。

### 11.3 范围扩张防御

- W → M 升级：必须先在 `decisions.md` 追加新决策
- S → M 升级：禁止；只允许"S 完成有富余 → 拣 v1.5 列表项作为 C"
- 新增需求：默认进 v1.1 队列；触发 USP / 红线 / 合规才进 v1

---

## 12. 决策与未解决问题

### 12.1 已锁决策（来自阶段 1-4）

| ID | 决策 |
|---|---|
| Q1 | v1 仅付费码兑换，不接真实支付 |
| Q2 | 访客可见：赛事列表 + 简单倾向 |
| Q3 | 缺证据 → 显式"信息不足"，不编造 |
| Q4 | v1 仅 Web，小程序入 v1.5 |
| Q5 | OSINT 后端按当前代码模块拆分，保留 spec 能力但不强追 10 个原始文件名 |
| Q6 | 6 维 chips 与自由提问共用 `/answer`，优先缓存/综合报告，失败后降级 |
| Q14 默认 | 信息不足阈值：form/h2h/squad 均无 enabled+impact>0.005 的信号（见 §4.2，硬编码非 admin 可调） |
| Q22 | 邀请码 30d / 付费码兑换窗口 90d / 兑换后权益 30d |
| Q12 默认 | 邮件/OTP 登录未实现；当前为用户名密码登录 |
| Q26 默认 | admin CLI 鉴权：ADMIN_TOKEN（.env，仅本地） |

### 12.2 v1 启动开发前必决

| ID | 问题 | 默认建议 |
|---|---|---|
| Q11 | 5-8 名内测用户名单 | 产品负责人定向邀请 |
| Q21 | 用户协议/隐私政策模板 | 通用 termly 模板自改 + 朋友审 |

### 12.3 v1 上线后做（不阻塞 v1）

| 行动 | 时点 |
|---|---|
| 5 人真实用户访谈 | 上线后 4 周内 |
| F1 ≥ 0.85 校验集构建 | 上线后 4 周内 |
| 关键埋点完善 | 上线后 1-2 周 |
| 公开评论正式内容分析 | 上线后 8 周内 |
| 信息不足阈值校准 | 上线后用真实数据 |

---

## 13. 词汇表

| 术语 | 含义 |
|---|---|
| 访客 | 未登录用户 |
| 已注册未付费 | 已通过邀请码注册但 entitlement 表无 full_analysis 记录 |
| 已付费 | 持有 entitlement(type='full_analysis') 的用户 |
| OSINT 流水线 | backend/football_osint/ 下的采集 → 加工 → 分析 → 落盘流程 |
| 主判断 | 默认 lean + confidence_level + 风险数 |
| 信息不足 | lean='info_insufficient'，触发 §4.2 阈值时显示 |
| 因子 | FactorImpact，含 enabled / weight / impact / direction / confidence |
| 证据 | OsintEvidence，含 id / source / url / observed_at / confidence |
| 付费码 | activation_code，兑换后给 user 写 entitlement |
| 邀请码 | registration_code，注册必需，当前由 admin 生成 |
| 权益 | entitlement，控制功能可见性 |
| L1-L4 | 置信等级（L1 最强 L4 最弱），来自 OSINT 通用方法论 |
| profile | match.profile，含 competition_type / data_density / factor_pack |

---

## 14. Traceability（来源追溯）

每个 PRD 决策都能追溯到阶段 1-4 的过程文档：

| 章节 | 主要来源 |
|---|---|
| §1 背景与定位 | 01-problem-framing.md |
| §1.3 目标用户 | 02-stakeholder-analysis.md, 03-value-proposition.md |
| §1.4 红线 | 01-problem-framing.md §4.3 |
| §2 范围与版本 | 01-problem-framing.md §5, 08-moscow.md |
| §3 用户角色与权限 | 04-proto-requirements.md A 类, 09-use-cases.md UC-01..03 |
| §4 核心研判 | 03-value-proposition.md USP, 04-proto-requirements.md B/C 类, 09-use-cases.md UC-04..08 |
| §5 后端架构 | 04-proto-requirements.md D 类 |
| §6 数据模型 | 07-gap-audit.md GAP-A-3 + 04-proto-requirements.md A 类 |
| §7 NFR | 07-gap-audit.md GAP-A-7..10, 10-acceptance-criteria.md NFR |
| §8 运维 | 07-gap-audit.md GAP-A-11..17 |
| §9 前端设计 | 04-proto-requirements.md E 类 + spec frontend-design |
| §10 用例与验收 | 09-use-cases.md, 10-acceptance-criteria.md |
| §11 实施计划 | 08-moscow.md §依赖 + §工期 |
| §12 决策 | decisions.md |

### 14.1 完整需求 ID 索引

107 条 v1 基线需求按 ID 顺序见 `08-moscow.md` 表格。

---

## 15. 开放问题登记册

| ID | 问题 | 影响 | 截止 | 责任人 |
|---|---|---|---|---|
| Q11 | 5-8 名内测名单 | 内测阶段 | v1 启动开发前 | 产品负责人 |
| Q13 | 可信度展示形式（双形式 - L+%） | UI | 阶段 5 设计稿 | 产品负责人 |
| Q14 实际值 | 信息不足阈值 | UC-08 | v1 上线后 4 周（用真实数据校准） | 产品负责人 |
| Q15 | 问答历史持久化（v1 不做） | RQ-B-14 | — | 已默认延后 v1.1 |
| Q16 | 证据 URL 显示形式 | RQ-C-4 | 阶段 5 设计稿 | 产品负责人 |
| Q17 | 未付费"强证据数量"显示 | UC-04 | 阶段 5 设计稿 | 产品负责人 |
| Q18 | bronze 落盘文件子集 | RQ-D-4 | 已默认（4 个核心进 v1） | — |
| Q19 | Web 移动端响应式优先级 | RQ-E-1 | 已默认（基础响应式 v1） | — |
| Q20 | 推荐追问算法 | RQ-E-4 | v1 默认静态 3 条 | — |
| Q23 | runbook 写在哪 | OPS-2 | W5 前 | 产品负责人 |
| Q24 | 监控/告警工具 | NFR-3 | W5 前 | 产品负责人 |
| Q25 | 备份目标 | NFR-5 | W5 前 | 产品负责人 |
| Q27 | 阈值校准用户群 | UC-08 | v1 上线后 | 产品负责人 |

---

## 16. 评审与版本

- **评审人**：产品负责人（自审）+ 5 人内测用户（W5）+ 朋友圈代码审查（建议）
- **版本**：v1.0.0（本文档）
- **后续**：v1.1.0（功能补充）、v1.5.0（小程序）、v2.0.0（赛后回看）

> 本 PRD 是动态文档。任何破坏 §1.4 红线、§2.1 范围、§4.2 信息不足判定 的变更，必须先在 `decisions.md` 追加新决策记录，并显式标注影响范围。

---

## 附录 A：阶段产物索引

```
docs/superpowers/specs/2026-06-12-prd-redo/
├── 01-problem-framing.md         (业务问题框定)
├── 02-stakeholder-analysis.md    (利益相关方分析)
├── 03-value-proposition.md       (价值主张画布)
├── decisions.md                  (锁定决策记录)
├── 04-proto-requirements.md      (草稿需求 86 条)
├── 05-elicitation-plan.md        (需求挖掘计划)
├── 06-elicitation-findings.md    (挖掘 findings, 降级版)
├── 07-gap-audit.md               (缺口审计)
├── 08-moscow.md                  (MoSCoW 优先级 107 条)
├── 09-use-cases.md               (10 个用例)
└── 10-acceptance-criteria.md     (53 AC + 8 NEG + 8 NFR + 12 DoD + 12 Rollout)
```

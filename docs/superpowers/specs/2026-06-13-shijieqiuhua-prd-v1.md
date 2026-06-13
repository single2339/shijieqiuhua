---
title: 世界球花 PRD v1
version: 1.0.0
status: review-ready
date: 2026-06-13
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

`shijieqiuhua` 子项目从 OSINT 网络分支而来，目标是为"懂球但不擅长读数据"的用户提供赛前研判工作台。当前已上线 MVP 骨架（FastAPI + React 19 + DeepSeek，部署在 `221.239.50.142:31080`），但前端组件、访问控制和后端模块化拆分均未完成。

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
| 用户与权限 | 邀请码注册、邮箱登录（含 OTP）、付费码兑换、3 级权限 |
| 核心研判 | 默认主判断 + 自由提问 + 6 维快捷追问 + 信息不足显式 |
| 证据系统 | 强/弱/不足三级 + 来源回溯 + "缺什么"清单 |
| 后端 OSINT | 按 spec 拆分 10 子模块；零配置采集；动态因子注册表 |
| Web 工作台 | 三栏布局；6 个核心组件 |
| 运维 | systemd 单进程 + 备份 + HTTPS + admin CLI + runbook 简版 |

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
- **邀请配额**：每位已付费用户每月 5 个邀请码（admin 可调）

### 2.4 成功标准

| 时点 | 标准 |
|---|---|
| v1 上线 | 已付费用户从打开赛事到看到主判断 < 5s；缺证据时明示"信息不足"；邀请-注册-兑换链路端到端通跑 |
| v1 上线 + 4 周 | 5 人真实用户访谈完成；F1 ≥ 0.85 校验集就绪；DeepSeek 月成本 < ¥500 |
| v1.5 时 | 微信小程序壳 + 跨端账号合并跑通 |
| v2 时 | 已付费用户 7 天留存 ≥ 30% |

---

## 3. 用户角色与权限

### 3.1 角色定义

| 角色 | 标识 | 进入路径 |
|---|---|---|
| 访客 | 无 cookie | 直接访问 |
| 已注册未付费 | 持有 access_token；entitlement 表无 full_analysis 记录 | 邀请码注册成功 |
| 已付费 | entitlement(type='full_analysis', expires_at=null) | 付费码兑换成功 |
| admin | 持有 ADMIN_TOKEN（仅服务器本地 CLI） | 通过 .env 配置 |

### 3.2 权限矩阵

| 行为 | 访客 | 已注册未付费 | 已付费 | admin |
|---|---|---|---|---|
| 看赛事列表 | ✅ | ✅ | ✅ | ✅ |
| 看简单胜负倾向（公开摘要） | ✅ | ✅ | ✅ | ✅ |
| 看默认主判断完整版 | ❌ | ❌ | ✅ | — |
| 看完整证据列表 | ❌ | ❌ | ✅ | — |
| 6 维快捷追问 | ❌ | ❌ | ✅ | — |
| 自由提问 | ❌ | ❌ | ✅ | — |
| 提交补充 URL/笔记 | ❌ | ❌ | ✅ | — |
| 注册新账号 | ✅（持邀请码） | — | — | — |
| 兑换付费码 | ❌ | ✅ | ❌（已持有，会被 A4 拒绝） | — |
| 生成邀请码 | ❌ | ❌ | ✅ | ✅ |
| 批发邀请/付费码 | ❌ | ❌ | ❌ | ✅ |
| 调阈值 / 封禁用户 | ❌ | ❌ | ❌ | ✅ |

### 3.3 服务端权限边界

- 访客的 `GET /api/football/osint/match/{id}/dashboard` 必须经服务端**字段过滤**，仅返回 match 元信息和 `public_lean`（不返回 evidence/factors/reasons）。
- 不依赖前端 AuthGate 的"隐藏"做权限。

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

满足以下**任一**条件 → `lean = 'info_insufficient'`：

1. 启用因子数 ≤ 1
2. 所有启用因子的 confidence 均值 < 0.30

阈值可在 admin CLI 调（`set_threshold --key info_insufficient_factor_min --value 1`）。

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

每维度走"加载 match + factors + evidence → 模板填充 → 返回 FootballOsintAnswer"，**不调 LLM**，目标响应时间 < 1s。

### 4.4 自由提问（LLM 路径 + 降级）

接口：`POST /api/football/osint/answer`（已实现）

流程：
1. `_is_match_related()` 判定（目标 F1 ≥ 0.85，校验集 v1 上线后构建）
2. 不相关 → `{ related: false, answer: '问题与比赛无关' }`
3. 相关 → 进入 `_ANSWER_SEMAPHORE`（默认 4 并发）→ 调 DeepSeek
4. Prompt 模板**显式列出当前比赛 evidence 列表 + 要求引用 [ev_xxx]**
5. LLM 返回 → 后端校验 reasons 中所有 `[ev_xxx]` 必须存在于上下文
6. 引用合法性失败/超时/限流 → 降级到模板路径（dimension='risk' 兜底）+ 文本前缀"详细解读暂不可用"

### 4.5 证据系统

`OsintEvidence` 字段（已实现）：
- `id, source, source_type, url, observed_at, claim, topic, side, confidence, freshness, raw_excerpt`

三级阈值：
- **强证据** ≥ 0.50
- **弱信号** [0.25, 0.50)
- **样本不足** < 0.25

EvidenceStrength 组件三栏展示，每条带：来源标签、可点击 URL（图标式）、observed_at、claim 摘要、置信度可视化。

### 4.6 文案规则

允许：倾向 / 压力偏高 / 压力偏低 / 风险 / 证据强弱 / 信息不足
**禁词清单**（CI 自动审计）：
- 必胜、稳赢、保赢、稳红
- 推荐、推单、跟单、内部消息
- 大胆、稳胆、稳串、专家、料、爆料
- 投注、押注、买注、单关、串关、过关

---

## 5. 后端架构

### 5.1 模块拆分（按 spec 完整执行）

```
backend/football_osint/
  __init__.py
  models.py              # 已存在，需对齐契约
  routes.py              # 已存在，已加 LRU+TTL+Sema
  pipeline.py            # 已存在 685 行 → 拆出后约 350 行
  storage.py             # 新增：bronze 落盘抽象
  factor_registry.py     # 新增：动态因子注册
  evidence.py            # 新增：证据构建/校验
  adapters/
    __init__.py
    base.py
    fixtures_public.py
    ddg_search.py
    official_site.py
    open_meteo.py
    geo_distance.py
    local_poisson.py
    user_supplied.py
    optional_bing.py     # 缺密钥 → skipped
    optional_odds.py     # 缺密钥 → skipped
  analysis/
    __init__.py
    profiling.py
    factor_scoring.py
    confidence.py
    prediction.py
    report.py
```

### 5.2 比赛 profile 规则

- U23 / 青年 → 提高 `squad.*`、`uncertainty.youth_volatility`；降低 `h2h.*`
- 国家队 → 提高旅行、赛程、阵容
- 友谊赛 → 提高不确定性；降低盘口/战意权重
- 临场 ≤ 2h → 首发权重大幅提高
- 缺盘口 → 跳过盘口因子，**不补中性默认值**（R2）

### 5.3 缓存策略

| 类别 | TTL | 触发失效 |
|---|---|---|
| 比赛验证（fixtures_public） | 6h | 开赛前 ≤ 6h 强制重算 |
| 搜索/抓取结果 | 30 min | 开赛前 ≤ 6h 强制重算 |
| 天气 | 到比赛结束后 2h | — |
| 用户输入（笔记、URL） | 永不缓存 | 永远优先 |

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

| 路径 | 方法 | 用途 | 公开度 |
|---|---|---|---|
| `/api/auth/register` | POST | 邀请码注册 | 公开 |
| `/api/auth/otp/send` | POST | 发邮箱 OTP | 公开 |
| `/api/auth/login` | POST | 邮箱 + OTP 登录 | 公开 |
| `/api/auth/logout` | POST | 注销当前 session | 已登录 |
| `/api/auth/me` | GET | 拉当前用户 + entitlements | 已登录 |
| `/api/billing/redeem` | POST | 付费码兑换 | 已注册 |
| `/api/invitation/create` | POST | 已付费用户生成邀请 | 已付费 |
| `/api/invitation/list` | GET | 我生成的邀请码列表 | 已付费 |
| `/api/matches` | GET | 公开赛事列表（含 public_lean） | 公开 |
| `/api/football/osint/match/{id}/dashboard` | GET | 比赛详情（按权限过滤字段） | 公开（字段过滤） |
| `/api/football/osint/jobs` | POST | 创建分析任务 | 已付费 |
| `/api/football/osint/jobs/{id}` | GET | 任务状态 | 已付费 |
| `/api/football/osint/jobs/{id}/report.md` | GET | Markdown 报告 | 已付费 |
| `/api/football/osint/predict-sync` | POST | 同步预测（测试用） | 已付费 |
| `/api/football/osint/answer` | POST | 自由提问 | 已付费 |
| `/api/football/osint/dimension` | POST | 6 维快捷追问 | 已付费 |

### 5.6 错误码命名

`E_<DOMAIN>_<REASON>`，用户文案与开发者消息分离：

```json
{
  "error_code": "E_INVITE_USED",
  "message_zh": "邀请码已使用，请联系邀请人",
  "message_en": "Invitation code already used, contact your inviter",
  "developer_hint": "invitation.id=inv_xxx, used_by=u_yyy at 2026-06-13T10:00Z"
}
```

清单（部分）：
- `E_INVITE_INVALID` / `E_INVITE_USED` / `E_INVITE_EXPIRED`
- `E_CODE_INVALID` / `E_CODE_USED` / `E_CODE_EXPIRED` / `E_ENTITLEMENT_DUPLICATE`
- `E_OTP_INVALID` / `E_OTP_EXPIRED` / `E_AUTH_FAILED` / `E_AUTH_LOCKED`
- `E_EMAIL_TAKEN` / `E_FORBIDDEN` / `E_QUOTA_EXCEEDED`
- `E_DB_TRANSIENT` / `E_LLM_DOWN`

---

## 6. 数据模型

### 6.1 SQLite 表（auth + billing 域）

```sql
-- user
CREATE TABLE user (
  id TEXT PRIMARY KEY,                       -- u_xxxxxxxxxx
  nickname TEXT NOT NULL,
  avatar_url TEXT,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'      -- active | banned
);

-- identity
CREATE TABLE identity (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user(id),
  provider TEXT NOT NULL,                    -- email (v1) | wechat_mp (v1.5)
  identifier TEXT NOT NULL,                  -- email or unionid
  metadata_json TEXT,
  created_at TIMESTAMP NOT NULL,
  UNIQUE(provider, identifier)
);

-- session (jwt + refresh)
-- 由于 v1 用 jwt，session 不落库；refresh_token 哈希落库以便撤销
CREATE TABLE refresh_token (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user(id),
  issued_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP
);

-- invitation
CREATE TABLE invitation (
  code TEXT PRIMARY KEY,                     -- [A-Z2-9]{12}
  inviter_user_id TEXT REFERENCES user(id),  -- null = admin 批发
  status TEXT NOT NULL,                      -- unused | used | expired
  used_by_user_id TEXT REFERENCES user(id),
  used_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  note TEXT
);
CREATE INDEX idx_invitation_inviter ON invitation(inviter_user_id);
CREATE INDEX idx_invitation_status ON invitation(status);

-- activation_code (付费码)
CREATE TABLE activation_code (
  code TEXT PRIMARY KEY,                     -- [A-Z0-9]{12-24}
  status TEXT NOT NULL,                      -- unused | used | expired
  granted_to_user_id TEXT REFERENCES user(id),
  source_order_id TEXT,                      -- null in v1
  redeemed_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  validity_days_after_redeem INTEGER,        -- null = 永久
  note TEXT
);
CREATE INDEX idx_activation_code_status ON activation_code(status);

-- entitlement
CREATE TABLE entitlement (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES user(id),
  type TEXT NOT NULL,                        -- full_analysis
  granted_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP,                      -- null = 永久
  source TEXT NOT NULL,                      -- code:<code> | admin:<admin_id>
  UNIQUE(user_id, type)                      -- v1 强制：单 user 单类型
);

-- audit_log
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TIMESTAMP NOT NULL,
  user_id TEXT,
  actor TEXT NOT NULL,                       -- user | admin | system
  event TEXT NOT NULL,                       -- invitation.consumed | billing.code_redeemed | ...
  payload_json TEXT,
  ip TEXT,
  user_agent TEXT
);
CREATE INDEX idx_audit_event_ts ON audit_log(event, ts);
CREATE INDEX idx_audit_user_ts ON audit_log(user_id, ts);

-- system_config (admin CLI 可调)
CREATE TABLE system_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by TEXT
);
```

### 6.2 Bronze JSON（OSINT 域）

仍采用文件系统：`bronze_storage/football_osint/{job_id}/*.json` + `bronze_storage/football_osint/_index.json`（job_id → 文件路径映射，加速 GET）。

### 6.3 数据约束

- 邀请码、付费码字符集：`[A-Z2-9]`（去除易混 0/O/1/I/L），长度 12（邀请）或 16（付费码）
- email 仅小写存储，不允许带 `+` 别名（防滥用注册）
- 用户昵称：1-20 字符，UTF-8，禁词过滤
- 默认有效期：邀请码 30 天 / 付费码兑换 90 天 / 权益永久

---

## 7. 非功能需求（NFR）

| ID | 要求 | 验收 |
|---|---|---|
| NFR-1 | 已付费看主判断 < 5s（缓存命中 < 200ms） | 上线前 5 比赛实测 + 上线后埋点 P95 |
| NFR-2 | OSINT pipeline P95 < 30s（无 lp-fetch-md），P99 < 60s | 自动化测试 + 上线埋点 |
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
| OPS-1 | systemd unit + MemoryMax=1.8G + 自动重启 | `osint-network.service` |
| OPS-2 | runbook 简版：DeepSeek 503 / 数据源全挂 / bronze 写失败 | `docs/runbook-v1.md` |
| OPS-3 | 故障 5 分钟定位：日志按 `request_id` 索引 | 日志查询脚本 |
| OPS-4 | admin CLI（详见 §8.1） | `python -m backend.admin` |
| OPS-5 | 采集触发：cron 每 6h 全量；用户首次访问比赛时按需触发 | crontab + 后端 |
| OPS-6 | 缓存失效：开赛前 6h 强制重算 | pipeline 检查 kickoff_at |
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

# 配置
python -m backend.admin set_threshold --key info_insufficient_factor_min --value 1
python -m backend.admin list_config

# 列表
python -m backend.admin list_codes --type invite|payment [--status unused|used]
```

鉴权：`ADMIN_TOKEN` 在 `.env` 中，CLI 仅服务器本地能跑（依赖文件系统读 .env）。

---

## 9. 前端设计

### 9.1 信息架构

Web 三栏：

```
┌─────────────┬───────────────────────────┬─────────────────────┐
│             │                           │                     │
│  赛事队列   │    比赛问答卡             │   Ask 面板          │
│  (左栏)     │    (中栏)                 │   (右栏)            │
│             │                           │                     │
│  联赛       │    联赛/时间/双方         │   问答历史          │
│  时间       │    默认主判断             │   推荐追问          │
│  关注状态   │    (lean+L+风险)          │   证据引用          │
│             │    因子折叠               │   报告生成          │
│             │    EvidenceStrength       │                     │
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
| 图标 | `@phosphor-icons/react`，禁 emoji |

### 9.3 v1 组件清单（6 个核心）

| 组件 | 职责 |
|---|---|
| `MatchQuestionCard` | 中栏比赛卡（已付费完整版 + 未付费降级版） |
| `EvidenceStrength` | 三栏证据展示 + "缺什么"清单 |
| `AuthGate` | 包裹受限内容，触发注册/登录引导 |
| `AccountStatus` | 账号状态卡（在右栏顶部） |
| `PaymentUnlock` | 付费码兑换面板 |
| `InvitePanel` | 已付费用户生成邀请码 + 二维码 |

延后到 v1.5：`SharePoster`、`SubscribeButton`、跨端账号合并 UI。

### 9.4 文案锚点

- 信息不足时 RQ-E-13："我们没编。这场缺关键数据，等开赛前 2 小时还会再扫一遍。"
- 访客升级提示："使用邀请码注册并兑换付费码后查看完整证据"
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
| UC-02 | 邮箱登录 |
| UC-03 | 付费码兑换权益 |
| UC-04 | 访客查看赛事列表与简单倾向 |
| UC-05 | 已付费查看默认主判断 |
| UC-06 | 6 维快捷追问（模板路径） |
| UC-07 | 自由提问（LLM + 降级） |
| UC-08 | 信息不足展示 |
| UC-09 | 已付费用户邀请新用户 |
| UC-10 | admin CLI 批发邀请码/付费码 |

---

## 11. 实施计划

### 11.1 工期估算

总工期：**5-6 周**（单人节奏）+ 1 周风险缓冲。

| 周 | 里程碑 |
|---|---|
| W1 | DB 模型 + admin CLI + 后端拆分骨架（D-1/D-2/D-3） |
| W2 | 注册/登录链路 + 邀请/付费码闭环 + 因子注册表完成 |
| W3 | 三栏布局 + MatchQuestionCard + EvidenceStrength + AuthGate |
| W4 | PaymentUnlock + InvitePanel + 文案审计 + LLM 引用约束 |
| W5 | 备份/HTTPS/systemd/runbook 简版 + 内测 5 人 |
| W6 | Rollout checklist + 上线灰度 |
| W7（缓冲） | 灰度修复 |

### 11.2 关键路径

```
DB 模型 → admin CLI → 注册/登录 → 邀请/付费码 → AuthGate/PaymentUnlock → Rollout
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
| Q5 | OSINT 后端按 spec 完整拆分（10 子模块） |
| Q6 | 6 维 chips 走模板，自由提问走 LLM 含降级 |
| Q14 默认 | 信息不足阈值：因子启用数 ≤ 1 或均值 < 0.30 |
| Q22 | 邀请码 30d / 付费码兑换 90d / 权益永久 |
| Q12 默认 | 邮件服务商：Resend |
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
| 邀请码 | invitation，注册必需 |
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

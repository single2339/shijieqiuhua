---
phase: 4
artifact: use-case-specification
date: 2026-06-13
status: draft
depends_on:
  - 04-proto-requirements.md
  - 07-gap-audit.md
  - 08-moscow.md
---

# 世界球花 — 用例规格 v1

## Summary

针对 v1（M 档）中**工程量大或风险高**的 10 个核心用例写规格。每个用例含：
- 主路径（happy path）
- 备选流程（alternate flows）
- 异常流程（exception flows）
- 后置/失败状态
- 关联 RQ ID（traceability）

不在本文档范围：纯 GET/CRUD 类用例（如查赛事列表）；NFR 类（在阶段 5 PRD 中合并）。

## 假设

- 术语：访客 = 未登录；已注册用户 = 已登录但 entitlement 空；已付费用户 = 持有 `entitlement(type='full_analysis')`。
- 错误码沿用 GAP-A-6 提的 `E_*` 形式。
- 接口路径沿用 spec backend §API（`/api/football/osint/*`）+ 新增 `/api/auth/*`、`/api/billing/*`、`/api/invitation/*`。
- 阶段 4 不画时序图（节省时间）；流程用编号步骤。

---

## 用例总览

| ID | 用例 | 主 actor | 关联 RQ |
|---|---|---|---|
| UC-01 | 邀请码注册新用户 | 访客 | A-4/A-7/A-8/A-9/H-7/G-2 |
| UC-02 | 邮箱登录 | 已注册用户 | A-17/A-3 |
| UC-03 | 付费码兑换权益 | 已注册用户 | A-13/A-14/G-1/G-3 |
| UC-04 | 访客查看赛事列表与简单倾向 | 访客 | B-16/E-5/G-5 |
| UC-05 | 已付费用户查看默认主判断 | 已付费 | B-1/B-2/B-3/C-3/F-1 |
| UC-06 | 6 维快捷追问（模板路径） | 已付费 | B-5/B-6/B-12/D-7 |
| UC-07 | 自由提问（LLM 路径 + 降级） | 已付费 | B-4/B-7/B-8/B-9/B-17 |
| UC-08 | 缺证据 → 信息不足展示 | 任意 | B-2/C-5/C-11 |
| UC-09 | 已付费用户邀请新用户 | 已付费 | A-11/A-4 |
| UC-10 | admin 批发邀请码 + 付费码 | admin | H-4/A-4/A-5 |

---

## UC-01 邀请码注册新用户

**Actor**：访客（持有有效邀请码）
**Trigger**：访客打开 `/register?invite=CODE` 或在注册页手动输入 invite_code
**Preconditions**：
- 邀请码存在且 `status='unused'`
- 邀请码未过期（`expires_at > now()`）
- 邀请码未达使用上限（默认 1 次）

**Postconditions（成功）**：
- 创建 user 记录（无 entitlement）
- 创建 identity 记录（provider='email'）
- 邀请码 `status='used'`、`used_by=user.id`、`used_at=now()`
- 写 audit_log（事件 `invitation.consumed`）
- 返回 access_token（cookie），重定向到注册成功页

### 主路径

1. 访客提交：邀请码、邮箱、邮箱验证码、用户昵称
2. 后端 `POST /api/auth/register` 接收
3. 校验邀请码（存在 / 未用 / 未过期）
4. 校验邮箱格式 + 验证码 + 邮箱未被其他 user 使用
5. 在事务内：
   - INSERT user
   - INSERT identity (provider='email', identifier=邮箱)
   - UPDATE invitation SET status='used', used_by=user.id, used_at=now()
   - INSERT audit_log
6. 签发 session（jwt + refresh）
7. 返回 200 + 用户基础信息

### 备选流程

| 编号 | 触发条件 | 走向 |
|---|---|---|
| A1 | 邀请码已用 | 步骤 3 失败 → 返回 `E_INVITE_USED` 「邀请码已使用，请联系邀请人」 |
| A2 | 邀请码过期 | 步骤 3 失败 → 返回 `E_INVITE_EXPIRED` 「邀请码已过期」 |
| A3 | 邀请码不存在 | 步骤 3 失败 → 返回 `E_INVITE_INVALID` 「邀请码无效」 |
| A4 | 邮箱已注册 | 步骤 4 失败 → 返回 `E_EMAIL_TAKEN` + 引导登录 |
| A5 | 邮箱验证码错误/过期 | 步骤 4 失败 → `E_OTP_INVALID` |

### 异常流程

| 编号 | 异常 | 处理 |
|---|---|---|
| E1 | 事务过程中数据库错误 | 回滚；返回 `E_DB_TRANSIENT`；用户可重试；不消耗邀请码 |
| E2 | 邮件发送验证码超时（前一步） | 步骤 1 之前；前端显示重试入口 |
| E3 | 速率限制（单 IP > 20 注册 / min） | 返回 429；不创建任何记录 |
| E4 | 用户中途关闭页面 | 邀请码未消耗，验证码 OTP 还有 10 min 有效期 |

### 接口契约

```http
POST /api/auth/register
Content-Type: application/json

{
  "invite_code": "AB12CD34",
  "email": "user@example.com",
  "otp_code": "123456",
  "nickname": "球友A"
}

→ 200
Set-Cookie: osint_access_token=...
Set-Cookie: osint_refresh_token=...
{
  "user": { "id": "u_xxx", "nickname": "球友A", "entitlements": [] },
  "redirect_to": "/onboarding"
}

→ 400 / 401 / 409 / 410 / 429（按 A1-A5/E3）
{ "error_code": "E_INVITE_USED", "message_zh": "...", "message_en": "..." }
```

### 验收注释

- T1：测试 happy path → user 数 +1，invitation.status='used'
- T2：测试同一邀请码 2 次注册 → 第 2 次返回 `E_INVITE_USED`，user 数不变
- T3：测试过期邀请码 → `E_INVITE_EXPIRED`
- T4：测试事务原子性 → 模拟 INSERT identity 失败，user 不应留下
- T5：测试速率限制 → 第 21 次返回 429

---

## UC-02 邮箱登录

**Actor**：已注册用户
**Trigger**：访问 `/login` 输入邮箱 + 验证码 / 邮箱 + 密码
**Preconditions**：user 存在、identity(provider='email') 存在
**Postconditions（成功）**：签发 session

### 主路径（验证码登录）

1. 用户输入邮箱 → 前端 `POST /api/auth/otp/send`
2. 后端校验邮箱已注册 → 发送 6 位 OTP（10 min 有效）
3. 用户输入 OTP → `POST /api/auth/login`
4. 后端校验 OTP
5. 签发 session 并返回 user + entitlements 摘要
6. 写 audit_log

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 邮箱未注册 | 步骤 2 不发 OTP；返回模糊提示 `E_AUTH_FAILED`（防枚举） |
| A2 | OTP 错误 | 步骤 4 失败；尝试 ≥ 5 次 IP 锁 15 min |
| A3 | OTP 过期 | `E_OTP_EXPIRED`；引导重发 |
| A4 | 用户已登录 | 返回 200 + 当前 user，不重新签发 |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | 邮件服务商 503 | OTP 发送失败 → 显示"暂时无法发送验证码，稍后重试"；不计入失败计数 |
| E2 | refresh_token 过期 + access_token 过期 | 用户自动跳回登录页 |

### 接口契约

```http
POST /api/auth/otp/send  { "email": "user@example.com" }
→ 200 { "expires_in": 600 }   或 E_AUTH_FAILED（防枚举仍返回 200）

POST /api/auth/login  { "email": ..., "otp_code": ... }
→ 200 + cookies + { "user": {...}, "entitlements": [...] }
```

---

## UC-03 付费码兑换权益

**Actor**：已注册用户（无 full_analysis 权益）
**Trigger**：账户页"付费码兑换"按钮 → 输入码 → 提交
**Preconditions**：
- user 已登录
- activation_code 存在 / 未用 / 未过期
- user 当前不持有 type='full_analysis' 的有效 entitlement（防重复消耗）

**Postconditions**：
- activation_code.status='used'，redeemed_at=now()
- user 获得 entitlement(type='full_analysis', granted_at=now(), expires_at=now()+30d)
- 缓存中 user.entitlements 立即失效重读
- 写 audit_log

### 主路径

1. 前端 `POST /api/billing/redeem { "code": "..." }`
2. 后端在事务内：
   - SELECT activation_code FOR UPDATE（锁行防双花）
   - 校验 status / expires_at
   - 校验 user 当前无重复 entitlement
   - UPDATE activation_code SET status='used', redeemed_by=user.id, redeemed_at=now()
   - INSERT entitlement
   - INSERT audit_log
3. 返回新 entitlement
4. 前端立即刷新 user 状态、解锁完整功能

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 付费码已用 | `E_CODE_USED` |
| A2 | 付费码过期 | `E_CODE_EXPIRED` |
| A3 | 付费码不存在 | `E_CODE_INVALID` |
| A4 | user 已持有有效 entitlement | `E_ENTITLEMENT_DUPLICATE` 「您已开通完整功能，付费码已退还为未使用」（**不消耗**） |
| A5 | user 未登录 | 401；前端跳登录 |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | 双客户端同时兑换同一付费码 | FOR UPDATE 锁；后到的事务被 A1 拒绝 |
| E2 | INSERT entitlement 失败 | 回滚整个事务；activation_code 不被消耗 |
| E3 | 速率限制（单 user > 10 次 / min） | 429 |

### 接口契约

```http
POST /api/billing/redeem
{ "code": "PRO-2026-XXXX-XXXX" }

→ 200
{ "entitlement": { "type": "full_analysis", "granted_at": "...", "expires_at": null } }

→ 409
{ "error_code": "E_CODE_USED" | "E_ENTITLEMENT_DUPLICATE" }
```

### 验收注释

- T1：happy path → entitlement 表新增 1 条
- T2：A4 重复持有时**不消耗**付费码（关键测试）
- T3：双客户端并发同一付费码 → 只有 1 个成功（用 SQLite 事务或 PostgreSQL FOR UPDATE，本项目 SQLite 用 BEGIN IMMEDIATE）
- T4：客户端"已成功"提示与服务端事务结果不一致时，以服务端为准（红线 G-1）

---

## UC-04 访客查看赛事列表与简单倾向

**Actor**：访客（未登录）
**Trigger**：访问 `/` 或 `/match/{id}`
**Preconditions**：无
**Postconditions**：访客看到比赛列表 + 公开摘要（无证据、无追问入口）

### 主路径

1. 前端 `GET /api/matches?date=today`（公开）
2. 后端从 bronze 拉取当日比赛 list
3. 对每场比赛：
   - 如果存在已生成的 job（缓存命中）→ 取 prediction.lean
   - 否则 → 触发后台异步生成（spec backend §错误和降级）；当下返回 `lean='unknown'`
4. **应用 RQ-B-2 / G-5 规则**：缺证据时 lean 改为 `info_insufficient`
5. 返回简单结构：`[{match_id, league, kickoff, home, away, public_lean}]`
6. 前端渲染列表 + 每条只显示 league/kickoff/home/away 和"主队倾向 / 平 / 客队倾向 / 信息不足"四值之一

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 访客点击某场进入详情 | 跳到比赛详情页 → AuthGate 包裹 Ask 面板 → 显示注册引导 |
| A2 | 访客点击"继续问" | AuthGate 拦截 → 显示注册/登录入口 |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | bronze 完全无数据 | 返回 `[]` 与"今天暂无重点赛事"文案 |
| E2 | 后端生成 job 失败 | 该比赛 lean 显示 `info_insufficient` |

### 文案约束（红线 R1 + RQ-E-11）

只能用：主队倾向 / 平局压力偏高 / 客队倾向 / 信息不足
禁用：必胜 / 稳赢 / 推荐 / 大胆 / 串关 / 推单 ……

---

## UC-05 已付费用户查看默认主判断

**Actor**：已付费用户
**Trigger**：访问 `/match/{id}`
**Preconditions**：user 已登录 + 持有 full_analysis entitlement
**Postconditions**：用户看到完整 MatchQuestionCard

### 主路径

1. 前端 `GET /api/football/osint/match/{id}/dashboard`
2. 后端按 RQ-D-5 缓存策略检查：
   - 缓存有效（开赛 > 6h 且 ≤ 6h 缓存）→ 返回缓存
   - 否则 → 异步重算（job），先返回 `phase='running', progress=N`
3. 数据返回（已就绪情况）：
   ```
   {
     match: {...},
     prediction: { lean, summary, probability_band, scoreline_band, drivers, uncertainties },
     confidence: { level: 'L3', reason: '...' },
     factors: [...],          # 启用的 + missing_reason 的
     evidence: [...],         # 完整列表
     missing_data: [...],     # RQ-C-11 "缺什么"
     report_md_url: '/api/.../report.md'
   }
   ```
4. 前端渲染：
   - 头部：联赛、开赛时间、双方
   - 默认主判断：lean / level / 风险数
   - 因子展开（折叠默认）
   - EvidenceStrength 三栏：强 / 弱 / 不足
   - 6 维 chips
   - 自由提问输入框
5. 5s 性能预算（RQ-F-1）：
   - 缓存命中：< 200ms
   - 缓存重算：< 5s（异步首屏渲染骨架，N=1.5s 后 polling 1 次拿结果）

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | job 状态 `needs_review` | 显示"比赛信息无法验证"+ 引导用户修改输入或提交 win007 matchId |
| A2 | 信息不足触发 RQ-B-2 阈值 | lean 显示"信息不足"+ missing_data 清单（UC-08） |
| A3 | 缓存重算耗时 > 30s（P95 兜底） | 前端显示骨架 ≤ 30s；超时后显示"加载较慢，已切换为基础视图"（仅展示赛事元信息和 lean='running'） |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | LLM 全部失败 | factors 中 form/squad 等因子 enabled=false + missing_reason；不阻塞主判断（继续走模板因子） |
| E2 | bronze 写入失败 | 当前请求继续返回内存计算结果；告警；下次重算 |

---

## UC-06 6 维快捷追问（模板路径）

**Actor**：已付费用户
**Trigger**：点击 chips（半场 / 红黄牌 / 角球 / 进球数 / 球员 / 风险）
**Preconditions**：UC-05 已完成
**Postconditions**：用户看到该维度的结构化判断

### 主路径

1. 前端 `POST /api/football/osint/dimension`
   ```
   { match_id, dimension: 'corners' | 'cards' | 'first_half' | ... }
   ```
2. 后端：
   - 加载 match + factors + evidence
   - 按 dimension 选模板：
     - corners → 选 form / tactical / weather / referee 因子
     - cards → 选 referee / tactical / motivation 因子
     - …
   - 检查所选因子是否有可用证据：
     - 全无 → 返回 "信息不足"（UC-08）
     - 有 → 模板填充：[lean / 关键因子 / 主要不确定性 / 关联 evidence_ids]
3. 返回 `FootballOsintAnswer`（同 spec § answer 结构）
4. 前端追加到右栏 Ask 历史

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 该维度对当前赛事 profile 不适用（如友谊赛 + 球员维度） | 模板返回 "信息不足，原因：友谊赛阵容信息透明度低" |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | factors 加载失败 | 返回 500 + 用户文案"维度分析暂不可用" |

### 验收注释

- T1：6 个 dimension 各跑一次，全有结构化输出（即使是"信息不足"）
- T2：友谊赛 + player 维度 → "信息不足"
- T3：response_time < 1s（无 LLM 调用）

---

## UC-07 自由提问（LLM 路径 + 降级）

**Actor**：已付费用户
**Trigger**：在比赛卡输入框敲入问题 + Enter
**Preconditions**：UC-05 已完成；问题非空
**Postconditions**：返回 FootballOsintAnswer

### 主路径

1. 前端 `POST /api/football/osint/answer`（已有）
2. 后端 `_is_match_related()` 判定：
   - 不相关 → 返回 `{ related: false, answer: '问题与比赛无关' }`（已实现）
3. 相关 → 在 `_ANSWER_SEMAPHORE` 内调用 LLM：
   - prompt 模板（GAP-W-6）：
     - 显式列出当前比赛的 evidence ID 列表 + claim 摘要
     - 要求 LLM 输出必须含 `[ev_xxx]` 形式引用
     - 要求 reasons ≤ 3 条
4. LLM 返回 → 后端校验：
   - reasons 中提到的 `[ev_xxx]` 必须存在于上下文 evidence 列表
   - 任何引用失败 → 走 A2 降级
5. 返回 FootballOsintAnswer

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | LLM 60s 超时 | 降级到 UC-06 模板路径，按 dimension="risk" 处理（兜底维度） + 答案文本前缀"详细解读暂不可用" |
| A2 | LLM 输出引用合法性失败 | 同 A1 降级 |
| A3 | LLM 限流 / 503 | 同 A1 降级 |
| A4 | 空问题或 < 2 字符 | 前端拦截，不发请求 |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | 信号量满（4 并发已用完） | 排队 ≤ 30s；超时返回 503 + 文案"系统繁忙" |
| E2 | bronze 中查不到 match | 返回 404 |

### 验收注释

- T1：正常问题 → 含 ≥ 1 条 `[ev_xxx]` 引用
- T2：LLM 编造证据 ID（如 `[ev_999]`）→ 走 A2 降级
- T3：信号量饱和测试 → 第 5 个请求排队，第 6 个被拒
- T4：F1 测试集（GAP-W-4）50 题中 `_is_match_related` 召回 ≥ 0.85（v1 上线后才能补集校准）

---

## UC-08 缺证据 → 信息不足展示

**Actor**：访客 / 已注册 / 已付费（任意）
**Trigger**：UC-04/UC-05/UC-06/UC-07 中触发 RQ-B-2 阈值
**Preconditions**：本场比赛因子 enabled 数 ≤ 1 或所有启用因子 confidence 均值 < 0.30
**Postconditions**：UI 不显示倾向；显示"信息不足"+"缺什么"清单

### 主路径

1. 后端在 `_predict()` 之前先检查 RQ-B-2 阈值
2. 不满足 → 设置 `prediction.lean = 'info_insufficient'`，`summary = '本场比赛证据不足，无法形成方向倾向'`
3. 计算 `missing_data: list[str]`：
   - 遍历 disabled 因子，按 group 归类：squad / form / h2h / weather / market / …
   - 输出 zh 文案：例如 "缺首发与伤停信息"、"缺球队近期状态数据"
4. 返回到前端
5. 前端：
   - 主判断区改为大字"信息不足"+ confidence_level 仍展示（多半是 L4）
   - 缺什么清单列表（最多 5 条）
   - **不显示** 倾向胜负箭头
   - 提供"我有补充信息"入口（链接到用户补充 URL/笔记输入）
   - 推荐文案 RQ-E-13：例如"我们没编。这场缺关键数据，等开赛前 2 小时还会再扫一遍。"

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 用户提交补充 URL/笔记 | 触发 UC-05 重算（异步） |
| A2 | 访客遇到 info_insufficient | 与已付费一致显示，并附"开通后可手动补充信息"引导 |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | missing_data 计算失败 | 兜底文案"信息不足"+ 不带清单 |

---

## UC-09 已付费用户邀请新用户

**Actor**：已付费用户
**Trigger**：账户页 InvitePanel → "生成邀请码"
**Preconditions**：user 已付费 + 当月已生成邀请码 < 配额（默认 5 个）
**Postconditions**：邀请码可分享

### 主路径

1. 前端 `POST /api/invitation/create`
2. 后端检查月度配额（GAP-A-5 admin 可调）
3. 生成邀请码（`[A-Z0-9]{12}`，避免易混 0/O/1/I/L），写入 invitation 表
4. 返回邀请码 + 分享链接 `https://xxx/register?invite=CODE`
5. 前端 InvitePanel 展示：码、链接、二维码（v1 用 `qrcode` 库前端生成）、复制按钮

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 配额已满 | `E_QUOTA_EXCEEDED` + 提示"本月配额已用完，下月 1 日重置" |
| A2 | 用户未付费 | `E_FORBIDDEN` |
| A3 | 用户查看历史邀请 | `GET /api/invitation/list` 返回我生成过的、含 status |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | 邀请码碰撞（极小概率）| 重试 3 次；3 次都碰撞 → 返回 500 |

---

## UC-10 admin 批发邀请码 + 付费码

**Actor**：admin（通过 CLI）
**Trigger**：运行 `python -m backend.admin invite_codes --count 50` 或 `payment_codes --count 100 --validity-days 90`
**Preconditions**：admin 鉴权（Q26 待定；建议：CLI 直接读 .env 中 ADMIN_TOKEN，且 CLI 只能在服务器本地运行）
**Postconditions**：N 条邀请码 / 付费码生成；输出到 stdout 或 CSV

### 主路径

1. CLI 解析参数（数量、有效期、备注）
2. 校验 ADMIN_TOKEN
3. 在事务内批量 INSERT
4. 输出（CSV 格式 to file）
5. 写 audit_log（事件 `admin.bulk_create_invite|payment_code`，含 admin 标识）

### 备选流程

| ID | 条件 | 走向 |
|---|---|---|
| A1 | 一次创建 > 1000 | 拒绝；防止误操作 |
| A2 | 自定义 expires_at | 接受参数 |
| A3 | 列出已分发 | `python -m backend.admin list_codes --type invite` |

### 异常流程

| ID | 异常 | 处理 |
|---|---|---|
| E1 | 数据库锁竞争 | retry 3 次 |
| E2 | ADMIN_TOKEN 错误 | 直接退出 + 退出码 1 |

### admin CLI 命令清单

```
python -m backend.admin invite_codes --count N [--validity-days 30] [--output codes.csv]
python -m backend.admin payment_codes --count N [--validity-days 90] [--note "..."]
python -m backend.admin list_users [--paid] [--limit 100]
python -m backend.admin ban_user --user-id u_xxx --reason "..."
python -m backend.admin set_threshold --key info_insufficient_factor_min --value 1
```

---

## 用例间依赖

```
UC-10 (admin 批发) ──→ UC-01 (注册) ──→ UC-02 (登录) ──→ UC-03 (兑换) ──→ UC-05/UC-06/UC-07
                                            │
                                            └─→ UC-04 (访客可见，无需 UC-02)

UC-08 嵌入 UC-04/05/06/07 的所有路径
UC-09 依赖 UC-03 完成（已付费）
```

## Acceptance Notes

每个用例的 T* 测试列表合计 **30+ 个测试用例**，将在阶段 4 下一步 **acceptance-criteria-writer** 中转化为 Gherkin/AAA 格式 + DoD。

## 未解决问题（feed 阶段 5）

| ID | 问题 | 影响 |
|---|---|---|
| Q26 | admin CLI 鉴权方案（ADMIN_TOKEN 文件 vs SSH only vs 二者） | UC-10 |
| Q12 | 邮件服务商 | UC-01/UC-02 |
| Q15 | 问答历史是否进 v1（决策已说不进） | UC-07 旁路 |
| Q14 | "信息不足"阈值是否可在生产环境运行时调（admin CLI 可调，建议默认值 1.0/0.30） | UC-08 |

---

## 推荐下一步

阶段 4 下一步：**acceptance-criteria-writer**（任务 #18）—— 把 10 个用例的 T* 列表转成完整可执行的验收标准 + DoD。

完成后进入阶段 5：**requirements-packager** 打包 PRD v1。

---
phase: 4
artifact: acceptance-criteria + DoD
date: 2026-06-13
status: draft
depends_on:
  - 09-use-cases.md
  - 08-moscow.md
---

# 世界球花 — 验收标准 (AC) 与 Definition of Done (DoD)

## Summary

把阶段 4 的 10 个用例（`09-use-cases.md`）转化为可观察、可测的 Given/When/Then 验收标准；并加 Definition of Done（v1 上线前每条 M 项都必须满足的"完成"定义）。

合计 **53 条 AC**（功能）+ **8 条 NFR AC** + **DoD 清单 12 项**。每条 AC 标注 `[blocked-by-Qxx]` 当前阻塞决策。

---

## Findings

- **可立即编写**：47 条 AC（用例契约清晰）
- **被 open question 阻塞**：6 条（标 `[blocked]`）
- **后续埋点验证类**（v1 上线后）：8 条
- **NFR 类 AC**（性能/可用性/安全）独立 8 条

---

## Structured Outputs

### 1. 功能验收标准（按 UC 组织）

#### UC-01 邀请码注册新用户

| ID | Given | When | Then |
|---|---|---|---|
| AC-01-1 | 一个 unused、未过期的邀请码、邮箱 OTP 已发送并有效 | 用户提交 invite_code + email + otp + nickname | 创建 user + identity；invitation.status='used'；返回 200 + cookies |
| AC-01-2 | 同一邀请码已被其他用户使用 | 第二位用户用同一邀请码注册 | 返回 409 `E_INVITE_USED`；不创建 user |
| AC-01-3 | 邀请码 expires_at < now() | 用户提交 | 返回 410 `E_INVITE_EXPIRED`；invitation 不变 |
| AC-01-4 | 邀请码不存在于 invitation 表 | 用户提交伪造码 | 返回 404 `E_INVITE_INVALID` |
| AC-01-5 | email 已存在于其他 user.identity | 用户提交 | 返回 409 `E_EMAIL_TAKEN`；引导登录 |
| AC-01-6 | OTP 错误或过期 | 用户提交错误 OTP | 返回 401 `E_OTP_INVALID`；不消耗邀请码 |
| AC-01-7 | INSERT identity 阶段抛错 | 事务执行 | 整个事务回滚；user 不被创建；invitation 仍 unused |
| AC-01-8 | 单 IP 60s 内已注册 20 次 | 第 21 次请求 | 返回 429；不消耗任何资源 |
| AC-01-9 | 注册成功 | 后置检查 audit_log | 写入一条 `event='invitation.consumed'`、含 `invite_code, user_id, ip, ua` |
| AC-01-10 | 邀请码使用并发：两个客户端用同一码同时提交 | 服务端处理 | 仅 1 个成功；另一个返回 `E_INVITE_USED` |

#### UC-02 邮箱登录

| ID | Given | When | Then |
|---|---|---|---|
| AC-02-1 | 邮箱已注册、OTP 有效 | 提交 email + otp | 返回 200 + cookies + user 摘要 |
| AC-02-2 | 邮箱未注册 | 调 `POST /auth/otp/send` | 返回 200（防枚举）；不实际发邮件；不计入失败次数 |
| AC-02-3 | OTP 错误 5 次（同 IP 内 15 min） | 第 6 次提交 | 返回 429 `E_AUTH_LOCKED`；锁 IP 15 min |
| AC-02-4 | OTP 已超 10 min | 提交 | 返回 401 `E_OTP_EXPIRED` |
| AC-02-5 | 邮件服务商超时/失败 | 调发送 OTP | 返回 503 + 用户文案"暂时无法发送验证码"；**不**计入失败次数 |
| AC-02-6 | 用户已登录持有 access cookie | 再次访问 `/login` | 不重新签发 session；前端跳到首页 |
| AC-02-7 | access_token 过期、refresh_token 有效 | 任意 API 请求 | 后端 auth_middleware 自动 refresh + Set-Cookie 新 access |

#### UC-03 付费码兑换权益

| ID | Given | When | Then |
|---|---|---|---|
| AC-03-1 | activation_code unused、未过期、user 已登录、user 无重复 entitlement | 提交 code | 200 返回新 entitlement；activation_code.status='used'；audit_log 写入 `billing.code_redeemed` |
| AC-03-2 | activation_code.status='used' | 提交 | 409 `E_CODE_USED` |
| AC-03-3 | activation_code.expires_at < now() | 提交 | 410 `E_CODE_EXPIRED` |
| AC-03-4 | activation_code 不存在 | 提交伪造码 | 404 `E_CODE_INVALID` |
| AC-03-5 | user 已持有 type='full_analysis' 有效 entitlement | 提交另一个 unused 码 | 409 `E_ENTITLEMENT_DUPLICATE`；**activation_code 仍为 unused**（不被消耗） |
| AC-03-6 | user 未登录 | 提交 | 401；前端跳登录页 |
| AC-03-7 | 单 user 60s 内提交 ≥ 10 次 | 第 11 次 | 429 |
| AC-03-8 | 双客户端同时提交同一 unused 码 | 服务端处理 | 仅 1 个成功；另一个返回 `E_CODE_USED`（依赖 BEGIN IMMEDIATE 锁） |
| AC-03-9 | INSERT entitlement 阶段失败 | 事务执行 | 全部回滚；activation_code 仍 unused |
| AC-03-10 | 兑换成功 | 前端立即调 `GET /api/auth/me` | entitlements 数组中含 `full_analysis` |

#### UC-04 访客查看赛事列表

| ID | Given | When | Then |
|---|---|---|---|
| AC-04-1 | bronze 中今日有 5 场比赛 | 访客 GET `/api/matches?date=today` | 返回 5 条；每条仅含 `match_id, league, kickoff, home, away, public_lean` |
| AC-04-2 | 某场比赛因子启用数 ≤ 1 或均值 < 0.30 | GET 该比赛 | public_lean = `info_insufficient` |
| AC-04-3 | 访客点击进入 `/match/{id}` | 后端返回数据 | 不返回 evidence、factors、reasons；返回字段被服务端过滤 |
| AC-04-4 | 访客点击"继续问"按钮 | 前端处理 | AuthGate 拦截，弹注册引导；**不**发任何 API 请求到 `/answer` |
| AC-04-5 | bronze 完全无数据 | GET | 返回 `[]` + UI 显示"今天暂无重点赛事" |
| AC-04-6 | response 包含禁词（必胜/稳赢/推荐/串/料/推单）| 自动化文案审计扫描 | 测试失败；CI 拒绝部署 |

#### UC-05 已付费用户查看默认主判断

| ID | Given | When | Then |
|---|---|---|---|
| AC-05-1 | 已付费 + 比赛缓存命中 | GET dashboard | 200 ≤ 200ms；返回完整结构（match, prediction, confidence, factors, evidence, missing_data）|
| AC-05-2 | 已付费 + 缓存过期 + 后台异步重算 | GET dashboard | 首次返回 `phase='running', progress<100`；前端 1.5s 后 polling，5s 内拿到结果 |
| AC-05-3 | LLM 全部失败 | 重算 | factors 中 form/squad enabled=false + missing_reason；主判断仍能给（基于 fixture 因子）或 `info_insufficient` |
| AC-05-4 | bronze 无该 match_id | GET | 404 |
| AC-05-5 | 比赛 needs_review（fixture 验证失败） | GET | 返回 `phase='needs_review'`；UI 显示"比赛信息无法验证"+ 引导用户提交 win007 matchId |
| AC-05-6 | 重算耗时 > 30s | GET | 30s 后前端切到"基础视图"（仅显示 match 元信息）+ 保留后台继续重算 |
| AC-05-7 | 已付费 dashboard 数据完整加载 | UI 渲染 | 显示 lean、confidence_level、风险数、因子折叠、强/弱/不足证据三栏、6 维 chips、自由提问框 |

#### UC-06 6 维快捷追问（模板路径）

| ID | Given | When | Then |
|---|---|---|---|
| AC-06-1 | 已付费 + 比赛 dashboard 加载完毕 | 点击 chips 任一维度 | 后端 < 1s 返回 FootballOsintAnswer（无 LLM 调用） |
| AC-06-2 | 该维度对应因子组的 enabled 数 = 0 | 后端处理 | 返回 `info_insufficient`，answer 文本含原因 |
| AC-06-3 | 友谊赛 + dimension=player | 后端处理 | 返回"信息不足，原因：友谊赛阵容透明度低" |
| AC-06-4 | 6 个 dimension 各点一次 | 测试 | 全部返回结构化结果；reasons ≤ 3；含 evidence_ids |
| AC-06-5 | 模板回答中包含禁词 | 文案审计 | 测试失败 |

#### UC-07 自由提问（LLM + 降级）

| ID | Given | When | Then |
|---|---|---|---|
| AC-07-1 | 已付费 + 问题 "本场角球会偏多吗" | POST `/answer` | LLM 调用成功；返回 reasons ≤ 3 条、含 ≥ 1 个 `[ev_xxx]` 引用 |
| AC-07-2 | LLM 编造证据 ID（如 `[ev_999]`） | 后端校验 | 引用合法性失败 → 降级到模板路径，answer 前缀"详细解读暂不可用" |
| AC-07-3 | LLM 60s 超时 | 后端处理 | 降级到模板路径（dimension='risk' 兜底） |
| AC-07-4 | LLM 限流（503） | 后端处理 | 降级到模板路径 |
| AC-07-5 | 信号量满（4 并发已用完） | 第 5 个请求 | 排队 ≤ 30s；超时返回 503 + 文案"系统繁忙" |
| AC-07-6 | 问题 "今天晚饭吃什么" | `_is_match_related` 判定 | 返回 `related=false, answer='问题与比赛无关'`；不调 LLM |
| AC-07-7 | 问题 < 2 字符 | 前端拦截 | 不发请求；显示"请输入完整问题" |
| AC-07-8 | 校验集 50 题人工标注 | 评估 `_is_match_related` | F1 ≥ 0.85 [blocked-by 校验集构建] |

#### UC-08 信息不足展示

| ID | Given | When | Then |
|---|---|---|---|
| AC-08-1 | 启用因子数 ≤ 1 | 后端 `_predict()` | `prediction.lean='info_insufficient'`，summary 含"证据不足，无法形成方向倾向" |
| AC-08-2 | 启用因子均值 confidence < 0.30 | 同上 | 同上 |
| AC-08-3 | 计算 missing_data | 后端 | 返回 list[str]，每条来自 disabled 因子的 missing_reason，按 group 去重 |
| AC-08-4 | 前端显示信息不足 | UI | **不显示** 主队/平/客队箭头；显示大字"信息不足"+ confidence_level（多半 L4） |
| AC-08-5 | 前端显示信息不足 | UI | 显示 missing_data 清单（最多 5 条）+ "我有补充信息"入口 |
| AC-08-6 | 已付费用户提交补充 URL（白名单内） | 触发 | UC-05 重算（异步）；UI 状态切换到 phase='running' |
| AC-08-7 | 访客遇到 info_insufficient | UI | 与已付费一致显示，并附"开通后可手动补充信息"引导 |

#### UC-09 已付费用户邀请新用户

| ID | Given | When | Then |
|---|---|---|---|
| AC-09-1 | 已付费 + 当月已生成 < 5 邀请码 | POST `/invitation/create` | 200 返回新邀请码 + 分享链接 + 有效期 30 天 |
| AC-09-2 | 当月已生成 = 5（默认配额） | POST | 429 `E_QUOTA_EXCEEDED` |
| AC-09-3 | 已注册未付费用户 | POST | 403 `E_FORBIDDEN` |
| AC-09-4 | 邀请码生成 | 字符集 | 仅含 `[A-Z2-9]`（去除易混 0/O/1/I/L），长度 12 |
| AC-09-5 | 已付费用户 GET `/invitation/list` | 返回 | 含我生成的所有邀请码；每条带 status / used_by_masked / used_at |
| AC-09-6 | 邀请码碰撞（同串）| 后端处理 | 重试 3 次；3 次都碰撞 → 500 |

#### UC-10 admin CLI 批发邀请码 / 付费码

| ID | Given | When | Then |
|---|---|---|---|
| AC-10-1 | ADMIN_TOKEN 正确、CLI `invite_codes --count 50` | 执行 | 数据库新增 50 条 invitation，输出 CSV，audit_log 写入 `admin.bulk_create_invite` |
| AC-10-2 | ADMIN_TOKEN 错误 | 执行 | CLI 退出码 1 + stderr "Unauthorized"；不写数据库 |
| AC-10-3 | --count 1500 | 执行 | 拒绝；提示"单次创建上限 1000" |
| AC-10-4 | `payment_codes --count 100 --validity-days 90` | 执行 | 100 条 activation_code，expires_at = now()+90d |
| AC-10-5 | `list_users --paid` | 执行 | 返回所有持有 full_analysis entitlement 的 user 列表 |
| AC-10-6 | `set_threshold --key info_insufficient_factor_min --value 1` | 执行 | 配置写入；下次 _predict 用新值 |

---

### 2. 负向（Negative）AC（防御性测试）

| ID | Given | When | Then |
|---|---|---|---|
| NEG-1 | 攻击者构造 SQL 注入 invite_code (`'; DROP TABLE`) | 提交 | 校验失败 `E_INVITE_INVALID`；表无变化；ORM 参数化查询 |
| NEG-2 | 用户在 question 里塞 `http://127.0.0.1:8000/api/admin` | answer 流程 | URL 校验拒绝（已实现 SRF 修复） |
| NEG-3 | 用户在 question 里塞 `http://169.254.169.254/...` | answer 流程 | URL 校验拒绝 |
| NEG-4 | 客户端伪造已支付提示 | 后端 entitlement 校验 | 凭 entitlement 表，不信前端；权限不开通 |
| NEG-5 | 已付费 user A 用另一已付费 user B 的邀请码 | 注册 | 拒绝（已注册不能再注册）+ 引导登录 |
| NEG-6 | 未付费用户调 `/api/football/osint/dashboard?match=X` 试图绕过权限 | 后端 | 服务端按 entitlement 过滤字段；不返回 evidence/factors/reasons |
| NEG-7 | 攻击者在 nickname / question 里塞 XSS（`<script>`） | 后端入库 + 前端渲染 | 入库不转义但前端 React 默认转义；测试用 OWASP 字典扫 |
| NEG-8 | 用户访问 `/api/football/osint/jobs/../../etc/passwd` | path 校验 | job_id 必须匹配 `^fo_\d{8}_[a-f0-9]{10}$`；其他返回 404 |

---

### 3. 非功能 AC（NFR）

| ID | 要求 | 验证方式 |
|---|---|---|
| NFR-1 | 已付费用户从打开赛事到看到主判断 < 5s（缓存命中 < 200ms） | 上线前用 5 个比赛测；上线后埋点 P95 |
| NFR-2 | OSINT pipeline P95 < 30s（无 lp-fetch-md），P99 < 60s（含） | 自动化测试 + 上线后埋点 |
| NFR-3 | 月度可用性 99% | 自建 uptime 监控 |
| NFR-4 | 单进程内存 < 1.8GB（systemd MemoryMax 强制） | systemd 限制 + 监控 |
| NFR-5 | bronze + SQLite 每日备份；保留 7 天；恢复演练 1 次/季度 | rsync cron + 手动演练 |
| NFR-6 | 全 API HTTPS（含 nginx） | curl -I 检查；HSTS header |
| NFR-7 | 速率限制：单 IP 20 写/min（已实现） | 自动化测试 |
| NFR-8 | URL 抓取经白名单 + DNS 公网检查（已实现） | 自动化测试（NEG-2/3） |

---

### 4. Definition of Done（v1 上线前每个 M 项必须满足）

逐条 M 项需求只有同时满足以下 12 项才能标记 done：

| # | 项 | 检查方式 |
|---|---|---|
| 1 | 代码已合并到 main 且通过 review | git log + PR review |
| 2 | 单元测试 + 集成测试覆盖 happy + 主备选 + 主异常路径 | pytest / vitest 覆盖率 ≥ 70% |
| 3 | 对应的 AC 全部测通 | AC checklist 标记 |
| 4 | 对应的 NEG / NFR AC 测通 | 同上 |
| 5 | 错误码命名遵循 `E_*` 规范、用户文案脱开发者文案 | code review |
| 6 | 日志含 request_id（GAP-A-8 / NFR-3） | grep 验证 |
| 7 | 文案审计扫描通过（无禁词） | CI 自动化 |
| 8 | 不破坏现有自动化测试（pytest + vitest 全过） | CI 通过 |
| 9 | runbook / README 中有该功能的故障排查路径 | 文档存在 |
| 10 | 有埋点（如适用）：关键事件计数 | 日志/SQLite 落点 |
| 11 | 数据库变更有 migration 脚本（即使 SQLite 也要） | sql/ 目录 |
| 12 | 安全 review：是否引入新的输入边界、是否需要 rate limit、是否需要 entitlement 校验 | checklist 自审 |

### 5. v1 上线 Rollout Checklist（RQ-I-1 一次性 12 项）

仅一次（不是每个 M 项）：

| # | 项 | 检查 |
|---|---|---|
| 1 | 用户协议、隐私政策已上线 | 链接可访问 |
| 2 | 文案审计 sweep（全产品） | CI + 人工 |
| 3 | 备份脚本运行 7 天可恢复 | 演练成功 |
| 4 | runbook 简版完成（DeepSeek 503 / 数据源全挂 / bronze 失败） | 文档存在 |
| 5 | SLO 99% 监控就绪 | uptime 仪表板 |
| 6 | 关键埋点就绪：邀请-注册-付费转化、研判完成率、信息不足触发率 | 数据可查 |
| 7 | admin CLI 就绪 + ADMIN_TOKEN 配置 | dry-run 通过 |
| 8 | DeepSeek 限额监控（成本告警） | 阈值配置 |
| 9 | 全链路 HTTPS（含 nginx + cert） | 证书有效 |
| 10 | 备份恢复演练 1 次成功 | 文档 |
| 11 | 5 人内测覆盖 UC-01/03/05/06/07/08（核心路径） | 反馈表 |
| 12 | 所有 GAP-A 必补项（17 条）已实现 | gap-audit 标记 |

---

## Assumptions

- 假设 SQLite 在中等并发（< 50 写/s）下满足事务一致性；如未来量级超过则迁 PostgreSQL（v2 决策）。
- 假设访客的 GET dashboard 完全经服务端字段过滤（不依赖前端隐藏）；测试 NEG-6 强制验证。
- 假设 LLM "引用合法性"校验用 regex `\[ev_\d{3}\]` 匹配；evidence_id 格式必须严格遵循（已实现）。

---

## Constraints

- 自动化测试不能依赖外网（DeepSeek、win007、example.com）：所有外部调用 mock；URL 安全检查测试用 `FOOTBALL_OSINT_SKIP_DNS_CHECK=1`。
- AC 测试要求"5 人内测"是质性标准而非数字硬指标；如内测发现 critical bug，按 1 周缓冲再上线。

---

## Open Questions

| ID | 问题 | 影响 | 默认建议（如无答复） |
|---|---|---|---|
| Q12 | 邮件服务商 | UC-01/UC-02 | Resend (开发友好、免费额度足够 v1) |
| Q26 | admin CLI 鉴权 | UC-10 / AC-10-2 | `ADMIN_TOKEN` 在 `.env`；CLI 仅服务器本地能跑（外部 SSH 不能直接调） |
| Q14 实际值 | 信息不足阈值 | AC-08-1/2 | 启用因子数 ≤ 1 或 均值 < 0.30；admin CLI 可调 |
| Q17 | 未付费"强证据数量"显示形式 | UC-04 / AC-04-3 | 不显示数量也不显示标题，只显示 lean 与"开通查看完整证据"；最简最克制 |
| Q22 | 邀请码/付费码默认有效期 | RQ-G-2 | 邀请码 30d / 付费码 90d 兑换有效期 / 兑换后权益 30d |
| Q21 | 用户协议/隐私政策模板 | NFR-8 / Rollout-1 | 通用 termly 模板自改，找朋友审一遍；上线前由产品负责人最终确认 |

---

## 推荐下一步

阶段 4 收尾。进阶段 5：**requirements-packager**（任务 #19）打包 PRD v1。

PRD v1 文件目标位置：`docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md`（与 redo 目录平级，作为正式 spec）。

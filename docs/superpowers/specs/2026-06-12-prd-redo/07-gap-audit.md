---
phase: 3
artifact: requirements-gap-audit
date: 2026-06-13
status: draft
depends_on:
  - 04-proto-requirements.md
  - 06-elicitation-findings.md
---

# 世界球花 — 需求缺口审计

## Summary

把 **94 条草稿**（86 + 8 新增 RQ-NEW-*）按工程交付完整性 14 大类做扫描，找出 **absent / weak / deferred** 三类缺口。本审计**不**重排优先级（那是 MoSCoW 的工作）；本审计只关心"如果照这 94 条做，工程师还会卡在哪里"。

发现汇总：

| 状态 | 计数 | 含义 |
|---|---|---|
| **GAP-A 缺失** | 17 | 主流场景但完全没条目 |
| **GAP-W 弱写** | 11 | 有条目但表达模糊或测试不出来 |
| **GAP-D 显式延后** | 6 | spec / 决策已说 v1.5+ 做的，备案登记 |
| **DUP 重复** | 3 | 多条草稿表达同一需求 |
| **CONFLICT 冲突** | 4 | 草稿之间或与决策相互矛盾 |

---

## Findings

### 1. 14 大完整性类别扫描

| # | 类别 | 覆盖度 | 关键缺口 |
|---|---|---|---|
| 1 | Actors（角色） | ✅ 充分 | 仅缺"系统角色"（cron、admin CLI），见 GAP-A-1 |
| 2 | Triggers（触发） | ⚠️ 弱 | 缺采集触发条件、缓存失效触发条件 GAP-A-2 |
| 3 | Preconditions（前置条件） | ⚠️ 弱 | 大部分需求没写前置；如 RQ-A-13 付费码兑换前置 GAP-W-1 |
| 4 | Postconditions（后置条件） | ⚠️ 弱 | 邀请码使用、登录态写入、缓存淘汰等后置缺写 GAP-W-2 |
| 5 | Data（数据模型） | ✅ 较充分 | 缺索引、唯一约束、关联完整性约束 GAP-A-3 |
| 6 | Validation（输入校验） | ⚠️ 弱 | 邀请码格式、付费码格式、邮箱/手机号校验未明示 GAP-A-4 |
| 7 | Permissions（权限） | ✅ 充分 | 仅 admin 权限未定义 GAP-A-5 |
| 8 | Error handling（错误处理） | ⚠️ 弱 | 错误码、错误文案、降级路径多处缺失 GAP-A-6 |
| 9 | NFR（非功能） | ⚠️ 弱 | 仅 8 条，缺可用性、可观测性、可备份 GAP-A-7~10 |
| 10 | Support/Ops（运维支持） | ❌ 缺 | 完全没有运维相关条目 GAP-A-11~13 |
| 11 | Reporting（报表） | ⚠️ 弱 | 业务指标未定义 GAP-A-14 |
| 12 | Auditability（可审计） | ⚠️ 弱 | RQ-A-19 一句带过，无字段定义 GAP-W-3 |
| 13 | Rollout（上线） | ❌ 缺 | 没有任何上线前置条件 GAP-A-15 |
| 14 | Maintenance（持续维护） | ❌ 缺 | 数据归档、密钥轮换、依赖升级未涉及 GAP-A-16~17 |

---

### 2. GAP-A：缺失（17 条）

| ID | 缺失条目（建议补） | 类别 | 影响 | 阶段 |
|---|---|---|---|---|
| **GAP-A-1** | 系统角色定义：collector cron、merge cron、admin CLI 的标识与职责 | Actors | 工程师不知道哪些不是用户触发 | v1 必补 |
| **GAP-A-2** | 数据源采集触发条件：定时（每 N 小时）/ 事件（用户首次访问比赛）/ 手动；缓存失效条件 | Triggers | 当前 spec 写"6h 缓存"但触发哪条逻辑没写 | v1 必补 |
| **GAP-A-3** | 数据库约束：邀请码唯一索引、付费码唯一索引、user.email 唯一约束、entitlement(user_id, type) 唯一约束 | Data | 数据竞态条件 | v1 必补 |
| **GAP-A-4** | 输入校验规则：邀请码 = `[A-Z0-9]{8,16}`；付费码 = `[A-Z0-9]{12,24}`；邮箱 RFC5322；手机号 = `1[3-9]\d{9}`（中国） | Validation | XSS、注入、误用风险 | v1 必补 |
| **GAP-A-5** | admin 角色权限：批发邀请码、批发付费码、查看用户列表、封禁用户；通过 CLI（无后台 UI）操作 | Permissions | 没有运营触手 | v1 必补 |
| **GAP-A-6** | 错误码命名规范：`E_INVITE_INVALID` / `E_INVITE_USED` / `E_CODE_EXPIRED` / `E_QUOTA_EXCEEDED` 等；用户文案 vs 开发者文案分离 | Error handling | 前端无统一处理 | v1 必补 |
| **GAP-A-7** | 可用性目标：v1 单机部署不强求 99.9%；目标 99% / 月（≈ 7.2 小时停机预算） | NFR | 没有 SLO 即没有"在线/离线"判定 | v1 必补 |
| **GAP-A-8** | 可观测性：结构化日志（JSON）、按 request_id 串联、关键事件埋点（采集成功率、LLM 失败率、付费码兑换率） | NFR | 上线后看不到健康状态 | v1 必补 |
| **GAP-A-9** | 备份与恢复：bronze JSON / SQLite 至少每天 1 次 rsync 到本地或 S3；恢复演练 1 次 | NFR | 单机磁盘故障 = 数据全失 | v1 必补 |
| **GAP-A-10** | 国密/HTTPS：所有 API 走 TLS；自签证书 vs Let's Encrypt 选择 | NFR | 微信小程序 v1.5 强制要求 HTTPS | v1 推荐 |
| **GAP-A-11** | 故障响应预案：服务进程挂掉 / DeepSeek 503 / 数据源全挂时分别如何处理 | Ops | 没有 runbook | v1 必补 |
| **GAP-A-12** | 日志查阅与故障排查 SOP：用户报错后 5 分钟内定位的最低能力 | Ops | 单人响应慢易丢用户 | v1 必补 |
| **GAP-A-13** | 容量规划：单机 2GB 内存、磁盘多少够用、bronze JSON 累积速度估算 | Ops | 失控膨胀 | v1 必补 |
| **GAP-A-14** | 业务指标：邀请-注册-付费转化率、研判完成率、追问发起率、留存（D1/D7/D30）、信息不足触发率 | Reporting | 没法判断是否成功 | v1 必补 |
| **GAP-A-15** | 上线前置条件清单（rollout checklist）：用户协议 / 隐私政策 / 文案审计 / 备份就绪 / SLO 定义 / runbook 等 | Rollout | 漏一项可能监管处罚 | v1 必补 |
| **GAP-A-16** | 密钥轮换：LLM_API_KEY / JWT secret / 微信支付商户号密钥（v1.5）的轮换周期 | Maintenance | 长期密钥泄露风险 | v1.5 |
| **GAP-A-17** | 数据归档与删除：bronze 文件 6 个月以上的处理（归档/删除/保留）；用户主动注销后数据保留期 | Maintenance | 合规要求 + 性能 | v1 推荐 |

---

### 3. GAP-W：弱写（11 条）

| ID | 现条目 | 弱在哪 | 修订建议 |
|---|---|---|---|
| **GAP-W-1** | RQ-A-13 付费码兑换流程 | 没写前置：用户必须已登录、未持有同类 entitlement | 加 "前置：user 已登录且 entitlement(user_id, 'full_analysis') 不存在" |
| **GAP-W-2** | RQ-A-7 邀请注册 | 没写后置：邀请码标记 used、记录 used_by/used_at、新用户 entitlement 默认空 | 加 "后置：invitation.status='used'，记录 used_by 和 used_at；新用户无 entitlement" |
| **GAP-W-3** | RQ-A-19 审计记录 | 太空，没字段、没存储 | 拆为：审计字段（user_id, action, payload_hash, ip, ua, ts），落 SQLite `audit_log` 表，保留 6 个月 |
| **GAP-W-4** | RQ-B-9 `_is_match_related` 召回 ≥ 90% | 没说"准确率"和"召回"哪个 90%；样本来源 | 改为 "F1 ≥ 0.85（基于人工标注 50 题，正负比 1:1）" |
| **GAP-W-5** | RQ-B-2 缺证据信息不足阈值 | "因子启用数 ≤ 1 或均值 < 0.30" 是 06-findings 推断，待校验 | 修订为 "v1 默认阈值：启用因子数 ≤ 1 或所有启用因子置信度均值 < 0.30；阈值在 admin CLI 可调" |
| **GAP-W-6** | RQ-B-7 LLM 路径自由提问 | 没说 prompt 模板、不能编造的硬约束如何强制 | 拆为：(a) prompt 模板必须显式列证据 ID 列表；(b) LLM 输出必须经"引用合法性校验"（reasons 中的 ev_xxx 必须存在于上下文）；(c) 校验失败则降级模板 |
| **GAP-W-7** | RQ-D-5 缓存策略 | 缺"开赛前 6h 内失效"规则（RQ-NEW-8） | 加 "开赛时间 ≤ 6h 时，所有缓存强制重算" |
| **GAP-W-8** | RQ-D-14 比赛无法验证返回 needs_review | 没定义"无法验证"的判定（缺 fixture.* 证据？多源都失败？） | 拆为：(a) fixtures_public adapter 失败 + 无任何 win007 抓取成功 → needs_review；(b) 用户输入字段缺失（队名空）→ 拒绝请求 |
| **GAP-W-9** | RQ-E-11 文案规则 | "倾向、压力、风险、证据强弱"是允许；禁词单不全 | 列禁词表：必胜、稳赢、推荐投注、胆、串、料、内部消息、专家推单、跟单等 |
| **GAP-W-10** | RQ-F-4 内存上限 2GB | 没说怎么测、超限怎么办 | 加 "通过 systemd 的 MemoryMax=1.8G 限制；超限自动重启；监控告警" |
| **GAP-W-11** | RQ-F-7 LLM 超时和降级 | 没数值 | 加 "翻译 30s / 摘要 30s / 分类 30s / 问答 60s；超时降级到模板路径" |

---

### 4. GAP-D：显式延后（6 条登记）

| ID | 条目 | 延后到 |
|---|---|---|
| GAP-D-1 | 微信小程序登录（unionid + session_key） | v1.5 |
| GAP-D-2 | 微信支付接入 | v1.5 |
| GAP-D-3 | 订阅消息 | v1.5 |
| GAP-D-4 | 跨端身份合并 | v1.5 |
| GAP-D-5 | 分享海报 | v1.5 |
| GAP-D-6 | 赛后回看与对照（RQ-NEW-4） | v2 |

---

### 5. DUP：重复（3 条）

| ID | 重复 | 处理 |
|---|---|---|
| **DUP-1** | RQ-A-15（付费码不出现在前端 / URL / 日志）+ GAP-A-4（输入校验）+ GAP-W-3（审计） | 拆得更细：RQ-A-15 → 仅说"前端不持久化、URL 不携带、日志脱敏"；输入校验单列；审计单列 |
| **DUP-2** | RQ-D-12 _JOBS LRU + RQ-D-13 ANSWER_SEMAPHORE 都属"已实现的资源治理" | 合并到 RQ-D-12 一条："job 缓存 + 并发控制使用 LRU+TTL+Semaphore，配置项见 routes.py" |
| **DUP-3** | RQ-B-6（chips 模板）+ RQ-B-7（自由 LLM）+ Q6 决策（混合）三处描述同一逻辑 | 保留 RQ-B-6/B-7 + GAP-W-6 修订；删除 Q6 决策后的重复表述 |

---

### 6. CONFLICT：冲突（4 条）

| ID | 冲突 | 双方 | 解决 |
|---|---|---|---|
| **CONFLICT-1** | "未付费用户能否看简单倾向" | Q2 决策（能）vs RQ-B-2（缺证据时不显示倾向） | 一致化：未付费看到的"简单倾向"也走 RQ-B-2 阈值；缺证据时显示"信息不足"（即使是公开摘要） |
| **CONFLICT-2** | 邀请码默认有效期 | RQ-G-2 写"30 天" vs Q22 待决 | 锁 30 天；admin CLI 可调；写入 GAP-A-5 admin 权限内 |
| **CONFLICT-3** | unionid 字段是否在 v1 数据模型出现 | Q4（小程序入 v1.5）vs RQ-A-2（identity 表含 unionid） | 一致化：identity 表保留 unionid 字段为 nullable；v1 不写入；v1.5 启用 |
| **CONFLICT-4** | 短信验证码 | RQ-A-16（须支持手机号）vs GAP-A-15 / Q12（v1 仅邮箱） | 修订 RQ-A-16："v1 仅邮箱，手机号字段保留为 nullable，v1.5 启用" |

---

## Structured Outputs

### 7.1 修订后的需求基线（94 → 100 条目录）

```
A. 用户体系与权限     19 条 + 0 新 = 19   (RQ-A-16 修订)
B. 核心研判          16 条 + 1 新 = 17   (RQ-B-2/B-7 修订；新增 RQ-B-17 来自 RQ-NEW-3)
C. 证据系统          10 条 + 1 新 = 11   (新增 RQ-C-11 来自 RQ-NEW-1)
D. 后端 OSINT       14 条 + 1 新 = 15   (RQ-D-5 修订；新增 RQ-D-15 来自 RQ-NEW-5)
E. Web UI           12 条 + 2 新 = 14   (RQ-E-11 修订；新增 RQ-E-13 来自 RQ-NEW-7、RQ-E-14 来自 RQ-NEW-6)
F. 非功能           8 条 + 8 GAP = 16   (RQ-F-2/F-4/F-7 修订)
G. 业务规则          7 条 + 0 新 = 7    (RQ-G-2 锁定 30 天)
H. 运维（新增）       0 + 8 GAP = 8     (来自 GAP-A-11~17 + GAP-A-2)
I. Rollout（新增）    0 + 1 GAP = 1     (来自 GAP-A-15)
———————————————————————————————————
合计                                108 条
```

> 实际 RQ-NEW-2（多场对比）和 RQ-NEW-4（赛后回看）放 v2，不进 v1 基线。
> RQ-NEW-8 已合并到 GAP-W-7。

### 7.2 新增 RQ ID 化表

| 新 ID | 来源 | 描述 | 归类 |
|---|---|---|---|
| RQ-B-17 | RQ-NEW-3 | LLM 自由提问回答必须引用证据 ID（[ev_xxx]）；不能引用则降级 | B |
| RQ-C-11 | RQ-NEW-1 | "信息不足"状态须列出"缺什么数据"清单（如"缺首发"、"缺天气"、"缺基本面"） | C |
| RQ-D-15 | RQ-NEW-5 | 后端访问海外数据源时支持代理配置 + retry（默认 3 次，指数退避） | D |
| RQ-E-13 | RQ-NEW-7 | 文案中明示产品边界（"不是预测，是研判"；"我们不知道时会说"） | E |
| RQ-E-14 | RQ-NEW-6 | 分享场景下不展示用户身份 / 头像 / 昵称（v1.5 分享海报） | E |

### 7.3 NFR 加固表（FR-F 由 8 → 16 条）

| 新 ID | 描述 | 验收 |
|---|---|---|
| RQ-F-9 | 月度可用性目标 99% | 自建 uptime 监控 |
| RQ-F-10 | 结构化日志（JSON）+ request_id 追踪 | 日志中 grep request_id 可串完整调用链 |
| RQ-F-11 | 关键埋点：采集成功率、LLM 失败率、付费码兑换率、研判完成率 | dashboard 可视 |
| RQ-F-12 | 备份：bronze + SQLite 每天 rsync；保留 7 天 | 恢复演练 1 次 |
| RQ-F-13 | 全 API HTTPS（含 nginx 配置） | curl -I 检查 |
| RQ-F-14 | 容量上限：bronze 单文件 ≤ 1MB；SQLite ≤ 5GB；超限告警 | 监控规则 |
| RQ-F-15 | 数据归档：bronze 6 个月以上压缩归档到独立目录 | cron 脚本 |
| RQ-F-16 | 注销用户数据 30 天内删除（合规） | 删除任务 |

### 7.4 运维需求（新类别 H）

| 新 ID | 描述 |
|---|---|
| RQ-H-1 | systemd unit + MemoryMax=1.8G + 自动重启 |
| RQ-H-2 | runbook：DeepSeek 503、数据源全挂、bronze 写入失败 |
| RQ-H-3 | 故障排查 SOP：用户报错 5 分钟内定位 |
| RQ-H-4 | admin CLI：批发邀请码 / 批发付费码 / 列用户 / 封禁用户 / 调阈值 |
| RQ-H-5 | 数据采集触发：cron 每 6 小时全量、用户首次查询时按需 |
| RQ-H-6 | 缓存失效触发：开赛前 6h 强制重算（GAP-W-7） |
| RQ-H-7 | 错误码命名 + 文案分离 |
| RQ-H-8 | 数据库约束（GAP-A-3） |

### 7.5 Rollout 需求（新类别 I）

| 新 ID | 描述 |
|---|---|
| RQ-I-1 | v1 上线 checklist：用户协议 / 隐私政策 / 文案审计 / 备份就绪 / runbook / SLO 定义 / 监控埋点 / admin CLI 就绪 / DeepSeek 限额监控 / HTTPS / 备份恢复演练 ✅ |

---

## Assumptions

- 自我代理的 06-findings 强度已知偏低；本审计基于"假定 06 是真"做完整性检查。如真实访谈推翻 USP，本审计输出全部失效。
- "v1 单机 2GB 内存 + 文件系统"是已锁定约束；如改 K8s/独立 DB，运维需求重写。
- DeepSeek API 在 v1 期间稳定；如改用本地 ollama，RQ-F-7 / RQ-F-11 数值要重定。

---

## Constraints

引用 04-proto-requirements § Constraints；本审计未发现新约束。

---

## Open Questions

继续阶段 2 的 11 个 + 阶段 3 新增：

| 新 QID | 问题 | 阶段 |
|---|---|---|
| Q23 | runbook 写在哪（仓库 / Notion / 私有 wiki） | 阶段 4 |
| Q24 | 监控/告警工具：用 systemd journald + 自写脚本，还是接入 Sentry / Grafana | 阶段 4 |
| Q25 | 备份目标：本地另一目录 / 异地服务器 / S3 兼容存储 | 阶段 4 |
| Q26 | admin CLI 鉴权：单用户硬编码 token / 文件系统权限 / SSH only | 阶段 4 |
| Q27 | "信息不足"阈值的真实校准用户群（5 人或上线后 50 人） | v1 上线后 |

---

## Recommended Next Skill

**moscow-prioritisation**（任务 #16）：

- 输入：108 条修订后基线
- 输出：M / S / C / W 四档分类
- 关键决策点：
  - 哪些"GAP-A 必补"放 M（绝大多数）
  - 哪些 GAP-W 留到 v1.5（如 LLM 引用合法性校验，工程量稍大）
  - 哪些 NFR 是 M（备份、HTTPS）哪些是 S（结构化日志）
- v1 工程量初估：M ≈ 60 条 → 4-6 周（与 ASM-6 一致）

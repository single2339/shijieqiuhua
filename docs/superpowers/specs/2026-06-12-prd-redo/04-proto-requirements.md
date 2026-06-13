---
phase: 2
artifact: proto-requirements
date: 2026-06-12
status: draft
depends_on:
  - 01-problem-framing.md
  - 02-stakeholder-analysis.md
  - 03-value-proposition.md
  - decisions.md
---

# 世界球花 — 草稿需求清单（Proto-Spec）

## Summary

把以下原料规整成结构化、有 ID 的草稿需求条目，**不做优先级排序，不做验收标准**：

- spec：`2026-06-11-shijieqiuhua-frontend-design.md`、`2026-06-11-shijieqiuhua-osint-football-redesign.md`
- 当前代码状态（`backend/football_osint/`、`frontend/src/shijieqiuhua/`、`backend/main.py`）
- 阶段 1 决策（`decisions.md` Q1-Q6）
- 价值主张 USP（U-1 证据链 + U-2 不编造）

每条需求 ID 形如 `RQ-A-N`：A = 类别字母，N = 序号。下一阶段（缺口审计 / MoSCoW）会复用这些 ID。

---

## Findings

### 来源覆盖度
- spec 覆盖：用户体系 / 核心组件 / 数据流 / 微信小程序 / 后端 OSINT 流水线
- 代码现状：MatchQuestionCard 1 个组件 / `/api/football/osint/{predict-sync,jobs,answer}` 已实现 / 访问控制被删 / 685 行 pipeline.py 单文件
- 决策锁定：付费码、Web 优先、完整 spec 后端拆分、模板+LLM 混合追问

### 草稿条目分布
- 共 **86 条**草稿需求
- 用户体系（A）= 19 条
- 核心研判（B）= 16 条
- 证据系统（C）= 10 条
- 后端 OSINT 流水线（D）= 14 条
- Web UI（E）= 12 条
- 非功能（F）= 8 条
- 业务规则（G）= 7 条

---

## Structured Outputs

### A. 用户体系与权限（19 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-A-1 | 系统须维护内部用户主表 `user`（id, 昵称, 头像, 创建时间, 权限等级） | spec frontend §用户体系 | — |
| RQ-A-2 | 系统须维护第三方身份表 `identity`（provider, openid, unionid, 手机号, 邮箱） | spec frontend §用户体系 | v1 仅启用 email/手机号；微信 unionid 字段在 v1.5 启用 |
| RQ-A-3 | 系统须维护服务端 `session` 表 | spec frontend §用户体系 | session 实现细节（jwt vs db）待定 |
| RQ-A-4 | 系统须维护邀请码表 `invitation`（code, inviter, status, expires_at, used_by, registered_at） | spec frontend §邀请注册 | — |
| RQ-A-5 | 系统须维护付费码表 `activation_code`（code, status, granted_to, source_order, redeemed_at） | spec frontend §付费与付费码 + Q1 决策 | 是否要 source_order：v1 没有 order，建议保留字段为 nullable |
| RQ-A-6 | 系统须维护权益表 `entitlement`（user_id, type, granted_at, expires_at） | spec frontend §权益分层 + Q8 待决 | 期限模式（永久 vs 月度）待 Q8 |
| RQ-A-7 | 注册流程：用户必须提交有效邀请码才能创建正式账号 | spec frontend §邀请注册 | — |
| RQ-A-8 | 邀请码默认单次使用；管理员可标记为可多次/限时 | spec frontend §邀请注册 | "管理员"在 v1 是 CLI 脚本 / admin UI 待 Q7 |
| RQ-A-9 | 邀请码记录邀请人、被邀请人、注册时间，仅用于增长统计 | spec frontend §邀请注册 + 红线 R5 | — |
| RQ-A-10 | 邀请码不影响预测结论或证据展示（红线 R5） | 决策 R5 | — |
| RQ-A-11 | 已付费用户可生成新的邀请码 | spec frontend §权限分层 | 单用户邀请码月配额待 Q11 |
| RQ-A-12 | 已注册未付费用户不能生成邀请码 | spec frontend §权限分层 | — |
| RQ-A-13 | 付费码兑换：用户输入码 → 服务端校验 → 标记 used → 写入 entitlement | spec frontend §付费与付费码 + Q1 | — |
| RQ-A-14 | 付费码必须一次性使用，兑换后绑定到具体 user_id | spec frontend §支付安全规则 | — |
| RQ-A-15 | 付费码不能出现在前端源码、URL 明文长期存储或日志明文（仅服务端校验） | spec frontend §支付安全规则 | 日志脱敏方案待补 |
| RQ-A-16 | 系统须支持手机号登录 | spec frontend §Web 登录 | 短信验证码服务商：阿里云？腾讯云？待 Q12（新增） |
| RQ-A-17 | 系统须支持邮箱登录（密码 / 验证码 二选一） | spec frontend §Web 登录 | 邮件服务商：SMTP / SES / 阿里云邮件待 Q12（新增） |
| RQ-A-18 | 系统须保留扩展字段为 v1.5 微信小程序登录留口（identity.provider 可填 'wechat_mp'） | Q4 决策 | — |
| RQ-A-19 | 注册/登录/兑换/邀请使用都必须有审计记录 | spec frontend §支付安全规则 | 审计存储位置待 Q12（新增） |

### B. 核心研判（16 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-B-1 | 已付费用户在赛事卡上看到"默认主判断"（赛前胜平负倾向 + 可信度 + 风险数量） | spec frontend §MatchQuestionCard | "可信度"展示形式（百分比/L1-L4）待 Q13（新增） |
| RQ-B-2 | 缺证据时，默认主判断必须显示"信息不足"，不显示倾向（红线 R2 + Q3） | 决策 R2 + Q3 | "信息不足"阈值：因子置信度均值 < 0.25？待 Q14（新增） |
| RQ-B-3 | 默认主判断包含"主判断 + 可信度等级 L1-L4 + 风险数量"三项 | spec frontend §MatchQuestionCard 默认主判断 | — |
| RQ-B-4 | 已付费用户可使用自由提问（输入框） | spec frontend §继续问输入框 | — |
| RQ-B-5 | 已付费用户可点击 6 维快捷追问 chips：半场 / 红黄牌 / 角球 / 进球数 / 球员 / 风险 | spec frontend §快捷问题 chips | — |
| RQ-B-6 | 6 维 chips 走"模板路径"：检索证据 → 模板生成 → 返回结构化判断（Q6） | 决策 Q6 | — |
| RQ-B-7 | 自由提问走 LLM 路径：调 `/api/football/osint/answer` → DeepSeek → 返回 judgment + reasons + confidence_level | 决策 Q6 + 现有 routes.py | — |
| RQ-B-8 | LLM 限流或失败时，自由提问降级到模板路径 + 提示"详细解读暂不可用" | 决策 Q6 + 价值风险 RISK-5 | — |
| RQ-B-9 | 自由提问必须先判定"是否与本场比赛相关"，无关问题不触发分析 | 现有 `_is_match_related` | "命中召回率 ≥ 90%"作为非功能，列入 F |
| RQ-B-10 | 输入框自动绑定当前 match_id，用户无需重复描述比赛上下文 | spec frontend §继续问输入框 | — |
| RQ-B-11 | 任意用户问题/追问必须返回：判断、置信等级（L1-L4）、推理理由（≤ 3 条）、关联证据 ID | 现有 `FootballOsintAnswer` | — |
| RQ-B-12 | 推理理由（reasons）必须是因子驱动 + 不确定性混合，不能是 LLM 自由文本编造 | 红线 R2 + 现有 `_answer_from_job` | "因子驱动"在模板路径已实现；LLM 路径需要约束 |
| RQ-B-13 | 默认主判断的预测结果必须包含 lean / probability_band / scoreline_band / drivers / uncertainties | 现有 `PredictionResult` | — |
| RQ-B-14 | 已付费用户可保存问答历史（report 列表） | spec frontend §报告 Tab | v1 持久化方式（bronze JSON vs SQLite）待 Q15（新增） |
| RQ-B-15 | 已付费用户可收藏比赛 | spec frontend §权限分层 | 收藏数据模型待补 |
| RQ-B-16 | 用户访客（未登录）只能看简单胜负倾向 + 公开摘要（Q2） | 决策 Q2 | "简单倾向"=主队/平/客队 之一，不显示置信度数值 |

### C. 证据系统（10 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-C-1 | 每条证据须包含：id, source, source_type, url, observed_at, claim, topic, side, confidence, freshness, raw_excerpt | 现有 `OsintEvidence` | — |
| RQ-C-2 | 证据置信度（confidence）取值 [0.0, 1.0]，按以下分级：≥0.5=强、[0.25, 0.5)=弱、<0.25=不足 | 03-VPC § 9 | 阈值在用户访谈中校验 |
| RQ-C-3 | EvidenceStrength 组件须按"强证据 / 弱信号 / 样本不足"三栏展示 | spec frontend §EvidenceStrength | — |
| RQ-C-4 | 每条证据须显示：来源标签、原始 URL（如有）、observed_at、claim 文本、置信度可视化 | spec frontend §EvidenceStrength + 现有 OsintEvidence | URL 显示方式：图标？文本？待 Q16（新增） |
| RQ-C-5 | "信息不足"状态须显示原因（缺哪类数据），而非空白 | spec backend §动态因子 + Q3 | — |
| RQ-C-6 | 已付费用户能看完整证据列表；未付费用户只看强证据数量（不展示内容） | spec frontend §权限分层 | "数量"是否展示前 N 条标题：待 Q17（新增） |
| RQ-C-7 | 因子启用/禁用须显式记录（FactorImpact.enabled 字段） | 现有 `FactorImpact` | — |
| RQ-C-8 | 因子未启用时须填 missing_reason 字段，前端可见 | 现有 `FactorImpact` + 红线 R2 | — |
| RQ-C-9 | 证据来源 host 须在白名单内（FOOTBALL_OSINT_URL_ALLOWLIST），私有 IP / 链路本地拒绝 | 修复 PR + 安全 R5 | 已实现 |
| RQ-C-10 | 用户提供的 URL 通过笔记/问题输入时，须经白名单 + DNS 公网检查 | 修复 PR | 已实现 |

### D. 后端 OSINT 流水线（14 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-D-1 | 后端按 spec 拆分为：models / routes / pipeline / storage / factor_registry / evidence / adapters/ / analysis/（Q5） | 决策 Q5 + spec backend §后端架构 | adapters/ 子目录文件名见 spec 行 31-43 |
| RQ-D-2 | adapters/ 必含：fixtures_public / ddg_search / official_site / open_meteo / geo_distance / local_poisson / user_supplied / optional_bing / optional_odds | spec backend §零配置采集策略 | optional_* 在缺密钥时返回 skipped |
| RQ-D-3 | analysis/ 必含：profiling / factor_scoring / confidence / prediction / report | spec backend §架构 | — |
| RQ-D-4 | 每个 job 须落盘到 `bronze_storage/football_osint/{job_id}/`，含 request.json / status.json / verify.json / raw/* / normalized.json / factors.json / prediction.json / report.md / provenance.json | spec backend §任务存储 | v1 部分文件可省（如 verify.json）；待 Q18（新增） |
| RQ-D-5 | 同一比赛验证结果缓存 6 小时；搜索结果缓存 30 分钟；天气缓存到比赛结束后 2 小时；用户输入永远优先 | spec backend §缓存策略 | 缓存实现：文件 mtime / Redis / 内存？v1 推荐文件 mtime |
| RQ-D-6 | 比赛 profile 须根据赛事类型动态启用因子组：U23 / 国家队 / 友谊赛 / 临场两小时 / 缺盘口 | spec backend §动态因子模型 | 友谊赛检测目前用 substring，需明示 |
| RQ-D-7 | 因子注册表 factor_registry 须支持启用/禁用、权重、impact、direction、confidence 五个属性 | spec backend §动态因子 | — |
| RQ-D-8 | 缺数据因子返回 missing_reason，禁止填中性默认分（红线 R2） | spec backend §零配置采集策略 + 红线 | — |
| RQ-D-9 | adapter 不允许因为缺密钥让任务失败，必须返回 skipped 和原因 | spec backend §零配置采集策略 | — |
| RQ-D-10 | 系统提供 4 个 OSINT 端点：POST /jobs / GET /jobs/{job_id} / GET /jobs/{job_id}/report.md / POST /predict-sync | spec backend §API + 现有 routes.py | — |
| RQ-D-11 | 系统额外提供 POST /api/football/osint/answer 用于自由提问简化回答 | 现有 routes.py | spec 中没有，但已实现且必要 |
| RQ-D-12 | OSINT 端点的 _JOBS 缓存使用 LRU+TTL（已实现） | 修复 PR | — |
| RQ-D-13 | OSINT 端点并发控制使用 ANSWER_SEMAPHORE（默认 4，可配置） | 修复 PR | — |
| RQ-D-14 | 比赛无法验证时返回 needs_review 状态，前端引导用户修改输入 | spec backend §错误和降级 | 当前实现总是 completed，未走 needs_review 分支 |

### E. Web UI（12 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-E-1 | Web 首屏三栏布局：左赛事队列 / 中比赛卡 / 右 Ask 面板 | spec frontend §Web 工作台 | 移动端响应式：Q19（新增） |
| RQ-E-2 | 左栏：联赛、时间、关注状态、风险变化 | spec frontend §Web | "关注状态"=已收藏 |
| RQ-E-3 | 中栏：默认主判断 + 6 维 chips + 自由提问输入框 | spec frontend §Web | — |
| RQ-E-4 | 右栏：Ask 历史 + 推荐追问 + 证据引用 + 报告生成入口 | spec frontend §Web | "推荐追问"算法待 Q20（新增） |
| RQ-E-5 | 未登录访客看到的中栏降级：只显示比赛信息和简单胜负倾向 | 决策 Q2 + spec frontend §权限分层 | — |
| RQ-E-6 | 未登录访客看到的右栏被 AuthGate 包裹，触发注册/登录引导 | spec frontend §AuthGate | — |
| RQ-E-7 | 已注册未付费用户看到 PaymentUnlock + 付费码兑换入口 | spec frontend §AuthGate + Q1 | — |
| RQ-E-8 | 视觉系统：深绿主色 / 草金辅色 / 暖纸背景 | spec frontend §品牌方向 | 已部分实现 |
| RQ-E-9 | 字体：Satoshi / Geist + 系统中文字体 | spec frontend §品牌方向 + 现有 css | — |
| RQ-E-10 | 图标：phosphor-icons/react，禁止 emoji 作为正式图标 | spec frontend §品牌方向 | — |
| RQ-E-11 | 文案：使用"倾向、压力、风险、证据强弱"，禁止"必胜、稳赢、推荐投注" | 红线 R1 | 文案审计 checklist 阶段 4 补 |
| RQ-E-12 | 权限不足状态：显示简短预览 + 明确登录/付费入口；不空白也不恐吓 | spec frontend §权限分层 | — |

### F. 非功能需求（8 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-F-1 | 已付费用户从打开赛事到看到主判断，时间 < 5 秒（含网络） | 01 §3.3 成功标准 | — |
| RQ-F-2 | `_is_match_related` 命中召回率 ≥ 90%（基于人工标注 50 条） | 01 §3.3 + RQ-B-9 | 校验集需要建立 |
| RQ-F-3 | OSINT pipeline 处理 1 场比赛 P95 < 30 秒（无需 lp-fetch-md），P99 < 60 秒（含 lp-fetch-md） | 经验值 + lp-fetch-md timeout 18s × ~7 候选 | 需上线后实测 |
| RQ-F-4 | 后端单进程，2GB 内存上限（足球服务器约束） | 02 §1.3 P5 | — |
| RQ-F-5 | OSINT 端点速率限制：单 IP 20 写/min（已实现） | 现有 main.py rate_limit_middleware | — |
| RQ-F-6 | URL 抓取须经白名单 + DNS 公网检查（已实现） | 修复 PR + 安全 R4 | — |
| RQ-F-7 | 所有 LLM 调用须有超时和降级路径 | 红线 R2 + 价值风险 RISK-5 | timeout 数值待定 |
| RQ-F-8 | 用户协议 + 隐私政策必须在 v1 上线前备齐 | 02 §2.2 P6 | 法务模板谁来出？Q21（新增） |

### G. 业务规则（7 条）

| ID | 条目 | 来源 | 不确定性 |
|---|---|---|---|
| RQ-G-1 | 客户端"支付/兑换成功"提示不能作为最终开通依据；只信服务端校验 | spec frontend §支付安全规则 | — |
| RQ-G-2 | 邀请码、付费码均须有过期机制（默认 30 天） | spec frontend §邀请注册 / 付费 | "默认 30 天"是 PRD 拍的，需用户确认 → Q22（新增） |
| RQ-G-3 | 付费码兑换后绑定到 user_id；同一码不可二次使用 | spec frontend §支付安全规则 + RQ-A-14 | — |
| RQ-G-4 | 系统不输出投注建议、不显示赔率（红线 R1） | 决策 R1 | — |
| RQ-G-5 | 系统不在缺证据时编造倾向（红线 R2） | 决策 R2 + RQ-B-2 | — |
| RQ-G-6 | 邀请关系不影响预测结果（红线 R5 + RQ-A-10） | 决策 R5 | — |
| RQ-G-7 | 用户可随时申请注销账户和数据导出（合规要求） | 02 §2.2 P6 | 实现细节延后到 v1.5 |

---

## Assumptions

| ID | 假设 | 阶段 |
|---|---|---|
| ASM-1 | 用户 U1（懂球研判型）数量足够支撑 v1（≥ 50 真实用户） | 阶段 2 用户访谈验证 |
| ASM-2 | 公开数据源（Win007 等）在 v1 期间稳定可抓 | 上线后监控 |
| ASM-3 | DeepSeek API 可用且成本可控（< ¥500/月，v1 期间） | 上线后实测 |
| ASM-4 | "邀请 + 付费码"门槛不会扼杀冷启动 | 上线后转化率验证 |
| ASM-5 | 用户接受"研判 ≠ 胜负预测"的定位 | 阶段 2 用户访谈 |
| ASM-6 | 单人开发能在 4-6 周内完成 v1 范围 | 阶段 3 MoSCoW 后才能确认 |

---

## Constraints

| ID | 约束 | 类型 |
|---|---|---|
| CON-1 | 仅采集合法公开数据 | 法律/合规 |
| CON-2 | session_key 不下发到任何前端 | 微信平台 |
| CON-3 | 部署到单机服务器 221.239.50.142，无 K8s | 工程 |
| CON-4 | 无付费足球数据 API 预算 | 资金 |
| CON-5 | DeepSeek API 限流和成本可见 | 第三方 |
| CON-6 | bronze JSON + SQLite 索引，无独立数据库 | 工程 |
| CON-7 | React 19 + Vite + FastAPI 技术栈不可变 | 工程 |
| CON-8 | 单人开发节奏 | 资源 |

---

## Open Questions（新增的待补决策 Q12-Q22）

| ID | 问题 | 影响范围 | 阶段 |
|---|---|---|---|
| Q12 | 短信/邮件验证码服务商选型 | RQ-A-16/17/19 审计存储 | 阶段 4（验收 DoD 时） |
| Q13 | 可信度展示形式：百分比 / L1-L4 / 双形式 | RQ-B-1 | 阶段 3 用户访谈 |
| Q14 | "信息不足"具体阈值（因子置信度均值或单因子） | RQ-B-2 | 阶段 3 |
| Q15 | 用户问答历史持久化方式（bronze JSON / SQLite / 二者） | RQ-B-14 | 阶段 4 |
| Q16 | 证据 URL 显示方式（图标 / 文本 / hover） | RQ-C-4 | 阶段 4 设计阶段 |
| Q17 | 未付费用户证据"数量预览"是否显示前 N 条标题 | RQ-C-6 | 阶段 3 用户访谈 |
| Q18 | bronze 落盘文件子集（v1 是否所有 9 个文件都落） | RQ-D-4 | 阶段 4 |
| Q19 | Web 移动端响应式优先级（v1 是否做） | RQ-E-1 | 阶段 3 |
| Q20 | "推荐追问"算法（基于历史 / 因子缺失 / 简单热门） | RQ-E-4 | 阶段 4 |
| Q21 | 用户协议/隐私政策模板来源（自写 / 法务 / 模板站） | RQ-F-8 | 阶段 4 |
| Q22 | 邀请码/付费码默认有效期 | RQ-G-2 | 阶段 4 |

---

## Recommended Next Skill

下一步是 **requirements-gap-auditor**（任务 #15）：

- 在已有 86 条草稿上找漏 / 找重 / 找冲突
- 重点检查类别间一致性（如 RQ-A-2 unionid vs RQ-A-18 留口、RQ-B-2 阈值 vs RQ-C-2 阈值）
- 输出 GAP/DUP/CONFLICT 三类标签

随后 **ambiguity-hunter** 处理本文档里 11 个 Open Questions。

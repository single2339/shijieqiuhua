---
artifact: decisions
date: 2026-06-12
status: locked
---

# PRD 重梳决策记录（阶段 1 → 阶段 2 输入）

阶段 1 三件产物完成后，与产品负责人对齐的 6 个关键决策。这些决策在阶段 2 起视为**已锁定**，需求挖掘和规整都基于这些假设。

| ID | 决策 | 选项 | 影响 |
|---|---|---|---|
| Q1 | v1 付费形式 | **仅付费码兑换**（运营手动发码 → 服务端校验兑换 → 开通权益） | 不接微信支付，工程量小；权益变更链路真实可练；v1.5 再考虑接真实支付 |
| Q2 | 访客可见范围 | **赛事列表 + 简单胜负倾向**（默认） | 公开摘要支撑冷启动；完整问答/证据/报告对未付费用户隐藏 |
| Q3 | 缺证据时显示 | **明确显示"信息不足"**（默认，红线 R2） | 无哈希伪造、无市场默认值；阈值见 03-value-proposition § 9 |
| Q4 | v1 是否含小程序 | **仅 Web，小程序入 v1.5** | 单人节奏可控；账号模型为 unionid 留口；小程序壳延后但接口契约提前布好 |
| Q5 | OSINT 后端拆分粒度 | **完整 spec 拆分**（10 子模块：models/routes/pipeline/storage/factor_registry/evidence/adapters//analysis/） | 工作量较大但架构最干净；建议作为 v1 M 项执行，用 1-2 周专门做 |
| Q6 | 6 维追问实现 | **模板 + LLM 混合**：6 维快捷 → 模板生成；自由提问 → LLM 走问答接口 | 模板路径覆盖热点维度（角球/红黄牌等）；LLM 兜底自由表达；LLM 限流降级到模板 |

## 待补决策（不阻塞阶段 2，但必须在 v1 上线前回答）

| ID | 决策 | 出现位置 | 阶段 |
|---|---|---|---|
| Q7 | 邀请码批发策略：admin UI vs CLI 脚本 | 02-stakeholder § 7 | 阶段 4（验收 DoD 时） |
| Q8 | 付费码定价（单次 / 月 / 永久）和有效期 | 03-VPC § 9 | 阶段 4 |
| Q9 | 数据保留：用户提问历史多久 | 03-VPC § 9 | 阶段 4 |
| Q10 | 反馈渠道：issue tracker / 微信群 / 邮件 | 02-stakeholder § 7 | 阶段 5（PRD packaging 时） |
| Q11 | 5-8 名核心用户访谈名单 | 02-stakeholder § 7 / 03-VPC § 1 假设 | 阶段 2（需求挖掘前） |

## 与现有 spec 的偏离

| 现有 spec 写法 | 本 PRD 决策 | 处理 |
|---|---|---|
| spec 写"邀请 + 付费"必需 | Q1 改为"付费码兑换"（不接真实支付） | 价值方向一致，仅实现路径降级；spec 不需要废弃 |
| spec 写"小程序优先" | Q4 改为"Web 优先，小程序 v1.5" | 长期保持小程序作为核心入口；v1 只是延后 |
| spec frontend-design 列 9 个组件 | v1 仅做 6 个：MatchQuestionCard、EvidenceStrength、AuthGate、AccountStatus、PaymentUnlock、InvitePanel | spec 中的 SharePoster（v1.5）、订阅消息（v1.5）、跨端身份合并（v1.5）显式延后 |
| spec backend-redesign 列 10 子模块 | 全部按 spec 拆分 | 与 Q5 决策一致 |

阶段 2 起，所有需求条目必须遵守 Q1-Q6；如有需要打破，必须先在 decisions.md 追加新决策。

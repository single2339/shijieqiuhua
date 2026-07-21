# 全球开源情报收集网络（递进式体系）— 实现说明

本目录包含架构计划的**可交付规格**：合规策略、采集契约、湖仓与核心对象、分渠道适配器、智能体平面与阶段路线图。未修改原始计划文件（`.cursor/plans/...`）。

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/01-compliance-and-data-classification.md](docs/01-compliance-and-data-classification.md) | 合法边界、审计字段、数据分级、留存 |
| [docs/02-collection-contracts.md](docs/02-collection-contracts.md) | 原始证据文档、采集任务、队列与背压 |
| [docs/03-medallion-architecture.md](docs/03-medallion-architecture.md) | 原始证据层、标准证据层、情报产品层，以及文档、实体、事件、可验证主张 |
| [docs/collectors/](docs/collectors/) | Web / 社交 / API / App 四类适配器 |
| [docs/04-agent-plane.md](docs/04-agent-plane.md) | 智能体编排、验真、经济分析智能体、人工复核 |
| [docs/05-roadmap.md](docs/05-roadmap.md) | 阶段 A–D 排期与退出标准 |

## 机器可读规格

| 路径 | 说明 |
|------|------|
| [schemas/collection-job.schema.json](schemas/collection-job.schema.json) | 采集任务 |
| [schemas/raw-document.schema.json](schemas/raw-document.schema.json) | 原始证据入库单元 |
| [schemas/silver-document.schema.json](schemas/silver-document.schema.json) | 标准证据文档 |
| [schemas/entity.schema.json](schemas/entity.schema.json) | 实体 |
| [schemas/event.schema.json](schemas/event.schema.json) | 事件 |
| [schemas/claim.schema.json](schemas/claim.schema.json) | 主张与验真 |
| [schemas/economic-brief.schema.json](schemas/economic-brief.schema.json) | 经济简报 |
| [sql/001_medallion_tables.sql](sql/001_medallion_tables.sql) | 参考 DDL |

## 原则

仅采集与处理**合法公开或已授权**数据；具体采集实现须遵守各平台条款与适用法律。详见合规文档。

## 架构幻灯片（PPT）

已用 **baoyu-slide-deck**（`blueprint` 风格）生成递进式架构说明幻灯片，见目录 [slide-deck/global-osint-architecture/](slide-deck/global-osint-architecture/)（含 `global-osint-architecture.pptx` 与 `.pdf`）。

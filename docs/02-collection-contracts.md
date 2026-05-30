# 采集平面统一契约：RawDocument、CollectionJob 与队列背压

## 1. 设计目标

- 渠道差异**完全封装**在适配器内；接入层只认 **`RawChunk` 流**与统一的 **`RawDocument`** 组装结果。
- 与 [01-compliance-and-data-classification.md](./01-compliance-and-data-classification.md) 中的审计字段一致。

## 2. 类型关系

```
CollectionJob (调度单元)
    → Collector.collect(job) → stream<RawChunk>
    → Assembler → RawDocument (入库单元，一条或按大小分片)
```

## 3. CollectionJob

表示一次可重试、可幂等的采集任务。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `job_id` | string (UUID) | 是 | 全局唯一 |
| `tenant_id` | string | 是 | 多租户 |
| `channel` | enum | 是 | `web` \| `social` \| `api` \| `app` |
| `collector_key` | string | 是 | 注册表中的采集器，如 `web_rss_v1` |
| `target` | object | 是 | 渠道特定负载，见 JSON Schema |
| `priority` | integer | 否 | 数值越大越优先，默认 0 |
| `dedupe_key` | string | 否 | 幂等键，如 `sha256(url+schedule)` |
| `schedule` | object | 否 | `cron` / `once` / `interval` |
| `max_attempts` | integer | 否 | 默认 3 |
| `created_at` | string (ISO-8601) | 是 | UTC |

机器可读定义见 [`../schemas/collection-job.schema.json`](../schemas/collection-job.schema.json)。

## 4. RawChunk

流式片段，用于大响应或分块下载。

| 字段 | 类型 | 说明 |
|------|------|------|
| `sequence` | integer | 从 0 递增 |
| `bytes` | string (base64) | 或二进制管道中的 buffer |
| `last` | boolean | 是否为最后一块 |

## 5. RawDocument

写入 Bronze 的**最小入库单元**。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `raw_document_id` | string (UUID) | 是 | 主键 |
| `job_id` | string | 是 | 关联任务 |
| `channel` | enum | 是 | 与 Job 一致 |
| `mime_type` | string | 是 | 如 `text/html`, `application/json` |
| `encoding` | string | 否 | 默认 `utf-8` |
| `body_ref` | string | 是 | 对象存储 URI 或内联小文本的占位 |
| `body_inline` | string | 否 | 小于阈值时可直接存（仍算 Bronze） |
| `headers_summary` | object | 否 | HTTP 头摘要或 API 响应元数据 |
| `captured_at` | string | 是 | UTC |
| `collector_id` | string | 是 | 与审计规范一致 |
| `collector_version` | string | 是 | SemVer |
| `source_url` | string | 条件 | Web/社交页面级 URL |
| `source_system` | string | 是 | 逻辑来源名 |
| `content_sha256` | string | 是 | 对**规范化后**正文字节计算 |
| `classification` | string | 否 | 数据分级，见 01 文档 |
| `extensions` | object | 否 | 渠道扩展字段，需版本化 `ext_schema_version` |

JSON Schema：[`../schemas/raw-document.schema.json`](../schemas/raw-document.schema.json)。

## 6. 接口约定（概念）

```ts
// 伪代码
interface Collector {
  readonly key: string;
  readonly supportedChannels: Channel[];
  collect(job: CollectionJob): AsyncIterable<RawChunk>;
}

interface RawDocumentAssembler {
  assemble(chunks: AsyncIterable<RawChunk>, job: CollectionJob): Promise<RawDocument>;
}
```

## 7. 队列与背压模型

### 7.1 队列主题

| 主题 | 用途 | 建议 |
|------|------|------|
| `jobs.pending` | 待调度任务 | 分区键 `tenant_id` |
| `jobs.running` | 执行中（可选，用于可观测性） | 短 TTL |
| `raw.ingest` | 已组装的 RawDocument 元数据 | 消费者写 Bronze |
| `jobs.dlq` | 失败耗尽重试 | 人工与自动重放 |

### 7.2 背压策略

| 机制 | 说明 |
|------|------|
| **生产者限流** | 每 `collector_key` + `tenant` 配置 QPS、并发数 |
| **队列深度告警** | `raw.ingest` 深度 > 阈值触发扩容或降采样 |
| **拒绝策略** | `jobs.pending` 满时：丢弃低优先级 / 延迟入队 / 返回 429（同步 API 场景） |
| **批量提交** | RawDocument 按 `batch_size` 或 `linger_ms` 批量写湖仓以降低小文件 |

### 7.3 幂等与去重

- `dedupe_key` 存在时，调度器在入队前查缓存（Redis）：命中则跳过或更新调度时间。
- Bronze 层按 `content_sha256` + `source_system` 可选唯一约束，避免重复存储（策略可配置为「允许重复但标记」）。

## 8. 版本化

- `collection-job.schema.json` 与 `raw-document.schema.json` 使用 `$id` 与 `version` 字段；破坏性变更递增主版本，并保留旧版 reader 直至迁移完成。

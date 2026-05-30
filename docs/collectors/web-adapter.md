# Web 渠道适配器设计

## 职责边界

- **输入**：`CollectionJob`，`channel=web`，`target` 含 URL 列表或站点爬取配置（深度、路径前缀、仅允许域名）。
- **输出**：`RawChunk` 流 → `RawDocument`（`mime_type` 多为 `text/html`）。
- **不负责**：跨文档实体合并、正文摘要（属 Silver）；**必须**遵守 robots.txt 与速率限制。

## 组件

| 组件 | 职责 |
|------|------|
| **Scheduler** | 从种子 URL 生成任务、去重、优先级 |
| **Fetcher** | HTTP(S)；可选 ETag/Last-Modified；重试与退避 |
| **Renderer** | 静态 HTML 直取；复杂 SPA 时**按需**无头浏览器（独立资源池） |
| **Parser（轻量）** | 仅提取原始 HTML；可选附带 `extracted_links[]` 供调度扩展，**不**写 Silver |

## 合规与隔离

- 每站点配置 `max_rps`、`max_concurrency`、`user_agent`、`respect_robots`。
- 失败与封禁隔离：单站点熔断不影响全局队列（见 [02-collection-contracts.md](../02-collection-contracts.md) 背压）。

## 版本与测试

- `collector_version` 随 HTML 选择器/渲染策略变更而递增。
- 回归测试：固定 HTML fixture → 快照比对 `content_sha256` 与元数据。

## target 示例（JSON）

```json
{
  "urls": ["https://example.com/news/1"],
  "fetch_profile": "static",
  "timeout_ms": 30000
}
```

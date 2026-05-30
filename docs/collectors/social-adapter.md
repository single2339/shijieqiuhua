# 社交网络渠道适配器设计

## 职责边界

- **输入**：`channel=social`，`target` 含官方 API 凭证引用（密钥由密钥管理服务解析）、或**已授权**的公开页面列表。
- **输出**：`RawDocument`，`mime_type` 常为 `application/json`（API）或 `text/html`（页面）。
- **不负责**：情感分析、话题建模（可放在 Silver/Gold 或独立特征管道）。

## 组件

| 组件 | 职责 |
|------|------|
| **QuotaManager** | 按应用/令牌跟踪速率与剩余配额；与调度联动降载 |
| **DTOMapper** | 将平台 JSON 映射为内部稳定结构写入 `extensions`，`ext_schema_version` 必填 |
| **StreamConsumer** | 若使用合规流式 API：offset/checkpoint 持久化 |

## 合规与隔离

- **禁止**默认使用违反平台 ToS 的登录自动化或爬虫；新数据源需走 [01-compliance](../01-compliance-and-data-classification.md) 闸门。
- 令牌按 `tenant_id` 隔离；日志中不得打印 access token。

## 版本与测试

- 平台 API 变更频繁：`collector_key` 可含平台代号，如 `social_twitter_api_v2`。
- Contract 测试：对录制响应（脱敏）做 schema 校验。

## target 示例

```json
{
  "provider": "example_social",
  "endpoint": "posts_search",
  "query_ref": "config:queries/econ_keywords_v3",
  "credential_ref": "vault:social/example/read"
}
```

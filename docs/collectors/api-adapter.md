# 开放 API / 数据集渠道适配器设计

## 职责边界

- **输入**：`channel=api`，`target` 描述 OpenAPI 操作、查询参数、分页游标、增量字段。
- **输出**：原始证据文档（`RawDocument`，格式为 `application/json` 或 CSV 等）；大响应用原始数据分片（`RawChunk`）分块。
- **不负责**：业务语义统一（由标准证据层解析器完成）；**负责**忠实保存分页原始页与游标状态。

## 组件

| 组件 | 职责 |
|------|------|
| **OpenAPIClient** | 由规范生成或手写；处理鉴权（API Key、OAuth2 client credentials） |
| **Pagination** | `cursor` / `offset` / `since` 策略可插拔 |
| **模式固定器** | 响应 JSON 对已知 `schema_version` 校验；失败写入原始证据层并打 `parse_error` 扩展标志 |

## 合规与隔离

- 数据集许可（ODbL、CC 等）记录在 `source_system` 元数据与独立**许可登记簿**。
- 密钥轮换：仅 `credential_ref`，不落地明文。

## 版本与测试

- `collector_version` 与 OpenAPI `major` 对齐或独立 SemVer。
- 契约测试：mock server 返回分页边界情况。

## target 示例

```json
{
  "openapi_ref": "registry:apis/trade_stats/v1",
  "operation_id": "getShipments",
  "params": { "region": "APAC" },
  "incremental": { "field": "updated_at", "since_ref": "state:job_last_run" }
}
```

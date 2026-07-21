# 手机 App 渠道适配器设计

## 职责边界

- **输入**：`channel=app`，仅针对**合法路径**：应用商店公开元数据、官方/合作 SDK、经法审的合作伙伴数据馈送。
- **输出**：原始证据文档（`RawDocument`，商店抓取多为 HTML/JSON；SDK 回调为 JSON）。
- **明确不包含**：绕过鉴权、破解协议、非授权抓取私有接口——不作为本仓库默认设计范围。

## 组件

| 组件 | 职责 |
|------|------|
| **StoreMetadataFetcher** | 从官方商店页面/API 获取版本、开发者、权限声明等 |
| **合作方接入** | 接收合作方批处理文件（S3/SFTP），病毒扫描与格式校验后写入原始证据层 |
| **SDKBridge（可选）** | 若组织自有 App 内嵌合规采集：仅上传**用户同意**且**脱敏**后的遥测摘要 |

## 合规与隔离

- 所有 App 相关采集需**单独法审**与数据清单；默认分级不低于 `SENSITIVE_METADATA`。
- 与 Web/API 队列**物理或逻辑隔离**（独立 `collector_key` 前缀与配额），避免故障扩散。

## 版本与测试

- `extensions` 中记录 `app_id`、`store_region`、`schema_version`。
- 对商店 HTML 使用 fixture 回归；合作文件用行级 schema 校验。

## target 示例

```json
{
  "mode": "store_metadata",
  "store": "example_store",
  "app_ids": ["com.example.reader"],
  "regions": ["US", "CN"]
}
```

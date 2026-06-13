---
title: 世界球花 v1 埋点设计 — 事件清单与数据模型
version: 0.1.0
date: 2026-06-13
status: draft
depends_on:
  - docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md
---

# v1 埋点设计 (1/2)：事件清单 + 数据模型

> 目标：在 W1-W2 完成数据落点；W5 接上 dashboard 即可（见 02-dashboards.md）。

## 0. 设计原则

1. **单一来源**：所有事件都从后端 emit。前端不直接落埋点（避免广告拦截、数据缺失、重复实现）。
2. **零外部依赖**：v1 不引入 Sentry / Mixpanel / GA。事件落 SQLite，dashboard 用 SQL 查。
3. **审计 vs 遥测分开**：
   - `audit_log`：合规需要、有 user_id 的关键事件（注册、兑换、邀请、admin 操作）
   - `telemetry_event`：性能、行为、漏斗指标（可有也可无 user_id）
4. **PII 最小化**：不存原始 question 文本；只存哈希 + 长度 + 是否相关。
5. **采样**：高频事件（dashboard 浏览）100% 采样（v1 量小，全量没问题；量大后再降采样）。
6. **可重放**：所有事件含 `event_id`、`request_id`、`ts`，便于按 request_id 串联完整调用链。

## 1. 数据模型

### 1.1 telemetry_event 表（新增）

```sql
CREATE TABLE telemetry_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,             -- ulid
  ts TIMESTAMP NOT NULL,                     -- ISO8601 UTC
  event_name TEXT NOT NULL,                  -- snake_case，见 §2 清单
  user_id TEXT,                              -- 可空（未登录场景）
  session_id TEXT,                           -- 浏览器 session（cookie 中）
  request_id TEXT,                           -- 串联同一 HTTP 请求的所有事件
  duration_ms INTEGER,                       -- 仅 *.duration / *.completed 用
  status TEXT,                               -- ok | error | skipped | timeout
  error_code TEXT,                           -- 仅 status=error 时
  payload_json TEXT,                         -- 事件特定字段，详见 §2
  ip_hash TEXT,                              -- IP 取 sha256 前 12 位，去隐私
  ua_class TEXT                              -- desktop | mobile | bot | unknown
);
CREATE INDEX idx_tel_event_ts ON telemetry_event(event_name, ts);
CREATE INDEX idx_tel_user_ts ON telemetry_event(user_id, ts);
CREATE INDEX idx_tel_request ON telemetry_event(request_id);
```

为什么用单表 + payload_json：
- v1 量级（< 1M 行/月）SQLite 完全扛得住
- 加新字段不用 migration
- dashboard SQL 用 `json_extract(payload_json, '$.x')` 取数

### 1.2 audit_log（PRD §6.1 已定义，沿用）

合规事件落 audit_log；不重复落 telemetry_event（避免双倍存储）。

| 字段 | 含义 |
|---|---|
| `actor` | user / admin / system |
| `event` | invitation.consumed / billing.code_redeemed / admin.bulk_create_invite / ... |
| `payload_json` | 事件载荷 |

### 1.3 落点决策矩阵

| 事件 | audit_log | telemetry_event |
|---|---|---|
| 邀请码消耗、付费码兑换、admin 批发 | ✅ | ❌ |
| 注册/登录成功失败 | ✅（失败也记） | ✅（漏斗用） |
| 看 dashboard / 提问 / 追问 | ❌ | ✅ |
| LLM 调用 / OSINT pipeline / 缓存命中 | ❌ | ✅ |
| 错误响应（500、503、超时） | ❌ | ✅ |
| 管理员封禁用户、调阈值 | ✅ | ❌ |
| 数据备份成功失败 | ❌ | ✅ |

---

## 2. 事件清单（v1 必有）

按域分组，30 个事件 = v1 起步集合。命名约定 `<domain>.<action>`，所有 `*.completed` 必带 `duration_ms` 和 `status`。

### 2.1 注册与登录漏斗（auth.*）

| event_name | 触发点 | payload 关键字段 | audit_log? |
|---|---|---|---|
| `auth.invite_visit` | 用户带 ?invite=CODE 打开注册页 | `{ invite_code_present: bool, invite_valid: bool }` | ❌ |
| `auth.otp_send` | POST /api/auth/otp/send | `{ provider: 'email', status: 'sent'/'rate_limited'/'failed' }` | ❌ |
| `auth.register_attempt` | POST /api/auth/register | `{ status, error_code }` | ❌ |
| `auth.register_success` | 同上成功 | `{ user_id, invite_code }` | ✅（事件 `invitation.consumed`） |
| `auth.login_attempt` | POST /api/auth/login | `{ status, error_code }` | ❌ |
| `auth.login_success` | 登录成功 | `{ user_id }` | ✅（事件 `auth.login`） |
| `auth.login_locked` | 5 次失败后锁 IP | `{ ip_hash }` | ✅ |
| `auth.session_refresh` | refresh_token 自动刷新 | `{ user_id }` | ❌ |

### 2.2 商业化漏斗（billing.*）

| event_name | 触发点 | payload | audit_log? |
|---|---|---|---|
| `billing.unlock_view` | 用户进入 PaymentUnlock 面板 | `{ entry: 'authgate' / 'menu' }` | ❌ |
| `billing.redeem_attempt` | POST /api/billing/redeem | `{ status, error_code }` | ❌ |
| `billing.redeem_success` | 兑换成功 | `{ user_id, code, validity_days }` | ✅（事件 `billing.code_redeemed`） |

### 2.3 邀请增长（invitation.*）

| event_name | 触发点 | payload | audit_log? |
|---|---|---|---|
| `invitation.create_attempt` | POST /api/invitation/create | `{ status, error_code }` | ❌ |
| `invitation.create_success` | 创建成功 | `{ user_id, invite_code, monthly_count }` | ✅ |
| `invitation.share_click` | 用户点"复制链接 / 二维码" | `{ user_id, channel: 'link'/'qr'/'wechat' }` | ❌ |

### 2.4 研判核心（research.*）

| event_name | 触发点 | payload | audit_log? |
|---|---|---|---|
| `research.dashboard_view` | GET /api/football/osint/match/{id}/dashboard | `{ user_role: 'guest'/'free'/'paid', match_id, cache_hit, lean }` | ❌ |
| `research.dashboard_completed` | 同上完成 | `{ duration_ms, status }` (NFR-1 P95) | ❌ |
| `research.info_insufficient_shown` | dashboard 返回 lean='info_insufficient' | `{ match_id, missing_data_count, factor_enabled_count, mean_confidence }` | ❌ |
| `research.dimension_attempt` | POST /api/football/osint/dimension | `{ user_id, dimension, status }` | ❌ |
| `research.dimension_completed` | 同上完成 | `{ duration_ms }` | ❌ |
| `research.answer_attempt` | POST /api/football/osint/answer | `{ user_id, related: bool, question_hash, question_len }` (无原文) | ❌ |
| `research.answer_completed` | 同上完成 | `{ duration_ms, llm_used: bool, fallback_reason: 'timeout'/'limit'/'cite_invalid'/null, status }` | ❌ |
| `research.answer_unrelated` | _is_match_related 判定 false | `{ question_hash, question_len }` | ❌ |
| `research.evidence_expand` | 用户展开证据列表 | `{ user_id, match_id, evidence_strength: 'strong'/'weak'/'insufficient' }` | ❌ |
| `research.user_supplied_url` | 用户提交补充 URL | `{ user_id, match_id, url_host, accepted: bool }` (host 只取域名) | ❌ |

### 2.5 OSINT 流水线（pipeline.*）

| event_name | 触发点 | payload |
|---|---|---|
| `pipeline.job_start` | run_prediction_sync 开始 | `{ job_id, match_id, profile.competition_type }` |
| `pipeline.job_completed` | 同上完成 | `{ job_id, duration_ms, status, evidence_count, factor_enabled_count, lean }` (NFR-2 P95/P99) |
| `pipeline.adapter_called` | 单个 adapter 完成 | `{ job_id, adapter, status: 'ok'/'skipped'/'failed', duration_ms, reason }` |
| `pipeline.cache_hit` | 命中缓存 | `{ cache_type: 'fixture'/'search'/'weather', match_id, age_seconds }` |
| `pipeline.cache_force_refresh` | 开赛 ≤6h 强制重算 | `{ match_id, hours_to_kickoff }` |

### 2.6 LLM 与外部（llm.* / external.*）

| event_name | 触发点 | payload |
|---|---|---|
| `llm.call_attempt` | 准备调 DeepSeek | `{ purpose: 'translate'/'summarize'/'classify'/'answer', model }` |
| `llm.call_completed` | 调用完成 | `{ purpose, duration_ms, status, error_code, prompt_tokens, completion_tokens }` |
| `llm.cite_invalid` | 引用合法性校验失败 | `{ purpose, missing_evidence_ids: [...] }` |
| `external.url_fetch_attempt` | lp-fetch-md 调用 | `{ host, status, duration_ms }` |
| `external.url_blocked` | URL 被白名单/DNS 检查拒绝 | `{ url_hash, reason: 'host_not_allowed'/'private_ip'/'invalid_scheme' }` |

### 2.7 系统健康（system.*）

| event_name | 触发点 | payload |
|---|---|---|
| `system.error_5xx` | 5xx 响应 | `{ path, error_code, duration_ms }` |
| `system.rate_limited` | 速率限制触发 | `{ path, ip_hash, method }` |
| `system.backup_attempt` | 备份脚本启动（cron） | `{ kind: 'bronze'/'sqlite' }` |
| `system.backup_completed` | 备份完成 | `{ kind, duration_ms, status, size_bytes }` |
| `system.uptime_heartbeat` | 每 60s 一次（cron） | `{ memory_mb, bronze_count }` |

### 2.8 admin（admin.*）

仅 audit_log：

| event | 来自 |
|---|---|
| `admin.bulk_create_invite` | UC-10 |
| `admin.bulk_create_payment` | UC-10 |
| `admin.ban_user` | admin CLI |
| `admin.set_threshold` | admin CLI |

---

## 3. Python 埋点 SDK 接口

### 3.1 模块位置

`backend/telemetry.py`（新建）

### 3.2 公开 API

```python
# backend/telemetry.py
from __future__ import annotations
import time, hashlib, ulid, json, sqlite3
from contextlib import contextmanager
from typing import Any

def emit(
    event_name: str,
    *,
    user_id: str | None = None,
    request_id: str | None = None,
    duration_ms: int | None = None,
    status: str | None = None,
    error_code: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """落 telemetry_event。永远不抛异常（埋点失败不能影响主流程）。"""

@contextmanager
def measure(event_name: str, **kwargs):
    """用上下文管理器自动测时长 + 写 status。
    用法:
        with measure('research.dashboard_completed', user_id=u, payload={'match_id': m}) as m:
            result = do_work()
            m['payload']['cache_hit'] = result.cache_hit
    异常时自动 status='error' 并 re-raise。
    """

def hash_text(text: str, length: int = 12) -> str:
    """文本 → sha256 前 N 位。用于 question_hash, ip_hash, url_hash。"""

def host_of(url: str) -> str:
    """url → 域名（不带 path/query），失败返回 ''。"""
```

### 3.3 用例：注册流程埋点

```python
# backend/auth/routes.py
from backend.telemetry import emit, measure, hash_text

@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    request_id = request.headers.get("x-request-id") or generate_request_id()
    emit('auth.register_attempt',
         request_id=request_id,
         payload={'invite_code_prefix': req.invite_code[:4]})

    try:
        user = await register_with_invite(...)
    except InviteUsed:
        emit('auth.register_attempt',
             request_id=request_id,
             status='error',
             error_code='E_INVITE_USED')
        raise HTTPException(409, ...)

    emit('auth.register_success',
         user_id=user.id,
         request_id=request_id,
         payload={'invite_code': req.invite_code})
    # audit_log 由 register_with_invite 内部写
    return ...
```

### 3.4 用例：dashboard 性能埋点

```python
# backend/main.py
@app.get("/api/football/osint/match/{match_id}/dashboard")
async def get_dashboard(match_id: str, user=Depends(get_current_user_optional)):
    with measure('research.dashboard_completed',
                 user_id=user.id if user else None,
                 payload={'match_id': match_id}) as m:
        m['payload']['user_role'] = user_role(user)
        cached = cache_get(match_id)
        m['payload']['cache_hit'] = cached is not None
        result = cached or await build_dashboard(match_id)
        m['payload']['lean'] = result.prediction.lean
        return result
```

`measure` 自动写 `duration_ms` 和 `status='ok'/'error'`。

### 3.5 异步与背压

埋点 emit 是同步 SQLite INSERT；v1 量级（峰值 < 50 写/s）SQLite 单连接足够。如果将来量大：

- 改 `emit` 为 push 到 `asyncio.Queue` + 后台 batch flush（每秒 1 次或满 100 条）
- v1 不需要

### 3.6 PII 与日志安全

| 数据 | 处理 |
|---|---|
| 邮箱 | 不进 telemetry_event（仅在 user 表）；只存 user_id |
| 手机号 | v1 不收集 |
| IP | sha256 前 12 位（`ip_hash`） |
| 自由提问原文 | 只存 sha256 前 12 位 + 长度（用于去重统计） |
| 邀请码/付费码 | 仅存 prefix 4 位（防全码泄露但保留可调试性） |
| URL | 只存 host（去 path/query） |

---

## 4. request_id 串联

引入中间件，每个 HTTP 请求生成 ulid 作为 request_id：

```python
# backend/main.py
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or ulid.new().str
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response
```

所有 emit 都从 `request.state.request_id` 取。dashboard 排查时按 `request_id` 一查到底。

---

## 5. 落库迁移

migration `sql/002_telemetry.sql`：

```sql
-- 见 §1.1 telemetry_event 表
-- 加 audit_log 索引（如还没建）
CREATE INDEX IF NOT EXISTS idx_audit_event_ts ON audit_log(event, ts);
```

启动时由 `backend/db.py` 执行 idempotent migration（v1 简化方案）。

---

## 6. 校验与测试

### 6.1 自动化测试要点

| 测试 | 位置 |
|---|---|
| `emit` 失败时不抛异常（DB 锁、磁盘满） | `tests/test_telemetry.py::test_emit_swallows_errors` |
| `measure` 异常时 status='error' 且 re-raise | `tests/test_telemetry.py::test_measure_on_exception` |
| PII 不进 payload（fixture 含邮箱 → 检查事件不含原文） | `tests/test_telemetry.py::test_no_pii_leak` |
| 50 并发 emit 不丢事件 | `tests/test_telemetry.py::test_concurrent_emit` |

### 6.2 上线前 dry-run

W4 末做一次：跑完 UC-01..UC-10 的所有路径，检查 telemetry_event 表是否每个用例至少有 1 个匹配事件。

---

## 7. 与 PRD 的对齐

| PRD 需求 | 本设计落点 |
|---|---|
| RQ-F-11 关键埋点 | §2 全部 30 事件 |
| RQ-F-10 结构化日志 + request_id | §4 |
| NFR-1 已付费看主判断 < 5s | `research.dashboard_completed.duration_ms` |
| NFR-2 OSINT pipeline P95/P99 | `pipeline.job_completed.duration_ms` |
| NFR-3 月可用性 99% | `system.uptime_heartbeat` + `system.error_5xx` |
| RISK-3 信息不足太频繁 | `research.info_insufficient_shown` 触发率 |
| RISK-1 U1 市场容量验证 | 注册-付费转化漏斗 |
| Q24（监控/告警工具） | v1 自建 SQL dashboard，不接 Sentry/Grafana（见 02-dashboards.md） |

---

## 推荐下一步

进入 **02-dashboards.md**：把这 30 个事件转成 7 天 / 30 天 dashboard + 告警规则。

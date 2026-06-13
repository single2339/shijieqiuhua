---
title: 世界球花 v1 埋点设计 — Dashboard 与告警
version: 0.1.0
date: 2026-06-13
status: draft
depends_on:
  - 01-events-and-model.md
  - docs/superpowers/specs/2026-06-13-shijieqiuhua-prd-v1.md
---

# v1 埋点设计 (2/2)：Dashboard + 告警规则

> 目标：W5 部署 dashboard 和告警；上线后 7 天 / 30 天看哪些数字。

## 0. 设计原则

1. **零外部依赖**：v1 不接 Grafana / Sentry。Dashboard = 一个静态 HTML 页 + 几个 SQL 视图 + cron 渲染。
2. **3 张 dashboard**：
   - **Daily Pulse**（每天看 1 次，5 分钟）— 最关键 8 个指标
   - **Weekly Funnel**（每周一看，30 分钟）— 漏斗 + 留存 + 因子分布
   - **Health & Cost**（运维专用，需要时看）— 错误、性能、成本
3. **告警分级**：P0（电话/短信，仅 v1.5+）/ P1（邮件，5 min 内响应）/ P2（每日摘要，24h 内响应）
4. **指标都有"上线 7 天 / 30 天目标值"**，避免"埋了不知道好坏"。

---

## 1. Daily Pulse Dashboard（每天 5 分钟）

8 个核心数字 + 7 天趋势图。

### 1.1 核心 KPI

| 指标 | 7 天目标 | 30 天目标 | SQL |
|---|---|---|---|
| **DAU**（昨日活跃用户） | ≥ 10 | ≥ 30 | §3.1 |
| **新注册** | ≥ 1/天 | ≥ 1/天 | §3.2 |
| **新付费** | ≥ 1/周 | ≥ 5/周 | §3.3 |
| **昨日提问数** | ≥ 5 | ≥ 30 | §3.4 |
| **5xx 错误率** | < 1% | < 0.5% | §3.5 |
| **dashboard P95 时延** | < 5s（NFR-1） | < 5s | §3.6 |
| **OSINT pipeline P95** | < 30s（NFR-2） | < 30s | §3.7 |
| **info_insufficient 触发率** | 30%-60%（健康区间） | 30%-60% | §3.8 |

### 1.2 7 天趋势图

每个 KPI 对应一个稀疏柱状图（last 7 days）。

### 1.3 异常红点

如果当前指标超出阈值，UI 标红（仅视觉提示，不发告警 — 告警走 §4 单独通道）。

---

## 2. Weekly Funnel Dashboard（每周一）

### 2.1 注册-付费漏斗

```
邀请码访问 (auth.invite_visit)
    │  ──→  转化率 invite_to_register
    ▼
注册成功 (auth.register_success)
    │  ──→  转化率 register_to_view_unlock
    ▼
看 PaymentUnlock (billing.unlock_view)
    │  ──→  转化率 view_to_redeem_attempt
    ▼
兑换尝试 (billing.redeem_attempt)
    │  ──→  转化率 attempt_to_success
    ▼
兑换成功 (billing.redeem_success)
```

| 转化阶段 | 7 天目标 | 30 天目标 |
|---|---|---|
| 邀请码访问 → 注册成功 | ≥ 50% | ≥ 60% |
| 注册成功 → 看付费面板 | ≥ 70% | ≥ 70% |
| 看付费面板 → 兑换尝试 | ≥ 50% | ≥ 60% |
| 兑换尝试 → 成功 | ≥ 80% | ≥ 90% |
| **整体邀请→付费** | ≥ 15% | ≥ 25% |

### 2.2 留存

| 指标 | 目标 |
|---|---|
| **D1 留存**（注册次日访问） | ≥ 40%（7 天）/ ≥ 50%（30 天） |
| **D7 留存** | ≥ 25%（30 天） |
| **D30 留存**（付费用户） | ≥ 30%（v1 成功标准之一） |

### 2.3 行为分布

| 指标 | 用途 |
|---|---|
| 每个已付费用户日均提问数 | 验证 J3 追问需求 |
| 6 维 chips 使用占比 | 验证哪个维度最热 |
| 自由提问 vs 模板路径占比 | 验证 LLM 投入回报 |
| 提问的 `_is_match_related=false` 占比 | 验证 Q9 召回质量 |
| evidence_expand 占比 | 验证 USP U-1（用户真的看证据吗） |

### 2.4 因子健康

| 指标 | 用途 |
|---|---|
| 各因子启用率 (factor_enabled / total_match) | 找"经常缺数据"的因子 |
| 各 adapter 成功率 | 找"经常失败"的数据源 |
| 缓存命中率 | 验证 §5.3 缓存策略 |
| 开赛 6h 强制重算次数 | 验证 OPS-6 |

---

## 3. SQL 视图

每个视图都创建为 SQL view，dashboard 直接 SELECT。

### 3.1 DAU

```sql
CREATE VIEW v_dau AS
SELECT
  date(ts) AS day,
  COUNT(DISTINCT user_id) AS dau
FROM telemetry_event
WHERE user_id IS NOT NULL
  AND event_name IN ('research.dashboard_view', 'research.answer_attempt', 'research.dimension_attempt')
  AND ts >= datetime('now', '-30 days')
GROUP BY date(ts);
```

### 3.2 注册

```sql
CREATE VIEW v_register_daily AS
SELECT date(ts) AS day, COUNT(*) AS new_users
FROM telemetry_event
WHERE event_name = 'auth.register_success'
  AND ts >= datetime('now', '-30 days')
GROUP BY date(ts);
```

### 3.3 付费

```sql
CREATE VIEW v_paid_daily AS
SELECT date(ts) AS day, COUNT(*) AS new_paid
FROM telemetry_event
WHERE event_name = 'billing.redeem_success'
  AND ts >= datetime('now', '-30 days')
GROUP BY date(ts);
```

### 3.4 提问数

```sql
CREATE VIEW v_questions_daily AS
SELECT
  date(ts) AS day,
  SUM(CASE WHEN event_name='research.answer_attempt' THEN 1 ELSE 0 END) AS free_questions,
  SUM(CASE WHEN event_name='research.dimension_attempt' THEN 1 ELSE 0 END) AS chip_questions
FROM telemetry_event
WHERE event_name IN ('research.answer_attempt', 'research.dimension_attempt')
  AND ts >= datetime('now', '-30 days')
GROUP BY date(ts);
```

### 3.5 错误率

```sql
CREATE VIEW v_error_rate_hourly AS
SELECT
  strftime('%Y-%m-%d %H:00', ts) AS hour,
  SUM(CASE WHEN event_name='system.error_5xx' THEN 1 ELSE 0 END) AS errors,
  COUNT(*) AS total,
  ROUND(100.0 * SUM(CASE WHEN event_name='system.error_5xx' THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_pct
FROM telemetry_event
WHERE ts >= datetime('now', '-7 days')
GROUP BY strftime('%Y-%m-%d %H:00', ts);
```

### 3.6 dashboard 时延 P95

SQLite 没有原生百分位函数，用窗口估算：

```sql
CREATE VIEW v_dashboard_p95 AS
SELECT
  date(ts) AS day,
  COUNT(*) AS n,
  -- 估算 P95（取第 ceil(n*0.95) 个）：用排序后取倒数 5%
  (SELECT duration_ms FROM telemetry_event t2
   WHERE t2.event_name='research.dashboard_completed'
     AND date(t2.ts)=date(t1.ts)
     AND t2.status='ok'
   ORDER BY duration_ms DESC
   LIMIT 1 OFFSET CAST(COUNT(*) * 0.05 AS INTEGER)
  ) AS p95_ms
FROM telemetry_event t1
WHERE event_name='research.dashboard_completed' AND status='ok'
  AND ts >= datetime('now', '-7 days')
GROUP BY date(ts);
```

> 量大后用更高效的 approx 算法。v1 量级 OK。

### 3.7 pipeline P95（同上模板）

```sql
CREATE VIEW v_pipeline_p95 AS
SELECT date(ts) AS day,
  (SELECT duration_ms FROM telemetry_event t2
   WHERE t2.event_name='pipeline.job_completed'
     AND date(t2.ts)=date(t1.ts)
   ORDER BY duration_ms DESC
   LIMIT 1 OFFSET CAST(COUNT(*) * 0.05 AS INTEGER)
  ) AS p95_ms
FROM telemetry_event t1
WHERE event_name='pipeline.job_completed'
  AND ts >= datetime('now', '-7 days')
GROUP BY date(ts);
```

### 3.8 信息不足触发率

```sql
CREATE VIEW v_info_insufficient_rate AS
SELECT
  date(t.ts) AS day,
  COUNT(*) AS dashboard_views,
  SUM(CASE WHEN json_extract(t.payload_json, '$.lean')='info_insufficient' THEN 1 ELSE 0 END) AS info_insufficient,
  ROUND(100.0 * SUM(CASE WHEN json_extract(t.payload_json, '$.lean')='info_insufficient' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM telemetry_event t
WHERE event_name='research.dashboard_view'
  AND ts >= datetime('now', '-7 days')
GROUP BY date(t.ts);
```

### 3.9 漏斗（按周聚合）

```sql
CREATE VIEW v_funnel_weekly AS
WITH this_week AS (
  SELECT user_id, event_name, MIN(ts) AS first_ts
  FROM telemetry_event
  WHERE ts >= datetime('now', '-7 days')
    AND user_id IS NOT NULL
    AND event_name IN ('auth.invite_visit', 'auth.register_success', 'billing.unlock_view',
                       'billing.redeem_attempt', 'billing.redeem_success')
  GROUP BY user_id, event_name
)
SELECT
  SUM(CASE WHEN event_name='auth.invite_visit' THEN 1 ELSE 0 END) AS step1_visit,
  SUM(CASE WHEN event_name='auth.register_success' THEN 1 ELSE 0 END) AS step2_register,
  SUM(CASE WHEN event_name='billing.unlock_view' THEN 1 ELSE 0 END) AS step3_unlock_view,
  SUM(CASE WHEN event_name='billing.redeem_attempt' THEN 1 ELSE 0 END) AS step4_redeem_attempt,
  SUM(CASE WHEN event_name='billing.redeem_success' THEN 1 ELSE 0 END) AS step5_redeem_success
FROM this_week;
```

### 3.10 留存

```sql
CREATE VIEW v_retention_d1 AS
WITH cohort AS (
  SELECT user_id, date(ts) AS reg_date
  FROM telemetry_event
  WHERE event_name='auth.register_success'
    AND ts >= datetime('now', '-30 days')
)
SELECT
  c.reg_date,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  COUNT(DISTINCT CASE
    WHEN EXISTS (
      SELECT 1 FROM telemetry_event t
      WHERE t.user_id=c.user_id
        AND date(t.ts)=date(c.reg_date, '+1 day')
    ) THEN c.user_id END) AS d1_returned,
  ROUND(100.0 * COUNT(DISTINCT CASE
    WHEN EXISTS (
      SELECT 1 FROM telemetry_event t
      WHERE t.user_id=c.user_id
        AND date(t.ts)=date(c.reg_date, '+1 day')
    ) THEN c.user_id END) / NULLIF(COUNT(DISTINCT c.user_id), 0), 1) AS d1_retention_pct
FROM cohort c
GROUP BY c.reg_date;
```

### 3.11 adapter 成功率

```sql
CREATE VIEW v_adapter_health AS
SELECT
  json_extract(payload_json, '$.adapter') AS adapter,
  COUNT(*) AS total,
  SUM(CASE WHEN json_extract(payload_json, '$.status')='ok' THEN 1 ELSE 0 END) AS ok,
  SUM(CASE WHEN json_extract(payload_json, '$.status')='failed' THEN 1 ELSE 0 END) AS failed,
  SUM(CASE WHEN json_extract(payload_json, '$.status')='skipped' THEN 1 ELSE 0 END) AS skipped,
  ROUND(100.0 * SUM(CASE WHEN json_extract(payload_json, '$.status')='ok' THEN 1 ELSE 0 END) / COUNT(*), 1) AS ok_pct
FROM telemetry_event
WHERE event_name='pipeline.adapter_called'
  AND ts >= datetime('now', '-7 days')
GROUP BY json_extract(payload_json, '$.adapter')
ORDER BY ok_pct ASC;
```

### 3.12 LLM 成本

```sql
CREATE VIEW v_llm_cost_daily AS
SELECT
  date(ts) AS day,
  json_extract(payload_json, '$.purpose') AS purpose,
  COUNT(*) AS calls,
  SUM(CAST(json_extract(payload_json, '$.prompt_tokens') AS INTEGER)) AS prompt_tokens,
  SUM(CAST(json_extract(payload_json, '$.completion_tokens') AS INTEGER)) AS completion_tokens
FROM telemetry_event
WHERE event_name='llm.call_completed' AND status='ok'
  AND ts >= datetime('now', '-30 days')
GROUP BY date(ts), json_extract(payload_json, '$.purpose');
```

DeepSeek 价格按 `purpose` 分类后乘单价；目标月成本 < ¥500（PRD §11.1 验收）。

---

## 4. 告警规则

### 4.1 告警通道

v1 简化方案：**邮件**（通过 Resend 或 SMTP）。
v1 暂不接 PagerDuty / 短信；v1.5 视情况升级。

### 4.2 告警级别与触发条件

| 级别 | 通道 | 响应窗口 | 含义 |
|---|---|---|---|
| **P1** | 邮件 + 控制台 | 5 min | 立即影响用户的故障 |
| **P2** | 每日摘要邮件 | 24h | 趋势异常但未"宕机" |

> v1 没有 P0（电话/短信）；单人节奏，5 分钟邮件响应已经是上限。

### 4.3 告警清单

| 规则 ID | 触发条件 | 级别 | 备注 |
|---|---|---|---|
| ALERT-1 | 5xx 错误率 > 5%（10 分钟窗口） | P1 | 故障 |
| ALERT-2 | uptime_heartbeat 缺失 > 3 分钟 | P1 | 进程挂了 |
| ALERT-3 | dashboard P95 > 10s（5 分钟窗口） | P1 | NFR-1 严重违规 |
| ALERT-4 | pipeline P95 > 90s（5 分钟窗口） | P1 | NFR-2 严重违规 |
| ALERT-5 | DeepSeek 失败率 > 50%（10 分钟窗口） | P1 | RISK-5 触发 |
| ALERT-6 | url_blocked 速率突增 > 20/min | P1 | 可能受到 SRF 攻击尝试 |
| ALERT-7 | 单 IP register_attempt > 30/min | P1 | 暴力刷邀请码 |
| ALERT-8 | backup 失败 | P1 | 数据安全 |
| ALERT-9 | telemetry_event 行数 24h 0 增长 | P1 | 埋点本身挂了 |
| ALERT-10 | DeepSeek 月成本预估 > ¥400 | P2 | 接近月预算 ¥500 |
| ALERT-11 | info_insufficient 占比 > 70% 持续 1 天 | P2 | 数据源大面积失败（RISK-3） |
| ALERT-12 | adapter ok_pct < 30% 持续 24h | P2 | 单一数据源持续失败 |
| ALERT-13 | DAU 周环比下降 > 50% | P2 | 流失警告 |
| ALERT-14 | 当周注册转化率 < 30% | P2 | 漏斗异常 |
| ALERT-15 | bronze 目录 > 4GB | P2 | 接近容量上限 |
| ALERT-16 | systemd 重启次数 > 3 次/小时 | P2 | OOM / 崩溃循环 |

### 4.4 告警实现

#### 4.4.1 P1 实时告警 — `backend/alert_runner.py`

```python
# 后台 cron 每分钟跑一次
def run_p1_checks() -> list[Alert]:
    """每分钟跑；查 SQL 视图 + 阈值；超阈值则 emit 邮件。"""
    alerts = []

    # ALERT-1: 5xx > 5%
    last_10min_error_pct = db.scalar("""
      SELECT 100.0 * SUM(CASE WHEN event_name='system.error_5xx' THEN 1 ELSE 0 END)
                   / NULLIF(COUNT(*), 0)
      FROM telemetry_event WHERE ts >= datetime('now', '-10 minutes')
    """)
    if last_10min_error_pct and last_10min_error_pct > 5:
        alerts.append(Alert('P1', 'ALERT-1', f'5xx error rate {last_10min_error_pct:.1f}%'))

    # ALERT-2: 心跳缺失
    last_hb = db.scalar("""
      SELECT (julianday('now') - julianday(MAX(ts))) * 24 * 60
      FROM telemetry_event WHERE event_name='system.uptime_heartbeat'
    """)
    if last_hb is None or last_hb > 3:
        alerts.append(Alert('P1', 'ALERT-2', f'No heartbeat for {last_hb} min'))

    # ... ALERT-3..9

    return alerts


def main():
    alerts = run_p1_checks()
    for a in alerts:
        if not is_recently_fired(a.rule_id, cooldown_minutes=15):
            send_email(a)
            mark_fired(a.rule_id)


if __name__ == '__main__':
    main()
```

cron：

```
* * * * * /opt/osint-network/.venv/bin/python -m backend.alert_runner >> /var/log/osint-alerts.log 2>&1
```

每 15 min 内同一规则不重复发邮件（`is_recently_fired` 用 `alert_fired` 表做去重）。

#### 4.4.2 P2 每日摘要 — `backend/alert_daily.py`

```
0 9 * * * /opt/osint-network/.venv/bin/python -m backend.alert_daily
```

每天 9 点跑：聚合昨日所有 P2 检查 → 一封摘要邮件。

#### 4.4.3 alert_fired 表

```sql
CREATE TABLE alert_fired (
  rule_id TEXT NOT NULL,
  fired_at TIMESTAMP NOT NULL,
  payload_json TEXT,
  PRIMARY KEY (rule_id, fired_at)
);
CREATE INDEX idx_alert_recent ON alert_fired(rule_id, fired_at);
```

---

## 5. Dashboard 渲染方案

### 5.1 选型

v1 不接 Grafana。三个备选：

| 方案 | 优点 | 缺点 | v1 推荐？ |
|---|---|---|---|
| **A. Datasette**（Python 自动生成 SQL UI） | 1 行命令；自动生成 dashboard；本地权限控制 | 风格朴素 | ✅（推荐） |
| B. 自写 FastAPI 路由 `/admin/dashboard` 渲染 HTML | 风格统一 | 工作量 1-2 天 | v1.5 |
| C. Grafana + SQLite plugin | 可视化好 | 引入新组件 | v2 |

**推荐 A**：`pip install datasette` → `datasette serve osint.db --port 8001 --auth-token=$ADMIN_TOKEN`，10 分钟搞定。所有 §3 视图直接 SQL 浏览。

### 5.2 nginx 反向代理

datasette 仅监听 127.0.0.1:8001；nginx 加 location：

```nginx
location /admin/dashboard/ {
    auth_basic "Admin Only";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:8001/;
}
```

仅产品负责人能访问。

---

## 6. 上线节奏

| 时点 | 动作 |
|---|---|
| W1-W2 | 落 telemetry_event 表 + emit/measure SDK + request_id 中间件 |
| W2-W3 | 在每个用例里加 emit（搭功能时一起） |
| W4 | 落 §3 SQL 视图 + alert_fired 表 |
| W5 | 部署 datasette + 配置 alert_runner cron + 测告警邮件 |
| W5 末 | dry-run：人工触发每个 P1 告警，验证邮件到达 |
| 上线后 D1 | 检查 dashboard 是否每个 KPI 有数据 |
| 上线后 D7 | 第一次 Weekly Funnel review |
| 上线后 D30 | 评估目标达成；调整 v1.1 优先级 |

---

## 7. 与 PRD 验收对齐

| PRD 验收 | 本设计落点 |
|---|---|
| NFR-1 dashboard < 5s P95 | `v_dashboard_p95` + ALERT-3 |
| NFR-2 pipeline P95 < 30s | `v_pipeline_p95` + ALERT-4 |
| NFR-3 月可用性 99% | uptime_heartbeat + ALERT-2 + 月度计算 |
| NFR-5 备份每日 | system.backup_completed + ALERT-8 |
| NFR-7 速率限制 | system.rate_limited + ALERT-7 |
| RISK-3 信息不足太频繁 | `v_info_insufficient_rate` + ALERT-11 |
| 30 天目标：付费用户 D7 留存 ≥ 30% | `v_retention_d1` 扩展为 D7 |
| Q24 监控/告警工具决策 | datasette + 自写 alert_runner |
| Q14 信息不足阈值校准 | dashboard 实时显示，admin CLI 可调 |

---

## 8. 隐私与保留策略

- telemetry_event 保留 90 天；超期归档（zip + 删除）
- audit_log 保留 6 个月（合规）
- alert_fired 保留 30 天

`backend/admin.py` 加命令：

```bash
python -m backend.admin telemetry purge --older-than-days 90
python -m backend.admin audit_log archive --older-than-days 180 --output audit-2026Q1.zip
```

cron 月初跑一次。

---

## 9. 不在 v1 范围（明确延后）

| 项 | 时点 | 原因 |
|---|---|---|
| 用户行为漏斗细分（设备、地域） | v2 | 需要更多 PII |
| 真实用户访谈数据集成（5 人访谈结论 → dashboard） | v1.1 | 等访谈做完 |
| LLM 成本自动告警（含估价） | v1.1 | DeepSeek 价格表硬编码风险 |
| Grafana 集成 | v2 | 工程量 |
| A/B 测试基础设施 | v2 | 量小没意义 |

---

## 10. 推荐下一步

埋点设计（1+2）完成。可选的下一步：

| 选项 | 说明 |
|---|---|
| **A 立刻启动 W1** | 按 PRD §11 开干 |
| **B 把埋点 SDK 写出来**（`backend/telemetry.py` + tests） | 1 天工作 |
| **C 先决 Q11 / Q21** | 内测名单 + 用户协议 |
| **D 把 datasette + 告警邮件先搭起来**（不带数据，只跑架子） | 半天工作；上线前提早验证告警通道 |

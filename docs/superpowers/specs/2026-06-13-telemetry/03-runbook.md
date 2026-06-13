---
title: 世界球花 v1 埋点设计 — 部署 Runbook
version: 0.1.0
date: 2026-06-13
status: draft
depends_on:
  - 01-events-and-model.md
  - 02-dashboards.md
---

# v1 埋点设计 (3/3)：部署 / 联调 / dry-run runbook

> 本文档假定你已经把 `backend/telemetry.py`、`backend/alert_runner.py`、`sql/002_telemetry.sql`、`scripts/run-dashboard.sh`、`scripts/datasette-metadata.json` 都拉到了仓库里。本 runbook 走完一次，告警通道就**算彻底验证过**。

## 0. 前置

- 已激活 backend `.venv`，已 `pip install -r requirements.txt`
- 把 `.env.telemetry.example` 拷成 `.env.telemetry`（或合到主 `.env`），按 §2 填 SMTP 凭据
- 把 datasette 装到一个独立 venv（避免把 backend 依赖弄乱）：
  ```bash
  python3 -m venv ~/.venvs/datasette
  ~/.venvs/datasette/bin/pip install datasette
  echo 'export DATASETTE_BIN=$HOME/.venvs/datasette/bin/datasette' >> .env.telemetry
  ```

## 1. 一次性 bootstrap

```bash
# 1. 让 telemetry SDK 自动建表（第一次 emit 触发 migration）
python -c "from backend import telemetry; telemetry.emit('system.uptime_heartbeat', payload={'bootstrap': True})"

# 2. 验证表存在
sqlite3 bronze_storage/_telemetry.db "SELECT name FROM sqlite_master WHERE type='table'"
# 期望输出：telemetry_event, alert_fired, sqlite_sequence
```

## 2. 配置 SMTP

按你选的服务商填 `.env.telemetry`。三个常见配置：

### 2.1 Resend（推荐，开发友好，每月 3000 封免费）

1. https://resend.com 注册 → 用自己的域名验证（或先用 Resend 提供的 `onboarding@resend.dev` 试发）
2. 拿到 API key（`re_xxx`）
3. `.env.telemetry`：
   ```
   ALERT_SMTP_HOST=smtp.resend.com
   ALERT_SMTP_PORT=587
   ALERT_SMTP_USER=resend
   ALERT_SMTP_PASSWORD=re_xxxxxxxxxxxxxxx
   ALERT_FROM="ShijieQiuhua Alerts <alerts@yourdomain.com>"
   ALERT_TO=your_personal_email@example.com
   ```

### 2.2 阿里云邮件推送

1. 控制台开通邮件推送 → 创建发信地址 + SMTP 密码
2. `.env.telemetry`：
   ```
   ALERT_SMTP_HOST=smtpdm.aliyun.com
   ALERT_SMTP_PORT=465
   ALERT_SMTP_USER=alerts@yourverifieddomain.com
   ALERT_SMTP_PASSWORD=your_smtp_password
   ALERT_SMTP_TLS=1
   ALERT_FROM=alerts@yourverifieddomain.com
   ALERT_TO=your_personal_email@example.com
   ```
3. 阿里云需要 SSL，端口 465 + STARTTLS 方式可能要小调；如不通，`ALERT_SMTP_PORT=80` 走非加密内网通道（仅服务器内）

### 2.3 QQ/163 个人邮箱（仅临时调试）

1. 邮箱设置 → 开 SMTP → 拿"授权码"（不是登录密码）
2. `.env.telemetry`：
   ```
   ALERT_SMTP_HOST=smtp.qq.com
   ALERT_SMTP_PORT=587
   ALERT_SMTP_USER=youraccount@qq.com
   ALERT_SMTP_PASSWORD=your_authorization_code
   ALERT_FROM=youraccount@qq.com
   ALERT_TO=your_personal_email@example.com
   ```

> 不推荐把 QQ/163 当生产告警通道：限速严、易被判垃圾。仅用于第一次跑通验证。

## 3. 端到端 dry-run（**核心步骤**）

按顺序跑这五条命令；每条都要看见预期输出。

### 3.1 测试 SMTP 凭据

```bash
set -a; source .env.telemetry; set +a
python -m backend.alert_runner test-email
```

期望日志：
```
INFO alert_runner: test email status: sent
```

如果是 `failed`：
- 检查 `ALERT_SMTP_HOST` / 端口 / 用户密码
- 检查 `ALERT_FROM` 域名是否在邮件服务商验证过
- 如果 STARTTLS 失败，试 `ALERT_SMTP_TLS=0` 看是否端口要求不同
- 看一下 `/var/log/maillog` 或服务商控制台的 reject 日志

### 3.2 检查邮箱

去 `ALERT_TO` 邮箱里看，应该收到一封：
- Subject: `[P1] TEST alert_runner test email`
- Body: `If you can read this, SMTP is configured correctly.`

如果**没收到但 §3.1 显示 sent**：
- 检查垃圾邮件
- 检查 `ALERT_FROM` 有没有 SPF/DKIM（否则会被收件方拒）

### 3.3 模拟一条 P1 告警

```bash
python -m backend.alert_runner simulate ALERT-1
python -m backend.alert_runner run-once
```

期望日志：
```
INFO alert_runner: FIRED P1 ALERT-1 -> sent
INFO alert_runner: done; 1 alerts processed
```

收件箱应该收到第二封邮件，标题类似 `[P1] ALERT-1 5xx error rate 50.0% (last 10 min)`。

### 3.4 验证 cooldown

立刻再跑一次：
```bash
python -m backend.alert_runner simulate ALERT-1
python -m backend.alert_runner run-once
```

期望日志：
```
INFO alert_runner: rule ALERT-1 in cooldown, skip
INFO alert_runner: done; 0 alerts processed
```

**不应该**收到第二封 ALERT-1 邮件（cooldown 默认 15 min）。

### 3.5 dry-run 不发邮件

```bash
python -m backend.alert_runner simulate ALERT-3
python -m backend.alert_runner dry-run
```

期望日志：
```
INFO alert_runner: DRY P1 ALERT-3 | dashboard P95 = 12000 ms (>10s, NFR-1)
INFO alert_runner: done; 1 alerts would have been sent
```

收件箱**不应该**有新邮件。`alert_fired` 表里这条应该是 `delivery_status=skipped_dryrun`。

## 4. 启动 datasette

```bash
scripts/run-dashboard.sh 8001
```

期望：
```
INFO:     Started server process [...]
INFO:     Uvicorn running on http://127.0.0.1:8001
```

浏览器开 http://127.0.0.1:8001/_telemetry → 应该看到：
- 两张表：`telemetry_event` / `alert_fired`
- 14 条 canned queries（左侧菜单）

逐个点开测：

| Query | 期望（dry-run 后） |
|---|---|
| `01_dau` | 空（还没真用户） |
| `13_recent_alerts` | 至少 3 行（来自 §3.3-3.5 三次 simulate） |
| `14_event_volume` | 至少 `system.error_5xx`、`research.dashboard_completed`、`system.uptime_heartbeat` 几行 |

如果 `13_recent_alerts` 看到了你模拟的告警，**端到端通了**。

## 5. 生产部署

### 5.1 cron 定时

服务器上加：

```bash
# alert_runner 每分钟跑（P1 实时检测）
* * * * * cd /opt/osint-network && set -a && source .env && source .env.telemetry && set +a && /opt/osint-network/.venv/bin/python -m backend.alert_runner run-once >> /var/log/osint-alerts.log 2>&1

# uptime heartbeat 每分钟（提供 ALERT-2 信号）
* * * * * cd /opt/osint-network && /opt/osint-network/.venv/bin/python -c "from backend import telemetry; telemetry.emit('system.uptime_heartbeat', payload={'memory_mb': 0})"
```

### 5.2 nginx 反代 datasette

```nginx
location /admin/dashboard/ {
    auth_basic "Admin Only";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`htpasswd` 加一个用户：
```bash
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

### 5.3 datasette systemd

`/etc/systemd/system/osint-dashboard.service`：

```ini
[Unit]
Description=ShijieQiuhua telemetry dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/osint-network
EnvironmentFile=/opt/osint-network/.env.telemetry
ExecStart=/bin/bash /opt/osint-network/scripts/run-dashboard.sh 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now osint-dashboard.service
```

### 5.4 ALERT_POSTLAUNCH

v1 上线**当天**才打开：

```bash
echo "ALERT_POSTLAUNCH=1" >> .env.telemetry
sudo systemctl restart osint-dashboard.service
# cron 下次跑时会自动读到新值
```

打开后 ALERT-9（telemetry 静默 24h）才会真触发。**不打开**会让 v1 上线前 7 天里持续 0 流量也不报警，给冷启动留余地。

## 6. 故障排查

| 症状 | 处理 |
|---|---|
| `test-email` 显示 `missing_smtp_config` | `ALERT_SMTP_HOST` / `ALERT_FROM` / `ALERT_TO` 至少一项空。`set -a; source .env.telemetry; set +a` 后再跑 |
| `test-email` 显示 `failed` | 检查 `/var/log/osint-alerts.log` 里的 SMTP 错误。常见：`Authentication failed`（密码错）、`Sender address rejected`（FROM 域未验证）、`Connection timed out`（防火墙挡住了 587）|
| dry-run 没 fire 任何规则 | `simulate` 返回的消息里说"insert N rows"，可以直接 `sqlite3 bronze_storage/_telemetry.db 'SELECT COUNT(*) FROM telemetry_event'` 验证；如果是 0，说明 emit 失败（看应用日志的 warning）|
| datasette 启动报 `database is locked` | telemetry.py 用 WAL 但 datasette 默认会拿 read 锁；脚本里加了 `serve` 不带 `--immutable` 是有意的（datasette 启动时就需要 schema 锁）。如果生产真锁住，把 datasette 切成 `--immutable` + 手动重启 |
| 收到大量 cooldown skip 日志 | 这是预期的；cooldown 期内同一规则不重发。要立刻重发：`sqlite3 _telemetry.db "DELETE FROM alert_fired WHERE rule_id='ALERT-X'"` |
| 邮件被收件方判垃圾 | `ALERT_FROM` 改成自己有 SPF/DKIM 的域名；不要用免费邮箱当 FROM |
| 单测在 CI 里跑得慢 | 不应该慢。每个 case < 10ms。如果慢检查是不是 `tmp_path` 在网络盘上 |

## 7. 上线前 checklist

W5 末必须每条勾选：

- [ ] §3.1 test-email 收到
- [ ] §3.3 ALERT-1 simulate 收到邮件
- [ ] §3.4 cooldown 验证通过（第二封不发）
- [ ] §3.5 dry-run 不发邮件
- [ ] §4 datasette 14 条 canned queries 全部能查
- [ ] §5.1 cron 配好，alert_runner 每分钟跑
- [ ] §5.1 uptime_heartbeat 每分钟跑
- [ ] §5.2 nginx 反代配好，外网无法直连 :8001
- [ ] `auth_basic` 用户密码已设置
- [ ] §5.4 `ALERT_POSTLAUNCH=1`（仅在 v1 上线那天打开）
- [ ] backup 把 `_telemetry.db` 也包进 rsync（NFR-5）

## 8. 与 PRD 对齐

| PRD 项 | 本 runbook 落点 |
|---|---|
| Q24 监控/告警工具 | datasette + 自写 alert_runner |
| Rollout-6 关键埋点就绪 | §3-§4 验证通过 |
| Rollout-9 全链路 HTTPS | §5.2 nginx 反代 |
| Rollout-12 GAP-A 必补项 | telemetry_event / alert_fired / admin CLI 都覆盖 |
| ALERT-2 心跳 | §5.1 uptime_heartbeat cron |
| ALERT-9 静默 | §5.4 POSTLAUNCH 开关 |

---
phase: audit
artifact: logic-hard-injury-audit
date: 2026-06-13
---

# 世界球花 v1 逻辑硬伤审计

## 致命 P0

### 1. register_user() 邀请码竞态 — 无事务

`backend/auth/service.py:96-113`

verify → INSERT users → consume 三次独立 DB 操作，不在同一事务。两个并发用户同时用 `max_uses=1` 邀请码可以一起通过 verify，邀请码被消费两次。

**修复**：`BEGIN IMMEDIATE` + 先 UPDATE current_uses 再加 WHERE current_uses < max_uses 检查。

### 2. login_user() 登录记录用 MAX(id)

`backend/auth/service.py:131`

```python
UPDATE ... WHERE id = (SELECT MAX(id) FROM login_attempts WHERE identifier = ?)
```

应使用 `cursor.lastrowid`，否则两个并发登录可能交叉更新对方行。

### 3. app_football.py 无速率限制

生产入口 `backend/app_football.py` 没有 `main.py` 的 rate_limit_middleware。任何人都可无限调用 OSINT/answer 端点。

---

## 严重 P1

### 4. 登录/注册响应不含 entitlements

`backend/auth/routes.py:100` — LoginResponse 不含 entitlements。前端依赖 `useEffect → getMe()` 二次请求补数据，但窗口期用户可能看到 AuthGate 遮挡。

### 5. handleLogout 不清 OSINT 状态

`frontend/src/App.tsx:55` — 退出后 osintJob / answer / error 未重置，上一个用户的研判数据残留页面。

---

## 中等 P2

### 6. PaymentUnlock 假权益 granted_at=''
### 7. AdminPanel 无 401 处理
### 8. register_user 不校验 email 格式

---

## 低风险（已知接受）
- OSINT predict-sync 匿名可访问（PRD 有意设计）
- Win007 依赖 lp-fetch-md（v1 零配置策略限制）
- SQLite 单文件（v1 量级足够）

## 修复优先级

| 优先级 | 项 | 工作量 |
|---|---|---|
| P0 | register 事务 + login lastrowid + 速率限制 | 30 min |
| P1 | entitlements + logout 清状态 | 15 min |
| **合计** | | **45 min** |

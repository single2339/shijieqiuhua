# Deployment Targets

## Shijie Qiuhua (世界球花) — PRODUCTION

- SSH alias: `sqh-server`
- Host: 139.155.117.190
- SSH user: root (key auth, `~/.ssh/id_ed25519`)
- App root: `/opt/shijieqiuhua`
- systemd service: `shijieqiuhua` — runs `backend.app_football:app` on `127.0.0.1:8002`
- EnvironmentFile: `/opt/shijieqiuhua/.env` (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, JWT_SECRET, FOOTBALL_DATA_API_KEY)
- nginx: `/etc/nginx/conf.d/shijieqiuhua.conf` — listen 80, root `/opt/shijieqiuhua/frontend/dist`, `/api` → `127.0.0.1:8002`
- Deploy backend: `rsync -avz --exclude='__pycache__' --exclude='*.pyc' backend/ sqh-server:/opt/shijieqiuhua/backend/ && ssh sqh-server 'systemctl restart shijieqiuhua'`
- Deploy frontend: `rsync -avz frontend/dist/ sqh-server:/opt/shijieqiuhua/frontend/dist/` (after `npm run build`)
- Verified deployed here on 2026-06-15.

## Other servers — NOT Shijie Qiuhua (do not deploy SQH here)

- `osint-server` = 221.239.50.138 (ubuntu, port 9022) — the osint-network system.
- `football-server` / 足球服务器 = 221.239.50.142 (ubuntu, port 9022) — separate box; purpose unverified, NOT the SQH production host.

Note: credentials are intentionally not stored in this repository memory file.

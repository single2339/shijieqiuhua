# 世界球花 v1 故障排查 SOP

## 服务挂了
1. `ssh sqh-server` → `systemctl status shijieqiuhua`
2. `journalctl -u shijieqiuhua --no-pager -n 30` 找崩溃原因
3. 常见：OOM → 调 MemoryMax；端口占用 → `ss -tlnp | grep 8002`

## DeepSeek 503
1. 确认 `.env` 中 `LLM_API_KEY` 未过期
2. curl 测试：`curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $LLM_API_KEY"`
3. 用户侧：自由提问降级为基础分析

## 数据源全挂 → 大量 info_insufficient
1. `curl -I http://m.win007.com/` 确认 Win007 可访问
2. 检查 adapter 日志：`journalctl -u shijieqiuhua | grep adapter`

## 前端空白
1. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/` → 须为 200
2. `ls /opt/shijieqiuhua/frontend/dist/index.html` 须存在
3. `nginx -t && systemctl reload nginx`

## DB 损坏
1. `systemctl stop shijieqiuhua`
2. `tar -xzf /opt/shijieqiuhua/backups/auth-*.tar.gz -C /`
3. `systemctl start shijieqiuhua`

## 磁盘满
1. `df -h /opt/shijieqiuhua`
2. `find /opt/shijieqiuhua/backups -mtime +7 -delete`
3. `journalctl --vacuum-size=200M`

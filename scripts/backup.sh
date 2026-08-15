#!/usr/bin/env bash
# Daily backup for shijieqiuhua — run as cron:
#   0 3 * * * cd /opt/shijieqiuhua && bash scripts/backup.sh >> /var/log/sqh-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/shijieqiuhua/backups}"
SOURCE_DIR="${SOURCE_DIR:-/opt/shijieqiuhua/bronze_storage}"
STAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/bronze_$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

tar -czf "$ARCHIVE" -C "$(dirname "$SOURCE_DIR")" "$(basename "$SOURCE_DIR")"
echo "[$STAMP] backup ok: $ARCHIVE ($(du -sh "$ARCHIVE" | cut -f1))"

# 7-day retention
find "$BACKUP_DIR" -name 'bronze_*.tar.gz' -mtime +7 -delete
echo "[$STAMP] old backups pruned"

# Emit telemetry so ALERT-8 can verify
python3 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath('$0'))))
try:
    from backend import telemetry
    telemetry.emit('system.backup_completed', status='ok', payload={'kind': 'bronze', 'archive': '$ARCHIVE'})
except Exception as e:
    print('telemetry emit failed (non-fatal):', e)
" 2>/dev/null || true

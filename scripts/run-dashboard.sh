#!/usr/bin/env bash
# Launch Datasette against the telemetry SQLite DB.
#
# Usage:
#   scripts/run-dashboard.sh [port]
#
# The default port is 8001. Datasette listens on 127.0.0.1 only — production
# deployments expose it via nginx with auth (see docs/.../03-runbook.md).
#
# Env:
#   FOOTBALL_OSINT_TELEMETRY_DB  override DB path (default: bronze_storage/_telemetry.db)
#   DATASETTE_BIN                override datasette executable (default: looked up on PATH)

set -euo pipefail

PORT="${1:-8001}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${FOOTBALL_OSINT_TELEMETRY_DB:-$ROOT/bronze_storage/_telemetry.db}"
META="$ROOT/scripts/datasette-metadata.json"

DATASETTE="${DATASETTE_BIN:-$(command -v datasette || true)}"
if [ -z "$DATASETTE" ]; then
  echo "datasette not on PATH. Install with: pip install datasette" >&2
  echo "Recommended: use a dedicated venv to avoid polluting backend deps." >&2
  exit 127
fi

if [ ! -f "$DB_PATH" ]; then
  echo "Telemetry DB not found at $DB_PATH"
  echo "Bootstrap it with one of:"
  echo "  - run any backend code that calls telemetry.emit()"
  echo "  - python -m backend.alert_runner simulate ALERT-1"
  exit 1
fi

# --immutable mounts the DB read-only inside Datasette — alert_runner still
# writes via its own connection. This avoids Datasette holding write locks.
exec "$DATASETTE" \
  serve "$DB_PATH" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --metadata "$META" \
  --setting suggest_facets off \
  --setting truncate_cells_html 256 \
  --setting default_page_size 50

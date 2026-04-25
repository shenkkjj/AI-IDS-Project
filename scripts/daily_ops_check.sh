#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
BASE_URL=${1:-"http://127.0.0.1:8000"}

check_url() {
  local url=$1
  local expected=${2:-200}
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" "$url" || true)
  if [[ "$code" != "$expected" ]]; then
    echo "[daily] FAIL $url expected=$expected got=$code"
    return 1
  fi
  echo "[daily] PASS $url ($code)"
}

check_url "$BASE_URL/health" 200

echo "[daily] reminder: verify alerts ingest token, site health panel, and run scripts/backup_db.sh"

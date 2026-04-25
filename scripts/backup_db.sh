#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DATE_TAG=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-"$ROOT_DIR/../ai-ids-backups"}
DB_PATH="$ROOT_DIR/data/app.db"
TARGET="$BACKUP_DIR/app-${DATE_TAG}.db"

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
  echo "[backup] missing database: $DB_PATH" >&2
  exit 1
fi

cp "$DB_PATH" "$TARGET"

echo "[backup] created: $TARGET"

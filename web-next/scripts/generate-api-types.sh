#!/usr/bin/env bash
# Generate TypeScript types from the FastAPI backend's OpenAPI schema.
#
# Usage:
#   BACKEND_URL=http://127.0.0.1:8000 ./scripts/generate-api-types.sh
#
# Output:
#   web-next/types/api.generated.ts  — types mirroring every backend route
#   web-next/types/api.generated.d.ts (in case the runner emits both)
#
# The generated file is .gitignored (see web-next/.gitignore entry) so the
# working tree stays free of regeneration noise. Re-run after every
# meaningful backend API change.

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/types"
OUT_FILE="$OUT_DIR/api.generated.ts"

mkdir -p "$OUT_DIR"

echo "▸ Fetching OpenAPI schema from $BACKEND_URL/openapi.json"
schema_json=$(curl -fsSL "$BACKEND_URL/openapi.json")

echo "▸ Running openapi-typescript"
# Try the local install first; fall back to npx.
if [ -x "node_modules/.bin/openapi-typescript" ]; then
  node_modules/.bin/openapi-typescript \
    --input "$BACKEND_URL/openapi.json" \
    --output "$OUT_FILE" \
    --enum "${@:-true}" \
    --immutable false
else
  npx --yes openapi-typescript@"^7" \
    --input "$BACKEND_URL/openapi.json" \
    --output "$OUT_FILE"
fi

echo "✓ Generated $OUT_FILE"
echo "  Add to your .gitignore:  web-next/types/api.generated.ts"

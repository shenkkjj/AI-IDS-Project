#!/usr/bin/env bash
set -euo pipefail

EMAIL=${1:-"qa-smoke-$(date +%s)@example.com"}
PASSWORD=${2:-}
BASE_URL=${3:-"http://127.0.0.1:8000"}

if ! command -v curl >/dev/null 2>&1; then
  echo "[smoke] missing curl runtime" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[smoke] missing node runtime" >&2
  exit 1
fi

if [[ -z "${PASSWORD}" ]]; then
  PASSWORD=$(node -e 'const crypto = require("node:crypto"); process.stdout.write(crypto.randomBytes(18).toString("base64url"));')
fi

log() {
  printf "[smoke] %s\n" "$1"
}

log "health check: ${BASE_URL}/health"
curl -fsS "${BASE_URL}/health" > /dev/null

log "register user: ${EMAIL}"
REGISTER_PAYLOAD=$(node -e 'const email = process.argv[1]; const password = process.argv[2]; const displayName = process.argv[3]; process.stdout.write(JSON.stringify({ email, password, display_name: displayName }));' "${EMAIL}" "${PASSWORD}" "QA Smoke")

REGISTER_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/auth/register" -H "Content-Type: application/json" -d "${REGISTER_PAYLOAD}")
if [[ "${REGISTER_CODE}" != "200" && "${REGISTER_CODE}" != "409" ]]; then
  log "register failed, status=${REGISTER_CODE}"
  exit 1
fi

log "password login: ${EMAIL}"
LOGIN_PAYLOAD=$(node -e 'const email = process.argv[1]; const password = process.argv[2]; process.stdout.write(JSON.stringify({ email, password }));' "${EMAIL}" "${PASSWORD}")
LOGIN_RAW=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/auth/login/password" -H "Content-Type: application/json" -d "${LOGIN_PAYLOAD}")
LOGIN_CODE=${LOGIN_RAW##*$'\n'}
LOGIN_BODY=${LOGIN_RAW%$'\n'*}
if [[ "${LOGIN_CODE}" != "200" ]]; then
  log "login failed, status=${LOGIN_CODE}"
  printf "%s\n" "${LOGIN_BODY}"
  exit 1
fi

ACCESS_TOKEN=$(LOGIN_BODY="${LOGIN_BODY}" node -e 'const raw = process.env.LOGIN_BODY || "{}"; const data = JSON.parse(raw); process.stdout.write(data.access_token || "")')

if [[ -z "${ACCESS_TOKEN}" ]]; then
  log "missing access_token in login response"
  exit 1
fi

log "site health with bearer token"
SITE_HEALTH_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${ACCESS_TOKEN}" "${BASE_URL}/site/health")
if [[ "${SITE_HEALTH_CODE}" != "200" ]]; then
  log "site health failed, status=${SITE_HEALTH_CODE}"
  exit 1
fi

log "PASS: register/login/site-health"

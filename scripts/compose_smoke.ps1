# AI-CyberSentinel Docker Compose local smoke script.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\compose_smoke.ps1 -EnvFile .env.compose.local
#
# Steps:
#   1. Verify env file exists
#   2. docker compose config (syntax only, no daemon needed)
#   3. build backend / frontend
#   4. up -d
#   5. wait /health 200 (max 60s)
#   6. wait /ready 200 (max 90s)
#   7. nginx http://127.0.0.1/health
#   8. frontend root page :3000
#   9. show ps / logs
#  10. do NOT auto-down (leave to operator)
#
# Design:
#   - never delete any volume or image
#   - never print real secrets to stdout
#   - fail fast on any step; print next-step hint
#   - never touch the real .env
#   - exit code: 0 = all passed / 1 = failed

[CmdletBinding()]
param(
    [string]$EnvFile = ".env.compose.local",
    [int]$HealthTimeoutSeconds = 60,
    [int]$ReadyTimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

function Write-Step($msg) { Write-Host "[smoke] $msg" -ForegroundColor Cyan }
function Write-Pass($msg) { Write-Host "[smoke] PASS $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[smoke] FAIL $msg" -ForegroundColor Red }

if (-not (Test-Path $EnvFile)) {
    Write-Fail "env file $EnvFile not found"
    Write-Host "    copy template: Copy-Item .env.example $EnvFile and fill in strong random secrets" -ForegroundColor Yellow
    exit 1
}

# 1. validate compose config syntax
Write-Step "validate docker compose config syntax"
$cfgOutput = docker compose --env-file $EnvFile config 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose config failed"
    Write-Host $cfgOutput
    exit 1
}
Write-Pass "compose config syntax OK"

# 2. build
Write-Step "build backend / frontend / nginx (may take several minutes)"
docker compose --env-file $EnvFile build backend frontend nginx 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "build failed; see output above"
    exit 1
}
Write-Pass "build completed"

# 3. up -d
Write-Step "start all services (migrate / backend / frontend / nginx / postgres / redis)"
docker compose --env-file $EnvFile up -d 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "up failed; see output above"
    exit 1
}
Write-Pass "up -d completed"

# 4. wait backend /health 200
Write-Step "wait backend http://127.0.0.1:8000/health to return 200 (max $HealthTimeoutSeconds s)"
$elapsed = 0
$healthOk = $false
while ($elapsed -lt $HealthTimeoutSeconds) {
    try {
        $code = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 3).StatusCode
        if ($code -eq 200) { $healthOk = $true; break }
    } catch {
        # not up yet; keep waiting
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
}
if (-not $healthOk) {
    Write-Fail "/health timeout"
    Write-Host "    docker compose --env-file $EnvFile logs --tail=100 backend" -ForegroundColor Yellow
    exit 1
}
Write-Pass "/health returned 200"

# 5. wait backend /ready 200
Write-Step "wait backend http://127.0.0.1:8000/ready to return 200 (max $ReadyTimeoutSeconds s)"
$elapsed = 0
$readyOk = $false
while ($elapsed -lt $ReadyTimeoutSeconds) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ready" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $readyOk = $true; break }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 503) {
            # still initializing; keep waiting
        } elseif ($statusCode) {
            Write-Host "    /ready returned $statusCode, keep waiting" -ForegroundColor DarkGray
        }
    }
    Start-Sleep -Seconds 3
    $elapsed += 3
}
if (-not $readyOk) {
    Write-Fail "/ready timeout"
    Write-Host "    docker compose --env-file $EnvFile logs --tail=100 backend" -ForegroundColor Yellow
    exit 1
}
Write-Pass "/ready returned 200"

# 6. nginx 80 /health
Write-Step "nginx http://127.0.0.1/health returns 200"
try {
    $code = (Invoke-WebRequest -Uri "http://127.0.0.1/health" -UseBasicParsing -TimeoutSec 5).StatusCode
    if ($code -ne 200) { throw "/health $code" }
    Write-Pass "nginx /health returned 200"
} catch {
    Write-Fail "nginx /health failed: $_"
    Write-Host "    docker compose --env-file $EnvFile logs --tail=100 nginx" -ForegroundColor Yellow
    exit 1
}

# 7. frontend root :3000
Write-Step "frontend root http://127.0.0.1:3000 returns HTML"
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -ne 200) { throw "frontend root $($resp.StatusCode)" }
    $hasHtml = ($resp.Content -match "<html") -or ($resp.Content -match "<!DOCTYPE")
    if (-not $hasHtml) { throw "frontend root content does not look like HTML" }
    Write-Pass "frontend root accessible (200 + contains HTML markers)"
} catch {
    Write-Fail "frontend root not accessible: $_"
    Write-Host "    docker compose --env-file $EnvFile logs --tail=100 frontend" -ForegroundColor Yellow
    exit 1
}

# 8. backend reachability through nginx
Write-Step "OPTIONS http://127.0.0.1/api/auth/login/password reaches backend through nginx"
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1/api/auth/login/password" -Method OPTIONS -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -in @(200, 204, 405)) {
        Write-Pass "backend reachable through nginx ($($r.StatusCode))"
    } else {
        Write-Host "    [smoke] INFO backend OPTIONS returned $($r.StatusCode), not treated as failure" -ForegroundColor DarkGray
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -in @(200, 204, 405)) {
        Write-Pass "backend reachable through nginx ($statusCode)"
    } else {
        Write-Fail "backend not reachable through nginx: $_"
        exit 1
    }
}

# 9. show ps
Write-Step "current docker compose ps"
docker compose --env-file $EnvFile ps

Write-Host ""
Write-Host "[smoke] all passed. next steps:"
Write-Host "        - open http://127.0.0.1 in a browser and sign in with a demo account"
Write-Host "        - run .\scripts\demo_attack.ps1 -BaseUrl http://127.0.0.1:8000 for demo attack"
Write-Host "        - stop: docker compose --env-file $EnvFile down (volumes preserved)"
Write-Host "        - full clean: docker compose --env-file $EnvFile down -v (deletes backend-data / postgres-data / redis-data)"
exit 0

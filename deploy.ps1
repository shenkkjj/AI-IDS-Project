# CyberSentinel 一键部署脚本
param(
    [string]$Env = "production",
    [switch]$BuildOnly,
    [switch]$SkipBuild,
    # M2-07: 允许指定非 .env 的临时 env 文件，默认仍走 .env（兼容旧用户）。
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CyberSentinel 部署脚本 v2.2" -ForegroundColor Cyan
Write-Host "  模式: $Env   EnvFile: $EnvFile" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 env 文件
if (-not (Test-Path $EnvFile)) {
    if ($EnvFile -eq ".env") {
        Write-Host "[!] .env 文件不存在，从 .env.example 创建..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "[-] 请编辑 .env 填入必要配置后重新运行" -ForegroundColor Yellow
        Write-Host "    必须配置: APP_SECRET, AUTH_SECRET" -ForegroundColor Yellow
        Write-Host "    生成命令:" -ForegroundColor Yellow
        Write-Host "      APP_SECRET=\$(openssl rand -base64 48)" -ForegroundColor Gray
        Write-Host "      AUTH_SECRET=\$(openssl rand -base64 48)" -ForegroundColor Gray
        exit 0
    } else {
        Write-Host "[!] 指定的 env 文件 $EnvFile 不存在" -ForegroundColor Red
        Write-Host "    复制模板: Copy-Item .env.example $EnvFile 并填入强随机 secret" -ForegroundColor Yellow
        exit 1
    }
}

# 生成密钥（仅当目标是真实 .env 时才允许；M2-07 临时 env 不动）
if ($EnvFile -eq ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -notmatch "APP_SECRET=" -or $envContent -match 'APP_SECRET=\s*$') {
        Write-Host "[!] APP_SECRET 未设置，自动生成..." -ForegroundColor Yellow
        $secret = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Max 256 }))
        if ($envContent -match "APP_SECRET=") {
            $envContent = $envContent -replace "APP_SECRET=.*", "APP_SECRET=$secret"
        } else {
            $envContent += "`nAPP_SECRET=$secret"
        }
        $envContent | Set-Content ".env" -NoNewline
    }

    if ($envContent -notmatch "AUTH_SECRET=" -or $envContent -match 'AUTH_SECRET=\s*$') {
        Write-Host "[!] AUTH_SECRET 未设置，自动生成..." -ForegroundColor Yellow
        $secret = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Max 256 }))
        if ($envContent -match "AUTH_SECRET=") {
            $envContent = $envContent -replace "AUTH_SECRET=.*", "AUTH_SECRET=$secret"
        } else {
            $envContent += "`nAUTH_SECRET=$secret"
        }
        $envContent | Set-Content ".env" -NoNewline
    }

    if ($envContent -notmatch "POSTGRES_PASSWORD=" -or $envContent -match 'POSTGRES_PASSWORD=\s*$') {
        Write-Host "[!] POSTGRES_PASSWORD 未设置，自动生成..." -ForegroundColor Yellow
        $password = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }))
        if ($envContent -match "POSTGRES_PASSWORD=") {
            $envContent = $envContent -replace "POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$password"
        } else {
            $envContent += "`nPOSTGRES_PASSWORD=$password"
        }
        $envContent | Set-Content ".env" -NoNewline
    }

    if ($envContent -notmatch "REDIS_PASSWORD=" -or $envContent -match 'REDIS_PASSWORD=\s*$') {
        Write-Host "[!] REDIS_PASSWORD 未设置，自动生成..." -ForegroundColor Yellow
        $password = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }))
        if ($envContent -match "REDIS_PASSWORD=") {
            $envContent = $envContent -replace "REDIS_PASSWORD=.*", "REDIS_PASSWORD=$password"
        } else {
            $envContent += "`nREDIS_PASSWORD=$password"
        }
        $envContent | Set-Content ".env" -NoNewline
    }
}

if ($BuildOnly) {
    Write-Host "[+] 仅构建镜像..." -ForegroundColor Green
    docker compose --env-file $EnvFile build --no-cache
    Write-Host "[+] 构建完成" -ForegroundColor Green
    exit 0
}

if (-not $SkipBuild) {
    Write-Host "[+] 构建镜像..." -ForegroundColor Green
    docker compose --env-file $EnvFile build
}

Write-Host "[+] 启动服务..." -ForegroundColor Green
docker compose --env-file $EnvFile up -d

Write-Host "[+] 等待服务就绪..." -ForegroundColor Green
Start-Sleep -Seconds 5

Write-Host "[+] 检查服务状态..." -ForegroundColor Green
docker compose --env-file $EnvFile ps

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  部署完成!" -ForegroundColor Green
Write-Host "  后端:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  前端:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Nginx: http://localhost (本地 HTTP 入口)" -ForegroundColor Cyan
Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

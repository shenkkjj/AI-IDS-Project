param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Email = "demo-analyst@example.com",
    [string]$Password = "DemoPass123!",
    [ValidateSet("sql_injection", "xss", "scanner")]
    [string]$Scenario = "sql_injection"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    $options = @{
        Method      = $Method
        Uri         = $Url
        Headers     = $Headers
        ContentType = "application/json"
    }
    if ($null -ne $Body) {
        $options.Body = ($Body | ConvertTo-Json -Depth 10)
    }
    Invoke-RestMethod @options
}

Write-Host "== AI-CyberSentinel Demo Flow =="
Write-Host "Backend: $BaseUrl"

$health = Invoke-Json -Method "GET" -Url "$BaseUrl/health"
Write-Host "Health: $($health.status)"

try {
    $auth = Invoke-Json -Method "POST" -Url "$BaseUrl/auth/register" -Body @{
        email = $Email
        password = $Password
        display_name = "Demo Analyst"
    }
    Write-Host "Registered demo user: $Email"
}
catch {
    $message = $_.Exception.Message
    if ($message -notmatch "409") {
        throw
    }
    $auth = Invoke-Json -Method "POST" -Url "$BaseUrl/auth/login/password" -Body @{
        email = $Email
        password = $Password
    }
    Write-Host "Logged in existing demo user: $Email"
}

$token = [string]$auth.access_token
if (-not $token) {
    throw "No access_token returned from auth flow."
}
$headers = @{ Authorization = "Bearer $token" }

$demo = Invoke-Json -Method "POST" -Url "$BaseUrl/alerts/demo" -Headers $headers -Body @{
    scenario = $Scenario
}
$alertId = [string]$demo.alert.alert_id
Write-Host "Demo alert created: $alertId ($Scenario)"
Write-Host "Risk: $($demo.alert.llm_analysis.risk_level)"
if ($null -ne $demo.copilot) {
    if ([bool]$demo.copilot.ready) {
        Write-Host "Copilot: ready ($($demo.copilot.provider) $($demo.copilot.model))"
    }
    else {
        Write-Host "Copilot: fallback ($($demo.copilot.fallback_reason))"
        Write-Host "Next: configure API Key and Base URL in Dashboard AI settings, then rerun Copilot analysis."
    }
}

$alerts = Invoke-Json -Method "GET" -Url "$BaseUrl/alerts?limit=5" -Headers $headers
$found = @($alerts.items | Where-Object { $_.alert_id -eq $alertId })
if ($found.Count -lt 1) {
    throw "Demo alert was not visible through /alerts."
}
Write-Host "Dashboard API visibility: ok"

$copilotBody = @{
    message = "Analyze the current demo security alert. Return risk, evidence, impact, and three immediate actions."
    alert_id = $alertId
    history = @()
}
$copilotOptions = @{
    Method = "POST"
    Uri = "$($BaseUrl)/copilot/stream"
    Headers = $headers
    ContentType = "application/json"
    Body = ($copilotBody | ConvertTo-Json -Depth 10)
}
$copilot = Invoke-WebRequest @copilotOptions

if ($copilot.Content -match "API Key|AI|event: done|data:|error") {
    Write-Host "Copilot SSE reachable: ok"
}
else {
    throw "Copilot SSE did not return an expected stream or fallback state."
}

Write-Host "Demo flow complete."

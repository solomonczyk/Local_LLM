param(
    [string]$LlmUrl = "http://localhost:8002/v1",
    [string]$ToolUrl = "http://localhost:8003",
    [ValidateSet("FAST", "STANDARD", "CRITICAL")][string]$ConsiliumMode = "FAST"
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path $Path)) { return $null }
    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -replace "^\s*$([regex]::Escape($Key))\s*=\s*", "").Trim()
}

$env:AGENT_LLM_URL = $LlmUrl
$env:TOOL_SERVER_URL = $ToolUrl
$env:CONSILIUM_MODE = $ConsiliumMode
$env:PYTHONUTF8 = "1"
if (-not $env:AGENT_API_KEY) {
    $env:AGENT_API_KEY = Get-EnvValue -Path ".env" -Key "AGENT_API_KEY"
}

python tools/consilium_audit.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$report = Get-ChildItem -Path "reports" -Filter "consilium_audit_*.json" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime |
    Select-Object -Last 1

if ($report) {
    Write-Host ("Latest report: " + $report.FullName)
}

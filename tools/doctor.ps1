param(
  [switch]$Json
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

function Test-DockerEngine {
  try {
    $out = & docker version 2>&1
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($out -match "error during connect") { return $false }
    return $true
  } catch {
    return $false
  }
}

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

$envPath = ".env"
$envExamplePath = ".env.example"
$modelPath = "models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

$dockerOk = Test-DockerEngine
$envOk = Test-Path $envPath
$modelOk = Test-Path $modelPath

$agentApiKey = Get-EnvValue -Path $envPath -Key "AGENT_API_KEY"
$pgPassword = Get-EnvValue -Path $envPath -Key "POSTGRES_PASSWORD"

$agentApiKeyPresent = [bool]$agentApiKey -and ($agentApiKey -notmatch "your_")
$pgPasswordPresent = [bool]$pgPassword -and ($pgPassword -notmatch "secure_")

$agentApiKeySecure = $agentApiKeyPresent -and $agentApiKey.Length -ge 32
$pgPasswordSecure = $pgPasswordPresent -and $pgPassword.Length -ge 16

$report = [ordered]@{
  docker_engine = @{ ok = $dockerOk; hint = "Start Docker Desktop (WSL2 backend)"; }
  env_file = @{ ok = $envOk; path = $envPath; hint = "Copy $envExamplePath -> $envPath and set AGENT_API_KEY + POSTGRES_PASSWORD"; }
  model_file = @{ ok = $modelOk; path = $modelPath; hint = "Download GGUF via: python tools/download_models.py"; }
  secrets = @{
    agent_api_key_present = $agentApiKeyPresent
    postgres_password_present = $pgPasswordPresent
    agent_api_key_secure = $agentApiKeySecure
    postgres_password_secure = $pgPasswordSecure
  }
}

if ($Json) {
  $report | ConvertTo-Json -Depth 6
  exit 0
}

Write-Host "=== Local Consilium Doctor ==="
Write-Host ("docker engine:           " + ($(if ($dockerOk) { "OK" } else { "FAIL" })))
Write-Host ("env file (.env):         " + ($(if ($envOk) { "OK" } else { "FAIL" })))
Write-Host ("GGUF model file:         " + ($(if ($modelOk) { "OK" } else { "FAIL" })))
Write-Host ("AGENT_API_KEY present:   " + ($(if ($agentApiKeyPresent) { "OK" } else { "FAIL" })))
Write-Host ("POSTGRES_PASSWORD present:" + ($(if ($pgPasswordPresent) { "OK" } else { "FAIL" })))
Write-Host ("AGENT_API_KEY secure:    " + ($(if ($agentApiKeySecure) { "OK" } else { "WARN" })))
Write-Host ("POSTGRES_PASSWORD secure:" + ($(if ($pgPasswordSecure) { "OK" } else { "WARN" })))

if (-not $dockerOk) {
  Write-Host "Hint: start Docker Desktop, then re-run: tools\\up.ps1"
}
if (-not $envOk) {
  Write-Host "Hint: copy .env.example -> .env and fill required values."
}
if (-not $modelOk) {
  Write-Host "Hint: python tools\\download_models.py"
}

if ($dockerOk -and $envOk -and $modelOk -and $agentApiKeyPresent -and $pgPasswordPresent) {
  exit 0
}
exit 1

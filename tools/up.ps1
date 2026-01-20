param(
  [switch]$Https,
  [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

Write-Host "=== Local Consilium: docker up ==="

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example. Fill at least: AGENT_API_KEY, POSTGRES_PASSWORD"
  Write-Host "Then re-run: tools\\up.ps1"
  exit 1
}

if (-not (Test-Path "models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")) {
  Write-Host "GGUF model not found. Trying to download via tools\\download_models.py..."
  & python tools/download_models.py
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Model download failed. Place the GGUF into: models\\qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    exit 1
  }
}

Write-Host "Running doctor checks..."
& powershell -ExecutionPolicy Bypass -File tools/doctor.ps1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Doctor checks failed. Fix issues above and re-run."
  exit 1
}

$composeArgs = @("compose")
if ($Https) { $composeArgs += @("--profile", "https") }
$composeArgs += @("up", "-d")
if (-not $NoBuild) { $composeArgs += "--build" }

Write-Host ("docker " + ($composeArgs -join " "))
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Endpoints:"
Write-Host "  UI (nginx):   http://localhost:8080"
Write-Host "  UI (direct):  http://localhost:7865"
Write-Host "  LLM (direct): http://localhost:8002/v1/models"
Write-Host "  LLM (nginx):  http://localhost:8080/v1/models"
Write-Host "  Tools:        http://localhost:8003/health"
Write-Host ""

Write-Host "Quick health checks (may take ~10-60s on first start):"
try { curl.exe -fsS "http://localhost:8002/health" | Out-Null; Write-Host "  LLM proxy: OK" } catch { Write-Host "  LLM proxy: FAIL" }
try { curl.exe -fsS "http://localhost:8003/health" | Out-Null; Write-Host "  Tools:     OK" } catch { Write-Host "  Tools:     FAIL" }
try { curl.exe -fsS "http://localhost:8080" | Out-Null; Write-Host "  UI nginx:  OK" } catch { Write-Host "  UI nginx:  FAIL" }


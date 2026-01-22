param(
  [string[]]$Branches = @("main", "master"),
  [string]$OldCheck = "CI / test",
  [string]$NewCheck = "CI / unit-tests",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Ensure-GhAuth {
  $out = gh auth status -h github.com 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Error $out
    throw "GitHub CLI is not authenticated. Run: gh auth login -h github.com"
  }
}

function Try-GetJson($endpoint) {
  try {
    $raw = gh api $endpoint 2>$null
    if ($LASTEXITCODE -ne 0) {
      return $null
    }
    return $raw | ConvertFrom-Json
  } catch {
    return $null
  }
}

function Update-ChecksAndContexts($required) {
  $strict = $false
  if ($null -ne $required.strict) { $strict = [bool]$required.strict }

  $contexts = @()
  if ($null -ne $required.contexts) { $contexts = @($required.contexts) }

  $checks = $null
  if ($null -ne $required.checks) { $checks = @($required.checks) }

  $contexts = @($contexts | Where-Object { $_ -and $_ -ne $OldCheck })
  if (-not ($contexts -contains $NewCheck)) { $contexts += $NewCheck }

  if ($checks -ne $null) {
    $appId = $null
    foreach ($c in $checks) {
      if ($c.context -eq $OldCheck -and $null -ne $c.app_id) { $appId = $c.app_id; break }
    }
    if ($appId -eq $null -and $checks.Count -gt 0 -and $null -ne $checks[0].app_id) {
      $appId = $checks[0].app_id
    }
    $checks = @($checks | Where-Object { $_.context -ne $OldCheck })
    $hasNew = $false
    foreach ($c in $checks) { if ($c.context -eq $NewCheck) { $hasNew = $true; break } }
    if (-not $hasNew) {
      if ($appId -eq $null) {
        throw "Cannot derive app_id for required check '$NewCheck'. Update the branch protection rule via GitHub UI."
      }
      $checks += [pscustomobject]@{ context = $NewCheck; app_id = $appId }
    }
  }

  $payload = @{ strict = $strict; contexts = $contexts }
  if ($checks -ne $null) { $payload.checks = $checks }
  return $payload
}

Ensure-GhAuth

foreach ($branch in $Branches) {
  Write-Host "== $branch =="

  $branchInfo = Try-GetJson "repos/{owner}/{repo}/branches/$branch"
  if ($null -eq $branchInfo) {
    Write-Host "  skip: branch not found (or no access)"
    continue
  }

  $required = Try-GetJson "repos/{owner}/{repo}/branches/$branch/protection/required_status_checks"
  if ($null -eq $required) {
    Write-Host "  skip: branch protection required_status_checks not available (rule may be absent or disabled)"
    continue
  }

  $payload = Update-ChecksAndContexts $required
  $json = $payload | ConvertTo-Json -Depth 10

  if ($DryRun) {
    Write-Host "  dry-run payload:"
    Write-Host $json
    continue
  }

  $json | gh api "repos/{owner}/{repo}/branches/$branch/protection/required_status_checks" --method PATCH --input - --silent
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to update required_status_checks for $branch"
  }

  Write-Host "  updated: '$OldCheck' -> '$NewCheck'"
}


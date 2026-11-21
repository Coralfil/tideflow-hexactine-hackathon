param(
    [switch]$BackendOnly,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$FrontendSrc = Join-Path $FrontendDir "src"

Write-Host "Starting TideFlow Hexactine development services from $RepoRoot"

$BackendArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010")
$BackendProc = Start-Process -FilePath "python" -ArgumentList $BackendArgs -WorkingDirectory $BackendDir -PassThru
Write-Host "Backend PID $($BackendProc.Id) listening on http://127.0.0.1:8010"

$FrontendProc = $null
if (-not $BackendOnly -and (Test-Path $FrontendSrc)) {
    $FrontendArgs = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173")
    $FrontendProc = Start-Process -FilePath "npm.cmd" -ArgumentList $FrontendArgs -WorkingDirectory $FrontendDir -PassThru
    Write-Host "Frontend PID $($FrontendProc.Id) listening on http://127.0.0.1:5173"
} elseif (-not $BackendOnly) {
    Write-Host "Frontend src directory not present yet; skipping Vite startup."
}

$HealthUrl = "http://127.0.0.1:8010/api/v1/health"
$Ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $Resp = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
        if ($Resp.status -eq "ok") {
            $Ready = $true
            Write-Host "Backend health OK (mode=$($Resp.backend_mode), cadence=$($Resp.active_cadence))"
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $Ready) {
    Write-Warning "Backend did not respond on $HealthUrl within 15 seconds."
}

if ($NoWait) {
    exit 0
}

Write-Host "Press Ctrl+C to stop development processes."
try {
    Wait-Process -Id $BackendProc.Id
} finally {
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Stop-Process -Id $BackendProc.Id -Force
    }
    if ($FrontendProc -and -not $FrontendProc.HasExited) {
        Stop-Process -Id $FrontendProc.Id -Force
    }
}

param (
    [switch]$Force = $false
)

Write-Host "[Conductor] Bootstrapping Agent Environment..." -ForegroundColor Cyan

# 1. Check for uv
$uvExists = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvExists) {
    Write-Host "[Conductor] uv not found. Installing uv Python package manager..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = "$HOME\.local\bin;" + $env:PATH
} else {
    Write-Host "[Conductor] uv is already installed." -ForegroundColor Green
}

# 2. Run Python Setup Script for Model / API provisioning
Write-Host "[Conductor] Provisioning LLM and Zephyr Agent configuration..." -ForegroundColor Cyan
uv run python "$PSScriptRoot\agent_setup.py"

Write-Host "[Conductor] Bootstrap Complete." -ForegroundColor Green

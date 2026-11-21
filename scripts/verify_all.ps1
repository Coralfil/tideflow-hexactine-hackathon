param(
    [switch]$RequireLive,
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    $PytestTmpRoot = Join-Path $RepoRoot ".pytest_tmp"
    New-Item -ItemType Directory -Path $PytestTmpRoot -Force | Out-Null
    $env:TEMP = $PytestTmpRoot
    $env:TMP = $PytestTmpRoot
    $env:PYTHONPATH = Join-Path $RepoRoot "backend"
    Write-Host "[1/7] Running backend unit and integration tests..."
    python -m pytest backend/tests -v --basetemp=".pytest_tmp/backend"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $AdversarialDir = Join-Path $RepoRoot "tests\adversarial"
    if (Test-Path $AdversarialDir) {
        Write-Host "[2/7] Running Tier 5 adversarial white-box tests..."
        python -m pytest tests/adversarial -v --basetemp=".pytest_tmp/adversarial"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
        Write-Host "[2/7] Adversarial test directory not present yet; skipping."
    }

    Write-Host "[3/7] Verifying Rook .mjs syntax and 5-phase hook lifecycle..."
    $HookFiles = Get-ChildItem -Path (Join-Path $RepoRoot ".testmuai\rook") -Recurse -Filter "*.mjs"
    if (-not $HookFiles) {
        throw "No .mjs hook files found under .testmuai/rook"
    }
    foreach ($Hook in $HookFiles) {
        node --check $Hook.FullName
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $TempStateDir = Join-Path $PytestTmpRoot ("tideflow-rook-smoke-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $TempStateDir -Force | Out-Null
    $env:ROOK_STATE_DIR = $TempStateDir
    $env:ROOK_RUN_STATE_DIR = $TempStateDir
    try {
        $MainHook = $HookFiles[0].FullName
        foreach ($Phase in @("prepare", "open", "execute", "close", "collect")) {
            if ($Phase -eq "execute") {
                $JsonOut = "Verify TideFlow permissions and cadence prompts" | node $MainHook $Phase
            } else {
                $JsonOut = node $MainHook $Phase
            }
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            $Parsed = $JsonOut | ConvertFrom-Json
            if ($null -eq $Parsed) {
                throw "Rook hook phase '$Phase' did not return a valid JSON object"
            }
        }
    } finally {
        Remove-Item Env:ROOK_STATE_DIR -ErrorAction SilentlyContinue
        Remove-Item Env:ROOK_RUN_STATE_DIR -ErrorAction SilentlyContinue
        Remove-Item -Path $TempStateDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[4/7] Running Rook doctor..."
    $env:ROOK_ENV = "prod"
    rook.cmd doctor --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "[5/7] Checking frontend build if present..."
    $FrontendSrc = Join-Path $RepoRoot "frontend\src"
    if (Test-Path $FrontendSrc) {
        Push-Location (Join-Path $RepoRoot "frontend")
        try {
            npm.cmd run type-check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            npm.cmd run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "Frontend src not present yet; skipping frontend type-check/build."
    }

    if (-not $SkipE2E) {
        Write-Host "[6/7] Running E2E verification suite..."
        $env:PYTHONPATH = $RepoRoot
        if ($RequireLive) {
            $env:TIDEFLOW_E2E_REQUIRE_LIVE = "1"
        }
        python -m pytest tests/e2e -v --basetemp=".pytest_tmp/e2e"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
        Write-Host "[6/7] Skipping E2E suite as requested."
    }

    Write-Host "[7/7] Running PowerShell and zero-em-dash hygiene audit..."
    @'
import pathlib, sys
root = pathlib.Path(r"d:\Kane Hackathon")
ps1_files = list((root / "scripts").rglob("*.ps1"))
bad_amp = [str(p) for p in ps1_files if (chr(38) * 2) in p.read_text(encoding="utf-8")]
if bad_amp:
    print("Forbidden double-ampersand in:", bad_amp)
    sys.exit(1)

check_exts = {".py", ".ps1", ".mjs", ".ts", ".tsx", ".css", ".yaml", ".yml", ".md"}
skip_dirs = {".git", "node_modules", ".pytest_cache", ".pytest_tmp", "__pycache__", ".venv", "evidence"}
bad_em = []
for p in root.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in check_exts:
        continue
    if any(part in skip_dirs for part in p.parts):
        continue
    if "\u2014" in p.read_text(encoding="utf-8", errors="ignore"):
        bad_em.append(str(p))
if bad_em:
    print("Forbidden U+2014 em dash in:", bad_em)
    sys.exit(1)
print(f"Hygiene OK: {len(ps1_files)} ps1 script(s), zero double-ampersand, zero U+2014.")
'@ | python -
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "All verification checks passed."
} finally {
    Pop-Location
}

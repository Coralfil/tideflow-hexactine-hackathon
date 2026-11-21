param(
    [string]$Url = "http://127.0.0.1:5173",
    [string]$Objective = "",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-KaneChromePath {
    if ($env:KANE_CLI_CHROME_PATH -and (Test-Path $env:KANE_CLI_CHROME_PATH)) {
        return $env:KANE_CLI_CHROME_PATH
    }
    $Candidates = @(
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        (Join-Path $env:USERPROFILE "AppData\Local\Google\Chrome\Application\chrome.exe"),
        "C:\chrome-for-testing\chrome-win64\chrome.exe",
        (Join-Path $env:USERPROFILE "AppData\Local\chrome-for-testing\chrome-win64\chrome.exe"),
        (Join-Path $env:USERPROFILE "AppData\Local\kane-chrome\chrome.exe")
    )
    foreach ($PathItem in $Candidates) {
        if (Test-Path $PathItem) {
            return $PathItem
        }
    }
    $PlaywrightGlob = Join-Path $env:LOCALAPPDATA "ms-playwright\chromium-*\chrome-win64\chrome.exe"
    $PlaywrightMatch = Get-ChildItem -Path $PlaywrightGlob -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($PlaywrightMatch) {
        return $PlaywrightMatch.FullName
    }
    return $null
}

Push-Location $RepoRoot
try {
    if (-not $env:KANE_CLI_USER_AGENT) {
        $env:KANE_CLI_USER_AGENT = "claude-code"
    }
    $ChromeExe = Resolve-KaneChromePath
    if ($ChromeExe) {
        $env:KANE_CLI_CHROME_PATH = $ChromeExe
        Write-Host "Using KANE_CLI_CHROME_PATH=$ChromeExe"
    } else {
        Write-Warning "No Chrome or Playwright Chromium binary found; live browser run may fail."
    }

    $env:ROOK_ENV = "prod"
    Write-Host "Checking KaneCLI and Rook readiness..."
    kane-cli.cmd --version; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    kane-cli.cmd config show; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    rook.cmd doctor --json; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Verifying Rook .mjs hooks..."
    $HookFiles = Get-ChildItem -Path (Join-Path $RepoRoot ".testmuai\rook") -Recurse -Filter "*.mjs"
    foreach ($Hook in $HookFiles) {
        node --check $Hook.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "Running KaneCLI saved-tests dry-run..."
    kane-cli.cmd testrun run --match '^tests[/\\]' --dry-run --agent
    $DryExit = $LASTEXITCODE
    Write-Host "kane-cli testrun --dry-run --agent exited with code $DryExit"

    if ($Objective) {
        Write-Host "Running live KaneCLI NDJSON objective against $Url..."
        $NdjsonLines = kane-cli.cmd run $Objective --url $Url --agent --headless --timeout $TimeoutSeconds
        $RunExit = $LASTEXITCODE
        $RunEnd = $null
        foreach ($Line in $NdjsonLines) {
            Write-Output $Line
            try {
                $Evt = $Line | ConvertFrom-Json -ErrorAction Stop
                if ($Evt.type -eq "run_end") {
                    $RunEnd = $Evt
                }
            } catch {
                continue
            }
        }
        if ($RunEnd) {
            Write-Host "run_end status=$($RunEnd.status) summary=$($RunEnd.summary)"
        }
        exit $RunExit
    }

    exit 0
} finally {
    Pop-Location
}

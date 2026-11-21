# TideFlow Hexactine E2E Test Readiness Report (`TEST_READY.md`)

## 1. Readiness Verdict Banner and Metadata
- **Overall Status**: `VERIFIED_LIVE_LOCAL_SUITES_GREEN_PENDING_CLOUD_OAUTH`
- **Timestamp (UTC)**: `2026-11-21T02:48:00Z`
- **Track**: `E2E Testing Track (Opaque-Box) + Tier 5 Adversarial`
- **Authoritative Specs**:
  - `docs/testing/TEST_INFRA.md`
  - `requirements/tideflow_prd.md`
  - `PROJECT.md` (Features 6 to 15)

### Coverage Summary Table
| Tier | Test File / Suite | Test Count | Focus |
|---|---|---:|---|
| Backend Unit & Integration | `backend/tests/` | 74 | Graph backends (`InProcess` + `Relate`), momentum, scheduler, Nemoclaw gate |
| Tier 1 | `tests/e2e/test_tier1_features.py` | 60 | Primary feature contracts (6 per feature, F6 to F15) |
| Tier 2 | `tests/e2e/test_tier2_boundaries.py` | 60 | Boundary conditions, negative inputs, static hygiene (6 per feature, F6 to F15) |
| Tier 3 | `tests/e2e/test_tier3_pairwise.py` | 15 | Pairwise cross-feature flows (`p01` to `p15`) |
| Tier 4 | `tests/e2e/test_tier4_scenarios.py` | 6 | Multi-step daily ADD workflows + headless Chromium UI (`s01` to `s06`) |
| Tier 5 | `tests/adversarial/test_tier5_adversarial.py` | 9 | White-box bypass probes, Hexactine burst, bitemporal chain, offline fallback |
| **Total E2E** | `tests/e2e/` | **141** | Complete opaque-box E2E suite |

---

## 2. Runner and Binary Readiness Matrix

| Check / Command | Exit Code | Observed Status |
|---|---:|---|
| `python -m pytest backend/tests -v --basetemp=".pytest_tmp/backend"` | `0` | `74 passed` |
| `python -m pytest tests/adversarial -v --basetemp=".pytest_tmp/adversarial"` | `0` | `9 passed` |
| `cd frontend ; npm.cmd run type-check ; npm.cmd run build` | `0` | `tsc --noEmit` + Vite production build green |
| `powershell -ExecutionPolicy Bypass -File scripts\verify_all.ps1 -RequireLive` | `0` | All 7 gates green including `141` live E2E tests and hygiene check |
| `relate info --database .\data\tideflow_memory.rl` | `0` | `Relate v1.0.1` store active |
| `kane-cli.cmd --version; kane-cli.cmd config show` | `0` | `0.10.6`, `profile: default`, `env: prod`, `mode: testing` (`login --oauth` needed for cloud runs) |
| `$env:ROOK_ENV='prod'; rook.cmd doctor --json` | `0` | `version: 0.1.21`, `controller: reachable`, `api: reachable`, 5-phase `.mjs` hooks verified |

---

## 3. Exact PowerShell `;` Verification Commands

### Full Live Verification Sequence (All 7 Stages)
Start FastAPI (`127.0.0.1:8010`) and Vite (`127.0.0.1:5173`), or run `.\scripts\dev.ps1`, then execute:
```powershell
$env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; powershell -ExecutionPolicy Bypass -File "d:\Kane Hackathon\scripts\verify_all.ps1" -RequireLive
```

### One-Time Cloud OAuth Sign-In for KaneCLI & Rook
```powershell
kane-cli.cmd login --oauth; $env:ROOK_ENV = 'prod'; rook.cmd login
```

### KaneCLI Assurance Pipeline (After OAuth Login + Live Servers)
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; $env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; kane-cli.cmd context ingest requirements\tideflow_prd.md --mode agent
```
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; $env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; kane-cli.cmd testmd run .testmuai\tests\cockpit_smoke_test.md --agent --headless
```

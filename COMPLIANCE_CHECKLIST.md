# KaneCLI Online Hackathon Compliance Checklist

Reference event: `https://luma.com/kanecli-online-hackathon?medium=Email_Hackthon&tk=0S1PLf&umt_source=LCM` (`evt-jTGOXA4VzEmw8QW`).

## 1. Hackathon Rules and Mandatory Gate Mapping

| Requirement | Status | Workspace Evidence |
|---|---|---|
| Fresh repository initialized on or after Nov 12, 2026 | Verified | `git init` in `d:\Kane Hackathon` (Nov 2026 commit history) |
| Any AI coding agent, any stack, with Kane CLI installed | Verified | `@testmuai/kane-cli@0.10.6` (`kane-cli.cmd`), `@testmuai/kane-cli-skill@0.1.5`, `@testmuai/rook@0.1.21` (`rook.cmd`) |
| KaneCLI agent guide installed in repo and personal agent | Verified | `AGENTS.md`, `.agents/deepcoder/02-SKILLS/playbook.md`, `D:\Projects\os\Atlantis_HSL\AGENTS\deepcoder\02-SKILLS\playbook.md` |
| Ready-to-Ship Bar 1: App works end to end locally in under 30 seconds | Verified | `scripts/dev.ps1`, FastAPI (`127.0.0.1:8010`), Vite React (`127.0.0.1:5173`), `README.md` |
| Ready-to-Ship Bar 2: Automated E2E + KaneCLI/Rook verification evidence | Verified (Local) / Pending OAuth (Cloud) | `backend/tests/` (74 tests), `tests/adversarial/` (9 tests), `tests/e2e/` (141 tests), `.testmuai/rook/`, `.testmuai/tests/cockpit_smoke_test.md` |
| Ready-to-Ship Bar 3: Agent and KaneCLI/Rook closed loop | Verified | `scripts/kane_loop.ps1` (`--agent` NDJSON loop), `requirements/tideflow_prd.md` (`context ingest` ready), 5-phase `.testmuai/rook/` hooks |
| PowerShell `;` syntax and zero U+2014 em dashes | Verified | Automated hygiene gate in `scripts/verify_all.ps1` and `tests/e2e/test_tier2_boundaries.py` |
| Public-facing copy `unslop` pass | Verified | Checked by `tests/e2e/test_tier1_features.py` and `test_tier2_boundaries.py` across `README.md`, `COMPLIANCE_CHECKLIST.md`, and rendered DOM |

## 2. One-Time Interactive Sign-In for Cloud Evidence Upload

Before recording cloud Test Manager runs or submitting, run these commands in PowerShell to authenticate your TestMu AI account (10,000 free KaneCLI credits at `https://www.testmuai.com/register/`):

```powershell
kane-cli.cmd login --oauth ; $env:ROOK_ENV = 'prod' ; rook.cmd login
```

Then execute the closed-loop verification runner against the running app (`.\scripts\dev.ps1`):

```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code' ; $env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe" ; kane-cli.cmd context ingest requirements\tideflow_prd.md --mode agent ; kane-cli.cmd testmd run .testmuai\tests\cockpit_smoke_test.md --agent --headless
```

## 3. Ready-to-Submit Hackathon Materials

### One-Paragraph Project Description (Unslop-Checked)
TideFlow Hexactine is a daily-use time-management, thought-capture, and side-quest momentum cockpit built for ADD-minded creative builders using Claude Code, Codex, and Antigravity agents on top of FastAPI, React, Relate (`helix_memory`), Neo4j Graph Science, and CSS Houdini Paint Worklets. Users capture rapid ideas with `Ctrl+K`, keep active work capped at `Now: 1` and `Next: 2` inside a 3-Slot Focus Horizon, park side quests in a guilt-free reef, recover project context with 3-line bitemporal breadcrumbs, schedule blocks across four tidal cadence windows, and gate real local/web retrieval behind default-deny Nemoclaw permissions. During development and verification, `scripts/kane_loop.ps1`, `requirements/tideflow_prd.md`, and `.testmuai/rook/` 5-phase hooks drive closed-loop KaneCLI NDJSON browser checks, Rook assurance probes, and a 141-test opaque-box Playwright suite to keep every UI, CSS Houdini, graph-invariant, and security gate verified on every run.

### Under-30-Second Judge Quickstart Command
```powershell
cd "d:\Kane Hackathon" ; .\scripts\dev.ps1
```
Then open `http://127.0.0.1:5173`.

### 3-Minute Demo Video Storyboard
1. **0:00 to 0:30 (Hook and Instant Capture)**: Open `http://127.0.0.1:5173`, show the animated CSS Houdini hexactine lattice, press `Ctrl+K`, capture a thought and an auto-parked side quest.
2. **0:30 to 1:15 (Momentum Recovery and Graph Science)**: Click `Run Triage Sweep`, save a breadcrumb, click `Resume Context` for the 3-line card, and switch between `PageRank`, `Communities`, `Shortest Path`, and `Degree Audit` (`deg <= 6`) with live `gds.` Cypher preview.
3. **1:15 to 2:00 (Rhythm Dial and Nemoclaw Gate)**: Slide the Energy Rhythm Dial (`--rhythm-bpm` updates live), trigger a `409` overlap conflict, then test Nemoclaw default-deny (`403` + `DENIED` audit), toggle `local_fs_read` on, and execute (`200` + `ALLOWED` + `RetrievalArtifact`).
4. **2:00 to 3:00 (Closed-Loop KaneCLI and Rook Verification)**: Run `.\scripts\kane_loop.ps1` and `kane-cli.cmd testmd run .testmuai\tests\cockpit_smoke_test.md --agent --headless` to show NDJSON step output, evidence packs, and `rook.cmd` checks.

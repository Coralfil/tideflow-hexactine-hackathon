# TideFlow Hexactine E2E Test Infrastructure (`TEST_INFRA.md`)

## 1. Header and Track Ownership Metadata
- **Document Status**: `READY`
- **Track**: `E2E Testing Track (Opaque-Box)`
- **Authoritative Spec Sources**: `PROJECT.md`, `ORIGINAL_REQUEST.md`, `requirements/tideflow_prd.md`
- **Target Service Endpoints**:
  - Backend API (`TIDEFLOW_API_URL`): `http://127.0.0.1:8010` (`/api/v1/*`)
  - Frontend UI (`TIDEFLOW_UI_URL`): `http://127.0.0.1:5173`
- **Product Features Mapped (`N = 10`, Features 6 to 15)**:
  - `F6`: Dual-Mode Graph Backend (`Relate v1.0.1`, `InProcess`, optional `Neo4j 5.26` Bolt)
  - `F7`: Graph Science and Hexactine Invariant (`PageRank`, `Communities`, `Shortest Path`, `deg <= 6`, `gds.*` Cypher preview)
  - `F8`: ADD Thought, Idea, and Side-Quest Capture and Linking (`spark_idea`, `project_task`, `side_quest`, `blocker`, park/promote)
  - `F9`: Momentum Recovery and 3-Slot Focus Horizon (`Breadcrumb` `SUPERSEDES`, 3-line Context Resume Card, `Now: 1 / Next: 2 / Parked`)
  - `F10`: Deterministic Cadence Scheduler (`ScheduleBlock` CRUD, `409` overlap conflict, 4 cadence windows, deterministic prompts)
  - `F11`: Permission-Gated Nemoclaw Retriever (default-deny `false` startup, `403` block + `DENIED` audit, `200` + `ALLOWED` + `RetrievalArtifact`)
  - `F12`: Rook and KaneCLI Closed-Loop Hooks (`.testmuai/rook/` YAML + `.mjs` 5-stage hooks, `scripts/*.ps1`, `kane-cli.cmd`, `rook.cmd`)
  - `F13`: CSS Houdini Rhythm Layer (`@property` tokens, Typed OM, `rhythm-lattice-paint.js`, `biolum-pulse-paint.js`, fallback)
  - `F14`: Interactive `neo4j-graph-science` and Rhythm UI (`Cmd+K` Brain Dump, 3-Slot Horizon, Graph Canvas, Scheduler, Rhythm Dial, Nemoclaw Console)
  - `F15`: Public Copy `unslop` Pass (zero U+2014 em dashes, zero AI filler words in docs, UI copy, and API responses)

---

## 2. Environment and Toolchain Prerequisites

### Verified Runtime Toolchain
| Component | Verified Version / Path | Purpose |
|---|---|---|
| Python | `3.13.15` (`pytest 9.1.1`, `httpx 0.28.1`, `pydantic 2.13.5`) | Tiers 1 to 4 pytest execution |
| Node.js | `v24.19.0` (`npm 11.17.0`) | Headless browser runner and `.mjs` syntax verification |
| Relate CLI | `relate.exe 1.0.1` (`./data/tideflow_memory.rl`) | Local graph database inspection |
| KaneCLI | `@testmuai/kane-cli@0.10.6` (`kane-cli.cmd`) | PRD ingestion, scenario design, NDJSON browser runs |
| Rook CLI | `@testmuai/rook@0.1.21` (`rook.cmd`) | Agent assurance hooks and scenario verdict reporting |

### Zero-Install Node Playwright + Chromium-1248 Resolution Rule
Global Python `playwright` and workspace `frontend/node_modules/playwright` are not installed. Instead, `tests/e2e/_browser_driver.py` and `tests/e2e/_playwright_runner.mjs` resolve Playwright dynamically in this order:
1. `PLAYWRIGHT_NODE_MODULES` environment variable (if set).
2. Local `tests/e2e/node_modules/playwright`.
3. Cached npx installation matching `%LOCALAPPDATA%\npm-cache\_npx\*\node_modules\playwright` (verified `playwright@1.64.1`).
4. Fallback to Python `playwright.sync_api` if manually installed in the active Python environment.

Chromium binary resolution checks `KANE_CLI_CHROME_PATH`, standard Chrome install paths, and `%LOCALAPPDATA%\ms-playwright\chromium-1248\chrome-win64\chrome.exe` (verified present for revision `1248` / `156.0.8078.4`).

### Required Environment Variables (PowerShell)
```powershell
$env:TIDEFLOW_API_URL = 'http://127.0.0.1:8010'
$env:TIDEFLOW_UI_URL = 'http://127.0.0.1:5173'
$env:TIDEFLOW_E2E_REQUIRE_LIVE = '1'
$env:ROOK_ENV = 'prod'
$env:KANE_CLI_USER_AGENT = 'claude-code'
$env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"
```
Never hardcode credentials or TestMu AI tokens in repository files. For non-interactive CI runs of KaneCLI or Rook cloud flows, supply `$env:LT_USERNAME` and `$env:LT_ACCESS_KEY` via CI secret injection or run `kane-cli.cmd login --oauth` interactively.

---

## 3. 5-Tier E2E Test Topology and Opaque-Box Boundary

### Directory Layout
- `tests/e2e/`: Opaque-box Tiers 1 to 4 suite (`141` tests) plus `conftest.py`, `_browser_driver.py`, and `_playwright_runner.mjs`.
- `tests/adversarial/`: Tier 5 white-box adversarial and fault-injection suite (owned by Milestone 5).
- `requirements/tideflow_prd.md`: Source specification formatted for `kane-cli context ingest`.
- `.testmuai/tests/`: Recorded KaneCLI `*_test.md` replay specs and `output-*/` recordings.
- `.testmuai/rook/`: Rook project/agent YAML profiles and `.mjs` lifecycle hooks.

### Tier-to-Feature and Surface Matrix
| Tier | File / Location | Count | Target Surfaces | Features Covered | Execution Stage |
|---|---|---:|---|---|---|
| Tier 1 | `tests/e2e/test_tier1_features.py` | 60 | REST API, Relate CLI, `.testmuai/rook/`, Chromium DOM/CSS, docs | F6 to F15 (6 per feature) | E2E Track + M5 |
| Tier 2 | `tests/e2e/test_tier2_boundaries.py` | 60 | Validation errors (`400/403/404/409/422`), viewport/motion/fallback, static hygiene | F6 to F15 (6 per feature) | E2E Track + M5 |
| Tier 3 | `tests/e2e/test_tier3_pairwise.py` | 15 | Cross-feature REST + Graph + Scheduler + Retriever + DOM flows | Pairwise F6 to F15 | E2E Track + M5 |
| Tier 4 | `tests/e2e/test_tier4_scenarios.py` | 6 | Full multi-step daily ADD workflows in headless Chromium + API | End-to-end F6 to F15 | E2E Track + M5 |
| Tier 5 | `tests/adversarial/` | M5 | White-box faults, concurrency races, Nemoclaw bypass probes | Hardening & security | M5 |

### Strict Opaque-Box Discipline
Tests inside `tests/e2e/` never import `backend.app`, `frontend/src`, or internal Python/TypeScript symbols. All checks communicate solely through:
1. HTTP calls to `TIDEFLOW_API_URL` (`/api/v1/*`) and `TIDEFLOW_UI_URL` (`/`, `/worklets/*.js`).
2. Headless Chromium DOM, keyboard, pointer, network, and `getComputedStyle` inspection via `_browser_driver.py`.
3. CLI invocations (`kane-cli.cmd`, `rook.cmd`, `relate`, `node`).
4. Public repository artifact inspection (`README.md`, `AGENTS.md`, `.mcp.json`, `data/tideflow_memory.rl`, `scripts/*.ps1`, `.testmuai/rook/*`, `COMPLIANCE_CHECKLIST.md`).

---

## 4. Isolation, Fixtures, and Deterministic Seeding

### Collection Purity and Live-Server Gating
- `tests/e2e/conftest.py` performs zero network calls, zero subprocess runs, and zero `playwright` imports at import/collection time. `python -m pytest tests/e2e --collect-only -q` exits `0` with `141` tests collected even when servers are offline.
- `require_api` and `require_ui` check connectivity (`timeout=2.0`):
  - If unreachable (`ConnectError` or `TimeoutException`) and `TIDEFLOW_E2E_REQUIRE_LIVE=1`: calls `pytest.fail(...)`.
  - If unreachable and `TIDEFLOW_E2E_REQUIRE_LIVE` is unset: calls `pytest.skip(...)`.
  - If reachable and HTTP status is not `200`: always calls `pytest.fail(...)`.
- `require_workspace_artifact(relative_path, milestone_hint)` handles unbuilt Milestone 3 and 4 files (`scripts/*.ps1`, `.testmuai/rook/*`, `COMPLIANCE_CHECKLIST.md`): fails when `TIDEFLOW_E2E_REQUIRE_LIVE=1`, skips with milestone context when unset. Milestone 1 artifacts (`data/tideflow_memory.rl`, `.mcp.json`, `README.md`, `AGENTS.md`, `.agents/deepcoder/`) run unconditionally.

### Deterministic Isolation Fixtures
- **`unique_slug`**: Generates `e2e-<hex8>` prefixes so project names, thoughts, and schedule blocks never collide across runs.
- **`reset_retriever_permissions`**: Function-scoped fixture that snapshots `GET /api/v1/retriever/permissions`, resets all 4 capabilities (`local_fs_read`, `repo_git_scan`, `web_fetch_public`, `local_llm_ollama`) to `false` before test body execution, and restores `false` in teardown.
- **`created_schedule_blocks`**: Tracks block IDs created via `POST /api/v1/schedule/blocks` and removes them via `DELETE /api/v1/schedule/blocks/{id}` in teardown.
- **Injectable Clock Queries**: `GET /api/v1/schedule/prompts` tests pass explicit `now_iso`, `energy`, and `minutes` parameters so scoring is deterministic regardless of wall-clock time.
- **KaneCLI Variables**: Non-secret variables generated during `design tests` live in `.testmuai/variables/assurance.json` (gitignored) and must contain zero unresolved keys before `testrun run`.

---

## 5. KaneCLI Assurance and Replay Pipeline

All Windows PowerShell commands use semicolon (`;`) separators and `.cmd` shims. Never run two `.context/`-mutating commands concurrently because `.context/` uses a single-writer append-only lock (`EXTRACT_LOCKED`).

### Step 1: Preflight Check
```powershell
$env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.gemini\skills\kane-cli\scripts\preflight.ps1"
```

### Step 2: Ingest PRD and Review Use Cases
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; kane-cli.cmd context ingest requirements\tideflow_prd.md --mode agent
```
```powershell
kane-cli.cmd context list --json --inferred; kane-cli.cmd context review --verdicts verdicts.json --json
```

### Step 3: Design and Approve Tests (`--max 8`)
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; kane-cli.cmd design tests --use-case <uc-ref> --mode agent --max 8; kane-cli.cmd context review --verdicts verdicts.json --json
```

### Step 4: Replay Single Flow or Full Suite (`--agent` Mandatory in PowerShell)
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; $env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; kane-cli.cmd testmd run .testmuai\tests\<slug>_test.md --agent --headless
```
```powershell
$env:KANE_CLI_USER_AGENT = 'claude-code'; $env:KANE_CLI_CHROME_PATH = "$env:LocalAppData\ms-playwright\chromium-1248\chrome-win64\chrome.exe"; kane-cli.cmd testrun run --match '^(\.testmuai[/\\]tests|tests)[/\\]' --parallel 1 --headless --agent
```

### Step 5: Coverage Gap Check
```powershell
kane-cli.cmd cover gaps --mode agent
```

---

## 6. Rook Agent Assurance Hooks and Runner

Rook configuration and lifecycle hooks reside under `.testmuai/rook/projects/<project-id>/agents/<agent-id>/` and implement all 5 lifecycle functions in `.mjs`: `prepare`, `open`, `execute`, `close`, and `collect`.

### Execution Commands
```powershell
$env:ROOK_ENV = 'prod'; rook.cmd doctor --json; rook.cmd run --test --json
```
Inspect run reports by explicit run ID:
```powershell
$env:ROOK_ENV = 'prod'; rook.cmd report <run-id> --json
```

### Assertion Rules
Never rely solely on exit code `0` from `rook.cmd run`. Parse stdout JSON and verify:
- Top-level `ok == true` and `halted == false`.
- Every scenario entry reports verdict `Pass` (reject `Fail` and `Unable to Verify`).
- Zero leaked secret tokens or `LT_ACCESS_KEY` literals inside `.testmuai/rook/**/*.yaml`.

---

## 7. PowerShell `;` Runner Matrix and Hygiene Gates

### One-Command Live Verification Sequence
```powershell
$env:TIDEFLOW_E2E_REQUIRE_LIVE = '1'; $env:ROOK_ENV = 'prod'; python -m pytest tests/e2e -v
```

### Offline M1 and Collection Verification
```powershell
python -m pytest tests/e2e --collect-only -q; python -m pytest tests/e2e -k "f06_relate or f06_mcp or f12_kane_cli_version or f12_rook_doctor or f12_b_deepcoder or f15_readme or f15_b_agents" -v
```

### Hygiene Gates (Zero Em Dash and Semicolon Only)
```powershell
python -c "import pathlib; roots=['tests/e2e','requirements','docs/testing']; files=[p for r in roots for p in pathlib.Path(r).rglob('*') if p.is_file() and p.suffix in {'.py','.mjs','.md','.ps1'}]; em=[str(p) for p in files if '\u2014' in p.read_text(encoding='utf-8')]; amp=[str(p) for p in files if p.suffix=='.ps1' and (chr(38)*2) in p.read_text(encoding='utf-8')]; print({'em_dash': em, 'double_amp_ps1': amp})"
```

---

## 8. Exit Criteria to Promote `TEST_INFRA.md` to `TEST_READY.md`

1. `requirements/tideflow_prd.md` exists, is UTF-8 under 2 MB, passes `unslop` and zero-em-dash checks, and defines `UC-1` through `UC-6` with explicit runtime URLs and no-auth rules.
2. `tests/e2e/` collects all `141` tests (`60` Tier 1, `60` Tier 2, `15` Tier 3, `6` Tier 4) with exit code `0` and zero `assert True` placeholders.
3. `_browser_driver.py` and `_playwright_runner.mjs` pass syntax checks (`node --check`) and render a local headless Chromium page cleanly using cached `playwright@1.64.1` and `chromium-1248`.
4. M1 workspace and CLI tests (`relate`, `kane-cli.cmd`, `rook.cmd`, `.mcp.json`, `README.md`, `AGENTS.md`, `.agents/deepcoder/`) execute and pass locally.
5. Remaining M5 environment prerequisites (`kane-cli` / `rook` interactive login or CI credentials, live backend/frontend server boot for `TIDEFLOW_E2E_REQUIRE_LIVE=1`) are explicitly recorded in `docs/testing/TEST_READY.md`.

# TideFlow Hexactine

TideFlow Hexactine is a daily-use time-management, ADD-minded thought capture, cadence scheduler, and permission-gated Nemoclaw retriever agent built for the KaneCLI Online Hackathon.

It captures overloaded ideas in seconds, tracks project momentum with bitemporal breadcrumbs, parks side quests without guilt, schedules work across four tidal cadence windows, and gates retrieval actions behind explicit default-deny permissions. The UI uses a `neo4j-graph-science` and biological rhythm visual theme powered by CSS Houdini typed tokens and Paint Worklets.

## Quickstart (Under 30 Seconds, PowerShell)

All Windows PowerShell commands use semicolon (`;`) separators:

```powershell
cd "d:\Kane Hackathon" ; .\scripts\dev.ps1
```

Or launch backend (`uvicorn`) and frontend separately in two PowerShell terminals:

```powershell
cd "d:\Kane Hackathon\backend" ; uvicorn app.main:app --host 127.0.0.1 --port 8010
```

```powershell
cd "d:\Kane Hackathon\frontend" ; npm.cmd run dev
```

Open `http://127.0.0.1:5173` in your browser. Press `Ctrl+K` to open Brain Dump, run a triage sweep, inspect `PageRank` / `Communities` / `Shortest Path` / `Degree Audit` (`deg <= 6`), adjust the Energy Rhythm Dial, and control Nemoclaw capabilities.

## Verification and Closed-Loop Assurance

Run the local verification script (backend unit/integration tests, Tier 5 adversarial suite, Rook 5-phase lifecycle hooks, frontend type-check and build, 141-test opaque-box E2E suite, and zero-em-dash hygiene audit):

```powershell
powershell -ExecutionPolicy Bypass -File "d:\Kane Hackathon\scripts\verify_all.ps1" -RequireLive
```

Run the closed-loop KaneCLI and Rook checker:

```powershell
powershell -ExecutionPolicy Bypass -File "d:\Kane Hackathon\scripts\kane_loop.ps1"
```

To sign in once for cloud Test Manager runs (`kane-cli` and `rook`):

```powershell
kane-cli.cmd login --oauth ; $env:ROOK_ENV = 'prod' ; rook.cmd login
```

## Architecture and Stack

- **Frontend (`frontend/`, `:5173`)**: React 19, Vite 8, TypeScript, Framer Motion, Lucide icons, CSS Houdini `@property` tokens, Typed OM, and Paint Worklets (`rhythm-lattice-paint.js`, `biolum-pulse-paint.js`).
- **Backend (`backend/`, `:8010`)**: FastAPI, Pydantic v2, HTTPX, deterministic Graph Science services (PageRank, Louvain/Leiden communities, shortest path, Hexactine `degree <= 6` invariant), Cadence Scheduler, and Nemoclaw Retriever with audit logging.
- **Graph Memory (`data/tideflow_memory.rl`)**: Local Relate v1.0.1 graph store (exposed read-only via `.mcp.json`), deterministic in-process fallback driver for CI, and optional Neo4j 5.26 Bolt driver (`bolt://127.0.0.1:7687`).
- **Personal AI Stack Bridges (`.agents/`)**:
  - `.agents/global_rules/`: Sanitized workspace `GEMINI.md` and `AGENTS.md` rules.
  - `.agents/agentsea/`: Read-only manifest and `helix_schema.cypher` for `AtlantisAgentSea`, `atlantis_cli`, and `helix_memory`.
  - `.agents/hsl_bridge/`: Read-only bridge config, schema reference, and `hexactine_session_sync.json` for `Atlantis_HSL` (`hexactine_lattice_state.json`) and local RTX 3060 worker endpoints (`D:\coralfil-os-worker`, zero credentials copied).
  - `.agents/deepcoder/`: Workspace mirror of updated `deepcoder` identity and KaneCLI verification playbook.
- **Assurance Tooling**: `@testmuai/kane-cli` (`kane-cli.cmd`) and `@testmuai/rook` (`rook.cmd`), configured in `AGENTS.md`, `TOOLING_STATUS.md`, `.testmuai/rook/`, and `.testmuai/tests/`.

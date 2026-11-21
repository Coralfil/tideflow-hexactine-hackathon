# TideFlow Hexactine Product Requirements Document (PRD)

## 1. Product Overview
TideFlow Hexactine is a daily-use time-management, thought capture, cadence scheduling, and permission-gated Nemoclaw retriever application built for builders with attention overload. It captures ideas in under two seconds, preserves project context using bitemporal breadcrumbs, parks side quests without guilt, schedules work across four tidal cadence windows, and gates retrieval actions behind explicit default-deny permissions.

---

## 2. Runtime Grounding and Startup Assumptions

1. **Application URLs**:
   - Web Frontend UI: `http://127.0.0.1:5173`
   - Backend REST API: `http://127.0.0.1:8010/api/v1`
2. **Authentication Model**:
   - No login screen or authentication wall exists in the web app; loading `http://127.0.0.1:5173` opens the TideFlow Hexactine cockpit directly.
   - Tests must never attempt to sign in or generate login credentials.
3. **Default Startup and Seed State**:
   - At startup, at least one seeded active project is present and selected in the cockpit.
   - The 3-Slot Focus Horizon enforces strict capacity limits: `Now` displays at most `1` item, `Next` displays at most `2` items, and `Parked Reef` starts collapsed with an item counter badge.
   - All four Nemoclaw retriever capabilities (`local_fs_read`, `repo_git_scan`, `web_fetch_public`, `local_llm_ollama`) initialize to `false` (disabled / default-deny) on startup.
4. **Offline Fallback Guarantees**:
   - When external Neo4j (`bolt://127.0.0.1:7687`) or local Ollama workers are offline, the backend operates on its local `Relate v1.0.1` (`data/tideflow_memory.rl`) or `InProcess` graph driver without HTTP 500 errors.
   - When `CSS.paintWorklet` is unavailable or `prefers-reduced-motion: reduce` is active, CSS Houdini rhythm tokens (`--rhythm-bpm`, `--overwhelm-index`, `--focus-depth`, `--cadence-color`, `--lattice-phase`) fall back cleanly to standard CSS styling with zero uncaught console errors.

---

## 3. User Personas

- **Persona 1: ADD-Minded Creative Builder (Primary Daily User)**
  - Experiences rapid idea bursts, context-switch fatigue, and open-tab overwhelm.
  - Needs sub-2-second capture via `Ctrl+K` / `Cmd+K`, guilt-free parking for intrusive side quests, a 3-slot WIP cap (`Now: 1`, `Next: 2`), and a 3-line resume card to recover momentum after interruptions.
- **Persona 2: Personal AI Stack Operator (Security and Retrieval Operator)**
  - Configures which local files, git repositories, public web pages, or local LLM calls the Nemoclaw retriever may touch.
  - Requires default-deny toggles on startup, strict path and host allowlists, and an append-only audit console recording every `ALLOWED` and `DENIED` attempt.

---

## 4. Use Cases and Acceptance Criteria

### UC-1: Instant Thought Capture (Brain Dump Modal)
- **Actor**: Persona 1 (ADD-Minded Creative Builder)
- **Preconditions**: TideFlow cockpit is loaded at `http://127.0.0.1:5173`; backend is healthy at `http://127.0.0.1:8010/api/v1/health`.
- **Start Entrypoint**: Cockpit root view (`http://127.0.0.1:5173`).
- **Primary Flow**:
  1. Press `Control+k` (or `Meta+k`) or click the `Brain Dump` button to open the capture modal.
  2. Enter a thought text description (for example, `"Draft graph snapshot cache check #perf"`).
  3. Select a kind (`spark_idea`, `project_task`, `side_quest`, or `blocker`), choose an energy cost (`1` to `5`), optionally select a project, and optionally toggle `Auto-Park`.
  4. Click `Capture Thought` to submit `POST /api/v1/thoughts/capture`.
- **Observable Acceptance Criteria**:
  - **AC-1-1**: Pressing `Control+k` or clicking `Brain Dump` opens the Brain Dump modal with a focused text input and `Capture Thought` button.
  - **AC-1-2**: Submitting valid text sends `POST /api/v1/thoughts/capture`, receives HTTP `200` or `201`, closes the modal, and displays the captured thought in the Focus Horizon or `Parked Reef`.
  - **AC-1-3**: Selecting `Auto-Park` places the captured item directly in `Parked Reef` without displacing `Now` or `Next` items.
  - **AC-1-4**: Pressing `Escape` inside the open modal closes it cleanly without sending a network request.
- **Error and Boundary States**:
  - **AC-1-E1**: Submitting empty or whitespace-only text keeps the `Capture Thought` button disabled or shows an inline validation error without creating a thought; direct API calls with empty text or invalid `kind` or `energy_cost` outside `1..5` return HTTP `422` or `400`.

### UC-2: 3-Slot Focus Horizon Triage and Breadcrumb Context Resume
- **Actor**: Persona 1 (ADD-Minded Creative Builder)
- **Preconditions**: Active project exists with at least two captured thoughts.
- **Start Entrypoint**: Focus Horizon and Momentum Resume panels on `http://127.0.0.1:5173`.
- **Primary Flow**:
  1. Inspect `Now` (maximum 1 item), `Next` (maximum 2 items), and `Parked Reef` (collapsed list with item count).
  2. Click `Park` on an active thought (`POST /api/v1/thoughts/{id}/park`) to move it to `Parked Reef`.
  3. Expand `Parked Reef` and click `Promote` on a parked thought (`POST /api/v1/thoughts/{id}/promote`) to return it to active triage.
  4. Click `Run Triage Sweep` (`POST /api/v1/triage/sweep`) to recalculate slot assignments, `parked_count`, `overwhelm_index`, and `recommendation`.
  5. Enter a short context note and click `Save Breadcrumb` (`POST /api/v1/breadcrumbs`), then click `Resume Context` (`GET /api/v1/momentum/resume?project_id=...`).
- **Observable Acceptance Criteria**:
  - **AC-2-1**: After `Run Triage Sweep`, `Now` renders at most `1` item, `Next` renders at most `2` items, and `overwhelm_index` displays a numeric value between `0.0` and `1.0`.
  - **AC-2-2**: Clicking `Park` moves the item out of `Now`/`Next` and increments the `Parked Reef` count badge; clicking `Promote` restores it to active triage.
  - **AC-2-3**: Saving a second breadcrumb for the same project creates a bitemporal `SUPERSEDES` link while preserving history, and the Context Resume Card displays at most `3` concise lines (Last Action, 5-Minute Micro-Step, Linked Sparks).
- **Error and Boundary States**:
  - **AC-2-E1**: Querying `/api/v1/momentum/resume` or `/park` with an unknown ID returns HTTP `404` and displays a non-crashing error banner in the UI.

### UC-3: Interactive Neo4j Graph-Science Canvas and Hexactine Invariant
- **Actor**: Persona 1 (ADD-Minded Creative Builder)
- **Preconditions**: At least one project and linked thoughts exist in the graph store.
- **Start Entrypoint**: Graph Science Canvas panel on `http://127.0.0.1:5173`.
- **Primary Flow**:
  1. View the rendered graph canvas showing project, thought, and concept nodes.
  2. Switch between the four graph lenses (`PageRank`, `Communities`, `Shortest Path`, `Degree Audit`), triggering `GET /api/v1/graph/snapshot?lens=...`.
  3. In `Shortest Path` lens, select a source node and target node to invoke `GET /api/v1/graph/path?source_id=...&target_id=...`.
  4. Inspect the `Cypher Preview` drawer and `Hexactine Degree Audit` badge (`deg <= 6`).
- **Observable Acceptance Criteria**:
  - **AC-3-1**: Switching each lens updates node scoring/grouping metadata, displays a non-empty `gds.` Cypher preview query, and produces zero uncaught JS console errors.
  - **AC-3-2**: Querying `Degree Audit` confirms primary structural degree stays `<= 6` on `:Project` / `:SpiculeHub` nodes even when more than 6 thoughts are linked (overflow routes through `:ConceptTag` hubs).
  - **AC-3-3**: Selecting two connected nodes highlights the path and displays hop count.
- **Error and Boundary States**:
  - **AC-3-E1**: Selecting two disconnected nodes displays `"No path found"` cleanly without throwing runtime or HTTP 500 errors.

### UC-4: Deterministic Cadence Scheduler and CSS Houdini Rhythm Dial
- **Actor**: Persona 1 (ADD-Minded Creative Builder)
- **Preconditions**: Cockpit loaded with Cadence Scheduler and Rhythm Dial panels visible.
- **Start Entrypoint**: Cadence Scheduler and Rhythm Dial panels on `http://127.0.0.1:5173`.
- **Primary Flow**:
  1. Create a schedule block (`title`, `start_iso`, `end_iso`, `cadence_window`) via `POST /api/v1/schedule/blocks`.
  2. Update block metadata via `PATCH /api/v1/schedule/blocks/{id}` or remove it via `DELETE /api/v1/schedule/blocks/{id}`.
  3. Adjust energy (`1..5`) or duration (`minutes`) on the Rhythm Dial to request `GET /api/v1/schedule/prompts?now_iso=...&energy=...&minutes=...`.
- **Observable Acceptance Criteria**:
  - **AC-4-1**: Created blocks appear immediately in the schedule list across the four tidal windows (`deep_tide`, `creative_swell`, `shallow_drift`, `recovery_ebb`).
  - **AC-4-2**: Adjusting the Rhythm Dial updates computed CSS Houdini root properties (`--rhythm-bpm`, `--overwhelm-index`, `--focus-depth`, `--cadence-color`, `--lattice-phase`) and renders updated momentum prompts deterministically.
  - **AC-4-3**: Deleting a block removes it from the list and returns HTTP `200` or `204`.
- **Error and Boundary States**:
  - **AC-4-E1**: Creating an overlapping block returns HTTP `409 Conflict` and displays a visible conflict notice without crashing the scheduler UI.
  - **AC-4-E2**: Submitting `end_iso <= start_iso` returns HTTP `422` validation error.

### UC-5: Permission-Gated Nemoclaw Retriever and Live Audit Console
- **Actor**: Persona 2 (Personal AI Stack Operator)
- **Preconditions**: Cockpit loaded; all Nemoclaw capabilities start `false`.
- **Start Entrypoint**: Nemoclaw Permission Matrix and Audit Console panel on `http://127.0.0.1:5173`.
- **Primary Flow**:
  1. Inspect the 4 capability toggles (`local_fs_read`, `repo_git_scan`, `web_fetch_public`, `local_llm_ollama`) and confirm all show disabled (`false`).
  2. Attempt to execute `local_fs_read` on target `README.md` (`POST /api/v1/retriever/execute`) while disabled.
  3. Toggle `local_fs_read` to enabled (`PUT /api/v1/retriever/permissions`) and execute `local_fs_read` on `README.md` again.
  4. Inspect the Live Audit Console (`GET /api/v1/retriever/audit`) and Graph Canvas.
- **Observable Acceptance Criteria**:
  - **AC-5-1**: Step 2 returns HTTP `403`, displays an explicit permission-denied message in the UI, and appends a `DENIED` row to the Audit Console.
  - **AC-5-2**: Step 3 returns HTTP `200`, displays the retrieved `README.md` excerpt, appends an `ALLOWED` row to the Audit Console, and creates a `RetrievalArtifact` node in the graph.
- **Error and Boundary States**:
  - **AC-5-E1**: Even when `local_fs_read` is `true`, executing a path traversal target (`../../Windows/System32/drivers/etc/hosts`) or private SSRF metadata URL (`http://169.254.169.254/latest/meta-data/`) returns HTTP `403` and logs a `DENIED` audit entry.

### UC-6: Personal Stack Health and Graceful Degradation
- **Actor**: Persona 1 and Persona 2
- **Preconditions**: Cockpit is open at `http://127.0.0.1:5173`.
- **Start Entrypoint**: Top status bar on `http://127.0.0.1:5173`.
- **Primary Flow**:
  1. Observe the status badge driven by `GET /api/v1/health`.
  2. Verify active `backend_mode` (`relate`, `inprocess`, or `neo4j`), `relate_available`, `neo4j_available`, and `active_cadence` render clearly.
- **Observable Acceptance Criteria**:
  - **AC-6-1**: Status bar renders live `backend_mode` and `active_cadence` with zero HTTP `>= 500` responses and zero uncaught page errors.
  - **AC-6-2**: When `neo4j_available` is `false`, all core workflows (`UC-1` to `UC-5`) remain operational.
- **Error and Boundary States**:
  - **AC-6-E1**: If the backend process is stopped, the UI displays a clear offline indicator rather than a blank white crash screen.

---

## 5. Non-Functional Requirements and UI Label Glossary

### Non-Functional Requirements
- **Console and Network Hygiene**: Zero uncaught `pageerror` exceptions and zero HTTP `>= 500` responses across all primary flows.
- **Responsive Layout**: No horizontal scroll overflow at `390x844` mobile viewport (`scrollWidth <= innerWidth + 2`) and no overlapping interactive controls at `1280x800`.
- **Copy Hygiene (`unslop` + Zero Em Dashes)**: All visible UI text, API recommendation strings, and public docs contain zero U+2014 em dashes and zero generic AI filler words per the workspace `unslop` policy.

### UI Label Glossary
| Concept in PRD | Expected UI Label / Control | Endpoint / Contract |
|---|---|---|
| Brain Dump Trigger | `Brain Dump` button or `Control+k` | Opens modal (`Escape` closes) |
| Thought Capture Submit | `Capture Thought` | `POST /api/v1/thoughts/capture` |
| Focus Slot 1 | `Now` (cap 1) | `POST /api/v1/triage/sweep` |
| Focus Slot 2 | `Next` (cap 2) | `POST /api/v1/triage/sweep` |
| Guilt-Free Parking Lot | `Parked Reef` | `POST /api/v1/thoughts/{id}/park` |
| Restore Parked Thought | `Promote` | `POST /api/v1/thoughts/{id}/promote` |
| Triage Recalculation | `Run Triage Sweep` | `POST /api/v1/triage/sweep` |
| Breadcrumb Snapshot | `Save Breadcrumb` / `Resume Context` | `POST /api/v1/breadcrumbs`, `GET /api/v1/momentum/resume` |
| Graph Lenses | `PageRank`, `Communities`, `Shortest Path`, `Degree Audit` | `GET /api/v1/graph/snapshot?lens=...` |
| Cadence Windows | `deep_tide`, `creative_swell`, `shallow_drift`, `recovery_ebb` | `GET|POST /api/v1/schedule/blocks` |
| Nemoclaw Toggles | `local_fs_read`, `repo_git_scan`, `web_fetch_public`, `local_llm_ollama` | `GET|PUT /api/v1/retriever/permissions` |
| Nemoclaw Run & Audit | `Execute` button / `Audit Console` | `POST /api/v1/retriever/execute`, `GET /api/v1/retriever/audit` |

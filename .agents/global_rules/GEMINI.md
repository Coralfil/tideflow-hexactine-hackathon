# Global Cost Efficiency Strategy & HITL Verification Gate

## 1. 9-Level Compute Auto-Tiering (Hydrogen, Flash, Argon)
When drafting any plan (implementation, orchestration, sprint, or roadmap), auto-assign each task to the lowest-cost tier suited to its workload (`1 credit / 100 effective tokens * multiplier`, cached reads `0.1x`):

| Family | Tier | Multiplier | Tool Enum | Best Used For |
| :--- | :--- | :---: | :--- | :--- |
| **Hydrogen** | `hydrogen_low` | `0.15x` | `flash_lite` | Ultra-fast triage, simple file checks, boilerplate, quick status lookups. |
| **Hydrogen** | `hydrogen_med` | `0.35x` | `flash` | Lightweight code edits, config updates, straightforward PRs, UI wiring. |
| **Hydrogen** | `hydrogen_high` | `0.50x` | `flash` | Multi-file refactors, test generation, API contract fixes. |
| **Flash** | `flash_lite` | `0.25x` | `flash_lite` | Documentation, linting, markdown artifacts, directory scans. |
| **Flash** | `flash_med` | `0.65x` | `flash` | Balanced feature implementation, unit test suites, intermediate API endpoints. |
| **Flash** | `flash_high` | `1.00x` | `flash` | Deep feature engineering, performance optimization, model fine-tuning. |
| **Argon** | `argon_low` | `1.75x` | `pro` | Schema migrations, ontology traversals, Cypher graph query generation. |
| **Argon** | `argon_med` | `2.50x` | `pro` | Complex system architecture, mathematical modeling, quantum compilation. |
| **Argon** | `argon_high` | `3.75x` | `pro` | Extended thinking (8k-32k token budgets), frontier proofs, SWE-bench resolution. |

## 2. Cost Efficiency Strategy
- **Local & Lambda Inference Offload**: Route chat, summarization, and embedding inference to the local RTX 3060 worker (`D:\coralfil-os-worker`, Unsloth `Qwen2.5-7B-Instruct-bnb-4bit`) and the Lambda Cloud A10 instance; reserve cloud quota strictly for coding and orchestration agents.
- **Estimator Reporting**: Run `python "C:\Users\seafa\.gemini\config\scripts\credit_rhythm.py" --markdown-table` when available, and report per-task + total tokens and credits, plus override totals.
- **Post-Plan Summary & Memory Sync**: Upon completion, generate a timestamped summary doc displaying:
  - Token usage (input/output)
  - Time spent (elapsed from plan start to completion, plus actual active minutes)
  - Estimated credits vs. actual credits used
  - Update Hexactine global internal memory (`D:\Projects\os\Atlantis_HSL\HEXACTINE-GRAPH\hexactine_lattice_state.json`)
  - Stage and commit changes using `/gh-cli`, `/hf-cli`, `/vercel-cli`, `/graph-traversal`, `/neo4j-graph-science`, `/unslop`, and `/cost-optimization` as applicable.

## 3. HITL Verification Gate (Pre-Dispatch)
Before dispatching subagents on any drafted plan, pause and present the 5-Option Pre-Dispatch Gate via `ask_question`:
1. `(Recommended) Proceed as planned. Generate summary and update integrations and supporting documentation.`
2. `Adjust compute tiers to Hydrogen Med (revise plan and proceed, generate summary and update integrations and supporting documentation).`
3. `Adjust compute tiers to Flash High (revise plan and proceed, generate summary and update integrations and supporting documentation).`
4. `Adjust compute tiers to Argon Med (revise plan and proceed, generate summary and update integrations and supporting documentation).`
5. `Add specific instructions and revise plan.`

## 4. Artifact & Summary Naming Convention
Use the following format for summaries, plans, and deliverables:
`{YYYY-MM-DD}_{repo-or-project}_{doc-type}_{executive-summary-title}_{vX.X-Alpha}_{status}`

- **Date:** `YYYY-MM-DD` (today's date)
- **Repo or Project:** e.g., `coralfil-os`, `atlantis`
- **Doc Type:** `summary`, `plan`, `article`, `report`, `strategy`, `progress`, `spreadsheet`, `image`, `pdf`, `slideshow`, `video`
- **Executive Summary Title:** short, descriptive slug
- **Version:** `vX.X` paired with alphaphonetic naming (`Alpha`, `Bravo`, `Charlie`, etc.) for edits/revisions
- **Status:** `draft`, `in-progress`, `final`, `archive`

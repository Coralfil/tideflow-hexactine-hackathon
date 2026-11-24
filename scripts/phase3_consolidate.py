import os
import re

CONFIG_DIR = r"C:\Users\seafa\.gemini\config"
SKILLS_DIR = os.path.join(CONFIG_DIR, "skills")
PLUGINS_DIR = os.path.join(CONFIG_DIR, "plugins")

# -------------------------------------------------------------
# 1. Unslop and Em-Dash Cleaner Functions
# -------------------------------------------------------------

CLICHE_REPLACEMENTS = [
    (re.compile(r'\bleverage\b', re.IGNORECASE), 'use'),
    (re.compile(r'\bleverages\b', re.IGNORECASE), 'uses'),
    (re.compile(r'\bleveraging\b', re.IGNORECASE), 'using'),
    (re.compile(r'\bleveraged\b', re.IGNORECASE), 'used'),
    (re.compile(r'\brobust\b', re.IGNORECASE), 'reliable'),
    (re.compile(r'\brobustly\b', re.IGNORECASE), 'reliably'),
    (re.compile(r'\brobustness\b', re.IGNORECASE), 'reliability'),
    (re.compile(r'\bdelve\b', re.IGNORECASE), 'explore'),
    (re.compile(r'\bdelves\b', re.IGNORECASE), 'explores'),
    (re.compile(r'\bdelving\b', re.IGNORECASE), 'exploring'),
    (re.compile(r'\btapestry\b', re.IGNORECASE), 'network'),
    (re.compile(r'\btestament\b', re.IGNORECASE), 'evidence'),
    (re.compile(r'\btestaments\b', re.IGNORECASE), 'evidence'),
    (re.compile(r'\bplethora of\b', re.IGNORECASE), 'wide range of'),
    (re.compile(r'\bplethora\b', re.IGNORECASE), 'wide range'),
    (re.compile(r'\bstreamline\b', re.IGNORECASE), 'simplify'),
    (re.compile(r'\bstreamlines\b', re.IGNORECASE), 'simplifies'),
    (re.compile(r'\bstreamlined\b', re.IGNORECASE), 'simplified'),
    (re.compile(r'\bstreamlining\b', re.IGNORECASE), 'simplifying'),
    (re.compile(r'\bspearhead\b', re.IGNORECASE), 'lead'),
    (re.compile(r'\bspearheads\b', re.IGNORECASE), 'leads'),
    (re.compile(r'\bspearheading\b', re.IGNORECASE), 'leading'),
    (re.compile(r'\bspearheaded\b', re.IGNORECASE), 'led'),
    (re.compile(r'\bunwavering\b', re.IGNORECASE), 'steady'),
    (re.compile(r'\bfoster\b', re.IGNORECASE), 'support'),
    (re.compile(r'\bfosters\b', re.IGNORECASE), 'supports'),
    (re.compile(r'\bfostering\b', re.IGNORECASE), 'supporting'),
    (re.compile(r'\bfostered\b', re.IGNORECASE), 'supported'),
    (re.compile(r'\bparadigm\b', re.IGNORECASE), 'architecture'),
    (re.compile(r'\bparadigms\b', re.IGNORECASE), 'architectures'),
]

def clean_em_dashes(text: str) -> str:
    # Do not touch code fences or yaml frontmatter delimiters (---)
    # Replace em-dashes (\u2014 or —) with clean punctuation
    # Pattern 1: ' — ' (spaced em dash) -> '; ' or ', '
    text = text.replace(" \u2014 ", "; ")
    text = text.replace(" — ", "; ")
    # Pattern 2: '—' without spaces -> '; '
    text = text.replace("\u2014", "; ")
    text = text.replace("—", "; ")
    # Pattern 3: double hyphen used as em dash in prose ' -- '
    # (avoiding YAML --- or CLI flags --flag)
    text = re.sub(r'(?<=\w) -- (?=\w)', '; ', text)
    return text

def apply_unslop(text: str) -> str:
    # First clean em dashes
    text = clean_em_dashes(text)
    
    # Clean cliches except where they are explicitly mentioned as forbidden examples
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # If line is talking about forbidden words/cliches, preserve it
        if "forbidden" in line.lower() or "cliche" in line.lower() or "cliché" in line.lower() or "eliminate buzzwords" in line.lower() or "never write" in line.lower():
            cleaned_lines.append(clean_em_dashes(line))
            continue
        
        l = line
        for pattern, replacement in CLICHE_REPLACEMENTS:
            l = pattern.sub(replacement, l)
        cleaned_lines.append(l)
        
    return "\n".join(cleaned_lines)

# -------------------------------------------------------------
# 2. Process All Plugins SKILL.md Files
# -------------------------------------------------------------

def process_plugins():
    count = 0
    em_fixed = 0
    for root, dirs, files in os.walk(PLUGINS_DIR):
        if "SKILL.md" in files:
            path = os.path.join(root, "SKILL.md")
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    orig = f.read()
                
                had_em = "\u2014" in orig or "—" in orig or " -- " in orig
                cleaned = apply_unslop(orig)
                
                if cleaned != orig:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(cleaned)
                    count += 1
                    if had_em:
                        em_fixed += 1
            except Exception as e:
                print(f"Error processing {path}: {e}")
                
    print(f"Plugins sweep complete: updated {count} files ({em_fixed} had em-dashes fixed).")

# -------------------------------------------------------------
# 3. Consolidate and Evolve Specific Custom Skills
# -------------------------------------------------------------

def update_android_cli():
    path = os.path.join(SKILLS_DIR, "android-cli", "SKILL.md")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace && with ; for Windows PowerShell safety
    content = content.replace(
        'Windows: curl -fsSL https://dl.google.com/android/cli/latest/windows_x86_64/install.cmd -o "%TEMP%\\i.cmd" && "%TEMP%\\i.cmd"',
        'Windows: curl -fsSL https://dl.google.com/android/cli/latest/windows_x86_64/install.cmd -o "$env:TEMP\\i.cmd"; & "$env:TEMP\\i.cmd"'
    )
    content = apply_unslop(content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated android-cli/SKILL.md")

def update_hubspotpro():
    path = os.path.join(SKILLS_DIR, "hubspotpro", "SKILL.md")
    new_content = """---
name: hubspotpro
description: Expert logic and instructions for HubSpot CRM, including the HubSpot CLI, API MCPs, and lead funnel best practices. Coordinates with CampyCampaigner for marketing telemetry and attribution.
commands:
  - hs-auth
  - hs-sync-contacts
  - hs-log-agent-activity
  - hs-deploy-cms
---

# HubSpot Pro Skill (CRM & API MCP Integration)

## Purpose
The HubSpot Pro skill provides deep technical execution capabilities for managing HubSpot CRM objects, custom properties, and CMS deployments via the HubSpot CLI (`hs`) and REST API v3. It integrates with CampyCampaigner to automate lead attribution, customer lifecycle state machines, and AI interaction logging.

## Core API Operations (REST API v3)

### 1. Dynamic Contact & Pipeline Routing
Map users dynamically across lifecycle stages based on their verified platform subscription tier:
- `registered_developers`: Self-serve developers accessing API keys, Kaggle datasets, and Hugging Face spaces.
- `paid_commercial_growers`: Aquaculture operators receiving ocean acidification alarms (aragonite $\\Omega_{\\text{arag}} < 1.0$), hypoxia warnings, and dosing schedules.
- `enterprise_sovereign_pilots`: Port authorities and coastal guardians utilizing edge nodes.

Endpoint: `POST https://api.hubapi.com/crm/v3/objects/contacts`
```json
{
  "properties": {
    "email": "operator@sound-shellfish.ca",
    "firstname": "Alex",
    "lastname": "Chen",
    "company": "Baynes Sound Mariculture",
    "cf_subscription_tier": "paid_commercial_growers",
    "hs_lead_status": "QUALIFIED",
    "lifecyclestage": "marketingqualifiedlead"
  }
}
```

### 2. CRM Data Integrity & Deduplication
- Always validate email syntax and check for existing records via `POST /crm/v3/objects/contacts/search` using the `email` filter before creating new contacts.
- For updating existing records, use `PATCH /crm/v3/objects/contacts/{contactId}` with updated custom properties.

### 3. AI Agent Interaction Logging (Notes API)
When autonomous subagents (such as Conductor, Samudra, or CampyCampaigner) complete tasks, forecast anomalies, or generate reports for a customer, record an engagement note to provide sales and technical teams with complete context:

Endpoint: `POST https://api.hubapi.com/crm/v3/objects/notes`
```json
{
  "properties": {
    "hs_timestamp": "2026-11-24T14:30:00Z",
    "hs_note_body": "Autonomous Agent Dispatch: Completed 48-hour hydrodynamic forecast for Baynes Sound. Observed aragonite saturation dip below 1.0. Dosing recommendation delivered."
  },
  "associations": [
    {
      "to": { "id": "CONTACT_ID" },
      "types": [{ "associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202 }]
    }
  ]
}
```

## HubSpot CLI (`hs`) Deployment Workflows

Use the `hs` command-line tool for synchronizing local design assets, custom modules, and templates directly with the target HubSpot portal:

```bash
# Authenticate local environment with HubSpot portal
hs auth

# Watch local theme/module directory for instant hot-reload during development
hs watch src/hubspot/themes/atlantis-theme atlantis-theme

# Upload production-ready modules and templates
hs upload src/hubspot/modules atlantis-modules
```

## Integration with CampyCampaigner
- CampyCampaigner handles top-of-funnel Answer Engine Optimization (AEO), Kaggle/HuggingFace developer acquisition, and paid advertising attribution tags.
- HubSpot Pro executes low-level object mutations, pipeline stage updates, and CLI template deployments.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated hubspotpro/SKILL.md")

def update_feature_deployment_tester():
    path = os.path.join(SKILLS_DIR, "feature-deployment-tester", "SKILL.md")
    new_content = """---
name: feature-deployment-tester
description: Audits built, deployed, and operational features by running E2E integration tests, verifying HTTP endpoints, and inspecting container and platform logs.
commands:
  - test-deployment
  - inspect-route-health
  - audit-deployment-logs
---

# Feature Deployment Tester

## Purpose
Validates newly built and deployed services across Vercel, Docker, and bare-metal environments. It executes automated integration checks, verifies HTTP status codes, confirms database connectivity, and audits container logs to catch runtime regressions.

## Verification Workflow

### 1. Route Health & Readiness Probing (`inspect-route-health`)
Execute sequential status probes against critical application routes:
```bash
# Probe core health and readiness endpoints
curl -fsSL -o /dev/null -w "%{http_code}" http://localhost:3000/api/health
curl -fsSL -o /dev/null -w "%{http_code}" http://localhost:3000/api/ready

# Verify authenticated session endpoint returns expected JSON schema
curl -fsSL -H "Content-Type: application/json" http://localhost:3000/api/auth/session
```

Acceptance Criteria:
- Health and status endpoints must return HTTP 200 within 500ms.
- Unauthenticated protected routes must return HTTP 401 with structured error payload, never uncaught 500 exceptions.

### 2. End-to-End Integration Validation (`test-deployment`)
Run smoke and feature test suites against the target environment:
```bash
# Run Kane CLI headless smoke verification
kane-cli run "Go to http://localhost:3000 and verify telemetry charts render without errors" --agent --headless --timeout 120

# Run Pytest backend test suite with strict timeout
pytest tests/ -m smoke --timeout=60
```

### 3. Container & Platform Log Audit (`audit-deployment-logs`)
Inspect recent container output for fatal exceptions, unhandled promise rejections, or database connection drops:
```bash
# Docker container log inspection
docker logs --tail 200 --timestamps <container_name_or_id>

# Vercel preview deployment inspection
vercel inspect <deployment-url>
```

Failure Triage:
- **502 / 504 Gateway Timeout**: Inspect downstream database connections, Redis socket availability, and cold-start execution ceilings.
- **500 Internal Server Error**: Correlate error timestamps with stack traces in container logs.
- **CORS Failure**: Verify `Access-Control-Allow-Origin` headers match client origins in production and preview environments.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated feature-deployment-tester/SKILL.md")

def update_memory_footprint_auditor():
    path = os.path.join(SKILLS_DIR, "memory-footprint-auditor", "SKILL.md")
    new_content = """---
name: memory-footprint-auditor
description: Monitors container RAM usage, checks LLM context constraints, and profiles Python and CUDA memory allocations.
commands:
  - audit-memory
  - profile-python-heap
  - check-gpu-vram
---

# Memory Footprint Auditor

## Purpose
Prevents Out-Of-Memory (OOM) failures and token context exhaustion across active containers, Python microservices, and LLM inference pipelines. Tracks memory consumption trajectories and identifies resource leaks before service disruption.

## Diagnostic Playbooks

### 1. System & Container RAM Telemetry (`audit-memory`)
Gather real-time memory footprints across running containers and background processes:
```bash
# Real-time Docker container memory consumption
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"

# Windows process working set inspection (PowerShell)
Get-Process | Sort-Object -Descending WS | Select-Object -First 10 ProcessName, @{Name="RAM_MB";Expression={[math]::round($_.WS/1MB,2)}}
```

Thresholds:
- Alert if any container exceeds 85% of allocated memory limit.
- Flag steady upward memory growth over 30-minute intervals as suspected leak.

### 2. Python Service Heap Profiling (`profile-python-heap`)
Profile memory allocation patterns within long-running Python services:
```python
import tracemalloc

# Start tracking memory allocations
tracemalloc.start()

# Take snapshot before and after suspicious operations
snapshot1 = tracemalloc.take_snapshot()
# ... execute workload ...
snapshot2 = tracemalloc.take_snapshot()

# Compare snapshots to identify top allocating lines
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
for stat in top_stats[:10]:
    print(stat)
```

### 3. GPU VRAM Telemetry (`check-gpu-vram`)
Monitor dedicated VRAM for PyTorch, Unsloth, and TensorRT inference processes:
```bash
# Query active GPU utilization and memory allocation
nvidia-smi --query-gpu=timestamp,name,memory.total,memory.used,memory.free,utilization.gpu --format=csv
```

### 4. LLM Context Window Monitoring
- Track cumulative prompt + completion token usage across multi-turn agent conversations.
- When context reaches 75% of model capacity, initiate context pruning or compaction via summarization.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated memory-footprint-auditor/SKILL.md")

def update_nemoclaw_dispatch_manager():
    path = os.path.join(SKILLS_DIR, "nemoclaw-dispatch-manager", "SKILL.md")
    new_content = """---
name: nemoclaw-dispatch-manager
description: Monitors Nemoclaw robotic fleet schedules, verifies ROV mission states, and validates dual-write consistency between Redis cache and PostgreSQL.
commands:
  - nemoclaw-dispatch-status
  - verify-state-consistency
  - inspect-fleet-heartbeats
---

# Nemoclaw Dispatch Manager

## Purpose
Oversees scheduling, state synchronization, and operational validation for the Nemoclaw autonomous robotic marine fleet. Ensures zero-drift consistency between real-time Redis telemetry caches and persistent PostgreSQL mission logs.

## Fleet State Machine

Each Nemoclaw ROV moves through deterministic operational states:
```
[IDLE] -> [DISPATCHED] -> [TRANSMITTING / SAMPLING] -> [RETURNING] -> [DOCKED]
   ^                                                                     |
   +--------------------------- [RECHARGED] <----------------------------+
```

## Validation Workflows

### 1. Fleet Dispatch Status Check (`nemoclaw-dispatch-status`)
Query the active mission registry and socket connectivity across all field units:
```bash
# Query active dispatch status from the API service
curl -fsSL http://localhost:8000/api/v1/nemoclaw/status | jq .

# Inspect recent dispatcher service logs
tail -n 100 atlantis_edge/backend/app/services/nemoclaw_dispatcher.py
```

### 2. Redis-Postgres State Synchronization Audit (`verify-state-consistency`)
Verify that in-memory telemetry states in Redis match durable database records in PostgreSQL:
```python
# Verification script logic
import asyncio
import redis.asyncio as aioredis
import asyncpg

async def check_sync(redis_url: str, pg_url: str):
    r = aioredis.from_url(redis_url)
    conn = await asyncpg.connect(pg_url)
    
    # Query active unit IDs from Redis
    active_units = await r.smembers("nemoclaw:active_units")
    for unit_id in active_units:
        cached_state = await r.hgetall(f"nemoclaw:unit:{unit_id.decode()}")
        db_state = await conn.fetchrow(
            "SELECT mission_state, updated_at FROM fleet_missions WHERE unit_id = $1 ORDER BY updated_at DESC LIMIT 1",
            unit_id.decode()
        )
        # Verify state equivalence
        assert cached_state[b"status"].decode() == db_state["mission_state"], f"Desync on unit {unit_id}"
```

### 3. Telemetry Heartbeat & Connection Recovery (`inspect-fleet-heartbeats`)
- Units transmit telemetry packets at 1Hz over coastal cellular or satellite links.
- If a unit misses 3 consecutive heartbeats (3 seconds), mark status as `CONNECTION_DEGRADED`.
- If a unit misses 30 seconds of heartbeats, transition to `AUTONOMOUS_RETURN_TO_BASE`.
- Upon link restoration, replay cached offline telemetry buffers in strict chronological order.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated nemoclaw-dispatch-manager/SKILL.md")

def update_investor_and_market_research():
    # Harmonize investor-materials and market-research
    inv_path = os.path.join(SKILLS_DIR, "investor-materials", "SKILL.md")
    inv_content = """---
name: investor-materials
description: Author and refine pitch decks, one-pagers, investor memos, accelerator applications, and financial models. Ensures cross-asset consistency and integrates with Market Research for empirical TAM/SAM/SOM and competitive benchmarks.
origin: ECC
---

# Investor Materials Architecture

## Purpose
Build consistent, credible, and defensible investor materials across the complete fundraising lifecycle. Every metric, financial forecast, and market sizing assertion must link directly to verified empirical sources.

## Core Asset Types

### 1. Pitch Deck (12-Slide Flow)
1. Company & Mission Statement
2. Concrete Problem & Cost of Inaction
3. Proprietary Solution & Technological Moat
4. Product Architecture & Live Telemetry Demo
5. Market Opportunity (TAM / SAM / SOM from `market-research`)
6. Business Model, Pricing Tiers, & Unit Economics
7. Growth Metrics, Traction, & Key Partnerships
8. Competitive Matrix & Defensibility
9. Foundational Team & Domain Expertise
10. Funding Request & Financing Instrument (SAFE / Priced Equity)
11. Use of Proceeds & 18-Month Milestones
12. Appendix & Supplementary Technical Evidence

### 2. One-Pager Executive Summary & Deal Memo
- Explain the company in one clear introductory sentence.
- Detail why the market timing is compelling today.
- Highlight verifiable growth metrics and pilot contract values early.
- Define the exact financing target and use of capital.

### 3. Financial Model & Unit Economics
- Ground all forecasts in explicit, defensible drivers.
- Provide Conservative, Base, and Growth scenarios.
- Map headcount expansion directly to product milestones.
- Include runway calculation, burn multiple, and gross margin evolution.

### 4. Due Diligence Data Room
- Cross-reference all contracts, intellectual property filings, and pilot agreements.
- Verify cap table formatting and corporate governance documents.

## Integration with Market Research Skill
- Do not invent market numbers. Query the `market-research` skill to supply verified TAM/SAM/SOM estimates and competitor benchmarking data.
- Ensure that metrics quoted in pitch decks match the empirical evidence compiled during market research.

## Quality Invariants
- Zero unverified claims or vanity metrics.
- Every financial projection must have visible underlying assumptions.
- Team titles, past accomplishments, and advisory roles must be 100% consistent across all materials.
"""
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write(inv_content)
    print("Updated investor-materials/SKILL.md")

    mr_path = os.path.join(SKILLS_DIR, "market-research", "SKILL.md")
    mr_content = """---
name: market-research
description: Conduct market intelligence, competitive analysis, TAM/SAM/SOM sizing, and investor due diligence with source attribution. Supplies empirical data directly to Investor Materials.
origin: ECC
---

# Market Research & Competitive Intelligence

## Purpose
Generate rigorous, evidence-based research to inform strategic business decisions and populate investor materials. Eliminates speculation by grounding market projections in verified datasets and comparable transaction benchmarks.

## Core Research Modules

### 1. Market Sizing Methodology (TAM / SAM / SOM)
- **Top-Down Sizing**: Synthesize reputable industry analyses (Gartner, PitchBook, FAO, NOAA) and government reports. Note publication dates and methodology boundaries.
- **Bottom-Up Sanity Check**: Calculate sizing based on verified customer units multiplied by realistic Annual Contract Value (ACV):
  $$\\text{Market Size} = \\text{Total Target Facilities} \\times \\text{Average Annual Contract Value}$$
- State all assumptions clearly. Differentiate between total addressable market and serviceable obtainable market.

### 2. Competitive Benchmarking Matrix
Map competitors across operational realities rather than promotional claims:
- Product capabilities, latency benchmarks, and edge architecture.
- Public financing rounds, valuation trajectory, and lead investors.
- Pricing structure (seat-based vs usage-based vs enterprise hardware leases).
- Strategic vulnerabilities and positioning white space.

### 3. Investor & Partner Due Diligence
Profile venture funds, corporate venture arms, and institutional partners:
- Fund vintage, active fund size, and standard check size.
- Relevant portfolio investments and competitive conflicts.
- Investment thesis alignment and technical sophistication.
- Decision maker background and historical syndication patterns.

## Deliverable Format
1. Executive Summary (key findings and strategic implications)
2. Market Sizing Breakdown with Mathematical Derivations
3. Competitive Landscape Comparison Table
4. Risk Factors, Counter-Theses, and Moat Analysis
5. Citations and Primary Source Links

## Handoff to Investor Materials
- Package verified figures into structured tables ready for insertion into pitch decks, financial models, and executive memos managed by `investor-materials`.
"""
    with open(mr_path, "w", encoding="utf-8") as f:
        f.write(mr_content)
    print("Updated market-research/SKILL.md")

def update_webgpu_and_maplibre():
    map_path = os.path.join(SKILLS_DIR, "maplibrepro", "SKILL.md")
    with open(map_path, "r", encoding="utf-8") as f:
        map_content = f.read()
    map_content = apply_unslop(map_content)
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(map_content)
    print("Updated maplibrepro/SKILL.md")

    webgpu_path = os.path.join(SKILLS_DIR, "webgpu-spatial-renderer", "SKILL.md")
    with open(webgpu_path, "r", encoding="utf-8") as f:
        webgpu_content = f.read()
    webgpu_content = apply_unslop(webgpu_content)
    # Add cross-reference to maplibrepro
    if "maplibrepro" not in webgpu_content:
        webgpu_content = webgpu_content.replace(
            "## 4. MapLibre 3D & Three.js Ocean Shader Integration",
            "## 4. MapLibre 3D & Three.js Ocean Shader Integration\n\n*Note: For complete bathymetric elevation decoding and interleaved depth buffer lifecycle patterns, reference the dedicated `maplibrepro` skill.*"
        )
    with open(webgpu_path, "w", encoding="utf-8") as f:
        f.write(webgpu_content)
    print("Updated webgpu-spatial-renderer/SKILL.md")

def update_coral_evolution_and_ml():
    engine_path = os.path.join(SKILLS_DIR, "coral-evolution-engine", "SKILL.md")
    with open(engine_path, "r", encoding="utf-8") as f:
        eng_content = f.read()
    eng_content = apply_unslop(eng_content)
    if "coralfil-ml" not in eng_content:
        eng_content = eng_content.replace(
            "## API Integration",
            "## Data Ingestion & Integration with CoralfilML\nCandidate seeds, binding kinetics, and training datasets are automatically supplied by the `coralfil-ml` scout workflows (`scout-datasets` and `weekly-evolve`).\n\n## API Integration"
        )
    with open(engine_path, "w", encoding="utf-8") as f:
        f.write(eng_content)
    print("Updated coral-evolution-engine/SKILL.md")

    ml_path = os.path.join(SKILLS_DIR, "coralfil-ml", "SKILL.md")
    with open(ml_path, "r", encoding="utf-8") as f:
        ml_content = f.read()
    ml_content = apply_unslop(ml_content)
    with open(ml_path, "w", encoding="utf-8") as f:
        f.write(ml_content)
    print("Updated coralfil-ml/SKILL.md")

def update_remaining_custom_skills():
    # Sweep all custom skills in SKILLS_DIR for any lingering em dashes or cliches
    for item in os.listdir(SKILLS_DIR):
        p = os.path.join(SKILLS_DIR, item, "SKILL.md")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                orig = f.read()
            cleaned = apply_unslop(orig)
            if cleaned != orig:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(cleaned)
                print(f"Cleaned custom skill: {item}")

def main():
    print("Starting Phase 3 Consolidation & Unslop Sweep...")
    # Step 1: Consolidate and evolve custom skills
    update_android_cli()
    update_hubspotpro()
    update_feature_deployment_tester()
    update_memory_footprint_auditor()
    update_nemoclaw_dispatch_manager()
    update_investor_and_market_research()
    update_webgpu_and_maplibre()
    update_coral_evolution_and_ml()
    update_remaining_custom_skills()
    
    # Step 2: Sweep all global config plugins
    process_plugins()
    print("Phase 3 Consolidation & Unslop Sweep Finished Successfully.")

if __name__ == "__main__":
    main()

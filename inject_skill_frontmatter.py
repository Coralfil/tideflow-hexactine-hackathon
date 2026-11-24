import json
import os
import re

REGISTRY_PATH = r"D:\Kane Hackathon\skill_routing_registry.json"
INDEX_PATH = r"D:\Kane Hackathon\all_skills_list.txt"

TOOLTIP_SUMMARIES = {
    "a11y-debugging": "Audits web accessibility, ARIA labels, focus states, and keyboard navigation using Chrome DevTools MCP.",
    "ai-gateway": "Configures Vercel AI Gateway routing, authentication, fallbacks, virtual models, and spend telemetry.",
    "ai-sdk": "Implements LLM text generation, structured outputs, tool calling, and streaming with Vercel AI SDK.",
    "alphafold-database-fetch-and-analyze": "Retrieves and analyzes AlphaFold predicted protein structures and per-residue pLDDT confidence scores from UniProt IDs.",
    "android-cli": "Manages Android projects, SDK components, virtual devices, and device interactions from the command line.",
    "android-device-hub": "Controls and mirrors local Android emulators and connected physical devices via the Device Hub sidecar.",
    "auth": "Configures authentication providers, session management, and route protection for Next.js applications.",
    "bcoceanwriter": "Analyzes coastal telemetry trends and drafts investigative marine biological reporting.",
    "bootstrap": "Orchestrates repository initialization and resource linking for Vercel-backed projects.",
    "brave-search-cli": "Executes privacy-focused web and news searches with AI summarization using the Brave Search API.",
    "build-agents": "Designs and scaffolds autonomous AI agents, tool-calling systems, and multi-agent workflows.",
    "campycampaigner": "Automates developer-marketing campaigns, inbound link generation, and search engine optimization for marine models.",
    "cdn-caching": "Diagnoses Vercel CDN cache hit ratios, revalidation rules, and incremental static regeneration headers.",
    "chat-sdk": "Builds multi-platform conversational bots for Slack, Discord, Teams, and Telegram using unified adapters.",
    "chembl-database": "Queries the ChEMBL database for bioactive molecules, drug targets, binding affinities, and pharmacological bioactivities.",
    "cheminformatics-core": "Calculates RDKit physicochemical descriptors, structural alerts, and ionization states for chemical series.",
    "cheminformatics-ml": "Trains and evaluates predictive SAR and QSAR machine learning regressors for chemical libraries.",
    "cheminformatics-physics": "Simulates 3D molecular conformations, dihedral angle energy scans, and molecular docking poses.",
    "cheminformatics-reactions": "Models organic retrosynthesis paths, reaction SMARTS transformations, and stereochemical mechanism validation.",
    "chrome-devtools": "Automates browser debugging, performance profiling, and network inspection via Chrome DevTools MCP.",
    "compose-preview": "Renders and inspects Jetpack Compose preview functions in the Android preview sidecar pane.",
    "conductor-logic": "Orchestrates multi-agent execution plans with dynamic subagent dispatch and automated build self-correction.",
    "context-audit": "Audits agent context overhead, MCP servers, rules, and token consumption to prevent context bloat.",
    "cookie-debugging": "Inspects and diagnoses session cookies, authentication headers, and SameSite policies using Chrome DevTools.",
    "coral-evolution-engine": "Orchestrates multi-generational genetic search over biopolymer formulas and marine digital twin parameters.",
    "creative-director": "Develops visual interface designs, UI mockups, and front-end styling architecture.",
    "credentials": "Validates and safely provisions API credentials and environment secrets without credential leakage.",
    "credit-rhythm": "Monitors token consumption, manages 3-bucket credit budgets, and calibrates subagent compute tiers.",
    "custom-metrics": "Instruments Vercel Functions to emit custom operational metrics and latency telemetry.",
    "daemons": "Configures persistent background container workers and queue consumers on Vercel infrastructure.",
    "debug-optimize-lcp": "Identifies and resolves Largest Contentful Paint bottlenecks and Core Web Vitals performance regressions.",
    "deployments-cicd": "Automates Vercel deployment pipelines, preview promotions, rollback triggers, and CI workflow configurations.",
    "domains": "Manages DNS records, SSL certificates, and custom domain registrations on Vercel.",
    "env-vars": "Manages environment variables, secrets, and environment scopes across deployment targets.",
    "feature-deployment-tester": "Executes automated end-to-end integration tests, verifies HTTP endpoints, and inspects service logs.",
    "gcloud": "Executes validated Google Cloud Platform administration, resource provisioning, and IAM commands.",
    "gdocs": "Creates, formats, reads, and exports Google Docs documents via Workspace APIs.",
    "gdrive": "Searches, organizes, downloads, and uploads files across Google Drive storage.",
    "gemini-api-cli": "Executes shell-based Gemini API calls for multimodal analysis, transcription, and research tasks.",
    "gemini-api-dev": "Integrates the Gemini API SDK into Python and TypeScript codebases for generation, streaming, and tool calling.",
    "gh-cli": "Manages GitHub repositories, pull requests, issues, releases, and workflow runs via the gh command line.",
    "gnomad-database": "Queries gnomAD population variant frequencies, allele counts, and constraint metrics for genetic loci.",
    "google-antigravity-sdk": "Builds, configures, and orchestrates multi-agent workflows using the Google Antigravity SDK.",
    "google-cloud-recipe-auth": "Configures Identity and Access Management and Application Default Credentials for Google Cloud services.",
    "google-cloud-recipe-onboarding": "Initializes new Google Cloud projects, billing accounts, and core developer infrastructure.",
    "grantwriter": "Extracts grant requirements and drafts structured non-dilutive funding applications.",
    "gsheets": "Reads, writes, updates, and formats structured spreadsheet data in Google Sheets.",
    "gslides": "Generates, modifies, and organizes presentation decks using the Google Slides API.",
    "gtex-database": "Retrieves tissue-specific gene expression levels and eQTL statistical data from the GTEx database.",
    "houdini-css-artist": "Implements off-main-thread CSS Houdini Paint worklets and GPU-accelerated styling shaders.",
    "hubspotpro": "Synchronizes CRM records, pipeline stages, and marketing attribution data via HubSpot APIs.",
    "investor-materials": "Drafts and refines investor pitch decks, executive memos, financial models, and accelerator applications.",
    "is-agentic": "Evaluates and scores web endpoints and MCP tools for agent readiness and discoverability.",
    "knowledge-update": "Supplies verified updates on platform APIs, runtime capabilities, and framework changes.",
    "literature-search-arxiv": "Searches scientific preprints on arXiv and downloads structured publication metadata and PDFs.",
    "literature-search-biorxiv": "Queries bioRxiv and medRxiv repositories for biomedical preprints and publication records.",
    "literature-search-openalex": "Extracts academic papers, citation taxonomies, and author impact metrics from the OpenAlex graph.",
    "llm-dataset-curator": "Audits training data quality, sanitizes formatting, and verifies dataset copyright licensing.",
    "maplibrepro": "Renders 3D bathymetric terrain and spatial vector tiles with WebGPU shaders via MapLibre GL.",
    "market-research": "Analyzes market sizing, competitive landscapes, and industry dynamics for technology ventures.",
    "marketplace": "Discovers, provisions, and configures third-party integrations from the Vercel Marketplace.",
    "memory-footprint-auditor": "Profiles container RAM consumption, CUDA allocations, and LLM context window memory overhead.",
    "memory-leak-debugging": "Diagnoses JavaScript and Node.js heap leaks by capturing and comparing memory snapshots.",
    "ncbi-sequence-fetch": "Downloads nucleotide and protein sequences directly from NCBI Entrez databases by accession ID.",
    "nemoclaw-dispatch-manager": "Coordinates robotic ROV fleet dispatch schedules and validates Redis to PostgreSQL state synchronization.",
    "nvidia-earth2-benthic-map": "Generates bathymetric tiles and aggregates oceanographic sensor telemetry via NVIDIA Earth-2 APIs.",
    "offload-to-sandbox": "Offloads compute-intensive builds, full test suites, and batch experiments to cloud sandboxes.",
    "opentargets-database": "Queries Open Targets for disease-target associations, drug indications, and genetic evidence scores.",
    "ponytail-review": "Reviews codebases to identify and prune unnecessary dependencies, speculative abstractions, and dead code.",
    "predictingthepast": "Restores, attributes, and dates ancient epigraphic inscriptions using neural language models.",
    "pricingeist": "Benchmarks competitive SaaS rate cards and models unit-economic monetization structures.",
    "pubchem-database": "Searches PubChem for chemical structures, molecular properties, bioassay outcomes, and SMILES strings.",
    "pubmed-database": "Queries PubMed literature and biomedical abstracts linked to genes, compounds, and diseases.",
    "pymol": "Visualizes macromolecular 3D structures and renders publication-ready structural representations via PyMOL.",
    "quantum-ising-computing": "Compiles quantum Ising error-correction circuits and optimizes QUBO formulations on D-Wave annealers.",
    "rdkit-general": "Generates 2D chemical structure drawings, interactive molecular grids, and ChemDraw documentation via RDKit.",
    "react-best-practices": "Enforces React and Next.js optimization rules for bundle size, rendering performance, and data fetching.",
    "rolands-job-hunter": "Scouts executive Blue Economy opportunities, RFP tenders, and technical advisory board seats.",
    "routing-middleware": "Configures edge request routing, authentication guards, and path rewrites before CDN caching.",
    "runtime-cache": "Implements distributed key-value caching with tag-based invalidation across serverless functions.",
    "samudra-agent": "Executes hydrodynamic ocean neural emulators and multi-scale coastal current simulations.",
    "solidity-auditor": "Audits smart contracts for reentrancy, accounting logic flaws, and stablecoin peg vulnerabilities.",
    "troubleshooting": "Diagnoses target connectivity issues, DevTools protocol errors, and browser automation failures.",
    "uv": "Installs and manages Python virtual environments and packages using the high-performance uv toolchain.",
    "vercel-agent": "Configures Vercel AI platform assistance, security reviews, and autonomous deployment debugging.",
    "vercel-deployment-pro": "Customizes Build Output API v3 structures, serverless routing rules, and deployment output configurations.",
    "vercel-firewall": "Configures Web Application Firewall rules, DDoS mitigations, and IP rate limits on Vercel.",
    "vercel-functions": "Configures serverless function runtimes, execution duration limits, memory allocations, and streaming.",
    "vercel-services": "Configures multi-service polyglot application routing and service bindings on Vercel.",
    "verification": "Executes end-to-end application verification across browser interactions, API endpoints, and database state.",
    "wandb-cli": "Tracks machine learning experiment runs, hyperparameter sweeps, and model artifacts with Weights & Biases.",
    "webgpu-spatial-renderer": "Implements WebGPU compute pipelines and WGSL shaders for real-time spatial marine telemetry.",
    "workflow-skill-creator": "Packages multi-step developer interactions and repeatable workflows into reusable agent skills."
}

def main():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)

    skill_domains = {}
    for domain, skills in registry.items():
        for s in skills:
            if s not in skill_domains:
                skill_domains[s] = []
            if domain not in skill_domains[s]:
                skill_domains[s].append(domain)

    print(f"Loaded {len(skill_domains)} unique skills from registry.")
    
    # Check tooltips
    missing_tooltips = set(skill_domains.keys()) - set(TOOLTIP_SUMMARIES.keys())
    if missing_tooltips:
        raise ValueError(f"Missing tooltips for skills: {missing_tooltips}")

    # Check for em dashes in tooltips
    for s, summary in TOOLTIP_SUMMARIES.items():
        if "\u2014" in summary or "--" in summary:
            raise ValueError(f"Found em dash or double dash in tooltip for {s}: {summary}")

    # Load existing skill paths
    with open(INDEX_PATH, "r", encoding="utf-16") as f:
        indexed_paths = [p.strip() for p in f if p.strip() and os.path.exists(p.strip())]

    extra_dirs = [
        r"C:\Users\seafa\.gemini\config\plugins",
        r"C:\Users\seafa\.gemini\config\skills",
        r"C:\Users\seafa\.gemini\antigravity\builtin\skills"
    ]
    for ed in extra_dirs:
        for root, dirs, files in os.walk(ed):
            if "SKILL.md" in files:
                p = os.path.join(root, "SKILL.md")
                if p not in indexed_paths:
                    indexed_paths.append(p)

    # Map skills to paths
    skill_to_paths = {}
    for s in skill_domains:
        s_norm = s.lower().replace("_", "-")
        matched = []
        for p in indexed_paths:
            parent = os.path.basename(os.path.dirname(p)).lower().replace("_", "-")
            if parent == s_norm or (s == "android-device-hub" and parent in ("device-hub", "android-device-hub")):
                matched.append(p)
        skill_to_paths[s] = list(dict.fromkeys(matched))

    unmatched = [s for s, paths in skill_to_paths.items() if not paths]
    if unmatched:
        raise ValueError(f"Unmatched skills: {unmatched}")

    total_files_updated = 0
    total_skills_processed = 0

    for s, paths in skill_to_paths.items():
        domains = skill_domains[s]
        summary = TOOLTIP_SUMMARIES[s]
        
        # Prepare injection YAML lines
        domains_json = json.dumps(domains)
        summary_escaped = summary.replace('"', '\\"')
        
        injection_text = f'execution_domain: {domains_json}\ntooltip_summary: "{summary_escaped}"\n'

        for p in paths:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Check if file has frontmatter
                if content.startswith("---"):
                    # Find the second '---' delimiter
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        body = parts[2]

                        # Remove existing execution_domain and tooltip_summary if present
                        fm_lines = frontmatter.splitlines()
                        filtered_lines = []
                        skip = False
                        for line in fm_lines:
                            if line.strip().startswith("execution_domain:"):
                                skip = True
                                continue
                            if skip and (line.strip().startswith("- ") or line.strip().startswith("[")):
                                continue
                            else:
                                skip = False
                            if line.strip().startswith("tooltip_summary:"):
                                continue
                            filtered_lines.append(line)

                        clean_fm = "\n".join(filtered_lines).rstrip() + "\n"
                        new_fm = clean_fm + injection_text
                        new_content = f"---{new_fm}---{body}"
                    else:
                        new_content = f"---\n{injection_text}---\n\n{content}"
                else:
                    new_content = f"---\n{injection_text}---\n\n{content}"

                with open(p, "w", encoding="utf-8") as f:
                    f.write(new_content)

                total_files_updated += 1
            except Exception as e:
                print(f"Error processing {p}: {e}")

        total_skills_processed += 1

    print(f"Injection complete!")
    print(f"Skills processed: {total_skills_processed} / {len(skill_domains)}")
    print(f"Total files updated: {total_files_updated}")

if __name__ == "__main__":
    main()

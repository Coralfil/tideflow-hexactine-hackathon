# Hexactine Lattice Schema Reference

Read-only reference for `D:\Projects\os\Atlantis_HSL\HEXACTINE-GRAPH\hexactine_lattice_state.json` and `agentsea_skills_taxonomy.cyp`.

## Verified Lattice Metadata
- `schema_version`: `2026-11-16-HEXACTINE-GDS-V3-SE3`
- `degree_invariant_max`: `6`
- `active_squad_agents`: `26`
- `orchestral_divisions`: 5 divisions (`surface`, `mesopelagic`, `bathypelagic`, `abyssopelagic`, `hadal`)
- `spicule_junctions`: 43 junctions (`spicule_integrity: 1.0`)
- Top-level governance and graph keys: `conductor_governance`, `neo4j_gds_workflow`, `sovereign_epistemic_memory_layer`, `glass_sponge_hsl_graph_state`, `agentsea_skill_taxonomy`.

## Orthogonal 6-Ray Mapping
| Lifecycle Stage | Hexactine Ray | Semantic Edge |
|---|---|---|
| `1_INTAKE_AND_CLASSIFICATION` | `+z` | `FUSES_CONSTANTS` |
| `2_SQUAD_FORMATION` | `+x` | `CORROBORATES` |
| `3_EPISTEMIC_GATING` | `-x` | `CONTRADICTS` |
| `4_MULTI_AGENT_EXECUTION` | `-y` | `DEMOTES` |
| `5_CONFLICT_RESOLUTION` | `+y` | `PROMOTES` |
| `6_OUTPUT_VERIFICATION_AND_PERSISTENCE` | `-z` | `ANNOTATES_AUDIT` |

## Local RTX 3060 Worker Contract (`D:\coralfil-os-worker`)
Local endpoints run on `127.0.0.1` (`:8000` Obelisk 14B chat, `:8001` MiniLM 384-dim embeddings and BGE reranker, `:8003` 3B glyph router, `:8004` physics/claim verification, `:8080` A10 proxy). No API keys or remote secrets are copied into this repository; services check `/health` and fall back to deterministic local logic when offline.

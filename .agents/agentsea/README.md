# AgentSea & Helix Memory Bridge

This folder connects TideFlow Hexactine to the local `AtlantisAgentSea`, `atlantis_cli`, and `helix_memory` stack on a read-only basis without altering `D:\Projects\os\`.

## Source References
- `D:\Projects\os\AtlantisAgentSea`: Local-first Relate graph cookbooks and agent architecture.
- `D:\Projects\os\atlantis_cli\atlantis_cli\commands\agent_sea.py`: `AtlantisAgentSeaEngine` orchestrating 26 agents across 5 oceanic divisions (`surface`, `mesopelagic`, `bathypelagic`, `abyssopelagic`, `hadal`).
- `D:\Projects\os\atlantis_cli\atlantis_cli\core\hexactine_lattice.py`: `HexactineLatticeEngine` enforcing `MAX_DEGREE_INVARIANT = 6` and `PROMOTION_THRESHOLD = 0.75`.
- `D:\Projects\os\helix_memory`: Bitemporal `Session`, `Episode`, `Entity`, and `Fact` memory layer over `relate` CLI (`Relate v1.0.1`).

## Local Relate Store
Initialize `d:\Kane Hackathon\data\tideflow_memory.rl` using PowerShell (`;` separator):

```powershell
New-Item -ItemType Directory -Force -Path 'd:\Kane Hackathon\data' | Out-Null; Get-Content 'd:\Kane Hackathon\.agents\agentsea\helix_schema.cypher' -Raw | relate query --database 'd:\Kane Hackathon\data\tideflow_memory.rl' --mode table --safe
```

Note: `helix_memory` and `atlantis_cli` are not installed in global Python `site-packages`. Backend services invoke `relate` directly or optionally install `D:\Projects\os\helix_memory` in editable mode inside a virtualenv.

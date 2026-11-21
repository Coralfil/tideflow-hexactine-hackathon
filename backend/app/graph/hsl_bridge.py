"""Read-only bridge to Atlantis_HSL Hexactine lattice and AgentSea taxonomy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.graph.backend import GraphBackend
from app.models.schemas import HSLSummaryResponse

_CANONICAL_RAYS: dict[str, str] = {
    "+x": "CORROBORATES",
    "-x": "CONTRADICTS",
    "+y": "PROMOTES",
    "-y": "DEMOTES",
    "+z": "FUSES_CONSTANTS",
    "-z": "ANNOTATES_AUDIT",
}

_SCHEMA_A_KEY_MAP: dict[str, str] = {
    "+x_CORROBORATES": "+x",
    "-x_CONTRADICTS": "-x",
    "+y_PROMOTES": "+y",
    "-y_DEMOTES": "-y",
    "+z_FUSES": "+z",
    "-z_ANNOTATES": "-z",
}

_CYP_SQUAD_RE = re.compile(
    r'MERGE\s+\(\w+:Squad\s+\{id:\s*"([^"]+)",\s*name:\s*"([^"]+)",\s*role:\s*"([^"]+)",\s*lead:\s*"([^"]+)"\}\)'
)
_CYP_AGENT_RE = re.compile(
    r'MERGE\s+\(\w+:Agent\s+\{id:\s*"([^"]+)",\s*name:\s*"([^"]+)"\}\)'
)
_CYP_SKILL_RE = re.compile(
    r'MERGE\s+\(\w+:Skill\s+\{name:\s*"([^"]+)",\s*category:\s*"([^"]+)"\}\)'
)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "item"


def normalize_spicule_junction(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize both Hexactine spicule_junctions JSON schemas into one structure."""
    spicule_id = str(item.get("spicule_id") or item.get("id") or "unknown")
    rays: dict[str, list[str]] = {axis: [] for axis in _CANONICAL_RAYS}

    if isinstance(item.get("hexactine_rays"), dict):
        schema_variant = "schema_a_hexactine_rays"
        raw_rays = item["hexactine_rays"]
        for raw_key, axis in _SCHEMA_A_KEY_MAP.items():
            entry = raw_rays.get(raw_key)
            if isinstance(entry, dict):
                detail = (
                    entry.get("summary")
                    or entry.get("proposition")
                    or entry.get("source_section")
                    or entry.get("type")
                    or ""
                )
                if detail:
                    rays[axis].append(str(detail))
            elif isinstance(entry, list):
                rays[axis].extend(str(x) for x in entry if x)
        title = str(item.get("proposition") or spicule_id)
        score = float(item.get("harmonic_integral_score") or 0.0)
        lead = ""
        conductor = item.get("conductor")
        if isinstance(conductor, dict):
            lead = str(conductor.get("lead") or "")
        elif isinstance(conductor, str):
            lead = conductor
    else:
        schema_variant = "schema_b_flat_rays"
        for axis in _CANONICAL_RAYS:
            raw_list = item.get(axis)
            if isinstance(raw_list, list):
                rays[axis] = [str(x) for x in raw_list if x]
            elif isinstance(raw_list, str) and raw_list:
                rays[axis] = [raw_list]
        title = str(item.get("topic") or item.get("proposition") or spicule_id)
        score = float(item.get("epistemic_score") or 0.0)
        lead = str(item.get("lead_agent") or "")

    return {
        "spicule_id": spicule_id,
        "schema_variant": schema_variant,
        "title": title,
        "lead_agent": lead,
        "score": round(score, 4),
        "rays": rays,
        "ray_counts": {axis: len(vals) for axis, vals in rays.items()},
    }


class HSLBridge:
    """Strictly read-only bridge to Atlantis_HSL and AgentSea metadata."""

    def __init__(
        self,
        bridge_config_path: str | Path,
        manifest_path: str | Path,
    ) -> None:
        self.bridge_config_path = Path(bridge_config_path)
        self.manifest_path = Path(manifest_path)

        self.bridge_config: dict[str, Any] = {}
        self.manifest: dict[str, Any] = {}
        self.lattice_state: dict[str, Any] = {}
        self.taxonomy_cypher: str = ""
        self.loaded: bool = False

        self._load_read_only()

    def _read_json_if_exists(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_read_only(self) -> None:
        self.bridge_config = self._read_json_if_exists(self.bridge_config_path)
        self.manifest = self._read_json_if_exists(self.manifest_path)

        lattice_path_str = self.bridge_config.get("hexactine_state_path")
        if lattice_path_str:
            self.lattice_state = self._read_json_if_exists(Path(lattice_path_str))

        cyp_path_str = self.bridge_config.get("skills_taxonomy_cypher")
        if cyp_path_str:
            cyp_path = Path(cyp_path_str)
            if cyp_path.is_file():
                try:
                    self.taxonomy_cypher = cyp_path.read_text(encoding="utf-8")
                except OSError:
                    self.taxonomy_cypher = ""

        self.loaded = bool(self.bridge_config or self.manifest or self.lattice_state)

    def get_normalized_junctions(self) -> list[dict[str, Any]]:
        raw = self.lattice_state.get("spicule_junctions")
        if not isinstance(raw, list):
            return []
        return [
            normalize_spicule_junction(item)
            for item in raw
            if isinstance(item, dict)
        ]

    def get_orchestral_sections(self) -> list[dict[str, Any]]:
        raw = self.lattice_state.get("orchestral_sections")
        if not isinstance(raw, dict):
            return []
        sections: list[dict[str, Any]] = []
        for name, details in raw.items():
            info = details if isinstance(details, dict) else {}
            sections.append(
                {
                    "id": f"hsl_sec_{_slugify(str(name))}",
                    "name": str(name),
                    "lead": str(info.get("lead") or ""),
                    "weight": float(info.get("weight") or 0.0),
                    "domain": str(info.get("domain") or ""),
                    "specialists": list(info.get("specialists") or []),
                }
            )
        return sections

    def parse_taxonomy_counts(self) -> tuple[int, int, int]:
        if not self.taxonomy_cypher:
            sections = self.get_orchestral_sections()
            skills = self.lattice_state.get("agentsea_skill_taxonomy") or {}
            skill_count = sum(
                len(v) for v in skills.values() if isinstance(v, list)
            )
            return len(sections), int(self.lattice_state.get("active_squad_agents") or 0), skill_count
        squads = _CYP_SQUAD_RE.findall(self.taxonomy_cypher)
        agents = _CYP_AGENT_RE.findall(self.taxonomy_cypher)
        skills = _CYP_SKILL_RE.findall(self.taxonomy_cypher)
        return len(squads), len(agents), len(skills)

    def summary(self) -> HSLSummaryResponse:
        junctions = self.get_normalized_junctions()
        schema_a = sum(
            1 for j in junctions if j["schema_variant"] == "schema_a_hexactine_rays"
        )
        schema_b = sum(
            1 for j in junctions if j["schema_variant"] == "schema_b_flat_rays"
        )
        squad_count, agent_count, skill_count = self.parse_taxonomy_counts()
        degree_max = int(
            self.lattice_state.get("degree_invariant_max")
            or self.bridge_config.get("degree_invariant_max")
            or 6
        )
        schema_version = (
            self.lattice_state.get("schema_version")
            or self.bridge_config.get("expected_schema_version")
        )
        return HSLSummaryResponse(
            loaded=self.loaded,
            read_only=True,
            schema_version=str(schema_version) if schema_version else None,
            degree_invariant_max=degree_max,
            status=str(self.lattice_state.get("status"))
            if self.lattice_state.get("status")
            else None,
            orthogonal_rays=dict(_CANONICAL_RAYS),
            orchestral_sections=self.get_orchestral_sections(),
            spicule_count=len(junctions),
            schema_a_count=schema_a,
            schema_b_count=schema_b,
            squad_count=squad_count,
            agent_count=agent_count,
            skill_count=skill_count,
            sample_junctions=junctions[:4],
        )

    def seed_into_graph(
        self,
        backend: GraphBackend,
        science_service: Any | None = None,
        max_junctions: int = 4,
    ) -> dict[str, int]:
        """Idempotently seed HSL divisions and sample junctions respecting deg <= 6."""
        sections = self.get_orchestral_sections()
        junctions = self.get_normalized_junctions()[:max_junctions]
        nodes_seeded = 0
        edges_seeded = 0

        root_id = "hsl_hexactine_root"
        if sections or junctions:
            backend.upsert_node(
                "SpiculeHub",
                {
                    "id": root_id,
                    "title": "Hexactine Lattice Root",
                    "schema_version": str(
                        self.lattice_state.get("schema_version")
                        or "2026-11-16-HEXACTINE-GDS-V3-SE3"
                    ),
                    "source": "atlantis_hsl_bridge",
                },
            )
            nodes_seeded += 1

        def _find_existing_link(
            src_id: str, rel_type: str, target_id: str
        ) -> dict[str, Any] | None:
            for edge in backend.get_edges(node_id=src_id, direction="out"):
                if edge["rel_type"] == rel_type and edge["target"] == target_id:
                    return edge
                if edge["rel_type"] == "ROUTED_THROUGH":
                    props = edge.get("properties") or {}
                    if (
                        props.get("canonical_target_id") == target_id
                        and props.get("original_rel") == rel_type
                    ):
                        return edge
            return None

        for sec in sections:
            backend.upsert_node(
                "SpiculeHub",
                {
                    "id": sec["id"],
                    "title": sec["name"],
                    "lead": sec["lead"],
                    "domain": sec["domain"],
                    "source": "atlantis_hsl_bridge",
                },
            )
            nodes_seeded += 1
            existing_sec_edge = _find_existing_link(sec["id"], "CORROBORATES", root_id)
            if existing_sec_edge is not None:
                backend.upsert_edge(
                    existing_sec_edge["source"],
                    existing_sec_edge["rel_type"],
                    existing_sec_edge["target"],
                    {"weight": max(sec["weight"], 0.1)},
                )
            else:
                if science_service is not None:
                    science_service.link_with_hexactine_invariant(
                        backend,
                        sec["id"],
                        "CORROBORATES",
                        root_id,
                        concept_tags=["hexactine", _slugify(sec["lead"])],
                        edge_props={"weight": max(sec["weight"], 0.1)},
                    )
                else:
                    backend.upsert_edge(
                        sec["id"],
                        "CORROBORATES",
                        root_id,
                        {"weight": max(sec["weight"], 0.1)},
                    )
                edges_seeded += 1

        for j in junctions:
            j_id = f"hsl_junc_{_slugify(j['spicule_id'])}"
            backend.upsert_node(
                "ConceptTag",
                {
                    "id": j_id,
                    "key": _slugify(j["spicule_id"]),
                    "name": j["title"][:120],
                    "schema_variant": j["schema_variant"],
                    "score": j["score"],
                    "source": "atlantis_hsl_bridge",
                },
            )
            nodes_seeded += 1
            existing_j_edge = _find_existing_link(j_id, "FUSES_CONSTANTS", root_id)
            if existing_j_edge is not None:
                backend.upsert_edge(
                    existing_j_edge["source"],
                    existing_j_edge["rel_type"],
                    existing_j_edge["target"],
                    {"weight": 1.0},
                )
            else:
                if science_service is not None:
                    science_service.link_with_hexactine_invariant(
                        backend,
                        j_id,
                        "FUSES_CONSTANTS",
                        root_id,
                        concept_tags=["hexactine", j["schema_variant"]],
                        edge_props={"weight": 1.0},
                    )
                else:
                    backend.upsert_edge(j_id, "FUSES_CONSTANTS", root_id, {"weight": 1.0})
                edges_seeded += 1

        return {"nodes_seeded": nodes_seeded, "edges_seeded": edges_seeded}

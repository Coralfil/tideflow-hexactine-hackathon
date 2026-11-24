"""Pure-Python deterministic Graph Science Service (PageRank, Louvain, Dijkstra, deg <= 6)."""

from __future__ import annotations

import heapq
import math
import re
from collections import defaultdict, deque
from typing import Any

from app.graph.backend import GraphBackend
from app.models.schemas import (
    DegreeViolation,
    GraphEdgeView,
    GraphLens,
    GraphNodeView,
    GraphScienceMetrics,
    GraphSnapshotResponse,
    ShortestPathResult,
)

CAPPED_STRUCTURAL_LABELS = frozenset({"Project", "SpiculeHub", "ConceptTag"})
EXCLUDED_DEGREE_REL_TYPES = frozenset({"SUPERSEDES"})


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "tag"


def _safe_edge_weight(edge: dict[str, Any], default: float = 1.0) -> float:
    raw = (edge.get("properties") or {}).get("weight", default)
    if raw is None or isinstance(raw, bool):
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(val) or val <= 0.0:
        return default
    return val


def _escape_cypher_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _node_title(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    return str(
        props.get("name")
        or props.get("title")
        or props.get("text")
        or props.get("last_action")
        or props.get("key")
        or node["id"]
    )[:120]


class GraphScienceService:
    """Deterministic graph analytics + Hexactine deg <= 6 invariant enforcement."""

    def __init__(self, degree_invariant_max: int = 6) -> None:
        self.degree_invariant_max = degree_invariant_max
        self._direct_leaf_limit = max(1, degree_invariant_max - 1)

    def compute_pagerank(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        damping: float = 0.85,
        max_iterations: int = 20,
        tolerance: float = 1e-6,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Compute deterministic PageRank (sorted node IDs, dangling mass handling)."""
        node_ids = sorted(n["id"] for n in nodes)
        n_count = len(node_ids)
        if n_count == 0:
            return {}, {}

        node_set = set(node_ids)
        out_edges: dict[str, list[tuple[str, float]]] = {nid: [] for nid in node_ids}
        out_weight: dict[str, float] = {nid: 0.0 for nid in node_ids}

        for edge in sorted(edges, key=lambda e: (e["source"], e["rel_type"], e["target"])):
            src = edge["source"]
            dst = edge["target"]
            if src not in node_set or dst not in node_set:
                continue
            w = _safe_edge_weight(edge, default=1.0)
            out_edges[src].append((dst, w))
            out_weight[src] += w

        ranks: dict[str, float] = {nid: 1.0 / n_count for nid in node_ids}
        dangling_nodes = [nid for nid in node_ids if out_weight[nid] == 0.0]

        for _ in range(max_iterations):
            dangling_mass = damping * sum(ranks[nid] for nid in dangling_nodes) / n_count
            base = (1.0 - damping) / n_count + dangling_mass
            new_ranks: dict[str, float] = {nid: base for nid in node_ids}

            for src in node_ids:
                total_w = out_weight[src]
                if total_w <= 0.0:
                    continue
                share_base = damping * ranks[src] / total_w
                for dst, w in out_edges[src]:
                    new_ranks[dst] += share_base * w

            diff = sum(abs(new_ranks[nid] - ranks[nid]) for nid in node_ids)
            ranks = new_ranks
            if diff < tolerance:
                break

        raw_scores = {nid: round(ranks[nid], 6) for nid in node_ids}
        min_r = min(ranks.values())
        max_r = max(ranks.values())
        span = max_r - min_r
        if span <= 1e-12:
            norm_scores = {nid: 1.0 if n_count == 1 else 0.5 for nid in node_ids}
        else:
            norm_scores = {
                nid: round((ranks[nid] - min_r) / span, 6) for nid in node_ids
            }
        return raw_scores, norm_scores

    def compute_communities(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        max_iterations: int = 20,
    ) -> tuple[dict[str, int], float]:
        """Compute deterministic undirected Louvain communities and modularity Q."""
        node_ids = sorted(n["id"] for n in nodes)
        if not node_ids:
            return {}, 0.0

        node_set = set(node_ids)
        adj: dict[str, dict[str, float]] = {nid: defaultdict(float) for nid in node_ids}
        k_deg: dict[str, float] = {nid: 0.0 for nid in node_ids}
        m2 = 0.0

        for edge in sorted(edges, key=lambda e: (e["source"], e["rel_type"], e["target"])):
            u = edge["source"]
            v = edge["target"]
            if u not in node_set or v not in node_set:
                continue
            w = _safe_edge_weight(edge, default=1.0)
            if u == v:
                adj[u][u] += w
                k_deg[u] += w
                m2 += w
            else:
                adj[u][v] += w
                adj[v][u] += w
                k_deg[u] += w
                k_deg[v] += w
                m2 += 2.0 * w

        if m2 <= 0.0:
            return {nid: idx for idx, nid in enumerate(node_ids)}, 0.0

        comm: dict[str, int] = {nid: idx for idx, nid in enumerate(node_ids)}
        sigma_tot: dict[int, float] = {idx: k_deg[nid] for idx, nid in enumerate(node_ids)}

        for _ in range(max_iterations):
            moved = False
            for u in node_ids:
                c_old = comm[u]
                k_u = k_deg[u]
                sigma_tot[c_old] -= k_u
                comm[u] = -1

                nbr_weights: dict[int, float] = defaultdict(float)
                for v, w in adj[u].items():
                    c_v = comm[v]
                    if c_v != -1:
                        nbr_weights[c_v] += w

                best_c = c_old
                best_gain = 0.0
                k_u_in_old = nbr_weights.get(c_old, 0.0)
                loss_old = k_u_in_old - (sigma_tot[c_old] * k_u) / m2

                candidate_comms = sorted(set(nbr_weights.keys()) | {c_old})
                for c_cand in candidate_comms:
                    gain = (
                        nbr_weights.get(c_cand, 0.0)
                        - (sigma_tot.get(c_cand, 0.0) * k_u) / m2
                        - loss_old
                    )
                    if gain > best_gain + 1e-9 or (
                        abs(gain - best_gain) <= 1e-9 and c_cand < best_c and gain > 1e-9
                    ):
                        best_gain = gain
                        best_c = c_cand

                comm[u] = best_c
                sigma_tot[best_c] = sigma_tot.get(best_c, 0.0) + k_u
                if best_c != c_old:
                    moved = True

            if not moved:
                break

        # Compute modularity Q
        q_sum = 0.0
        for u in node_ids:
            for v in node_ids:
                if comm[u] == comm[v]:
                    a_uv = adj[u].get(v, 0.0)
                    q_sum += a_uv - (k_deg[u] * k_deg[v]) / m2
        modularity = round(q_sum / m2, 6)

        # Relabel consecutive IDs 0..K-1 ordered by lexicographically smallest node_id
        groups: dict[int, list[str]] = defaultdict(list)
        for nid in node_ids:
            groups[comm[nid]].append(nid)
        ordered_groups = sorted(groups.values(), key=lambda members: members[0])
        consecutive: dict[str, int] = {}
        for new_cid, members in enumerate(ordered_groups):
            for nid in members:
                consecutive[nid] = new_cid

        return consecutive, modularity

    def compute_shortest_path(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        source_id: str,
        target_id: str,
        directed: bool = False,
    ) -> ShortestPathResult:
        """Deterministic Dijkstra shortest path with lexicographic tie-breaking."""
        cypher_preview = self.gds_cypher_preview(
            "path", source_id=source_id, target_id=target_id
        )
        node_ids = {n["id"] for n in nodes}
        if source_id not in node_ids or target_id not in node_ids:
            return ShortestPathResult(
                found=False,
                source_id=source_id,
                target_id=target_id,
                gds_cypher_preview=cypher_preview,
            )

        if source_id == target_id:
            return ShortestPathResult(
                found=True,
                source_id=source_id,
                target_id=target_id,
                node_ids=[source_id],
                edges=[],
                total_cost=0.0,
                hop_count=0,
                gds_cypher_preview=cypher_preview,
            )

        adj: dict[str, list[tuple[str, float, dict[str, Any]]]] = defaultdict(list)
        for edge in sorted(edges, key=lambda e: (e["source"], e["rel_type"], e["target"])):
            src = edge["source"]
            dst = edge["target"]
            if src not in node_ids or dst not in node_ids:
                continue
            weight = max(_safe_edge_weight(edge, default=1.0), 1e-6)
            cost = 1.0 / weight
            adj[src].append((dst, cost, edge))
            if not directed:
                adj[dst].append((src, cost, edge))

        for nid in adj:
            adj[nid].sort(key=lambda item: (item[0], item[2]["rel_type"]))

        best_cost: dict[str, tuple[float, int]] = {source_id: (0.0, 0)}
        pq: list[tuple[float, int, str, list[str], list[dict[str, Any]]]] = [
            (0.0, 0, source_id, [source_id], [])
        ]

        while pq:
            cost, hops, curr, path_nodes, path_edges = heapq.heappop(pq)
            if curr == target_id:
                edge_views = [
                    GraphEdgeView(
                        id=e["id"],
                        source=e["source"],
                        target=e["target"],
                        rel_type=e["rel_type"],
                        weight=_safe_edge_weight(e, default=1.0),
                        routed_via_subhub=bool(
                            (e.get("properties") or {}).get("routed_via_subhub", False)
                        ),
                        in_active_path=True,
                        properties=dict(e.get("properties") or {}),
                    )
                    for e in path_edges
                ]
                return ShortestPathResult(
                    found=True,
                    source_id=source_id,
                    target_id=target_id,
                    node_ids=path_nodes,
                    edges=edge_views,
                    total_cost=round(cost, 6),
                    hop_count=len(path_edges),
                    gds_cypher_preview=cypher_preview,
                )

            recorded = best_cost.get(curr)
            if recorded is not None and (cost, hops) > recorded:
                continue

            for nbr, step_cost, edge in adj.get(curr, []):
                next_state = (round(cost + step_cost, 9), hops + 1)
                prev_best = best_cost.get(nbr)
                if prev_best is None or next_state < prev_best:
                    best_cost[nbr] = next_state
                    heapq.heappush(
                        pq,
                        (
                            next_state[0],
                            next_state[1],
                            nbr,
                            [*path_nodes, nbr],
                            [*path_edges, edge],
                        ),
                    )

        return ShortestPathResult(
            found=False,
            source_id=source_id,
            target_id=target_id,
            gds_cypher_preview=cypher_preview,
        )

    def _compute_structural_degrees(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        degrees: dict[str, int] = {n["id"]: 0 for n in nodes}
        for edge in edges:
            if edge["rel_type"] in EXCLUDED_DEGREE_REL_TYPES:
                continue
            src = edge["source"]
            dst = edge["target"]
            if src in degrees:
                degrees[src] += 1
            if dst in degrees:
                degrees[dst] += 1
        return degrees

    def audit_degrees(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[dict[str, int], list[DegreeViolation], int, int]:
        """Audit deg <= degree_invariant_max across capped structural labels."""
        degrees = self._compute_structural_degrees(nodes, edges)
        violations: list[DegreeViolation] = []
        max_observed = 0
        sub_hub_count = 0

        for node in sorted(nodes, key=lambda n: n["id"]):
            nid = node["id"]
            labels = list(node.get("labels") or [])
            deg = degrees.get(nid, 0)
            if deg > max_observed:
                max_observed = deg
            if "SpiculeHub" in labels:
                sub_hub_count += 1
            if any(lbl in CAPPED_STRUCTURAL_LABELS for lbl in labels):
                if deg > self.degree_invariant_max:
                    violations.append(
                        DegreeViolation(
                            node_id=nid,
                            labels=labels,
                            degree=deg,
                            max_allowed=self.degree_invariant_max,
                            exceeded_by=deg - self.degree_invariant_max,
                        )
                    )

        return degrees, violations, max_observed, sub_hub_count

    def _is_capped_node(self, node: dict[str, Any] | None) -> bool:
        if node is None:
            return False
        return any(lbl in CAPPED_STRUCTURAL_LABELS for lbl in node.get("labels", []))

    def _find_hub_candidate(
        self,
        backend: GraphBackend,
        root_id: str,
        concept_tags: list[str],
        max_degree_exclusive: int,
        exclude_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """BFS over ConceptTag / SpiculeHub neighbors for a hub with deg < max_degree_exclusive."""
        excluded = set(exclude_ids or set())
        tag_slugs = {_slugify(t) for t in concept_tags}
        visited: set[str] = {root_id}
        queue: deque[str] = deque([root_id])
        candidates: list[tuple[int, int, int, str, dict[str, Any]]] = []

        while queue:
            curr = queue.popleft()
            edges = backend.get_edges(node_id=curr, direction="both", limit=500)
            neighbor_ids: set[str] = set()
            for edge in edges:
                other = edge["target"] if edge["source"] == curr else edge["source"]
                if other not in visited:
                    neighbor_ids.add(other)

            for nbr_id in sorted(neighbor_ids):
                visited.add(nbr_id)
                node = backend.get_node(nbr_id)
                if node is None:
                    continue
                labels = set(node.get("labels") or [])
                if not (labels & {"ConceptTag", "SpiculeHub"}):
                    continue
                queue.append(nbr_id)
                if nbr_id in excluded:
                    continue
                deg = backend.get_node_degree(
                    nbr_id, excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
                )
                if deg < max_degree_exclusive:
                    key_slug = _slugify(
                        str((node.get("properties") or {}).get("key") or nbr_id)
                    )
                    tag_match_rank = 0 if key_slug in tag_slugs else 1
                    hub_type_rank = 0 if "SpiculeHub" in labels else 1
                    candidates.append((tag_match_rank, hub_type_rank, deg, nbr_id, node))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return candidates[0][4]

    def _find_anchor_for_new_hub(
        self,
        backend: GraphBackend,
        target_id: str,
    ) -> dict[str, Any] | None:
        """Find target_id or an existing SpiculeHub/ConceptTag with deg < degree_invariant_max."""
        target_node = backend.get_node(target_id)
        if target_node is None:
            return None
        target_deg = backend.get_node_degree(
            target_id, excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
        )
        if target_deg < self.degree_invariant_max:
            return target_node

        visited: set[str] = {target_id}
        queue: deque[str] = deque([target_id])
        while queue:
            curr = queue.popleft()
            edges = backend.get_edges(node_id=curr, direction="both", limit=500)
            nbrs = sorted(
                {
                    e["target"] if e["source"] == curr else e["source"]
                    for e in edges
                }
            )
            for nbr_id in nbrs:
                if nbr_id in visited:
                    continue
                visited.add(nbr_id)
                node = backend.get_node(nbr_id)
                if node is None:
                    continue
                labels = set(node.get("labels") or [])
                if not (labels & {"SpiculeHub", "ConceptTag"}):
                    continue
                deg = backend.get_node_degree(
                    nbr_id, excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
                )
                if deg < self.degree_invariant_max:
                    return node
                queue.append(nbr_id)

        # Fallback: attach to an existing SpiculeHub for this canonical target (or any open SpiculeHub)
        all_hubs = backend.query_nodes("SpiculeHub", limit=1000)
        preferred = [
            h
            for h in all_hubs
            if (h.get("properties") or {}).get("canonical_target_id") == target_id
        ]
        others = [
            h
            for h in all_hubs
            if (h.get("properties") or {}).get("canonical_target_id") != target_id
        ]
        for candidate in [*preferred, *others]:
            deg = backend.get_node_degree(
                candidate["id"], excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
            )
            if deg < self.degree_invariant_max:
                return candidate
        return None

    def _allocate_subhub(
        self,
        backend: GraphBackend,
        canonical_target_id: str,
    ) -> dict[str, Any]:
        """Create a new :SpiculeHub attached to an anchor with deg < degree_invariant_max."""
        existing_hubs = backend.query_nodes("SpiculeHub", limit=1000)
        prefix = f"hub_{_slugify(canonical_target_id)}_"
        seq = 1
        existing_ids = {h["id"] for h in existing_hubs}
        while f"{prefix}{seq}" in existing_ids:
            seq += 1
        hub_id = f"{prefix}{seq}"

        anchor = self._find_anchor_for_new_hub(backend, canonical_target_id)
        hub_props: dict[str, Any] = {
            "id": hub_id,
            "title": f"Spicule Sub-Hub {seq}",
            "canonical_target_id": canonical_target_id,
            "seq": seq,
        }
        if anchor is None:
            hub_props["anchor_status"] = "unanchored_capacity_full"
        hub_node = backend.upsert_node("SpiculeHub", hub_props)
        if anchor is not None:
            backend.upsert_edge(
                hub_id,
                "SUB_HUB",
                anchor["id"],
                {
                    "weight": 1.0,
                    "canonical_target_id": canonical_target_id,
                },
            )
        return hub_node

    def _resolve_endpoint(
        self,
        backend: GraphBackend,
        endpoint_id: str,
        other_id: str,
        concept_tags: list[str],
    ) -> tuple[str, bool]:
        """Return (effective_endpoint_id, routed_via_subhub) preserving deg <= max."""
        node = backend.get_node(endpoint_id)
        if not self._is_capped_node(node):
            return endpoint_id, False

        deg = backend.get_node_degree(
            endpoint_id, excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
        )
        if deg < self._direct_leaf_limit:
            return endpoint_id, False

        hub = self._find_hub_candidate(
            backend,
            endpoint_id,
            concept_tags,
            max_degree_exclusive=self._direct_leaf_limit,
            exclude_ids={other_id},
        )
        if hub is None:
            hub = self._allocate_subhub(backend, endpoint_id)
        return hub["id"], True

    def link_with_hexactine_invariant(
        self,
        backend: GraphBackend,
        src_id: str,
        rel_type: str,
        target_id: str,
        concept_tags: list[str] | None = None,
        edge_props: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool, str | None]:
        """Connect src_id -> target_id while guaranteeing deg(v) <= 6 on capped nodes."""
        tags = concept_tags or []
        base_props = dict(edge_props or {})
        base_props.setdefault("weight", 1.0)

        existing_direct = [
            e
            for e in backend.get_edges(node_id=src_id, rel_type=rel_type, direction="out")
            if e["target"] == target_id
        ]
        if existing_direct:
            edge = backend.upsert_edge(src_id, rel_type, target_id, base_props)
            return edge, False, None

        existing_routed = [
            e
            for e in backend.get_edges(
                node_id=src_id, rel_type="ROUTED_THROUGH", direction="out"
            )
            if (e.get("properties") or {}).get("canonical_target_id") == target_id
            and (e.get("properties") or {}).get("original_rel") == rel_type
        ]
        if existing_routed:
            existing_edge = existing_routed[0]
            existing_props = dict(existing_edge.get("properties") or {})
            existing_props.update(base_props)
            edge = backend.upsert_edge(
                existing_edge["source"],
                "ROUTED_THROUGH",
                existing_edge["target"],
                existing_props,
            )
            subhub = str(existing_props.get("routed_via") or existing_edge["target"])
            return edge, True, subhub

        eff_src, src_routed = self._resolve_endpoint(backend, src_id, target_id, tags)
        eff_dst, dst_routed = self._resolve_endpoint(backend, target_id, eff_src, tags)
        routed = src_routed or dst_routed

        if not routed:
            edge = backend.upsert_edge(eff_src, rel_type, eff_dst, base_props)
            return edge, False, None

        subhub_id = eff_dst if dst_routed else eff_src
        routed_props: dict[str, Any] = {
            **base_props,
            "canonical_src_id": src_id,
            "canonical_target_id": target_id,
            "original_rel": rel_type,
            "routed_via_subhub": True,
            "routed_via": subhub_id,
        }
        if src_routed and dst_routed:
            routed_props["routed_via_src"] = eff_src
            routed_props["routed_via_dst"] = eff_dst
        edge = backend.upsert_edge(eff_src, "ROUTED_THROUGH", eff_dst, routed_props)
        return edge, True, subhub_id

    def gds_cypher_preview(
        self,
        lens: GraphLens,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> str:
        """Emit valid Neo4j GDS Cypher preview matching neo4j-graph-science."""
        graph_name = "tideflow_hexactine"
        orientation = "UNDIRECTED" if lens in {"communities", "path", "degree_audit"} else "NATURAL"
        project_stmt = (
            f"CALL gds.graph.project('{graph_name}', "
            "['Project', 'Thought', 'ConceptTag', 'Breadcrumb', 'SpiculeHub'], "
            "{ALL_RELS: {type: '*', orientation: '" + orientation + "', "
            "properties: {weight: {defaultValue: 1.0}}}});"
        )
        if lens == "pagerank":
            algo_stmt = (
                f"CALL gds.pageRank.stream('{graph_name}', "
                "{maxIterations: 20, dampingFactor: 0.85, relationshipWeightProperty: 'weight'}) "
                "YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).id AS id, score ORDER BY score DESC;"
            )
        elif lens == "communities":
            algo_stmt = (
                f"CALL gds.leiden.stream('{graph_name}', "
                "{gamma: 1.0, theta: 0.05, consecutiveIds: true}) "
                "YIELD nodeId, communityId "
                "RETURN gds.util.asNode(nodeId).id AS id, communityId ORDER BY communityId ASC;"
            )
        elif lens == "path":
            src = _escape_cypher_str(source_id or "<source_id>")
            dst = _escape_cypher_str(target_id or "<target_id>")
            algo_stmt = (
                f"MATCH (s:TideNode {{id: '{src}'}}), (t:TideNode {{id: '{dst}'}}) "
                f"CALL gds.shortestPath.dijkstra.stream('{graph_name}', "
                "{sourceNode: s, targetNode: t, relationshipWeightProperty: 'weight'}) "
                "YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs "
                "RETURN totalCost, [nid IN nodeIds | gds.util.asNode(nid).id] AS path;"
            )
        else:
            algo_stmt = (
                f"CALL gds.degree.stream('{graph_name}', {{orientation: 'UNDIRECTED'}}) "
                "YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).id AS id, toInteger(score) AS degree "
                "ORDER BY degree DESC;"
            )
        drop_stmt = f"CALL gds.graph.drop('{graph_name}', false);"
        return "\n".join([project_stmt, algo_stmt, drop_stmt])

    def build_snapshot(
        self,
        backend: GraphBackend,
        lens: GraphLens = "pagerank",
        focus_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        limit: int = 200,
    ) -> GraphSnapshotResponse:
        """Project subgraph and compute deterministic GraphScience metrics."""
        raw_nodes, raw_edges = backend.get_subgraph(focus_id=focus_id, limit=limit)
        raw_pr, norm_pr = self.compute_pagerank(raw_nodes, raw_edges)
        communities, modularity = self.compute_communities(raw_nodes, raw_edges)
        degrees, violations, max_observed, sub_hub_count = self.audit_degrees(
            raw_nodes, raw_edges
        )

        active_path: ShortestPathResult | None = None
        path_node_set: set[str] = set()
        path_edge_set: set[str] = set()

        resolved_source = source_id or focus_id
        resolved_target = target_id
        if lens == "path" and resolved_source:
            if not resolved_target:
                project_candidates = [
                    n["id"]
                    for n in raw_nodes
                    if "Project" in (n.get("labels") or []) and n["id"] != resolved_source
                ]
                if project_candidates:
                    project_candidates.sort(
                        key=lambda nid: (-raw_pr.get(nid, 0.0), nid)
                    )
                    resolved_target = project_candidates[0]
            if resolved_target:
                active_path = self.compute_shortest_path(
                    raw_nodes, raw_edges, resolved_source, resolved_target
                )
                if active_path.found:
                    path_node_set = set(active_path.node_ids)
                    path_edge_set = {e.id for e in active_path.edges}

        node_views: list[GraphNodeView] = []
        for node in sorted(raw_nodes, key=lambda n: n["id"]):
            nid = node["id"]
            labels = list(node.get("labels") or ["Node"])
            props = dict(node.get("properties") or {})
            deg = degrees.get(nid, 0)
            is_capped = any(lbl in CAPPED_STRUCTURAL_LABELS for lbl in labels)
            node_views.append(
                GraphNodeView(
                    id=nid,
                    labels=labels,
                    label=labels[0],
                    title=_node_title(node),
                    status=str(props["status"]) if props.get("status") else None,
                    kind=str(props["kind"]) if props.get("kind") else None,
                    degree=deg,
                    pagerank=raw_pr.get(nid, 0.0),
                    normalized_pagerank=norm_pr.get(nid, 0.0),
                    community_id=communities.get(nid, 0),
                    hexactine_compliant=(
                        deg <= self.degree_invariant_max if is_capped else True
                    ),
                    in_active_path=(nid in path_node_set),
                    properties=props,
                )
            )

        edge_views = [
            GraphEdgeView(
                id=edge["id"],
                source=edge["source"],
                target=edge["target"],
                rel_type=edge["rel_type"],
                weight=_safe_edge_weight(edge, default=1.0),
                routed_via_subhub=bool(
                    (edge.get("properties") or {}).get("routed_via_subhub", False)
                ),
                in_active_path=(edge["id"] in path_edge_set),
                properties=dict(edge.get("properties") or {}),
            )
            for edge in sorted(
                raw_edges, key=lambda e: (e["source"], e["rel_type"], e["target"])
            )
        ]

        top_pagerank_ids = [
            nid
            for nid, _ in sorted(
                raw_pr.items(), key=lambda kv: (-kv[1], kv[0])
            )[:5]
        ]

        metrics = GraphScienceMetrics(
            node_count=len(node_views),
            edge_count=len(edge_views),
            community_count=len(set(communities.values())) if communities else 0,
            modularity=modularity,
            max_degree_allowed=self.degree_invariant_max,
            max_observed_degree=max_observed,
            sub_hub_count=sub_hub_count,
            degree_violations=violations,
            invariant_ok=(len(violations) == 0),
            top_pagerank_ids=top_pagerank_ids,
        )

        return GraphSnapshotResponse(
            lens=lens,
            focus_id=focus_id,
            nodes=node_views,
            edges=edge_views,
            metrics=metrics,
            active_path=active_path,
            gds_cypher_preview=self.gds_cypher_preview(
                lens, source_id=resolved_source, target_id=resolved_target
            ),
        )

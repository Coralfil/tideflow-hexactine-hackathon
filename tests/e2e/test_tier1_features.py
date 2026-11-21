from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.e2e.conftest import (
    CAPABILITY_KEYS,
    EM_DASH,
    assert_health_contract,
    assert_no_server_errors,
    assert_permissions_contract,
    assert_triage_contract,
    assert_zero_em_dashes,
    extract_audit_verdict,
    extract_edges,
    extract_id,
    find_slop_matches,
    require_workspace_artifact,
    unwrap_list,
    unwrap_thought,
)


def _create_project(api_client: httpx.Client, name: str, description: str = "E2E test project") -> dict[str, Any]:
    resp = api_client.post("/api/v1/projects", json={"name": name, "description": description})
    assert resp.status_code in {200, 201}, f"POST /projects failed: {resp.status_code} {resp.text}"
    data = resp.json()
    extract_id(data)
    return data


def _capture_thought(
    api_client: httpx.Client,
    text: str,
    *,
    kind: str = "project_task",
    project_id: str | None = None,
    energy_cost: int = 3,
    auto_park: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text, "kind": kind, "energy_cost": energy_cost, "auto_park": auto_park}
    if project_id is not None:
        payload["project_id"] = project_id
    resp = api_client.post("/api/v1/thoughts/capture", json=payload)
    assert resp.status_code in {200, 201}, f"POST /thoughts/capture failed: {resp.status_code} {resp.text}"
    data = resp.json()
    extract_id(data)
    return data


def _edge_touches(edge: dict[str, Any], node_id: str) -> bool:
    return (
        edge.get("source") == node_id
        or edge.get("target") == node_id
        or edge.get("src_id") == node_id
        or edge.get("dst_id") == node_id
        or edge.get("from") == node_id
        or edge.get("to") == node_id
    )


def _edge_type(edge: dict[str, Any]) -> str:
    return str(edge.get("rel_type") or edge.get("type") or edge.get("label") or "").upper()


def _parse_css_number(raw: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", raw or "")
    assert match, f"Expected numeric CSS token value, got: {raw!r}"
    return float(match.group(0))


# ==============================================================================
# F6: Dual-Mode Graph Backend (6 tests)
# ==============================================================================


def test_f06_health_endpoint_contract(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert_health_contract(resp.json())


def test_f06_project_create_and_list_roundtrip(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    project_name = f"Project {unique_slug}"
    created = _create_project(api_client, project_name)
    created_id = extract_id(created)
    list_resp = api_client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    projects = unwrap_list(list_resp.json(), "projects")
    assert any(extract_id(p) == created_id and p.get("name") == project_name for p in projects)


def test_f06_created_project_visible_in_graph_snapshot(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    created = _create_project(api_client, f"GraphNode {unique_slug}")
    created_id = extract_id(created)
    snap_resp = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200})
    assert snap_resp.status_code == 200
    nodes = unwrap_list(snap_resp.json(), "nodes")
    assert any(extract_id(n) == created_id for n in nodes), f"Project {created_id} missing from graph snapshot"


def test_f06_relate_database_file_and_cli_healthy(workspace_root: Path) -> None:
    db_path = workspace_root / "data" / "tideflow_memory.rl"
    assert db_path.exists() and db_path.stat().st_size > 0
    relate_bin = shutil.which("relate") or shutil.which("relate.exe")
    assert relate_bin, "relate CLI executable not found on PATH"
    proc = subprocess.run(
        [relate_bin, "info", "--database", str(db_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"relate info failed: {proc.stderr}"
    assert "format version" in proc.stdout.lower()


def test_f06_mcp_config_enforces_read_only(workspace_root: Path) -> None:
    mcp_path = workspace_root / ".mcp.json"
    assert mcp_path.exists()
    config = json.loads(mcp_path.read_text(encoding="utf-8"))
    server = config["mcpServers"]["tideflow-memory"]
    assert server["command"] == "relate"
    assert "--read-only" in server["args"]


def test_f06_fallback_operates_when_neo4j_offline(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    health = api_client.get("/api/v1/health").json()
    assert_health_contract(health)
    if health["neo4j_available"] is False:
        assert health["backend_mode"].lower() in {"relate", "inprocess", "memory"}
    created = _create_project(api_client, f"Fallback {unique_slug}")
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank"})
    assert snap.status_code == 200
    nodes = unwrap_list(snap.json(), "nodes")
    assert any(extract_id(n) == extract_id(created) for n in nodes)


# ==============================================================================
# F7: Graph Science & Hexactine Invariant (6 tests)
# ==============================================================================


def test_f07_snapshot_pagerank_lens_returns_deterministic_scores(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"PR {unique_slug}")
    _capture_thought(api_client, f"Rank node {unique_slug}", project_id=extract_id(proj))
    r1 = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "focus_id": extract_id(proj)})
    r2 = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "focus_id": extract_id(proj)})
    assert r1.status_code == 200 and r2.status_code == 200
    s1 = {extract_id(n): n.get("pagerank", n.get("score")) for n in unwrap_list(r1.json(), "nodes")}
    s2 = {extract_id(n): n.get("pagerank", n.get("score")) for n in unwrap_list(r2.json(), "nodes")}
    assert s1 == s2
    assert any(isinstance(v, (int, float)) for v in s1.values())


def test_f07_snapshot_communities_lens_assigns_clusters(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"Comm {unique_slug}")
    _capture_thought(api_client, f"Cluster thought {unique_slug} #graph", project_id=extract_id(proj))
    resp = api_client.get("/api/v1/graph/snapshot", params={"lens": "communities"})
    assert resp.status_code == 200
    nodes = unwrap_list(resp.json(), "nodes")
    assert nodes
    assert any(
        n.get("community") is not None or n.get("community_id") is not None or n.get("cluster") is not None
        for n in nodes
    )


def test_f07_snapshot_degree_audit_lens_reports_hexactine_compliance(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    resp = api_client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit"})
    assert resp.status_code == 200
    body = resp.json()
    nodes = unwrap_list(body, "nodes")
    assert nodes
    for node in nodes:
        labels = [str(x).lower() for x in (node.get("labels") or [node.get("label", "")])]
        if "project" in labels or "spiculehub" in labels:
            deg = node.get("structural_degree", node.get("degree"))
            if isinstance(deg, (int, float)):
                assert deg <= 6, f"Node {extract_id(node)} violated deg <= 6: {deg}"


def test_f07_shortest_path_between_linked_nodes(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"PathProj {unique_slug}")
    thought = _capture_thought(api_client, f"Path thought {unique_slug}", project_id=extract_id(proj))
    resp = api_client.get(
        "/api/v1/graph/path",
        params={"source_id": extract_id(proj), "target_id": extract_id(thought)},
    )
    assert resp.status_code == 200
    body = resp.json()
    path_nodes = body.get("path") or body.get("nodes") or body.get("node_ids")
    assert isinstance(path_nodes, list) and len(path_nodes) >= 2


def test_f07_hexactine_degree_cap_routes_overflow_via_concept_tags(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"HexCap {unique_slug}")
    pid = extract_id(proj)
    captured_bodies = []
    for idx in range(8):
        captured_bodies.append(
            _capture_thought(
                api_client,
                f"Overflow idea {idx} {unique_slug} #tag{idx}",
                kind="spark_idea",
                project_id=pid,
            )
        )
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid, "limit": 200})
    assert snap.status_code == 200
    data = snap.json()
    nodes = unwrap_list(data, "nodes")
    edges = extract_edges(data)
    direct_structural = [e for e in edges if _edge_touches(e, pid)]
    # Primary structural links attached directly to :Project must remain in [1, 6].
    assert 1 <= len(direct_structural) <= 6, (
        f"Project {pid} has {len(direct_structural)} direct structural edges (expected 1..6)"
    )
    overflow_nodes = [
        n
        for n in nodes
        if any(str(lbl) in {"ConceptTag", "SpiculeHub"} for lbl in (n.get("labels") or [n.get("label")]))
    ]
    routed_edges = [
        e
        for e in edges
        if e.get("routed_via_subhub") is True
        or _edge_type(e) in {"ROUTED_THROUGH", "SUB_HUB", "TAGGED_WITH"}
    ]
    assert overflow_nodes and (
        routed_edges or any(b.get("routed_via_subhub") is True for b in captured_bodies)
    ), f"Expected :ConceptTag or :SpiculeHub overflow routing for 8 thoughts under {pid}"


def test_f07_snapshot_includes_gds_cypher_preview(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    for lens in ("pagerank", "communities", "degree_audit"):
        resp = api_client.get("/api/v1/graph/snapshot", params={"lens": lens})
        assert resp.status_code == 200
        body = resp.json()
        cypher = (
            body.get("gds_cypher_preview")
            or body.get("cypher_preview")
            or body.get("gds_cypher")
            or body.get("cypher")
            or ""
        )
        assert isinstance(cypher, str) and "gds." in cypher, f"Missing gds. Cypher preview for lens={lens}: {body}"


# ==============================================================================
# F8: ADD Thought/Idea/Side-Quest Capture & Linking (6 tests)
# ==============================================================================


def test_f08_capture_each_thought_kind(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    for kind in ("spark_idea", "project_task", "side_quest", "blocker"):
        body = _capture_thought(api_client, f"Kind {kind} {unique_slug}", kind=kind, energy_cost=2)
        thought = unwrap_thought(body)
        assert thought["kind"] == kind
        assert unique_slug in thought["text"]


def test_f08_capture_extracts_auto_tags_and_links_concept(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"TagProj {unique_slug}")
    body = _capture_thought(
        api_client,
        f"Explore #biolum shaders and #houdini cadence {unique_slug}",
        kind="spark_idea",
        project_id=extract_id(proj),
    )
    thought = unwrap_thought(body)
    tags = (
        body.get("linked_tags")
        or thought.get("concept_tags")
        or thought.get("tags")
        or thought.get("concepts")
        or []
    )
    assert any("biolum" in str(t).lower() or "houdini" in str(t).lower() for t in tags)
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200}).json()
    edges = extract_edges(snap)
    assert any(_edge_touches(e, extract_id(thought)) for e in edges)


def test_f08_capture_with_auto_park_starts_parked(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    body = _capture_thought(
        api_client, f"Auto park quest {unique_slug}", kind="side_quest", auto_park=True
    )
    thought = unwrap_thought(body)
    status = str(thought.get("status") or thought.get("slot") or "").lower()
    assert thought.get("parked") is True or "park" in status


def test_f08_park_thought_moves_to_guilt_free_parking_lot(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    captured = _capture_thought(api_client, f"Parkable {unique_slug}", kind="side_quest", auto_park=False)
    tid = extract_id(captured)
    resp = api_client.post(f"/api/v1/thoughts/{tid}/park")
    assert resp.status_code == 200
    thought = unwrap_thought(resp.json())
    status = str(thought.get("status") or thought.get("slot") or "").lower()
    assert thought.get("parked") is True or "park" in status


def test_f08_promote_parked_thought_restores_active_state(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    captured = _capture_thought(api_client, f"Promote me {unique_slug}", kind="project_task", auto_park=True)
    tid = extract_id(captured)
    resp = api_client.post(f"/api/v1/thoughts/{tid}/promote")
    assert resp.status_code == 200
    thought = unwrap_thought(resp.json())
    status = str(thought.get("status") or thought.get("slot") or "").strip().lower()
    assert status in {"active", "now", "next", "captured"}, f"Unexpected promoted status: {thought}"
    assert "park" not in status


def test_f08_capture_links_to_target_project(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"LinkTarget {unique_slug}")
    pid = extract_id(proj)
    thought = _capture_thought(api_client, f"Linked task {unique_slug}", project_id=pid)
    tid = extract_id(thought)
    path_resp = api_client.get("/api/v1/graph/path", params={"source_id": pid, "target_id": tid})
    assert path_resp.status_code == 200
    path_nodes = path_resp.json().get("path") or path_resp.json().get("nodes") or path_resp.json().get("node_ids")
    assert isinstance(path_nodes, list) and len(path_nodes) >= 2


# ==============================================================================
# F9: Momentum Recovery & 3-Slot Focus Horizon (6 tests)
# ==============================================================================


def test_f09_create_breadcrumb_snapshot(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"BreadProj {unique_slug}")
    pid = extract_id(proj)
    resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Wired endpoint {unique_slug}", "next_micro_step": "Run pytest"},
    )
    assert resp.status_code in {200, 201}
    body = resp.json()
    extract_id(body)
    assert body.get("project_id") == pid


def test_f09_second_breadcrumb_supersedes_first_bitemporally(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"SuperProj {unique_slug}")
    pid = extract_id(proj)
    b1_resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Step 1 {unique_slug}", "next_micro_step": "Step 2"},
    )
    assert b1_resp.status_code in {200, 201}, b1_resp.text
    b2_resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Step 2 {unique_slug}", "next_micro_step": "Step 3"},
    )
    assert b2_resp.status_code in {200, 201}, b2_resp.text
    b1_id = extract_id(b1_resp.json())
    b2_id = extract_id(b2_resp.json())
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200}).json()
    node_ids = {extract_id(n) for n in unwrap_list(snap, "nodes")}
    assert b1_id in node_ids and b2_id in node_ids
    edges = extract_edges(snap)
    assert any(_edge_type(e) == "SUPERSEDES" and _edge_touches(e, b2_id) and _edge_touches(e, b1_id) for e in edges)


def test_f09_momentum_resume_returns_three_line_context_card(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"ResumeProj {unique_slug}")
    pid = extract_id(proj)
    bc_resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Finished parser {unique_slug}", "next_micro_step": "Add assertions"},
    )
    assert bc_resp.status_code in {200, 201}, bc_resp.text
    resp = api_client.get("/api/v1/momentum/resume", params={"project_id": pid})
    assert resp.status_code == 200
    data = resp.json()
    lines = (data.get("resume_card") or {}).get("card_lines") or data.get("lines")
    assert isinstance(lines, list) and 1 <= len(lines) <= 3, f"Expected 1..3 resume card lines: {data}"
    assert any(unique_slug in str(line) for line in lines)


def test_f09_triage_sweep_contract_fields_and_slot_caps(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"SweepProj {unique_slug}")
    _capture_thought(api_client, f"Sweep task {unique_slug}", project_id=extract_id(proj))
    resp = api_client.post("/api/v1/triage/sweep", json={"project_id": extract_id(proj)})
    assert resp.status_code == 200
    assert_triage_contract(resp.json())


def test_f09_triage_sweep_caps_many_active_thoughts(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"CapProj {unique_slug}")
    pid = extract_id(proj)
    for idx in range(6):
        _capture_thought(api_client, f"Active item {idx} {unique_slug}", kind="project_task", project_id=pid)
    resp = api_client.post("/api/v1/triage/sweep", json={"project_id": pid})
    assert resp.status_code == 200
    data = resp.json()
    assert_triage_contract(data)
    assert len(data["now"]) <= 1
    assert len(data["next"]) <= 2


def test_f09_triage_sweep_overwhelm_index_bounded(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"OverwhelmProj {unique_slug}")
    pid = extract_id(proj)
    low = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(low)
    for idx in range(5):
        _capture_thought(api_client, f"Load {idx} {unique_slug}", kind="blocker", project_id=pid, energy_cost=5)
    high = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(high)
    assert float(high["overwhelm_index"]) >= float(low["overwhelm_index"])


# ==============================================================================
# F10: Deterministic Cadence Scheduler (6 tests)
# ==============================================================================


def test_f10_create_and_list_schedule_block(
    api_client: httpx.Client, require_api: dict[str, Any], created_schedule_blocks: list[str], unique_slug: str
) -> None:
    resp = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Deep Tide {unique_slug}",
            "start_iso": "2026-11-25T09:00:00Z",
            "end_iso": "2026-11-25T09:45:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert resp.status_code in {200, 201}
    block = resp.json()
    bid = extract_id(block)
    created_schedule_blocks.append(bid)
    listing = api_client.get("/api/v1/schedule/blocks")
    assert listing.status_code == 200
    blocks = unwrap_list(listing.json(), "blocks")
    assert any(extract_id(b) == bid for b in blocks)


def test_f10_patch_schedule_block_updates_fields(
    api_client: httpx.Client, require_api: dict[str, Any], created_schedule_blocks: list[str], unique_slug: str
) -> None:
    created = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Initial {unique_slug}",
            "start_iso": "2026-11-26T10:00:00Z",
            "end_iso": "2026-11-26T10:30:00Z",
            "cadence_window": "creative_swell",
        },
    ).json()
    bid = extract_id(created)
    created_schedule_blocks.append(bid)
    patch = api_client.patch(
        f"/api/v1/schedule/blocks/{bid}",
        json={"title": f"Updated {unique_slug}", "cadence_window": "shallow_drift"},
    )
    assert patch.status_code == 200
    assert patch.json().get("title") == f"Updated {unique_slug}"


def test_f10_delete_schedule_block_removes_block(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    created = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Temp {unique_slug}",
            "start_iso": "2026-11-27T11:00:00Z",
            "end_iso": "2026-11-27T11:30:00Z",
            "cadence_window": "recovery_ebb",
        },
    ).json()
    bid = extract_id(created)
    delete_resp = api_client.delete(f"/api/v1/schedule/blocks/{bid}")
    assert delete_resp.status_code in {200, 204}
    blocks = unwrap_list(api_client.get("/api/v1/schedule/blocks").json(), "blocks")
    assert not any(extract_id(b) == bid for b in blocks)


def test_f10_overlapping_schedule_block_returns_conflict(
    api_client: httpx.Client, require_api: dict[str, Any], created_schedule_blocks: list[str], unique_slug: str
) -> None:
    first = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Slot A {unique_slug}",
            "start_iso": "2026-11-28T13:00:00Z",
            "end_iso": "2026-11-28T14:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert first.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(first.json()))
    overlap = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Slot B {unique_slug}",
            "start_iso": "2026-11-28T13:30:00Z",
            "end_iso": "2026-11-28T14:30:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert overlap.status_code in {409, 400, 422}


def test_f10_schedule_prompts_deterministic_for_fixed_clock(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    params = {"now_iso": "2026-11-19T09:15:00Z", "energy": 3, "minutes": 25}
    r1 = api_client.get("/api/v1/schedule/prompts", params=params)
    r2 = api_client.get("/api/v1/schedule/prompts", params=params)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_f10_schedule_prompts_surface_four_cadence_windows(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    cadences = set()
    for hour in ("09:00:00Z", "14:00:00Z", "19:00:00Z", "23:30:00Z"):
        resp = api_client.get(
            "/api/v1/schedule/prompts",
            params={"now_iso": f"2026-11-19T{hour}", "energy": 3, "minutes": 25},
        )
        assert resp.status_code == 200
        body = resp.json()
        cadence = body.get("active_cadence") or body.get("cadence_window") or body.get("cadence")
        assert isinstance(cadence, str) and cadence.strip()
        cadences.add(cadence)
    assert len(cadences) >= 3, f"Expected distinct tidal windows across 24h, got: {cadences}"


# ==============================================================================
# F11: Permission-Gated Nemoclaw Retriever (6 tests)
# ==============================================================================


def test_f11_permissions_default_all_false(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    resp = api_client.get("/api/v1/retriever/permissions")
    assert resp.status_code == 200
    data = resp.json()
    assert_permissions_contract(data)
    for cap in CAPABILITY_KEYS:
        assert data[cap] is False


def test_f11_execute_denied_403_when_capability_disabled(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert resp.status_code == 403


def test_f11_denied_execution_records_denied_audit_entry(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    audit_resp = api_client.get("/api/v1/retriever/audit")
    assert audit_resp.status_code == 200
    entries = unwrap_list(audit_resp.json(), "audit", "entries")
    assert any(extract_audit_verdict(e) == "DENIED" for e in entries)


def test_f11_put_permissions_toggles_capability_on(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    put_resp = api_client.put(
        "/api/v1/retriever/permissions",
        json={"local_fs_read": True, "repo_git_scan": False, "web_fetch_public": False, "local_llm_ollama": False},
    )
    assert put_resp.status_code == 200
    get_resp = api_client.get("/api/v1/retriever/permissions")
    assert get_resp.status_code == 200
    assert get_resp.json()["local_fs_read"] is True


def test_f11_execute_allowed_workspace_read_returns_200_and_audit(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    exec_resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert exec_resp.status_code == 200
    body = exec_resp.json()
    assert "TideFlow" in json.dumps(body)
    audit_entries = unwrap_list(api_client.get("/api/v1/retriever/audit").json(), "audit", "entries")
    assert any(extract_audit_verdict(e) == "ALLOWED" for e in audit_entries)


def test_f11_allowed_execution_creates_retrieval_artifact_node(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    exec_resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert exec_resp.status_code == 200
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200}).json()
    nodes = unwrap_list(snap, "nodes")
    assert any(
        "retrieval" in str(n.get("label") or n.get("labels") or n.get("kind") or "").lower()
        for n in nodes
    )


# ==============================================================================
# F12: Rook & KaneCLI Closed-Loop Hooks (6 tests)
# ==============================================================================


def test_f12_rook_directory_has_profile_and_mjs_hooks() -> None:
    rook_dir = require_workspace_artifact(".testmuai/rook", "M3")
    yamls = list(rook_dir.rglob("*.yaml")) + list(rook_dir.rglob("*.yml"))
    hooks = list(rook_dir.rglob("*.mjs"))
    assert yamls, "Expected at least one Rook profile YAML under .testmuai/rook/"
    assert hooks, "Expected at least one Rook lifecycle hook .mjs under .testmuai/rook/"


def test_f12_rook_hooks_declare_five_lifecycle_stages() -> None:
    rook_dir = require_workspace_artifact(".testmuai/rook", "M3")
    hooks = list(rook_dir.rglob("*.mjs"))
    assert hooks, "No .mjs hook files found under .testmuai/rook/"
    combined = "\n".join(h.read_text(encoding="utf-8") for h in hooks)
    for stage in ("prepare", "open", "execute", "close", "collect"):
        assert stage in combined, f"Missing Rook lifecycle stage '{stage}' in .testmuai/rook/*.mjs"


def test_f12_powershell_scripts_exist_with_semicolon_only() -> None:
    for rel in ("scripts/dev.ps1", "scripts/verify_all.ps1", "scripts/kane_loop.ps1"):
        script = require_workspace_artifact(rel, "M3/M4")
        content = script.read_text(encoding="utf-8")
        assert "&&" not in content, f"Forbidden '&&' found in {rel}"
        assert_zero_em_dashes(content, rel)


def test_f12_kane_loop_script_enforces_agent_ndjson_flag() -> None:
    script = require_workspace_artifact("scripts/kane_loop.ps1", "M3")
    content = script.read_text(encoding="utf-8")
    assert "--agent" in content
    assert "KANE_CLI_USER_AGENT" in content


def test_f12_kane_cli_version_and_config_show() -> None:
    kane_bin = shutil.which("kane-cli.cmd") or shutil.which("kane-cli")
    assert kane_bin, "kane-cli.cmd not found on PATH"
    ver = subprocess.run([kane_bin, "--version"], capture_output=True, text=True, timeout=20)
    assert ver.returncode == 0, ver.stderr
    cfg = subprocess.run([kane_bin, "config", "show"], capture_output=True, text=True, timeout=20)
    assert cfg.returncode == 0, cfg.stderr
    parsed = json.loads(cfg.stdout)
    assert parsed.get("mode") == "testing"


def test_f12_rook_doctor_json_healthy() -> None:
    rook_bin = shutil.which("rook.cmd") or shutil.which("rook")
    assert rook_bin, "rook.cmd not found on PATH"
    env = os.environ.copy()
    env["ROOK_ENV"] = "prod"
    proc = subprocess.run([rook_bin, "doctor", "--json"], capture_output=True, text=True, env=env, timeout=25)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report.get("environment") == "prod"
    assert report.get("api", {}).get("status") == "reachable"


# ==============================================================================
# F13: CSS Houdini Rhythm Layer (6 tests)
# ==============================================================================


def test_f13_rhythm_lattice_worklet_served(require_ui: str) -> None:
    resp = httpx.get(f"{require_ui}/worklets/rhythm-lattice-paint.js", timeout=5.0)
    assert resp.status_code == 200
    assert "registerPaint" in resp.text


def test_f13_biolum_pulse_worklet_served(require_ui: str) -> None:
    resp = httpx.get(f"{require_ui}/worklets/biolum-pulse-paint.js", timeout=5.0)
    assert resp.status_code == 200
    assert "registerPaint" in resp.text


def test_f13_houdini_tokens_initial_values_in_dom(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    h = res["houdini"]
    assert _parse_css_number(h["rhythm_bpm"]) == pytest.approx(68.0, abs=10.0)
    assert 0.0 <= _parse_css_number(h["overwhelm_index"]) <= 1.0
    assert "%" in h["focus_depth"]
    assert h["cadence_color"], "Expected non-empty --cadence-color"
    assert "deg" in h["lattice_phase"]


def test_f13_houdini_register_property_or_css_tokens_active(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    h = res["houdini"]
    assert h["has_register_property"] is True
    for key in ("rhythm_bpm", "overwhelm_index", "focus_depth", "cadence_color", "lattice_phase"):
        assert h[key], f"CSS Houdini token {key} resolved to empty string"


def test_f13_rhythm_dial_interaction_updates_bpm_token(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "inspect_houdini"},
            {
                "type": "set_input_value",
                "selectors": [
                    "input[type='range'][aria-label*='energy' i]",
                    "input[type='range'][aria-label*='bpm' i]",
                    "input[type='range'][aria-label*='rhythm' i]",
                    "input[type='range']",
                ],
                "value": "5",
            },
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    bpm_before = _parse_css_number(res["stepResults"][0]["value"]["rhythm_bpm"])
    bpm_after = _parse_css_number(res["houdini"]["rhythm_bpm"])
    assert 30.0 <= bpm_before <= 220.0
    assert 30.0 <= bpm_after <= 220.0
    assert bpm_after != bpm_before, f"Expected --rhythm-bpm to change after dial input, stayed {bpm_after}"


def test_f13_worklet_fallback_renders_without_console_errors(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    assert res["dom"]["rootChildCount"] >= 1
    assert len(res["dom"]["innerText"].strip()) > 20


# ==============================================================================
# F14: Interactive neo4j-graph-science & Rhythm UI (6 tests)
# ==============================================================================


def test_f14_cockpit_loads_cleanly(browser_runner) -> None:
    res = browser_runner()
    assert res["statusCode"] == 200
    assert_no_server_errors(res)
    assert res["dom"]["rootChildCount"] >= 1


def test_f14_cmd_k_opens_brain_dump_and_captures_thought(browser_runner, unique_slug: str) -> None:
    thought_text = f"UI capture {unique_slug}"
    res = browser_runner(
        actions=[
            {"type": "press", "key": "Control+k"},
            {"type": "wait_ms", "ms": 200},
            {
                "type": "fill_first",
                "selectors": [
                    "[role='dialog'] textarea",
                    "[role='dialog'] input[type='text']",
                    "textarea",
                    "input[placeholder*='thought' i]",
                    "input[placeholder*='idea' i]",
                ],
                "value": thought_text,
            },
            {"type": "click_text", "patterns": ["Capture Thought", "Capture", "Submit"]},
            {"type": "wait_ms", "ms": 500},
        ]
    )
    assert_no_server_errors(res)
    capture_calls = [r for r in res["responses"] if "/api/v1/thoughts/capture" in r["url"] and r["method"] == "POST"]
    assert capture_calls and capture_calls[-1]["status"] in {200, 201}


def test_f14_three_slot_focus_horizon_renders_now_next_parked(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    text = res["dom"]["innerText"].lower()
    assert "now" in text
    assert "next" in text
    assert "parked" in text


def test_f14_graph_canvas_renders_nodes_and_lens_switcher(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["Communities"]},
            {"type": "wait_ms", "ms": 250},
            {"type": "click_text", "patterns": ["Degree Audit"]},
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    assert res["dom"]["svgCount"] + res["dom"]["canvasCount"] >= 1
    snap_calls = [r for r in res["responses"] if "/api/v1/graph/snapshot" in r["url"]]
    assert len(snap_calls) >= 2 and all(r["status"] == 200 for r in snap_calls)
    assert "gds." in res["dom"]["innerText"]


def test_f14_cadence_scheduler_and_rhythm_dial_interactive(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["Refresh Prompts", "Prompts", "creative_swell", "deep_tide"]},
            {"type": "wait_ms", "ms": 300},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    text = res["dom"]["innerText"].lower()
    assert any(k in text for k in ("cadence", "rhythm", "schedule", "tide"))


def test_f14_nemoclaw_console_renders_toggles_and_audit_log(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    text = res["dom"]["innerText"].lower()
    assert "local_fs_read" in text or "nemoclaw" in text
    assert "audit" in text


# ==============================================================================
# F15: Public Copy unslop Pass (6 tests)
# ==============================================================================


def test_f15_readme_contains_zero_em_dashes(workspace_root: Path) -> None:
    readme = workspace_root / "README.md"
    assert readme.exists()
    assert_zero_em_dashes(readme.read_text(encoding="utf-8"), "README.md")


def test_f15_readme_passes_unslop_word_check(workspace_root: Path) -> None:
    readme = workspace_root / "README.md"
    hits = find_slop_matches(readme.read_text(encoding="utf-8"))
    assert not hits, f"Banned slop words in README.md: {hits}"


def test_f15_compliance_checklist_clean_if_present(workspace_root: Path) -> None:
    for rel in ("README.md", "AGENTS.md", "requirements/tideflow_prd.md", "docs/testing/TEST_INFRA.md"):
        p = workspace_root / rel
        if p.exists():
            assert_zero_em_dashes(p.read_text(encoding="utf-8"), rel)
    checklist = workspace_root / "COMPLIANCE_CHECKLIST.md"
    if checklist.exists():
        content = checklist.read_text(encoding="utf-8")
        assert_zero_em_dashes(content, "COMPLIANCE_CHECKLIST.md")
        assert not find_slop_matches(content)


def test_f15_ui_rendered_copy_contains_zero_em_dashes(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    assert EM_DASH not in res["dom"]["innerText"], "Found U+2014 em dash in rendered UI text"


def test_f15_ui_rendered_copy_passes_unslop_word_check(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    hits = find_slop_matches(res["dom"]["innerText"])
    assert not hits, f"Banned slop words in rendered UI: {hits}"


def test_f15_api_recommendation_copy_contains_zero_em_dashes(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    triage = api_client.post("/api/v1/triage/sweep", json={})
    assert triage.status_code == 200
    assert_zero_em_dashes(json.dumps(triage.json(), ensure_ascii=False), "/api/v1/triage/sweep")
    prompts = api_client.get(
        "/api/v1/schedule/prompts",
        params={"now_iso": "2026-11-19T09:00:00Z", "energy": 3, "minutes": 25},
    )
    assert prompts.status_code == 200
    assert_zero_em_dashes(json.dumps(prompts.json(), ensure_ascii=False), "/api/v1/schedule/prompts")

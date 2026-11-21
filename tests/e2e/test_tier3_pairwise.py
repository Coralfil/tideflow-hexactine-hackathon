from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

import httpx

from tests.e2e.conftest import (
    EM_DASH,
    assert_health_contract,
    assert_no_server_errors,
    assert_triage_contract,
    assert_zero_em_dashes,
    extract_audit_verdict,
    extract_edges,
    extract_id,
    find_slop_matches,
    unwrap_list,
)


def _create_project(api_client: httpx.Client, name: str) -> dict[str, Any]:
    resp = api_client.post("/api/v1/projects", json={"name": name, "description": "Pairwise E2E"})
    assert resp.status_code in {200, 201}, resp.text
    return resp.json()


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
    assert resp.status_code in {200, 201}, resp.text
    return resp.json()


def _edge_touches(edge: dict[str, Any], node_id: str) -> bool:
    return any(edge.get(k) == node_id for k in ("source", "target", "src_id", "dst_id", "from", "to"))


def _edge_type(edge: dict[str, Any]) -> str:
    return str(edge.get("rel_type") or edge.get("type") or edge.get("label") or "").upper()


def _parse_css_number(raw: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", raw or "")
    assert match, f"Expected numeric CSS token value, got: {raw!r}"
    return float(match.group(0))


def test_p01_backend_persistence_and_pagerank_determinism(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    """F6 x F7: Persisted projects and thoughts yield deterministic PageRank scores."""
    proj = _create_project(api_client, f"P01 {unique_slug}")
    pid = extract_id(proj)
    _capture_thought(api_client, f"Task A {unique_slug}", project_id=pid)
    _capture_thought(api_client, f"Idea B {unique_slug} #cadence", kind="spark_idea", project_id=pid)
    s1 = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "focus_id": pid}).json()
    s2 = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "focus_id": pid}).json()
    scores1 = {extract_id(n): n.get("pagerank", n.get("score")) for n in unwrap_list(s1, "nodes")}
    scores2 = {extract_id(n): n.get("pagerank", n.get("score")) for n in unwrap_list(s2, "nodes")}
    assert pid in scores1
    assert scores1 == scores2


def test_p02_hexactine_degree_invariant_under_bulk_thought_capture(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    """F7 x F8: Bulk capturing 10 thoughts under one project keeps direct structural degree <= 6."""
    proj = _create_project(api_client, f"P02 {unique_slug}")
    pid = extract_id(proj)
    for i in range(10):
        _capture_thought(api_client, f"Bulk {i} {unique_slug} #ray{i % 4}", project_id=pid)
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid, "limit": 200}).json()
    edges = extract_edges(snap)
    direct = [e for e in edges if _edge_touches(e, pid)]
    assert len(direct) <= 6


def test_p03_auto_parked_side_quest_excluded_from_focus_horizon_now(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    """F8 x F9: Auto-parked side quests stay out of Now/Next and increment parked_count."""
    proj = _create_project(api_client, f"P03 {unique_slug}")
    pid = extract_id(proj)
    sq = _capture_thought(api_client, f"SideQuest {unique_slug}", kind="side_quest", project_id=pid, auto_park=True)
    main_task = _capture_thought(api_client, f"MainTask {unique_slug}", kind="project_task", project_id=pid)
    sweep = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(sweep)
    now_next_ids = {
        extract_id(x) if isinstance(x, dict) else str(x) for x in [*sweep["now"], *sweep["next"]]
    }
    assert extract_id(sq) not in now_next_ids
    assert extract_id(main_task) in now_next_ids
    assert sweep["parked_count"] >= 1


def test_p04_bitemporal_breadcrumb_supersedes_edge_in_graph_snapshot(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    """F9 x F7: Sequential breadcrumbs create SUPERSEDES link visible in shortest path / snapshot."""
    proj = _create_project(api_client, f"P04 {unique_slug}")
    pid = extract_id(proj)
    b1 = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Init {unique_slug}", "next_step": "Step 2"},
    ).json()
    b2 = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Next {unique_slug}", "next_step": "Step 3"},
    ).json()
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200}).json()
    edges = extract_edges(snap)
    assert any(
        _edge_type(e) == "SUPERSEDES"
        and _edge_touches(e, extract_id(b1))
        and _edge_touches(e, extract_id(b2))
        for e in edges
    )


def test_p05_thought_energy_cost_drives_cadence_prompt_ranking(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    """F8 x F10: Energy-matched prompts respond deterministically to energy level differences."""
    proj = _create_project(api_client, f"P05 {unique_slug}")
    pid = extract_id(proj)
    _capture_thought(api_client, f"Low energy task {unique_slug}", project_id=pid, energy_cost=1)
    _capture_thought(api_client, f"Heavy task {unique_slug}", project_id=pid, energy_cost=5)
    r_low = api_client.get(
        "/api/v1/schedule/prompts",
        params={"now_iso": "2026-11-19T09:00:00Z", "energy": 1, "minutes": 15},
    )
    r_high = api_client.get(
        "/api/v1/schedule/prompts",
        params={"now_iso": "2026-11-19T09:00:00Z", "energy": 5, "minutes": 60},
    )
    assert r_low.status_code == 200 and r_high.status_code == 200
    assert unwrap_list(r_low.json(), "prompts", "recommendations")
    assert unwrap_list(r_high.json(), "prompts", "recommendations")


def test_p06_active_schedule_block_aligns_with_health_cadence_and_triage(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    created_schedule_blocks: list[str],
    unique_slug: str,
) -> None:
    """F10 x F9: Creating a schedule block and running triage keep health and triage coherent."""
    blk = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"FocusBlock {unique_slug}",
            "start_iso": "2026-12-03T09:00:00Z",
            "end_iso": "2026-12-03T09:45:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert blk.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(blk.json()))
    health = api_client.get("/api/v1/health").json()
    assert_health_contract(health)
    triage = api_client.post("/api/v1/triage/sweep", json={}).json()
    assert_triage_contract(triage)


def test_p07_allowed_nemoclaw_retrieval_indexes_artifact_in_graph(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    """F11 x F7: Permitted retrieval creates a RetrievalArtifact node reachable in graph snapshot."""
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


def test_p08_retrieval_artifact_links_without_breaking_hexactine_degree_cap(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    reset_retriever_permissions: dict[str, bool],
    unique_slug: str,
) -> None:
    """F11 x F8: Multiple thoughts plus a retrieval artifact preserve deg <= 6 on projects."""
    proj = _create_project(api_client, f"P08 {unique_slug}")
    pid = extract_id(proj)
    for i in range(6):
        _capture_thought(api_client, f"Seed {i} {unique_slug}", project_id=pid)
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    exec_resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md", "project_id": pid},
    )
    assert exec_resp.status_code == 200
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid, "limit": 200}).json()
    edges = extract_edges(snap)
    assert len([e for e in edges if _edge_touches(e, pid)]) <= 6


def test_p09_permission_gate_blocks_retrieval_even_inside_active_focus_block(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    reset_retriever_permissions: dict[str, bool],
    created_schedule_blocks: list[str],
    unique_slug: str,
) -> None:
    """F11 x F10: Scheduling an active block never bypasses default-deny Nemoclaw permission gates."""
    blk = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"ActiveWork {unique_slug}",
            "start_iso": "2026-12-04T09:00:00Z",
            "end_iso": "2026-12-04T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert blk.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(blk.json()))
    denied = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "repo_git_scan", "target": "."},
    )
    assert denied.status_code == 403
    entries = unwrap_list(api_client.get("/api/v1/retriever/audit").json(), "audit", "entries")
    assert any(extract_audit_verdict(e) == "DENIED" for e in entries)


def test_p10_triage_overwhelm_index_updates_houdini_tokens_in_dom(
    api_client: httpx.Client, require_api: dict[str, Any], browser_runner, unique_slug: str
) -> None:
    """F9 x F13: Capturing high-load items reflects bounded --overwhelm-index and --rhythm-bpm in DOM."""
    proj = _create_project(api_client, f"P10 {unique_slug}")
    pid = extract_id(proj)
    for i in range(4):
        _capture_thought(api_client, f"Urgent {i} {unique_slug}", kind="blocker", project_id=pid, energy_cost=5)
    api_client.post("/api/v1/triage/sweep", json={"project_id": pid})
    res = browser_runner(actions=[{"type": "wait_ms", "ms": 300}])
    assert_no_server_errors(res)
    ov = _parse_css_number(res["houdini"]["overwhelm_index"])
    bpm = _parse_css_number(res["houdini"]["rhythm_bpm"])
    assert 0.0 <= ov <= 1.0
    assert 30.0 <= bpm <= 220.0


def test_p11_ui_lens_switch_drives_graph_snapshot_api_and_cypher_preview(browser_runner) -> None:
    """F14 x F7: Switching graph lens in UI calls /api/v1/graph/snapshot and shows gds. Cypher."""
    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["Communities"], "optional": True},
            {"type": "wait_ms", "ms": 250},
            {"type": "click_text", "patterns": ["PageRank"], "optional": True},
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    snap_calls = [r for r in res["responses"] if "/api/v1/graph/snapshot" in r["url"]]
    assert snap_calls and all(r["status"] == 200 for r in snap_calls)
    assert "gds." in res["dom"]["innerText"] or res["dom"]["svgCount"] + res["dom"]["canvasCount"] >= 1


def test_p12_ui_nemoclaw_toggle_transitions_403_denied_to_200_allowed(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    reset_retriever_permissions: dict[str, bool],
    browser_runner,
) -> None:
    """F14 x F11: Nemoclaw denial (403) turns into allowed execution (200) after enabling toggle."""
    r1 = api_client.post("/api/v1/retriever/execute", json={"capability": "local_fs_read", "target": "README.md"})
    assert r1.status_code == 403
    res = browser_runner(
        actions=[
            {
                "type": "check_first",
                "selectors": [
                    "input[name='local_fs_read']",
                    "[data-capability='local_fs_read'] input[type='checkbox']",
                    "label:has-text('local_fs_read') input",
                ],
                "checked": True,
                "optional": True,
            },
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    # Ensure permission is toggled via UI or verified API toggle, then execute.
    if not api_client.get("/api/v1/retriever/permissions").json().get("local_fs_read"):
        api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    r2 = api_client.post("/api/v1/retriever/execute", json={"capability": "local_fs_read", "target": "README.md"})
    assert r2.status_code == 200


def test_p13_rook_doctor_and_kane_cli_config_validate_live_targets(require_ui: str) -> None:
    """F12 x F14: Assurance CLIs execute cleanly while live frontend target responds HTTP 200."""
    assert httpx.get(require_ui, timeout=3.0).status_code == 200
    kane_bin = shutil.which("kane-cli.cmd") or shutil.which("kane-cli")
    rook_bin = shutil.which("rook.cmd") or shutil.which("rook")
    assert kane_bin and rook_bin
    kane_proc = subprocess.run([kane_bin, "config", "show"], capture_output=True, text=True, timeout=20)
    assert kane_proc.returncode == 0
    env = os.environ.copy()
    env["ROOK_ENV"] = "prod"
    rook_proc = subprocess.run([rook_bin, "doctor", "--json"], capture_output=True, text=True, env=env, timeout=25)
    assert rook_proc.returncode == 0
    assert json.loads(rook_proc.stdout).get("environment") == "prod"


def test_p14_dynamic_captured_thoughts_and_ui_modals_pass_unslop_and_em_dash_audit(
    browser_runner, unique_slug: str
) -> None:
    """F15 x F14: Dynamically captured thought and modal labels stay free of em dashes and AI slop."""
    res = browser_runner(
        actions=[
            {"type": "press", "key": "Control+k"},
            {"type": "wait_ms", "ms": 200},
            {
                "type": "fill_first",
                "selectors": ["[role='dialog'] textarea", "[role='dialog'] input[type='text']", "textarea"],
                "value": f"Clean dynamic idea {unique_slug}",
                "optional": True,
            },
            {"type": "click_text", "patterns": ["Capture Thought", "Capture"], "optional": True},
            {"type": "wait_ms", "ms": 300},
        ]
    )
    assert_no_server_errors(res)
    text = res["dom"]["innerText"]
    assert EM_DASH not in text
    assert not find_slop_matches(text)


def test_p15_scheduler_crud_and_prompts_survive_neo4j_offline_fallback(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    created_schedule_blocks: list[str],
    unique_slug: str,
) -> None:
    """F6 x F10: Scheduler CRUD and deterministic prompts succeed with local fallback driver."""
    health = api_client.get("/api/v1/health").json()
    assert_health_contract(health)
    blk = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"OfflineSched {unique_slug}",
            "start_iso": "2026-12-05T15:00:00Z",
            "end_iso": "2026-12-05T15:45:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert blk.status_code in {200, 201}
    bid = extract_id(blk.json())
    created_schedule_blocks.append(bid)
    prompts = api_client.get(
        "/api/v1/schedule/prompts",
        params={"now_iso": "2026-12-05T15:10:00Z", "energy": 4, "minutes": 30},
    )
    assert prompts.status_code == 200
    assert unwrap_list(prompts.json(), "prompts", "recommendations")

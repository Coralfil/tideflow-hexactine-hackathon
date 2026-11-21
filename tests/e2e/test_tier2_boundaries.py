from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

from tests.e2e.conftest import (
    EM_DASH,
    assert_no_server_errors,
    assert_triage_contract,
    assert_zero_em_dashes,
    extract_audit_verdict,
    extract_edges,
    extract_id,
    find_chatbot_phrases,
    require_workspace_artifact,
    unwrap_list,
    unwrap_thought,
)


def _create_project(api_client: httpx.Client, name: str) -> dict[str, Any]:
    resp = api_client.post("/api/v1/projects", json={"name": name, "description": "Boundary test"})
    assert resp.status_code in {200, 201}, resp.text
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
    assert resp.status_code in {200, 201}, resp.text
    data = resp.json()
    extract_id(data)
    return data


def _edge_touches(edge: dict[str, Any], node_id: str) -> bool:
    return any(edge.get(k) == node_id for k in ("source", "target", "src_id", "dst_id", "from", "to"))


def _edge_type(edge: dict[str, Any]) -> str:
    return str(edge.get("rel_type") or edge.get("type") or edge.get("label") or "").upper()


def _parse_css_number(raw: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", raw or "")
    assert match, f"Expected numeric CSS token value, got: {raw!r}"
    return float(match.group(0))


# ==============================================================================
# F6: Dual-Mode Graph Backend Boundaries (6 tests)
# ==============================================================================


def test_f06_b_project_empty_name_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post("/api/v1/projects", json={"name": ""})
    assert resp.status_code in {400, 422}


def test_f06_b_project_whitespace_name_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post("/api/v1/projects", json={"name": "   \t\n  "})
    assert resp.status_code in {400, 422}


def test_f06_b_project_unicode_and_emoji_persists_cleanly(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    unicode_name = f"TideFlow Café 海月 {unique_slug}"
    created = _create_project(api_client, unicode_name)
    assert created["name"] == unicode_name
    projects = unwrap_list(api_client.get("/api/v1/projects").json(), "projects")
    assert any(extract_id(p) == extract_id(created) and p.get("name") == unicode_name for p in projects)


def test_f06_b_project_very_long_name_handled_cleanly(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    long_name = f"{unique_slug}-" + ("x" * 500)
    resp = api_client.post("/api/v1/projects", json={"name": long_name})
    assert resp.status_code in {200, 201, 400, 422}, f"Unexpected status {resp.status_code} on 500-char name"


def test_f06_b_unknown_project_id_resume_returns_404(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.get("/api/v1/momentum/resume", params={"project_id": f"missing-{unique_slug}"})
    assert resp.status_code == 404


def test_f06_b_concurrent_project_creates_do_not_corrupt_store(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    created_ids = []
    for idx in range(5):
        proj = _create_project(api_client, f"Burst-{idx}-{unique_slug}")
        created_ids.append(extract_id(proj))
    assert len(set(created_ids)) == 5
    projects = unwrap_list(api_client.get("/api/v1/projects").json(), "projects")
    stored_ids = {extract_id(p) for p in projects}
    assert set(created_ids).issubset(stored_ids)


# ==============================================================================
# F7: Graph Science & Hexactine Boundaries (6 tests)
# ==============================================================================


def test_f07_b_invalid_lens_param_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.get("/api/v1/graph/snapshot", params={"lens": "invalid_lens_xyz"})
    assert resp.status_code in {400, 422}


def test_f07_b_snapshot_limit_zero_or_negative_rejected(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    r_zero = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 0})
    r_neg = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": -5})
    assert r_zero.status_code in {400, 422}
    assert r_neg.status_code in {400, 422}


def test_f07_b_snapshot_limit_bounds_respected(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    _create_project(api_client, f"Lim1 {unique_slug}")
    _create_project(api_client, f"Lim2 {unique_slug}")
    resp = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 1})
    assert resp.status_code == 200
    nodes = unwrap_list(resp.json(), "nodes")
    assert len(nodes) <= 1


def test_f07_b_path_disconnected_nodes_handled_cleanly(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    p1 = _create_project(api_client, f"IsoA {unique_slug}")
    p2 = _create_project(api_client, f"IsoB {unique_slug}")
    resp = api_client.get(
        "/api/v1/graph/path",
        params={"source_id": extract_id(p1), "target_id": extract_id(p2)},
    )
    assert resp.status_code in {200, 404}
    if resp.status_code == 200:
        body = resp.json()
        path_nodes = body.get("path") or body.get("nodes") or body.get("node_ids") or []
        assert body.get("found") is False or len(path_nodes) == 0


def test_f07_b_path_same_source_and_target_returns_zero_hops(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"SelfPath {unique_slug}")
    pid = extract_id(proj)
    resp = api_client.get("/api/v1/graph/path", params={"source_id": pid, "target_id": pid})
    assert resp.status_code in {200, 400}
    if resp.status_code == 200:
        body = resp.json()
        path_nodes = body.get("path") or body.get("nodes") or body.get("node_ids") or []
        hops = body.get("hop_count")
        if hops is None:
            hops = body.get("hops")
        if hops is None:
            hops = body.get("length")
        if hops is None:
            hops = max(0, len(path_nodes) - 1)
        assert hops == 0


def test_f07_b_hexactine_invariant_holds_at_exact_boundary_6_and_7(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"Bound67 {unique_slug}")
    pid = extract_id(proj)
    captured = []
    for idx in range(7):
        captured.append(_capture_thought(api_client, f"Edge {idx} {unique_slug} #hex{idx}", project_id=pid))
    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid, "limit": 200}).json()
    nodes = unwrap_list(snap, "nodes")
    edges = extract_edges(snap)
    direct = [e for e in edges if _edge_touches(e, pid)]
    assert 1 <= len(direct) <= 6, (
        f"Project {pid} direct structural edges out of [1, 6] at 7th thought: {len(direct)}"
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
        routed_edges or any(c.get("routed_via_subhub") is True for c in captured)
    ), f"Expected :ConceptTag or :SpiculeHub overflow routing at 7th thought for {pid}"


# ==============================================================================
# F8: Thought Capture & Linking Boundaries (6 tests)
# ==============================================================================


def test_f08_b_capture_empty_text_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post("/api/v1/thoughts/capture", json={"text": "", "kind": "spark_idea"})
    assert resp.status_code in {400, 422}


def test_f08_b_capture_invalid_kind_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post("/api/v1/thoughts/capture", json={"text": "Valid text", "kind": "invalid_type"})
    assert resp.status_code in {400, 422}


def test_f08_b_capture_energy_cost_zero_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Energy zero test", "kind": "project_task", "energy_cost": 0},
    )
    assert resp.status_code in {400, 422}


def test_f08_b_capture_energy_cost_above_five_rejected(api_client: httpx.Client, require_api: dict[str, Any]) -> None:
    resp = api_client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Energy six test", "kind": "project_task", "energy_cost": 6},
    )
    assert resp.status_code in {400, 422}


def test_f08_b_park_nonexistent_thought_returns_404(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.post(f"/api/v1/thoughts/does-not-exist-{unique_slug}/park")
    assert resp.status_code == 404


def test_f08_b_double_park_and_double_promote_idempotent(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    tid = extract_id(_capture_thought(api_client, f"Idem {unique_slug}", kind="side_quest"))
    p1 = api_client.post(f"/api/v1/thoughts/{tid}/park")
    p2 = api_client.post(f"/api/v1/thoughts/{tid}/park")
    assert p1.status_code == 200 and p2.status_code == 200
    assert str(unwrap_thought(p2.json()).get("status", "")).lower() == "parked"
    r1 = api_client.post(f"/api/v1/thoughts/{tid}/promote")
    r2 = api_client.post(f"/api/v1/thoughts/{tid}/promote")
    assert r1.status_code == 200 and r2.status_code == 200
    assert str(unwrap_thought(r2.json()).get("status", "")).lower() in {"active", "now", "next", "captured"}


# ==============================================================================
# F9: Momentum Recovery & Triage Boundaries (6 tests)
# ==============================================================================


def test_f09_b_breadcrumb_missing_project_returns_404_or_422(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": f"missing-{unique_slug}", "last_action": "Did X", "next_micro_step": "Do Y"},
    )
    assert resp.status_code in {404, 422}


def test_f09_b_breadcrumb_empty_summary_rejected(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"EmptyBread {unique_slug}")
    resp = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": extract_id(proj), "last_action": "   ", "next_micro_step": ""},
    )
    assert resp.status_code in {400, 422}


def test_f09_b_resume_without_breadcrumbs_returns_graceful_fallback(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"NoBread {unique_slug}")
    resp = api_client.get("/api/v1/momentum/resume", params={"project_id": extract_id(proj)})
    assert resp.status_code in {200, 404}
    assert resp.status_code != 500


def test_f09_b_triage_sweep_empty_state_safe(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"EmptySweep {unique_slug}")
    resp = api_client.post("/api/v1/triage/sweep", json={"project_id": extract_id(proj)})
    assert resp.status_code == 200
    data = resp.json()
    assert_triage_contract(data)
    assert data["now"] == []
    assert data["next"] == []
    assert float(data["overwhelm_index"]) == 0.0


def test_f09_b_triage_sweep_repeated_calls_idempotent(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"IdemSweep {unique_slug}")
    pid = extract_id(proj)
    _capture_thought(api_client, f"Focus A {unique_slug}", project_id=pid)
    s1 = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    s2 = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(s1)
    assert_triage_contract(s2)
    assert [extract_id(x) if isinstance(x, dict) else str(x) for x in s1["now"]] == [
        extract_id(x) if isinstance(x, dict) else str(x) for x in s2["now"]
    ]
    assert [extract_id(x) if isinstance(x, dict) else str(x) for x in s1["next"]] == [
        extract_id(x) if isinstance(x, dict) else str(x) for x in s2["next"]
    ]
    assert s1["parked_count"] == s2["parked_count"]


def test_f09_b_triage_sweep_excludes_parked_side_quests_from_now(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    proj = _create_project(api_client, f"ParkSweep {unique_slug}")
    pid = extract_id(proj)
    parked = _capture_thought(api_client, f"ParkedSQ {unique_slug}", kind="side_quest", project_id=pid, auto_park=True)
    parked_id = extract_id(parked)
    sweep = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(sweep)
    now_ids = {extract_id(item) if isinstance(item, dict) else str(item) for item in sweep["now"]}
    assert parked_id not in now_ids


# ==============================================================================
# F10: Cadence Scheduler Boundaries (6 tests)
# ==============================================================================


def test_f10_b_schedule_block_end_before_start_rejected(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Inverted {unique_slug}",
            "start_iso": "2026-11-29T12:00:00Z",
            "end_iso": "2026-11-29T11:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert resp.status_code in {400, 422}


def test_f10_b_schedule_block_invalid_iso_rejected(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"BadDate {unique_slug}",
            "start_iso": "not-a-date",
            "end_iso": "also-not-a-date",
            "cadence_window": "deep_tide",
        },
    )
    assert resp.status_code in {400, 422}


def test_f10_b_patch_nonexistent_block_returns_404(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.patch(f"/api/v1/schedule/blocks/missing-{unique_slug}", json={"title": "NoOp"})
    assert resp.status_code == 404


def test_f10_b_delete_nonexistent_block_returns_404(
    api_client: httpx.Client, require_api: dict[str, Any], unique_slug: str
) -> None:
    resp = api_client.delete(f"/api/v1/schedule/blocks/missing-{unique_slug}")
    assert resp.status_code == 404


def test_f10_b_adjacent_non_overlapping_blocks_allowed(
    api_client: httpx.Client, require_api: dict[str, Any], created_schedule_blocks: list[str], unique_slug: str
) -> None:
    b1 = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Adj1 {unique_slug}",
            "start_iso": "2026-12-01T10:00:00Z",
            "end_iso": "2026-12-01T10:30:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert b1.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(b1.json()))
    b2 = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"Adj2 {unique_slug}",
            "start_iso": "2026-12-01T10:30:00Z",
            "end_iso": "2026-12-01T11:00:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert b2.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(b2.json()))


def test_f10_b_prompts_energy_out_of_range_and_zero_minutes_rejected(
    api_client: httpx.Client, require_api: dict[str, Any]
) -> None:
    r_low = api_client.get(
        "/api/v1/schedule/prompts", params={"now_iso": "2026-11-19T10:00:00Z", "energy": 0, "minutes": 25}
    )
    r_high = api_client.get(
        "/api/v1/schedule/prompts", params={"now_iso": "2026-11-19T10:00:00Z", "energy": 6, "minutes": 25}
    )
    r_zero_min = api_client.get(
        "/api/v1/schedule/prompts", params={"now_iso": "2026-11-19T10:00:00Z", "energy": 3, "minutes": 0}
    )
    assert r_low.status_code in {400, 422}
    assert r_high.status_code in {400, 422}
    assert r_zero_min.status_code in {400, 422}


# ==============================================================================
# F11: Nemoclaw Retriever Boundaries (6 tests)
# ==============================================================================


def test_f11_b_execute_path_traversal_blocked_403(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "../../Windows/System32/drivers/etc/hosts"},
    )
    assert resp.status_code == 403
    entries = unwrap_list(api_client.get("/api/v1/retriever/audit").json(), "audit", "entries")
    assert any(extract_audit_verdict(e) == "DENIED" for e in entries)


def test_f11_b_execute_absolute_outside_path_blocked_403(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "C:\\Windows\\win.ini"},
    )
    assert resp.status_code == 403


def test_f11_b_execute_ssrf_metadata_url_blocked_403(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"web_fetch_public": True})
    r_meta = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "web_fetch_public", "target": "http://169.254.169.254/latest/meta-data/"},
    )
    r_local = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "web_fetch_public", "target": "http://127.0.0.1:8010/api/v1/health"},
    )
    assert r_meta.status_code == 403
    assert r_local.status_code == 403


def test_f11_b_execute_file_scheme_web_fetch_blocked_403(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"web_fetch_public": True})
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "web_fetch_public", "target": "file:///etc/passwd"},
    )
    assert resp.status_code in {400, 403, 422}


def test_f11_b_execute_unknown_capability_rejected(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "shell_exec_root", "target": "whoami"},
    )
    assert resp.status_code in {400, 403, 422}


def test_f11_b_nonexistent_allowlisted_file_does_not_500(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    resp = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "nonexistent_e2e_file_xyz.md"},
    )
    assert resp.status_code in {400, 403, 404}
    assert resp.status_code != 500


# ==============================================================================
# F12: Rook & KaneCLI Hooks Boundaries (6 tests)
# ==============================================================================


def test_f12_b_all_ps1_files_zero_double_ampersand(workspace_root: Path) -> None:
    require_workspace_artifact("scripts/dev.ps1", "M3/M4")
    ps1_files = list((workspace_root / "scripts").rglob("*.ps1"))
    assert ps1_files
    for ps1 in ps1_files:
        assert "&&" not in ps1.read_text(encoding="utf-8"), f"Found '&&' in {ps1}"


def test_f12_b_all_ps1_files_zero_em_dash(workspace_root: Path) -> None:
    require_workspace_artifact("scripts/dev.ps1", "M3/M4")
    ps1_files = list((workspace_root / "scripts").rglob("*.ps1"))
    assert ps1_files
    for ps1 in ps1_files:
        assert_zero_em_dashes(ps1.read_text(encoding="utf-8"), str(ps1))


def test_f12_b_rook_mjs_hooks_parse_valid_syntax() -> None:
    rook_dir = require_workspace_artifact(".testmuai/rook", "M3")
    node_bin = shutil.which("node")
    assert node_bin, "Node.js executable not found"
    mjs_files = list(rook_dir.rglob("*.mjs"))
    assert mjs_files
    for mjs in mjs_files:
        proc = subprocess.run([node_bin, "--check", str(mjs)], capture_output=True, text=True, timeout=15)
        assert proc.returncode == 0, f"Syntax check failed for {mjs}: {proc.stderr}"


def test_f12_b_rook_profile_yaml_non_empty_and_no_secrets() -> None:
    rook_dir = require_workspace_artifact(".testmuai/rook", "M3")
    yamls = list(rook_dir.rglob("*.yaml")) + list(rook_dir.rglob("*.yml"))
    assert yamls
    for yml in yamls:
        text = yml.read_text(encoding="utf-8")
        assert text.strip(), f"Empty Rook YAML: {yml}"
        assert not re.search(r"LT_ACCESS_KEY\s*[:=]\s*['\"]?[A-Za-z0-9]{12,}", text)


def test_f12_b_kane_cli_dry_run_without_live_credits_graceful(workspace_root: Path) -> None:
    kane_bin = shutil.which("kane-cli.cmd") or shutil.which("kane-cli")
    assert kane_bin
    proc = subprocess.run(
        [kane_bin, "testrun", "run", "--match", "^tests[/\\\\]", "--dry-run", "--agent"],
        cwd=str(workspace_root),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc.returncode in {0, 1, 2}, f"Unexpected exit code {proc.returncode}: {proc.stderr}"


def test_f12_b_deepcoder_mirror_contains_kane_cli_guide(workspace_root: Path) -> None:
    playbook = workspace_root / ".agents" / "deepcoder" / "02-SKILLS" / "playbook.md"
    assert playbook.exists()
    content = playbook.read_text(encoding="utf-8")
    assert "kane-cli.cmd" in content
    assert "&&" not in content


# ==============================================================================
# F13: CSS Houdini Rhythm Layer Boundaries (6 tests)
# ==============================================================================


def test_f13_b_bpm_clamped_at_low_and_high_bounds(browser_runner) -> None:
    range_selectors = [
        "input[type='range'][aria-label*='energy' i]",
        "input[type='range'][aria-label*='bpm' i]",
        "input[type='range'][aria-label*='rhythm' i]",
        "input[type='range']",
    ]
    res_low = browser_runner(
        actions=[
            {"type": "set_input_value", "selectors": range_selectors, "value": "1"},
            {"type": "wait_ms", "ms": 200},
        ]
    )
    assert_no_server_errors(res_low)
    assert all(step["ok"] is True for step in res_low["stepResults"])
    bpm_low = _parse_css_number(res_low["houdini"]["rhythm_bpm"])
    assert 30.0 <= bpm_low <= 220.0

    res_high = browser_runner(
        actions=[
            {"type": "set_input_value", "selectors": range_selectors, "value": "5"},
            {"type": "wait_ms", "ms": 200},
        ]
    )
    assert_no_server_errors(res_high)
    assert all(step["ok"] is True for step in res_high["stepResults"])
    bpm_high = _parse_css_number(res_high["houdini"]["rhythm_bpm"])
    assert 30.0 <= bpm_high <= 220.0
    assert bpm_low != bpm_high, f"Expected clamped low (1) and high (5) BPM values to differ, got {bpm_low}"


def test_f13_b_overwhelm_index_token_stays_within_0_to_1(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    val = _parse_css_number(res["houdini"]["overwhelm_index"])
    assert 0.0 <= val <= 1.0


def test_f13_b_focus_depth_token_retains_percentage_unit(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    raw = res["houdini"]["focus_depth"]
    assert raw.endswith("%"), f"Expected percentage unit in --focus-depth, got {raw!r}"
    val = _parse_css_number(raw)
    assert 0.0 <= val <= 100.0


def test_f13_b_paint_worklet_fallback_when_paintworklet_undefined(browser_runner) -> None:
    res = browser_runner(disable_paint_worklet=True)
    assert_no_server_errors(res)
    assert res["dom"]["rootChildCount"] >= 1


def test_f13_b_reduced_motion_preference_respected(browser_runner) -> None:
    res = browser_runner(reduced_motion="reduce")
    assert_no_server_errors(res)
    assert res["dom"]["rootChildCount"] >= 1


def test_f13_b_worklets_contain_zero_em_dashes(require_ui: str) -> None:
    for path in ("/worklets/rhythm-lattice-paint.js", "/worklets/biolum-pulse-paint.js"):
        resp = httpx.get(f"{require_ui}{path}", timeout=5.0)
        assert resp.status_code == 200
        assert_zero_em_dashes(resp.text, path)


# ==============================================================================
# F14: Interactive UI Boundaries (6 tests)
# ==============================================================================


def test_f14_b_empty_brain_dump_submit_disabled_or_shows_validation(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "press", "key": "Control+k"},
            {"type": "wait_ms", "ms": 200},
            {
                "type": "fill_first",
                "selectors": ["[role='dialog'] textarea", "[role='dialog'] input[type='text']", "textarea"],
                "value": "",
            },
            {
                "type": "click_first",
                "selectors": [
                    "[role='dialog'] button[type='submit']",
                    "button:has-text('Capture Thought')",
                    "button:has-text('Capture')",
                ],
                "skipIfDisabled": True,
            },
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    capture_posts = [r for r in res["responses"] if "/api/v1/thoughts/capture" in r["url"] and r["method"] == "POST"]
    assert not capture_posts or all(r["status"] in {400, 422} for r in capture_posts)


def test_f14_b_escape_closes_brain_dump_modal(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "press", "key": "Control+k"},
            {"type": "wait_ms", "ms": 150},
            {
                "type": "eval",
                "script": "() => Boolean(document.querySelector('[role=\"dialog\"]'))",
            },
            {"type": "press", "key": "Escape"},
            {"type": "wait_ms", "ms": 150},
            {
                "type": "eval",
                "script": "() => Boolean(document.querySelector('[role=\"dialog\"]'))",
            },
        ]
    )
    assert_no_server_errors(res)
    opened = res["stepResults"][2]["value"]
    closed_state = res["stepResults"][5]["value"]
    assert opened is True, "Expected Ctrl+K to open [role='dialog'] modal"
    assert closed_state is False, "Expected Escape to close [role='dialog'] modal"


def test_f14_b_mobile_viewport_no_horizontal_overflow(browser_runner) -> None:
    res = browser_runner(viewport={"width": 390, "height": 844})
    assert_no_server_errors(res)
    assert res["dom"]["scrollWidth"] <= res["dom"]["innerWidth"] + 2


def test_f14_b_rapid_lens_switching_no_uncaught_errors(browser_runner) -> None:
    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["PageRank"]},
            {"type": "click_text", "patterns": ["Communities"]},
            {"type": "click_text", "patterns": ["Shortest Path"]},
            {"type": "click_text", "patterns": ["Degree Audit"]},
            {"type": "wait_ms", "ms": 300},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    snap_calls = [r for r in res["responses"] if "/api/v1/graph/snapshot" in r["url"]]
    assert len(snap_calls) >= 3 and all(r["status"] == 200 for r in snap_calls)


def test_f14_b_ui_handles_api_403_denial_gracefully(
    browser_runner, reset_retriever_permissions: dict[str, bool]
) -> None:
    res = browser_runner(
        actions=[
            {
                "type": "fill_first",
                "selectors": [
                    "input[name='target']",
                    "input[aria-label*='target' i]",
                    "input[placeholder*='target' i]",
                    "input[placeholder*='README' i]",
                ],
                "value": "README.md",
            },
            {"type": "click_text", "patterns": ["Execute", "Run Retrieval"]},
            {"type": "wait_ms", "ms": 350},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    exec_403 = [r for r in res["responses"] if "/api/v1/retriever/execute" in r["url"] and r["status"] == 403]
    ui_text = res["dom"]["innerText"].lower()
    assert exec_403 or ("403" in ui_text or "denied" in ui_text), (
        f"Expected HTTP 403 response or explicit denied UI alert; responses={res['responses']}"
    )
    assert res["dom"]["rootChildCount"] >= 1


def test_f14_b_ui_handles_schedule_conflict_409_gracefully(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    created_schedule_blocks: list[str],
    browser_runner,
    unique_slug: str,
) -> None:
    seed = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"SeedBlock {unique_slug}",
            "start_iso": "2026-12-02T09:00:00Z",
            "end_iso": "2026-12-02T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert seed.status_code in {200, 201}, seed.text
    created_schedule_blocks.append(extract_id(seed.json()))
    res = browser_runner(
        actions=[
            {
                "type": "fill_first",
                "selectors": [
                    "input[name='title']",
                    "input[name='block_title']",
                    "input[aria-label*='block title' i]",
                    "input[placeholder*='block title' i]",
                ],
                "value": f"OverlapProbe {unique_slug}",
            },
            {
                "type": "fill_first",
                "selectors": [
                    "input[name='start_iso']",
                    "input[aria-label*='start' i]",
                    "input[placeholder*='start' i]",
                ],
                "value": "2026-12-02T09:30:00Z",
            },
            {
                "type": "fill_first",
                "selectors": [
                    "input[name='end_iso']",
                    "input[aria-label*='end' i]",
                    "input[placeholder*='end' i]",
                ],
                "value": "2026-12-02T10:30:00Z",
            },
            {
                "type": "select_first",
                "selectors": ["select[name='cadence_window']", "select[aria-label*='cadence' i]"],
                "value": "deep_tide",
            },
            {"type": "click_text", "patterns": ["Add Block", "Schedule Block"]},
            {"type": "wait_ms", "ms": 350},
        ]
    )
    assert_no_server_errors(res)
    assert all(step["ok"] is True for step in res["stepResults"])
    post_calls = [
        r for r in res["responses"] if "/api/v1/schedule/blocks" in r["url"] and r["method"] == "POST"
    ]
    assert post_calls and post_calls[-1]["status"] in {400, 409, 422}, (
        f"Expected 409 conflict POST from Scheduler UI form, got: {post_calls}"
    )
    ui_text = res["dom"]["innerText"].lower()
    assert any(tok in ui_text for tok in ("conflict", "overlap", "409")), (
        "Expected visible conflict notice in Scheduler UI"
    )
    assert res["dom"]["rootChildCount"] >= 1


# ==============================================================================
# F15: Public Copy unslop Boundaries (6 tests)
# ==============================================================================


def test_f15_b_agents_md_contains_zero_em_dashes(workspace_root: Path) -> None:
    agents = workspace_root / "AGENTS.md"
    assert agents.exists()
    assert_zero_em_dashes(agents.read_text(encoding="utf-8"), "AGENTS.md")


def test_f15_b_frontend_source_copy_zero_em_dashes(workspace_root: Path) -> None:
    src_dir = require_workspace_artifact("frontend/src", "M4")
    source_files = [
        p for p in src_dir.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx", ".css"}
    ]
    assert source_files
    for src in source_files:
        assert_zero_em_dashes(src.read_text(encoding="utf-8"), str(src))


def test_f15_b_backend_api_messages_zero_em_dashes(
    api_client: httpx.Client, require_api: dict[str, Any], reset_retriever_permissions: dict[str, bool]
) -> None:
    r403 = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    r422 = api_client.post("/api/v1/thoughts/capture", json={"text": ""})
    r404 = api_client.get("/api/v1/momentum/resume", params={"project_id": "nonexistent-e2e-check"})
    for resp in (r403, r422, r404):
        assert_zero_em_dashes(resp.text, f"API {resp.status_code} response")


def test_f15_b_readme_has_under_30s_quickstart_command(workspace_root: Path) -> None:
    readme = workspace_root / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert ";" in text
    assert "&&" not in text
    assert "uvicorn" in text


def test_f15_b_no_chatbot_opener_or_closer_in_ui_text(browser_runner) -> None:
    res = browser_runner()
    assert_no_server_errors(res)
    hits = find_chatbot_phrases(res["dom"]["innerText"])
    assert not hits, f"Found chatbot phrase(s) in UI copy: {hits}"


def test_f15_b_all_docs_md_files_zero_em_dashes(workspace_root: Path) -> None:
    md_files = list(workspace_root.glob("*.md")) + list((workspace_root / "docs").rglob("*.md"))
    assert md_files
    for md in md_files:
        assert_zero_em_dashes(md.read_text(encoding="utf-8"), str(md))

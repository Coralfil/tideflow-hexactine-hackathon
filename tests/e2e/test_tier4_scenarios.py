from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

import httpx

from tests.e2e.conftest import (
    CAPABILITY_KEYS,
    EM_DASH,
    assert_no_server_errors,
    assert_permissions_contract,
    assert_triage_contract,
    assert_zero_em_dashes,
    extract_audit_verdict,
    extract_edges,
    extract_id,
    find_slop_matches,
    unwrap_list,
)


def _create_project(api_client: httpx.Client, name: str) -> dict[str, Any]:
    resp = api_client.post("/api/v1/projects", json={"name": name, "description": "Tier 4 scenario"})
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


def _parse_css_number(raw: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", raw or "")
    assert match, f"Expected numeric CSS token value, got: {raw!r}"
    return float(match.group(0))


def test_s01_hyperfocus_capture_and_guilt_free_parking_flow(
    api_client: httpx.Client, require_api: dict[str, Any], browser_runner, unique_slug: str
) -> None:
    """F8 + F9 + F14: Capture active task via Cmd+K, park intrusive side quest, sweep 3-slot horizon."""
    proj = _create_project(api_client, f"S01 {unique_slug}")
    pid = extract_id(proj)
    side_quest = _capture_thought(
        api_client, f"Intrusive synth quest {unique_slug}", kind="side_quest", project_id=pid, auto_park=True
    )
    res = browser_runner(
        actions=[
            {"type": "press", "key": "Control+k"},
            {"type": "wait_ms", "ms": 200},
            {
                "type": "fill_first",
                "selectors": ["[role='dialog'] textarea", "[role='dialog'] input[type='text']", "textarea"],
                "value": f"Ship focus slice {unique_slug}",
            },
            {"type": "click_text", "patterns": ["Capture Thought", "Capture", "Submit"]},
            {"type": "wait_ms", "ms": 350},
            {"type": "click_text", "patterns": ["Run Triage Sweep", "Triage Sweep", "Sweep"], "optional": True},
            {"type": "wait_ms", "ms": 300},
        ]
    )
    assert_no_server_errors(res)
    sweep = api_client.post("/api/v1/triage/sweep", json={"project_id": pid}).json()
    assert_triage_contract(sweep)
    assert sweep["parked_count"] >= 1
    assert extract_id(side_quest) not in {
        extract_id(x) if isinstance(x, dict) else str(x) for x in sweep["now"]
    }
    text = res["dom"]["innerText"].lower()
    assert "now" in text and "next" in text and "parked" in text


def test_s02_momentum_recovery_after_context_switch_flow(
    api_client: httpx.Client, require_api: dict[str, Any], browser_runner, unique_slug: str
) -> None:
    """F6 + F7 + F9 + F14: Sequential breadcrumbs supersede cleanly, resume card <= 3 lines, graph renders."""
    proj = _create_project(api_client, f"S02 {unique_slug}")
    pid = extract_id(proj)
    _capture_thought(api_client, f"Anchor task {unique_slug}", project_id=pid)
    b1 = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Old state {unique_slug}", "next_step": "Continue"},
    ).json()
    b2 = api_client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": pid, "last_action": f"Latest resume {unique_slug}", "next_step": "Verify path"},
    ).json()
    resume = api_client.get("/api/v1/momentum/resume", params={"project_id": pid})
    assert resume.status_code == 200
    resume_data = resume.json()
    assert unique_slug in json.dumps(resume_data)
    if isinstance(resume_data.get("lines"), list):
        assert len(resume_data["lines"]) <= 3

    path_resp = api_client.get(
        "/api/v1/graph/path", params={"source_id": extract_id(b2), "target_id": extract_id(b1)}
    )
    assert path_resp.status_code == 200

    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["PageRank"], "optional": True},
            {"type": "wait_ms", "ms": 200},
            {"type": "click_text", "patterns": ["Shortest Path"], "optional": True},
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert res["dom"]["svgCount"] + res["dom"]["canvasCount"] >= 1


def test_s03_tidal_energy_drop_and_cadence_rescheduling_flow(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    created_schedule_blocks: list[str],
    browser_runner,
    unique_slug: str,
) -> None:
    """F10 + F13 + F14: Schedule block + 409 conflict + low-energy prompt + Houdini rhythm token inspection."""
    blk = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"S03 Tide {unique_slug}",
            "start_iso": "2026-12-06T09:00:00Z",
            "end_iso": "2026-12-06T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert blk.status_code in {200, 201}
    created_schedule_blocks.append(extract_id(blk.json()))

    conflict = api_client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": f"S03 Overlap {unique_slug}",
            "start_iso": "2026-12-06T09:30:00Z",
            "end_iso": "2026-12-06T10:30:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert conflict.status_code in {400, 409, 422}

    low_prompts = api_client.get(
        "/api/v1/schedule/prompts",
        params={"now_iso": "2026-12-06T19:00:00Z", "energy": 2, "minutes": 20},
    )
    assert low_prompts.status_code == 200
    assert unwrap_list(low_prompts.json(), "prompts", "recommendations")

    res = browser_runner(
        actions=[
            {"type": "set_input_value", "selectors": ["input[type='range']"], "value": "2", "optional": True},
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert 30.0 <= _parse_css_number(res["houdini"]["rhythm_bpm"]) <= 220.0
    assert res["houdini"]["cadence_color"]


def test_s04_nemoclaw_default_deny_then_permitted_retrieval_flow(
    api_client: httpx.Client,
    require_api: dict[str, Any],
    reset_retriever_permissions: dict[str, bool],
    browser_runner,
) -> None:
    """F11 + F7 + F14: Default-deny 403 + DENIED audit -> toggle ON -> 200 + ALLOWED + RetrievalArtifact."""
    perms = api_client.get("/api/v1/retriever/permissions").json()
    assert_permissions_contract(perms)
    assert all(perms[k] is False for k in CAPABILITY_KEYS)

    denied = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert denied.status_code == 403

    api_client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    allowed = api_client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert allowed.status_code == 200

    audit_entries = unwrap_list(api_client.get("/api/v1/retriever/audit").json(), "audit", "entries")
    verdicts = {extract_audit_verdict(e) for e in audit_entries}
    assert "DENIED" in verdicts and "ALLOWED" in verdicts

    snap = api_client.get("/api/v1/graph/snapshot", params={"lens": "pagerank", "limit": 200}).json()
    assert any(
        "retrieval" in str(n.get("label") or n.get("labels") or n.get("kind") or "").lower()
        for n in unwrap_list(snap, "nodes")
    )

    res = browser_runner(actions=[{"type": "wait_ms", "ms": 250}])
    assert_no_server_errors(res)
    assert "audit" in res["dom"]["innerText"].lower()


def test_s05_graph_overgrowth_hexactine_self_healing_flow(
    api_client: httpx.Client, require_api: dict[str, Any], browser_runner, unique_slug: str
) -> None:
    """F7 + F8 + F14: 9 captured thoughts across concept tags preserve deg <= 6 via sub-hubs."""
    proj = _create_project(api_client, f"S05 {unique_slug}")
    pid = extract_id(proj)
    for idx in range(9):
        _capture_thought(
            api_client,
            f"Node {idx} {unique_slug} #spicule{idx % 3}",
            kind="spark_idea",
            project_id=pid,
        )
    snap = api_client.get(
        "/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid, "limit": 200}
    ).json()
    edges = extract_edges(snap)
    assert len([e for e in edges if _edge_touches(e, pid)]) <= 6

    res = browser_runner(
        actions=[
            {"type": "click_text", "patterns": ["Degree Audit"], "optional": True},
            {"type": "wait_ms", "ms": 250},
        ]
    )
    assert_no_server_errors(res)
    assert res["dom"]["svgCount"] + res["dom"]["canvasCount"] >= 1


def test_s06_worklets_unslop_and_assurance_readiness_flow(require_ui: str, browser_runner) -> None:
    """F12 + F13 + F15: Paint worklets serve 200, UI passes unslop/zero-em-dash, Rook/KaneCLI healthy."""
    for path in ("/worklets/rhythm-lattice-paint.js", "/worklets/biolum-pulse-paint.js"):
        resp = httpx.get(f"{require_ui}{path}", timeout=5.0)
        assert resp.status_code == 200
        assert "registerPaint" in resp.text
        assert_zero_em_dashes(resp.text, path)

    res = browser_runner()
    assert_no_server_errors(res)
    ui_text = res["dom"]["innerText"]
    assert EM_DASH not in ui_text
    assert not find_slop_matches(ui_text)

    kane_bin = shutil.which("kane-cli.cmd") or shutil.which("kane-cli")
    rook_bin = shutil.which("rook.cmd") or shutil.which("rook")
    assert kane_bin and rook_bin
    assert subprocess.run([kane_bin, "config", "show"], capture_output=True, text=True, timeout=20).returncode == 0
    env = os.environ.copy()
    env["ROOK_ENV"] = "prod"
    rook_proc = subprocess.run([rook_bin, "doctor", "--json"], capture_output=True, text=True, env=env, timeout=25)
    assert rook_proc.returncode == 0
    assert json.loads(rook_proc.stdout).get("environment") == "prod"

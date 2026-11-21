"""Unit and integration tests for Feature 10 (Deterministic Cadence Scheduler) and delete_node parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.graph.backend import InProcessGraphDriver, Neo4jGDSDriver, RelateGraphDriver
from app.main import create_app


class _FixedStepClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture(params=["inprocess", "relate"])
def graph_backend(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "inprocess":
        driver = InProcessGraphDriver()
        yield driver
        driver.close()
        return

    driver = RelateGraphDriver(db_path=str(tmp_path / "scheduler_test.rl"))
    yield driver
    driver.close()


@pytest.fixture
async def api_client(graph_backend, tmp_path: Path):
    clock = _FixedStepClock(datetime(2026, 11, 19, 9, 30, 0, tzinfo=timezone.utc))
    settings = Settings(
        graph_mode="inprocess",
        relate_db_path=str(tmp_path / "unused.rl"),
        local_worker_enabled=False,
    )
    app = create_app(settings=settings, graph_backend=graph_backend, clock=clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, graph_backend, app, clock


def test_delete_node_parity_and_neo4j_cypher(graph_backend) -> None:
    graph_backend.upsert_node("Project", {"id": "p_del_1", "name": "TempProj"})
    graph_backend.upsert_node("ScheduleBlock", {"id": "blk_del_1", "title": "TempBlock"})
    graph_backend.upsert_edge("blk_del_1", "SCHEDULED_FOR", "p_del_1", {"weight": 1.0})

    assert graph_backend.get_node("blk_del_1") is not None
    assert len(graph_backend.get_edges(node_id="blk_del_1")) == 1

    assert graph_backend.delete_node("blk_del_1") is True
    assert graph_backend.get_node("blk_del_1") is None
    assert graph_backend.get_edges(node_id="blk_del_1") == []
    assert graph_backend.delete_node("blk_del_1") is False

    driver = Neo4jGDSDriver.__new__(Neo4jGDSDriver)
    captured: list[tuple[str, dict[str, Any] | None]] = []

    def _fake_execute(cypher: str, params: dict[str, Any] | None = None):
        captured.append((cypher, params))
        return [{"deleted": 1}]

    driver._execute = _fake_execute  # type: ignore[method-assign]
    assert driver.delete_node("blk_neo_1") is True
    assert "DETACH DELETE" in captured[0][0]
    assert captured[0][1] == {"id": "blk_neo_1"}


async def test_health_reflects_scheduler_injectable_clock(api_client) -> None:
    client, _, _, clock = api_client

    for hour, expected in (
        (9, "deep_tide"),
        (14, "creative_swell"),
        (19, "shallow_drift"),
        (23, "recovery_ebb"),
    ):
        clock.current = datetime(2026, 11, 19, hour, 15, 0, tzinfo=timezone.utc)
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["active_cadence"] == expected


async def test_schedule_block_crud_and_adjacent_boundaries(api_client) -> None:
    client, backend, _, _ = api_client

    r1 = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Morning Deep Work",
            "start_iso": "2026-11-25T10:00:00Z",
            "end_iso": "2026-11-25T10:30:00Z",
            "cadence_window": "deep_tide",
            "energy_required": 4,
            "notes": "Ship scheduler",
        },
    )
    assert r1.status_code == 201
    b1 = r1.json()
    b1_id = b1["id"]

    # Touching boundary after (end == next.start) must succeed.
    r2 = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Followup Block",
            "start_iso": "2026-11-25T10:30:00Z",
            "end_iso": "2026-11-25T11:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert r2.status_code == 201

    # Touching boundary before (new.end == existing.start) must succeed.
    r0 = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Warmup Block",
            "start_iso": "2026-11-25T09:30:00Z",
            "end_iso": "2026-11-25T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert r0.status_code == 201

    listed = await client.get("/api/v1/schedule/blocks")
    assert listed.status_code == 200
    titles = [b["title"] for b in listed.json()]
    assert titles == ["Warmup Block", "Morning Deep Work", "Followup Block"]

    patched = await client.patch(
        f"/api/v1/schedule/blocks/{b1_id}",
        json={"title": "Updated Deep Work", "cadence_window": "shallow_drift"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Updated Deep Work"
    assert patched.json()["cadence_window"] == "shallow_drift"

    deleted = await client.delete(f"/api/v1/schedule/blocks/{b1_id}")
    assert deleted.status_code == 200
    assert backend.get_node(b1_id) is None

    remaining = await client.get("/api/v1/schedule/blocks")
    assert all(b["id"] != b1_id for b in remaining.json())

    assert (await client.patch(f"/api/v1/schedule/blocks/{b1_id}", json={"title": "Ghost"})).status_code == 404
    assert (await client.delete(f"/api/v1/schedule/blocks/{b1_id}")).status_code == 404


async def test_schedule_overlap_and_validation_boundaries(api_client) -> None:
    client, _, _, _ = api_client

    first = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Primary Window",
            "start_iso": "2026-11-28T13:00:00Z",
            "end_iso": "2026-11-28T14:00:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    # Partial overlap -> 409
    overlap = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Overlapping Window",
            "start_iso": "2026-11-28T13:30:00Z",
            "end_iso": "2026-11-28T14:30:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert overlap.status_code == 409

    # Non-overlapping second block, then PATCH into conflict -> 409
    second = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Later Window",
            "start_iso": "2026-11-28T15:00:00Z",
            "end_iso": "2026-11-28T16:00:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    patch_conflict = await client.patch(
        f"/api/v1/schedule/blocks/{second_id}",
        json={"start_iso": "2026-11-28T13:45:00Z", "end_iso": "2026-11-28T14:15:00Z"},
    )
    assert patch_conflict.status_code == 409

    # Cancelling first block allows reusing its time range
    cancel_resp = await client.patch(
        f"/api/v1/schedule/blocks/{first_id}",
        json={"status": "cancelled"},
    )
    assert cancel_resp.status_code == 200
    reused = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Reclaimed Window",
            "start_iso": "2026-11-28T13:00:00Z",
            "end_iso": "2026-11-28T14:00:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert reused.status_code == 201

    # Inverted / equal / invalid timestamps -> 422
    assert (
        await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": "Inverted",
                "start_iso": "2026-11-29T12:00:00Z",
                "end_iso": "2026-11-29T11:00:00Z",
                "cadence_window": "deep_tide",
            },
        )
    ).status_code == 422

    assert (
        await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": "ZeroLength",
                "start_iso": "2026-11-29T12:00:00Z",
                "end_iso": "2026-11-29T12:00:00Z",
                "cadence_window": "deep_tide",
            },
        )
    ).status_code == 422

    assert (
        await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": "InvalidISO",
                "start_iso": "not-a-date",
                "end_iso": "also-not-a-date",
                "cadence_window": "deep_tide",
            },
        )
    ).status_code == 422

    # Unknown project/thought target -> 404
    assert (
        await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": "MissingProject",
                "project_id": "proj_missing_xyz",
                "start_iso": "2026-11-30T09:00:00Z",
                "end_iso": "2026-11-30T10:00:00Z",
            },
        )
    ).status_code == 404


async def test_schedule_project_linking_preserves_hexactine_invariant(api_client) -> None:
    client, _, _, _ = api_client

    proj = (await client.post("/api/v1/projects", json={"name": "HexSchedProj"})).json()
    pid = proj["id"]
    for idx in range(6):
        cap = await client.post(
            "/api/v1/thoughts/capture",
            json={"text": f"Task {idx}", "project_id": pid},
        )
        assert cap.status_code == 201

    for idx in range(2):
        blk = await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": f"Block {idx}",
                "project_id": pid,
                "start_iso": f"2026-12-01T{8 + idx:02d}:00:00Z",
                "end_iso": f"2026-12-01T{9 + idx:02d}:00:00Z",
                "cadence_window": "deep_tide",
            },
        )
        assert blk.status_code == 201

    audit = (
        await client.get("/api/v1/graph/snapshot", params={"lens": "degree_audit", "focus_id": pid})
    ).json()
    assert audit["metrics"]["invariant_ok"] is True
    assert audit["metrics"]["max_observed_degree"] <= 6


async def test_schedule_prompts_determinism_windows_and_energy_scoring(api_client) -> None:
    client, _, _, _ = api_client

    proj = (await client.post("/api/v1/projects", json={"name": "PromptProj"})).json()
    pid = proj["id"]
    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Quick 10m note cleanup", "project_id": pid, "kind": "side_quest", "energy_cost": 1},
    )
    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Build core graph solver", "project_id": pid, "kind": "project_task", "energy_cost": 5},
    )
    await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Active Deep Sprint",
            "project_id": pid,
            "start_iso": "2026-11-19T09:00:00Z",
            "end_iso": "2026-11-19T10:00:00Z",
            "cadence_window": "deep_tide",
            "energy_required": 4,
        },
    )

    params = {"now_iso": "2026-11-19T09:15:00Z", "energy": 4, "minutes": 30}
    r1 = await client.get("/api/v1/schedule/prompts", params=params)
    r2 = await client.get("/api/v1/schedule/prompts", params=params)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    assert r1.json()["prompts"][0]["source_type"] == "schedule_block"
    assert "\u2014" not in json.dumps(r1.json(), ensure_ascii=False)

    seen_windows = set()
    for hour, expected in (
        ("09:00:00Z", "deep_tide"),
        ("14:00:00Z", "creative_swell"),
        ("19:00:00Z", "shallow_drift"),
        ("23:30:00Z", "recovery_ebb"),
    ):
        resp = await client.get(
            "/api/v1/schedule/prompts",
            params={"now_iso": f"2026-11-19T{hour}", "energy": 3, "minutes": 25},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_cadence"] == expected
        assert len(body["prompts"]) >= 1
        seen_windows.add(body["active_cadence"])
    assert len(seen_windows) == 4

    # Boundary rejections -> 422
    assert (await client.get("/api/v1/schedule/prompts", params={"energy": 0, "minutes": 25})).status_code == 422
    assert (await client.get("/api/v1/schedule/prompts", params={"energy": 6, "minutes": 25})).status_code == 422
    assert (await client.get("/api/v1/schedule/prompts", params={"energy": 3, "minutes": 0})).status_code == 422
    assert (await client.get("/api/v1/schedule/prompts", params={"now_iso": "bad-ts", "energy": 3, "minutes": 25})).status_code == 422

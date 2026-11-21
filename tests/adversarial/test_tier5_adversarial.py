"""Tier 5 white-box adversarial, security, and fault-injection tests."""

from __future__ import annotations

from datetime import datetime, timezone
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from app.config import Settings
from app.graph.backend import InProcessGraphDriver, RelateGraphDriver
from app.graph.science import GraphScienceService
from app.main import create_app
from app.models.schemas import (
    RetrieverExecuteRequest,
    RetrieverPermissionsUpdateRequest,
)
from app.services.local_worker_client import LocalWorkerClient
from app.services.nemoclaw_retriever import NemoclawRetriever, PermissionDeniedError


def _fixed_clock() -> datetime:
    return datetime(2026, 11, 20, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(params=["inprocess", "relate"])
def dual_driver(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "inprocess":
        drv = InProcessGraphDriver()
        yield drv
        drv.close()
        return

    drv = RelateGraphDriver(db_path=str(tmp_path / "adv_memory.rl"))
    yield drv
    drv.close()


@pytest_asyncio.fixture
async def adv_client(dual_driver, tmp_path: Path):
    settings = Settings(
        graph_mode="inprocess",
        relate_db_path=str(tmp_path / "unused.rl"),
        local_worker_enabled=False,
    )
    app = create_app(settings=settings, graph_backend=dual_driver, clock=_fixed_clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://adv-test") as client:
        yield client, dual_driver, app


async def test_t5_nemoclaw_traversal_ssrf_and_redirect_bypass_probes(
    adv_client, dual_driver, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _ = adv_client
    await client.put(
        "/api/v1/retriever/permissions",
        json={"local_fs_read": True, "web_fetch_public": True},
    )

    fs_probes = [
        "..%2f..%2fWindows%2fSystem32%2fdrivers%2fetc%2fhosts",
        "..\\..\\..\\Windows\\win.ini",
        ".env",
        ".env.local",
        ".git/HEAD",
        ".testmuai/evidence/run.json",
        "secrets/prod.json",
    ]
    for target in fs_probes:
        resp = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": "local_fs_read", "target": target},
        )
        assert resp.status_code in {403, 404}, f"FS probe {target} returned {resp.status_code}"
        if resp.status_code == 403:
            assert resp.json()["detail"]["verdict"] == "DENIED"

    ssrf_probes = [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8010/api/v1/health",
        "http://[::1]:8010/api/v1/health",
        "http://2130706433/api/v1/health",
        "http://0.0.0.0:8010/",
        "file:///C:/Windows/win.ini",
    ]
    for url in ssrf_probes:
        resp = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": "web_fetch_public", "target": url},
        )
        assert resp.status_code == 403, f"SSRF probe {url} returned {resp.status_code}"

    unknown = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "system_shell_exec", "target": "cmd /c dir"},
    )
    assert unknown.status_code == 403

    def _public_dns(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port or 443)))]

    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)

    def _redirect_to_metadata(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    retriever = NemoclawRetriever(
        backend=dual_driver,
        science=GraphScienceService(),
        settings=Settings(graph_mode="inprocess", local_worker_enabled=False),
        clock=_fixed_clock,
        http_transport=httpx.MockTransport(_redirect_to_metadata),
        repo_root=tmp_path,
    )
    retriever.update_permissions(
        RetrieverPermissionsUpdateRequest(web_fetch_public=True, allowed_domains=["example.org"])
    )
    with pytest.raises(PermissionDeniedError):
        await retriever.execute(
            RetrieverExecuteRequest(
                capability="web_fetch_public",
                target="https://example.org/hop",
            )
        )

    audit = (await client.get("/api/v1/retriever/audit")).json()
    assert len(audit) >= len(ssrf_probes) + 1
    assert all(entry["verdict"] == "DENIED" for entry in audit)


async def test_t5_hexactine_degree_invariant_under_mixed_burst(adv_client) -> None:
    client, _, _ = adv_client
    proj = (await client.post("/api/v1/projects", json={"name": "BurstHex"})).json()
    pid = proj["id"]

    for i in range(18):
        cap = await client.post(
            "/api/v1/thoughts/capture",
            json={
                "text": f"Burst thought {i} #ray{i % 5}",
                "kind": "spark_idea" if i % 2 == 0 else "project_task",
                "project_id": pid,
                "energy_cost": (i % 5) + 1,
            },
        )
        assert cap.status_code == 201

    for b in range(4):
        blk = await client.post(
            "/api/v1/schedule/blocks",
            json={
                "title": f"Burst block {b}",
                "project_id": pid,
                "start_iso": f"2026-12-10T0{b + 1}:00:00Z",
                "end_iso": f"2026-12-10T0{b + 1}:30:00Z",
                "cadence_window": "deep_tide",
            },
        )
        assert blk.status_code == 201

    await client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    for r in range(3):
        ret = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": "local_fs_read", "target": "README.md", "project_id": pid},
        )
        assert ret.status_code == 200

    snap = (
        await client.get(
            "/api/v1/graph/snapshot",
            params={"lens": "degree_audit", "focus_id": pid, "limit": 500},
        )
    ).json()
    assert snap["metrics"]["invariant_ok"] is True
    assert snap["metrics"]["max_observed_degree"] <= 6
    direct_edges = [e for e in snap["edges"] if e["source"] == pid or e["target"] == pid]
    assert len(direct_edges) <= 6


async def test_t5_bitemporal_breadcrumb_chain_integrity(adv_client) -> None:
    client, _, app = adv_client
    proj = (await client.post("/api/v1/projects", json={"name": "ChainProj"})).json()
    pid = proj["id"]

    ids: list[str] = []
    for idx in range(5):
        resp = await client.post(
            "/api/v1/breadcrumbs",
            json={
                "project_id": pid,
                "last_action": f"Completed step {idx}",
                "next_micro_step": f"Start step {idx + 1}",
            },
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    resumed = (await client.get("/api/v1/momentum/resume", params={"project_id": pid})).json()
    assert resumed["chain_depth"] == 5
    assert resumed["active_breadcrumb"]["id"] == ids[-1]
    assert resumed["active_breadcrumb"]["valid_to"] is None
    assert len(resumed["resume_card"]["card_lines"]) == 3

    all_crumbs = app.state.graph_backend.query_nodes("Breadcrumb", {"project_id": pid})
    active = [c for c in all_crumbs if c.get("properties", c).get("valid_to") is None]
    closed = [c for c in all_crumbs if c.get("properties", c).get("valid_to") is not None]
    assert len(active) == 1
    assert len(closed) == 4


async def test_t5_scheduler_one_second_overlap_adjacency_and_cancel_slot_release(
    adv_client,
) -> None:
    client, _, _ = adv_client
    first = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Anchor Window",
            "start_iso": "2026-12-12T09:00:00Z",
            "end_iso": "2026-12-12T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert first.status_code == 201
    bid = first.json()["id"]

    one_sec_overlap = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "One Sec Conflict",
            "start_iso": "2026-12-12T09:59:59Z",
            "end_iso": "2026-12-12T10:30:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert one_sec_overlap.status_code == 409

    adjacent = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Adjacent Window",
            "start_iso": "2026-12-12T10:00:00Z",
            "end_iso": "2026-12-12T10:45:00Z",
            "cadence_window": "creative_swell",
        },
    )
    assert adjacent.status_code == 201

    cancelled = await client.patch(
        f"/api/v1/schedule/blocks/{bid}",
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200

    reclaimed = await client.post(
        "/api/v1/schedule/blocks",
        json={
            "title": "Reclaimed Window",
            "start_iso": "2026-12-12T09:00:00Z",
            "end_iso": "2026-12-12T10:00:00Z",
            "cadence_window": "deep_tide",
        },
    )
    assert reclaimed.status_code == 201


async def test_t5_offline_worker_and_stub_fallback_safety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_post(*_args: Any, **_kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Local RTX 3060 worker offline")

    async def _failing_get(*_args: Any, **_kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Local RTX 3060 worker offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", _failing_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", _failing_get)

    worker = LocalWorkerClient(
        Settings(graph_mode="inprocess", local_worker_enabled=True),
    )
    classified = await worker.classify_and_extract(
        "Urgent blocker fixing #neo4j latency",
    )
    assert classified.inference_source == "deterministic_fallback"
    assert classified.kind == "blocker"

    lines = await worker.summarize_resume_card(
        project_name="TideFlow",
        last_action="Built Houdini dial",
        next_micro_step="Verify live E2E",
        linked_sparks=["Spark A"],
    )
    assert len(lines) == 3
    assert any("TideFlow" in line or "Built Houdini dial" in line for line in lines)

"""Unit and integration tests for Feature 11 (Permission-Gated Nemoclaw Retriever)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import socket
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.graph.backend import InProcessGraphDriver, RelateGraphDriver
from app.graph.science import GraphScienceService
from app.main import create_app
from app.models.schemas import RetrieverExecuteRequest, RetrieverPermissionsUpdateRequest
from app.services.nemoclaw_retriever import NemoclawRetriever, PermissionDeniedError


def _fixed_clock() -> datetime:
    return datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(params=["inprocess", "relate"])
def graph_backend(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "inprocess":
        driver = InProcessGraphDriver()
        yield driver
        driver.close()
        return

    driver = RelateGraphDriver(db_path=str(tmp_path / "retriever_test.rl"))
    yield driver
    driver.close()


@pytest.fixture
async def api_client(graph_backend, tmp_path: Path):
    settings = Settings(
        graph_mode="inprocess",
        relate_db_path=str(tmp_path / "unused.rl"),
        local_worker_enabled=False,
    )
    app = create_app(settings=settings, graph_backend=graph_backend, clock=_fixed_clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, graph_backend, app


async def test_retriever_startup_permissions_default_deny(api_client) -> None:
    client, _, _ = api_client

    perms = (await client.get("/api/v1/retriever/permissions")).json()
    assert perms["local_fs_read"] is False
    assert perms["repo_git_scan"] is False
    assert perms["web_fetch_public"] is False
    assert perms["local_llm_ollama"] is False
    assert perms["allowed_domains"] == []
    assert len(perms["allowed_paths"]) >= 1

    for cap, target in (
        ("local_fs_read", "README.md"),
        ("repo_git_scan", "."),
        ("web_fetch_public", "https://example.org"),
        ("local_llm_ollama", "Summarize focus"),
    ):
        resp = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": cap, "target": target},
        )
        assert resp.status_code == 403
        assert "\u2014" not in resp.text

    audit = (await client.get("/api/v1/retriever/audit")).json()
    assert len(audit) == 4
    assert all(entry["verdict"] == "DENIED" and entry["decision"] == "DENIED" for entry in audit)

    snap = (await client.get("/api/v1/graph/snapshot")).json()
    assert not any("RetrievalArtifact" in n.get("labels", []) for n in snap["nodes"])


async def test_retriever_partial_and_full_permissions_update(api_client) -> None:
    client, _, _ = api_client

    partial = await client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})
    assert partial.status_code == 200
    body = partial.json()
    assert body["local_fs_read"] is True
    assert body["repo_git_scan"] is False
    assert body["web_fetch_public"] is False
    assert body["local_llm_ollama"] is False

    full = await client.put(
        "/api/v1/retriever/permissions",
        json={
            "local_fs_read": False,
            "repo_git_scan": True,
            "web_fetch_public": False,
            "local_llm_ollama": True,
            "allowed_domains": ["Example.ORG"],
        },
    )
    assert full.status_code == 200
    full_body = full.json()
    assert full_body["local_fs_read"] is False
    assert full_body["repo_git_scan"] is True
    assert full_body["local_llm_ollama"] is True
    assert full_body["allowed_domains"] == ["example.org"]

    invalid = await client.put("/api/v1/retriever/permissions", json={"unknown_flag": True})
    assert invalid.status_code == 422


async def test_retriever_path_security_blocks_traversal_outside_and_sensitive(api_client) -> None:
    client, _, _ = api_client
    await client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})

    blocked_targets = [
        "../../Windows/System32/drivers/etc/hosts",
        "C:\\Windows\\win.ini",
        ".env",
        ".env.production",
        ".git/config",
        ".testmuai/evidence/run.json",
        "secrets/staging.json",
    ]
    for target in blocked_targets:
        resp = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": "local_fs_read", "target": target},
        )
        assert resp.status_code == 403, f"Expected 403 for {target}, got {resp.status_code}"

    missing = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "nonexistent_e2e_file_xyz.md"},
    )
    assert missing.status_code == 404

    audit = (await client.get("/api/v1/retriever/audit")).json()
    assert len(audit) >= len(blocked_targets)
    assert all(e["verdict"] == "DENIED" for e in audit)


async def test_retriever_ssrf_and_unknown_capability_blocked(
    api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _ = api_client
    await client.put("/api/v1/retriever/permissions", json={"web_fetch_public": True})

    for target in (
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8010/api/v1/health",
        "http://localhost:8010/api/v1/health",
        "http://10.0.0.1/admin",
        "http://[::1]:8010/api/v1/health",
        "file:///etc/passwd",
    ):
        resp = await client.post(
            "/api/v1/retriever/execute",
            json={"capability": "web_fetch_public", "target": target},
        )
        assert resp.status_code == 403, f"Expected 403 for {target}, got {resp.status_code}"
        assert "\u2014" not in resp.text

    unknown = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "shell_exec_root", "target": "whoami"},
    )
    assert unknown.status_code == 403

    # DNS resolution returning loopback IP must also be blocked as SSRF
    def _fake_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", int(port or 80)))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    dns_ssrf = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "web_fetch_public", "target": "https://rebind.example.com/data"},
    )
    assert dns_ssrf.status_code == 403


async def test_retriever_local_fs_read_and_repo_git_scan_execution(api_client) -> None:
    client, _, _ = api_client
    await client.put(
        "/api/v1/retriever/permissions",
        json={"local_fs_read": True, "repo_git_scan": True},
    )

    fs_resp = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md"},
    )
    assert fs_resp.status_code == 200
    fs_body = fs_resp.json()
    assert fs_body["verdict"] == "ALLOWED"
    assert "TideFlow" in fs_body["artifact"]["excerpt"]

    git_resp = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "repo_git_scan", "target": "."},
    )
    assert git_resp.status_code == 200
    git_body = git_resp.json()
    assert git_body["verdict"] == "ALLOWED"
    assert git_body["artifact"]["label"] == "RetrievalArtifact"

    audit = (await client.get("/api/v1/retriever/audit")).json()
    assert [e["verdict"] for e in audit[-2:]] == ["ALLOWED", "ALLOWED"]

    snap = (await client.get("/api/v1/graph/snapshot", params={"lens": "pagerank"})).json()
    retrieval_nodes = [n for n in snap["nodes"] if "RetrievalArtifact" in n["labels"]]
    assert len(retrieval_nodes) >= 2


async def test_retriever_web_fetch_redirect_and_domain_allowlist(
    graph_backend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _public_dns(host: str, port: Any, *args: Any, **kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port or 443)))]

    monkeypatch.setattr(socket, "getaddrinfo", _public_dns)

    def _handler(request: httpx.Request) -> httpx.Response:
        if "redirect" in str(request.url):
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/"})
        return httpx.Response(200, text="TideFlow public telemetry ok")

    service = NemoclawRetriever(
        backend=graph_backend,
        science=GraphScienceService(),
        settings=Settings(graph_mode="inprocess", local_worker_enabled=False),
        clock=_fixed_clock,
        http_transport=httpx.MockTransport(_handler),
        repo_root=tmp_path,
    )
    service.update_permissions(
        RetrieverPermissionsUpdateRequest(
            web_fetch_public=True,
            allowed_domains=["example.org"],
        )
    )

    ok_res = await service.execute(
        RetrieverExecuteRequest(capability="web_fetch_public", target="https://example.org/ocean")
    )
    assert ok_res.verdict == "ALLOWED"
    assert "TideFlow public telemetry ok" in ok_res.artifact.excerpt

    with pytest.raises(PermissionDeniedError):
        await service.execute(
            RetrieverExecuteRequest(capability="web_fetch_public", target="https://other.org/ocean")
        )

    with pytest.raises(PermissionDeniedError):
        await service.execute(
            RetrieverExecuteRequest(capability="web_fetch_public", target="https://example.org/redirect")
        )


async def test_retriever_ollama_stub_rejection_and_valid_response(
    graph_backend, tmp_path: Path
) -> None:
    stub_mode = {"stub": True}

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/api/generate"):
            if stub_mode["stub"]:
                return httpx.Response(200, json={"response": "OBELISK_14B_DET_OK <GLYPH:01>"})
            return httpx.Response(200, json={"response": "Focus on one 15-minute graph benchmark."})
        return httpx.Response(503)

    service = NemoclawRetriever(
        backend=graph_backend,
        science=GraphScienceService(),
        settings=Settings(graph_mode="inprocess", local_worker_enabled=True),
        clock=_fixed_clock,
        http_transport=httpx.MockTransport(_handler),
        repo_root=tmp_path,
    )
    service.update_permissions(RetrieverPermissionsUpdateRequest(local_llm_ollama=True))

    res_stub = await service.execute(
        RetrieverExecuteRequest(capability="local_llm_ollama", target="Plan next step")
    )
    assert res_stub.artifact.inference_source == "deterministic_fallback"
    assert "OBELISK_14B_DET_OK" not in res_stub.artifact.excerpt

    stub_mode["stub"] = False
    res_real = await service.execute(
        RetrieverExecuteRequest(capability="local_llm_ollama", target="Plan next step")
    )
    assert res_real.artifact.inference_source == "ollama"
    assert "Focus on one 15-minute graph benchmark." in res_real.artifact.excerpt


async def test_retriever_project_grounding_preserves_hexactine_invariant(api_client) -> None:
    client, _, _ = api_client

    proj = (await client.post("/api/v1/projects", json={"name": "GroundProj"})).json()
    pid = proj["id"]
    for idx in range(6):
        cap = await client.post(
            "/api/v1/thoughts/capture",
            json={"text": f"Thought {idx}", "project_id": pid},
        )
        assert cap.status_code == 201

    await client.put("/api/v1/retriever/permissions", json={"local_fs_read": True})

    missing_proj = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md", "project_id": "proj_missing_xyz"},
    )
    assert missing_proj.status_code == 404

    grounded = await client.post(
        "/api/v1/retriever/execute",
        json={"capability": "local_fs_read", "target": "README.md", "project_id": pid},
    )
    assert grounded.status_code == 200
    body = grounded.json()
    assert body["grounded_edge_id"] is not None

    snap = (
        await client.get(
            "/api/v1/graph/snapshot",
            params={"lens": "degree_audit", "focus_id": pid, "limit": 200},
        )
    ).json()
    assert snap["metrics"]["invariant_ok"] is True
    assert snap["metrics"]["max_observed_degree"] <= 6
    direct_project_edges = [
        e for e in snap["edges"] if e["source"] == pid or e["target"] == pid
    ]
    assert len(direct_project_edges) <= 6

"""Parity and unit tests for Milestone 2 (Dual-Mode Graph & ADD Momentum Engine)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, resolve_cadence_window
from app.graph.backend import (
    BackendUnavailableError,
    InProcessGraphDriver,
    Neo4jGDSDriver,
    RelateGraphDriver,
    create_graph_backend,
)
from app.graph.hsl_bridge import HSLBridge, normalize_spicule_junction
from app.graph.science import GraphScienceService
from app.main import create_app
from app.services.local_worker_client import (
    EMBEDDING_DIM,
    LocalWorkerClient,
    hash_embed_384,
    is_stub_or_invalid_llm_output,
)


class _StepClock:
    def __init__(self, start: datetime) -> None:
        self._current = start

    def __call__(self) -> datetime:
        val = self._current
        self._current = self._current + timedelta(seconds=1)
        return val


@pytest.fixture(params=["inprocess", "relate"])
def graph_backend(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "inprocess":
        driver = InProcessGraphDriver()
        yield driver
        driver.close()
        return

    db_path = tmp_path / "test_tideflow.rl"
    driver = RelateGraphDriver(db_path=str(db_path))
    yield driver
    driver.close()


@pytest.fixture
async def api_client(graph_backend, tmp_path: Path):
    clock = _StepClock(datetime(2026, 11, 19, 9, 30, 0, tzinfo=timezone.utc))
    settings = Settings(
        graph_mode="inprocess",
        relate_db_path=str(tmp_path / "unused.rl"),
        local_worker_enabled=False,
    )
    app = create_app(settings=settings, graph_backend=graph_backend, clock=clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, graph_backend, app


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (6, "deep_tide"),
        (11, "deep_tide"),
        (12, "creative_swell"),
        (15, "creative_swell"),
        (16, "shallow_drift"),
        (20, "shallow_drift"),
        (21, "recovery_ebb"),
        (3, "recovery_ebb"),
    ],
)
def test_canonical_cadence_windows(hour: int, expected: str) -> None:
    dt = datetime(2026, 11, 19, hour, 15, 0, tzinfo=timezone.utc)
    assert resolve_cadence_window(dt) == expected


async def test_health_and_project_crud_parity(api_client) -> None:
    client, backend, _ = api_client
    health_resp = await client.get("/api/v1/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health["status"] == "ok"
    assert health["backend_mode"] == backend.backend_name
    assert health["degree_invariant_max"] == 6
    assert health["active_cadence"] == "deep_tide"
    assert health["local_worker_available"] is False

    create_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Kelp Telemetry Grid",
            "description": "Coastal CTD sensor dashboard",
            "cadence_preference": "deep_tide",
            "priority": 5,
            "tags": ["telemetry", "graph"],
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Kelp Telemetry Grid"
    assert created["priority"] == 5
    assert created["tags"] == ["telemetry", "graph"]
    assert created["degree"] == 2

    list_resp = await client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]


async def test_thought_capture_classification_and_overwhelm_warning(api_client) -> None:
    client, _, _ = api_client
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "TideFlow Core", "tags": ["graph"]},
    )
    proj_id = proj_resp.json()["id"]

    t1 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Implement pagerank lens endpoint #graph", "project_id": proj_id},
    )
    assert t1.status_code == 201
    d1 = t1.json()
    assert d1["thought"]["kind"] == "project_task"
    assert d1["thought"]["status"] == "now"
    assert "graph" in d1["linked_tags"]
    assert d1["active_wip_count"] == 1
    assert d1["overwhelm_warning"] is False

    t2 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Blocked on Neo4j Bolt port failing locally", "project_id": proj_id},
    )
    assert t2.json()["thought"]["kind"] == "blocker"
    assert t2.json()["thought"]["status"] == "next"

    t3 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Visual bioluminescent pulse concept", "project_id": proj_id},
    )
    assert t3.json()["thought"]["kind"] == "spark_idea"
    assert t3.json()["active_wip_count"] == 3
    assert t3.json()["overwhelm_warning"] is False

    # Unlinked side_quest should auto-park without raising WIP
    sq = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Side quest explore WebGPU fluid shaders"},
    )
    assert sq.json()["thought"]["kind"] == "side_quest"
    assert sq.json()["thought"]["status"] == "parked"
    assert sq.json()["active_wip_count"] == 3

    # 4th active WIP item triggers overwhelm_warning
    t4 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Write unit tests for triage horizon", "project_id": proj_id},
    )
    assert t4.json()["active_wip_count"] == 4
    assert t4.json()["overwhelm_warning"] is True
    assert "triage" in (t4.json()["overwhelm_message"] or "").lower()


async def test_park_and_promote_slot_transitions(api_client) -> None:
    client, _, _ = api_client
    r1 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Build scheduler crud routes"},
    )
    th1_id = r1.json()["thought"]["id"]
    assert r1.json()["thought"]["status"] == "now"

    r2 = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Side quest explore shader ripples", "auto_park": True},
    )
    th2_id = r2.json()["thought"]["id"]
    assert r2.json()["thought"]["status"] == "parked"

    promo = await client.post(
        f"/api/v1/thoughts/{th2_id}/promote",
        json={"target_slot": "now"},
    )
    assert promo.status_code == 200
    pdata = promo.json()
    assert pdata["thought"]["status"] == "now"
    assert pdata["demoted_thought_id"] == th1_id

    parked = await client.post(
        f"/api/v1/thoughts/{th2_id}/park",
        json={"reason": "defer_until_creative_swell"},
    )
    assert parked.status_code == 200
    assert parked.json()["thought"]["status"] == "parked"
    assert parked.json()["thought"]["park_reason"] == "defer_until_creative_swell"


async def test_hexactine_degree_invariant_subhub_overflow(api_client) -> None:
    client, _, _ = api_client
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Hexactine Lattice Hub", "tags": ["hexactine", "sponge"]},
    )
    proj_id = proj_resp.json()["id"]

    routed_flags: list[bool] = []
    for idx in range(12):
        resp = await client.post(
            "/api/v1/thoughts/capture",
            json={
                "text": f"Implement hexactine ray task {idx} #hexactine",
                "project_id": proj_id,
            },
        )
        assert resp.status_code == 201
        routed_flags.append(resp.json()["routed_via_subhub"])

    assert any(routed_flags), "Expected subhub overflow routing once degree >= 5"

    snap_resp = await client.get(
        f"/api/v1/graph/snapshot?lens=degree_audit&focus_id={proj_id}"
    )
    assert snap_resp.status_code == 200
    snap = snap_resp.json()
    metrics = snap["metrics"]
    assert metrics["invariant_ok"] is True
    assert metrics["max_observed_degree"] <= 6
    assert metrics["degree_violations"] == []
    assert metrics["sub_hub_count"] >= 1

    proj_get = await client.get(f"/api/v1/projects/{proj_id}")
    assert proj_get.status_code == 200
    assert proj_get.json()["active_wip_count"] == 12
    assert proj_get.json()["degree"] <= 6


async def test_bitemporal_breadcrumb_supersedes_and_resume_card(api_client) -> None:
    client, backend, _ = api_client
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Momentum Recovery", "tags": ["momentum"]},
    )
    proj_id = proj_resp.json()["id"]
    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Wire 3-line resume card #momentum", "project_id": proj_id},
    )

    bc1 = (
        await client.post(
            "/api/v1/breadcrumbs",
            json={
                "project_id": proj_id,
                "last_action": "Defined Pydantic schemas",
                "next_micro_step": "Write RelateGraphDriver",
            },
        )
    ).json()
    bc2 = (
        await client.post(
            "/api/v1/breadcrumbs",
            json={
                "project_id": proj_id,
                "last_action": "Implemented RelateGraphDriver",
                "next_micro_step": "Implement PageRank",
            },
        )
    ).json()
    bc3 = (
        await client.post(
            "/api/v1/breadcrumbs",
            json={
                "project_id": proj_id,
                "last_action": "Implemented PageRank",
                "next_micro_step": "Run dual-driver parity suite",
            },
        )
    ).json()

    assert bc2["supersedes_id"] == bc1["id"]
    assert bc3["supersedes_id"] == bc2["id"]

    stored_bc1 = backend.get_node(bc1["id"])
    stored_bc2 = backend.get_node(bc2["id"])
    assert stored_bc1 is not None
    assert stored_bc2 is not None
    assert stored_bc1["properties"]["closed_at"] is not None
    assert stored_bc1["properties"]["valid_to"] is not None
    assert stored_bc2["properties"]["closed_at"] is not None

    supersedes_edges = backend.get_edges(rel_type="SUPERSEDES")
    assert len(supersedes_edges) == 2

    resume_resp = await client.get(f"/api/v1/momentum/resume?project_id={proj_id}")
    assert resume_resp.status_code == 200
    resume = resume_resp.json()
    assert resume["chain_depth"] == 3
    assert resume["active_breadcrumb"]["id"] == bc3["id"]
    assert len(resume["resume_card"]["card_lines"]) == 3
    assert resume["path_bridge"]["found"] is True
    assert resume["project"]["degree"] <= 6


async def test_triage_sweep_enforces_3_slot_focus_horizon(api_client) -> None:
    client, _, _ = api_client
    proj_id = (
        await client.post("/api/v1/projects", json={"name": "Horizon Test"})
    ).json()["id"]

    texts = [
        ("Side quest check aquarium cams", "side_quest"),
        ("Spark idea about bioluminescent dials", "spark_idea"),
        ("Implement core graph snapshot route", "project_task"),
        ("Blocked on broken auth middleware", "blocker"),
        ("Write pytest fixture parity checks", "project_task"),
        ("Maybe later tune cosine weights", "side_quest"),
    ]
    for txt, kind in texts:
        await client.post(
            "/api/v1/thoughts/capture",
            json={"text": txt, "kind": kind, "project_id": proj_id},
        )

    sweep_resp = await client.post(
        "/api/v1/triage/sweep",
        json={"project_id": proj_id},
    )
    assert sweep_resp.status_code == 200
    sweep = sweep_resp.json()
    assert len(sweep["now"]) == 1
    assert len(sweep["next"]) == 2
    assert sweep["parked_count"] == 3
    assert len(sweep["newly_parked_ids"]) == 3
    assert sweep["now"][0]["kind"] in {"blocker", "project_task"}
    assert all(item["kind"] != "side_quest" for item in sweep["now"] + sweep["next"])
    assert 0.0 <= sweep["overwhelm_index"] <= 1.0


async def test_graph_science_pagerank_communities_shortest_path_and_gds_preview(
    api_client,
) -> None:
    client, _, _ = api_client
    p1 = (
        await client.post(
            "/api/v1/projects",
            json={"name": "Project Alpha", "tags": ["graph"]},
        )
    ).json()["id"]
    p2 = (
        await client.post(
            "/api/v1/projects",
            json={"name": "Project Beta", "tags": ["graph"]},
        )
    ).json()["id"]

    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Implement shared graph index #graph", "project_id": p1},
    )

    pr_snap = (await client.get("/api/v1/graph/snapshot?lens=pagerank")).json()
    total_pr = sum(n["pagerank"] for n in pr_snap["nodes"])
    assert 0.95 <= total_pr <= 1.05
    assert "gds.graph.project" in pr_snap["gds_cypher_preview"]
    assert "gds.pageRank.stream" in pr_snap["gds_cypher_preview"]

    comm_snap = (await client.get("/api/v1/graph/snapshot?lens=communities")).json()
    cids = {n["community_id"] for n in comm_snap["nodes"]}
    assert min(cids) == 0
    assert max(cids) == len(cids) - 1
    assert "gds.leiden.stream" in comm_snap["gds_cypher_preview"]

    path_resp = (
        await client.get(f"/api/v1/graph/path?source_id={p1}&target_id={p2}")
    ).json()
    assert path_resp["found"] is True
    assert path_resp["node_ids"][0] == p1
    assert path_resp["node_ids"][-1] == p2
    assert "tag_graph" in path_resp["node_ids"]
    assert "gds.shortestPath.dijkstra.stream" in path_resp["gds_cypher_preview"]


async def test_error_handling_and_input_validation(api_client) -> None:
    client, backend, _ = api_client
    missing_cap = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Orphan target", "project_id": "proj_missing_999"},
    )
    assert missing_cap.status_code == 404

    missing_bc = await client.post(
        "/api/v1/breadcrumbs",
        json={
            "project_id": "proj_missing_999",
            "last_action": "a",
            "next_micro_step": "b",
        },
    )
    assert missing_bc.status_code == 404

    missing_resume = await client.get("/api/v1/momentum/resume?project_id=missing")
    assert missing_resume.status_code == 404

    bad_lens = await client.get("/api/v1/graph/snapshot?lens=invalid_lens")
    assert bad_lens.status_code == 422

    bad_energy = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Too much energy", "energy_cost": 99},
    )
    assert bad_energy.status_code == 422

    with pytest.raises(ValueError):
        backend.upsert_node("Bad-Label; DROP", {"id": "x1"})


async def test_driver_output_parity_cross_check(tmp_path: Path) -> None:
    async def run_scenario(driver) -> dict[str, Any]:
        clock = _StepClock(datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc))
        settings = Settings(local_worker_enabled=False)
        app = create_app(settings=settings, graph_backend=driver, clock=clock)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            p1 = (
                await client.post(
                    "/api/v1/projects",
                    json={"name": "Parity One", "tags": ["parity"]},
                )
            ).json()["id"]
            p2 = (
                await client.post(
                    "/api/v1/projects",
                    json={"name": "Parity Two", "tags": ["parity"]},
                )
            ).json()["id"]
            for i in range(5):
                await client.post(
                    "/api/v1/thoughts/capture",
                    json={
                        "text": f"Implement parity check {i} #parity",
                        "project_id": p1,
                    },
                )
            await client.post(
                "/api/v1/breadcrumbs",
                json={
                    "project_id": p1,
                    "last_action": "Step A",
                    "next_micro_step": "Step B",
                },
            )
            sweep = (await client.post("/api/v1/triage/sweep")).json()
            snap = (await client.get("/api/v1/graph/snapshot?lens=pagerank")).json()
            path = (
                await client.get(f"/api/v1/graph/path?source_id={p1}&target_id={p2}")
            ).json()
            return {
                "top_pagerank_prefixes": [
                    nid.rsplit("_", 1)[0] if "_" in nid and nid != "tag_parity" and not nid.startswith("hub_") else nid
                    for nid in snap["metrics"]["top_pagerank_ids"]
                ],
                "top_pagerank_scores": sorted(
                    round(n["pagerank"], 6) for n in snap["nodes"]
                ),
                "community_count": snap["metrics"]["community_count"],
                "modularity": snap["metrics"]["modularity"],
                "invariant_ok": snap["metrics"]["invariant_ok"],
                "path_found": path["found"],
                "path_hops": path["hop_count"],
                "sweep_now_kind": sweep["now"][0]["kind"],
                "sweep_next_count": len(sweep["next"]),
                "sweep_parked_count": sweep["parked_count"],
            }

    inproc = InProcessGraphDriver()
    rel = RelateGraphDriver(db_path=str(tmp_path / "parity.rl"))
    try:
        res_inproc = await run_scenario(inproc)
        res_relate = await run_scenario(rel)
    finally:
        inproc.close()
        rel.close()

    assert res_inproc == res_relate


def test_hsl_bridge_dual_schema_and_seeding() -> None:
    cfg = Settings.from_env()
    bridge = HSLBridge(cfg.hsl_bridge_config_path, cfg.agentsea_manifest_path)
    summary = bridge.summary()
    if bridge.loaded and summary.spicule_count > 0:
        assert summary.read_only is True
        assert summary.degree_invariant_max == 6
        assert summary.schema_a_count >= 1
        assert summary.schema_b_count >= 1
        assert summary.squad_count >= 5

    # Explicit unit test of both spicule schemas
    schema_a = normalize_spicule_junction(
        {
            "spicule_id": "sp_a",
            "proposition": "Anchor lattice",
            "harmonic_integral_score": 0.95,
            "conductor": {"lead": "ZEPHYR"},
            "hexactine_rays": {
                "+x_CORROBORATES": {"summary": "Verified"},
                "-x_CONTRADICTS": {"summary": ""},
            },
        }
    )
    schema_b = normalize_spicule_junction(
        {
            "spicule_id": "sp_b",
            "topic": "Salish Survey",
            "lead_agent": "ZEPHYR",
            "epistemic_score": 0.92,
            "+x": ["Squad allocated"],
            "-x": [],
            "+z": ["TEOS-10"],
        }
    )
    assert schema_a["schema_variant"] == "schema_a_hexactine_rays"
    assert schema_a["rays"]["+x"] == ["Verified"]
    assert schema_b["schema_variant"] == "schema_b_flat_rays"
    assert schema_b["rays"]["+z"] == ["TEOS-10"]

    driver = InProcessGraphDriver()
    science = GraphScienceService(degree_invariant_max=6)
    bridge.seed_into_graph(driver, science_service=science, max_junctions=4)
    snap = science.build_snapshot(driver, lens="degree_audit")
    assert snap.metrics.invariant_ok is True
    assert snap.metrics.max_observed_degree <= 6


async def test_local_worker_client_stub_rejection_and_offline_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert is_stub_or_invalid_llm_output("<GLYPH:ok> OBELISK_14B_DET_OK len=42") is True
    assert is_stub_or_invalid_llm_output('{"kind": "blocker"}') is False

    v1 = hash_embed_384("hexactine ocean graph")
    v2 = hash_embed_384("hexactine ocean graph")
    assert len(v1) == EMBEDDING_DIM
    assert v1 == v2

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            return _FakeResponse(200, {"status": "ok"})

        async def post(self, url: str, json: dict[str, Any]):
            if "11434" in url:
                raise httpx.ConnectError("offline")
            if "chat/completions" in url:
                return _FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "<GLYPH:det> OBELISK_14B_DET_OK len=12"
                                }
                            }
                        ]
                    },
                )
            if "rerank" in url:
                docs = json.get("documents", [])
                return _FakeResponse(
                    200,
                    {
                        "results": [
                            {"index": 0, "score": 0.85, "document": docs[0]}
                        ]
                    },
                )
            return _FakeResponse(404, {})

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    settings = Settings(local_worker_enabled=True)
    client = LocalWorkerClient(settings)
    classified = await client.classify_and_extract(
        "Blocked on Neo4j Bolt connection timeout"
    )
    assert classified.kind == "blocker"
    assert "OBELISK_14B_DET_OK" not in classified.suggested_micro_step
    assert "graph" in classified.concept_tags


def test_neo4j_gds_driver_fast_fail_and_fallback(tmp_path: Path) -> None:
    with pytest.raises(BackendUnavailableError) as exc_info:
        Neo4jGDSDriver(
            uri="bolt://127.0.0.1:17687",
            user="neo4j",
            password="super_secret_do_not_leak",
            connection_timeout=0.3,
        )
    assert "super_secret_do_not_leak" not in str(exc_info.value)

    cfg = Settings(
        graph_mode="neo4j",
        neo4j_uri="bolt://127.0.0.1:17687",
        relate_db_path=str(tmp_path / "fallback.rl"),
    )
    backend = create_graph_backend(cfg)
    assert backend.backend_name in {"relate", "inprocess"}
    backend.close()


def test_relate_cli_subprocess_fallback_in_tmp_path(tmp_path: Path) -> None:
    db_path = tmp_path / "cli_fallback.rl"
    driver = RelateGraphDriver(db_path=str(db_path), prefer_cli=True)
    n1 = driver.upsert_node("Project", {"id": "p_cli", "name": "CLI Parity", "priority": 2})
    n2 = driver.upsert_node("ConceptTag", {"id": "tag_cli", "key": "cli", "name": "cli"})
    edge = driver.upsert_edge(n1["id"], "TAGGED_WITH", n2["id"], {"weight": 1.0})
    assert edge["rel_type"] == "TAGGED_WITH"
    nodes, edges = driver.get_subgraph(focus_id="p_cli", limit=50)
    assert len(nodes) == 2
    assert len(edges) == 1
    driver.close()


def test_query_nodes_filter_before_limit_parity(tmp_path: Path) -> None:
    inproc = InProcessGraphDriver()
    rel = RelateGraphDriver(db_path=str(tmp_path / "filter_limit.rl"))
    try:
        for drv in (inproc, rel):
            for idx in range(1, 6):
                drv.upsert_node(
                    "Thought",
                    {
                        "id": f"th_{idx:02d}",
                        "status": "now" if idx >= 4 else "next",
                    },
                )
        r_inproc = inproc.query_nodes("Thought", {"status": "now"}, limit=1)
        r_rel = rel.query_nodes("Thought", {"status": "now"}, limit=1)
        assert len(r_inproc) == 1
        assert r_inproc[0]["id"] == "th_04"
        assert r_rel == r_inproc
    finally:
        inproc.close()
        rel.close()


def test_relate_persistence_across_close_and_reopen(tmp_path: Path) -> None:
    db_path = str(tmp_path / "persist_reopen.rl")
    d1 = RelateGraphDriver(db_path=db_path)
    d1.upsert_node("Project", {"id": "proj_persist", "name": "Persistent Reef", "priority": 4})
    d1.upsert_node("Thought", {"id": "th_persist", "text": "Keep node after reopen", "status": "now"})
    d1.upsert_edge("th_persist", "BELONGS_TO", "proj_persist", {"weight": 1.0})
    d1.close()

    d2 = RelateGraphDriver(db_path=db_path)
    try:
        proj = d2.get_node("proj_persist")
        thought = d2.get_node("th_persist")
        edges = d2.get_edges(node_id="th_persist", rel_type="BELONGS_TO", direction="out")
        assert proj is not None
        assert proj["properties"]["name"] == "Persistent Reef"
        assert thought is not None
        assert thought["properties"]["status"] == "now"
        assert len(edges) == 1
        assert edges[0]["target"] == "proj_persist"
    finally:
        d2.close()


async def test_whitespace_validation_and_breadcrumb_alias(api_client) -> None:
    client, _, _ = api_client

    ws_proj = await client.post("/api/v1/projects", json={"name": "   \t\n  "})
    assert ws_proj.status_code == 422

    ws_thought = await client.post("/api/v1/thoughts/capture", json={"text": "   \t\n  "})
    assert ws_thought.status_code == 422

    proj_id = (
        await client.post("/api/v1/projects", json={"name": "Alias Validation Hub"})
    ).json()["id"]

    ws_bc_last = await client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": proj_id, "last_action": "   ", "next_micro_step": "ok"},
    )
    assert ws_bc_last.status_code == 422

    ws_bc_next = await client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": proj_id, "last_action": "ok", "next_step": " \n\t "},
    )
    assert ws_bc_next.status_code == 422

    ws_bc_pid = await client.post(
        "/api/v1/breadcrumbs",
        json={"project_id": "   ", "last_action": "ok", "next_micro_step": "step"},
    )
    assert ws_bc_pid.status_code == 422

    extra_bc = await client.post(
        "/api/v1/breadcrumbs",
        json={
            "project_id": proj_id,
            "last_action": "ok",
            "next_step": "step",
            "unknown_extra": True,
        },
    )
    assert extra_bc.status_code == 422

    bc_micro = await client.post(
        "/api/v1/breadcrumbs",
        json={
            "project_id": proj_id,
            "last_action": "Started check",
            "next_micro_step": "Verify micro step",
        },
    )
    assert bc_micro.status_code == 201
    assert bc_micro.json()["next_micro_step"] == "Verify micro step"

    bc_alias = await client.post(
        "/api/v1/breadcrumbs",
        json={
            "project_id": proj_id,
            "last_action": "Sent next_step alias",
            "next_step": "Confirm 201 alias support",
        },
    )
    assert bc_alias.status_code == 201
    assert bc_alias.json()["next_micro_step"] == "Confirm 201 alias support"
    assert bc_alias.json()["supersedes_id"] == bc_micro.json()["id"]


def test_startup_seeding_idempotency_via_lifespan(tmp_path: Path) -> None:
    db_path = str(tmp_path / "seed_lifespan.rl")
    cfg = Settings(
        graph_mode="relate",
        relate_db_path=db_path,
        local_worker_enabled=False,
        seed_default_project=True,
    )

    app1 = create_app(settings=cfg)
    with TestClient(app1) as client1:
        projects1 = client1.get("/api/v1/projects").json()
        assert len(projects1) == 1
        assert projects1[0]["name"] == "TideFlow Hexactine Cockpit"
        assert projects1[0]["status"] == "active"
        snap1 = client1.get("/api/v1/graph/snapshot?lens=degree_audit").json()
        assert len(snap1["nodes"]) >= 1

    app2 = create_app(settings=cfg)
    with TestClient(app2) as client2:
        projects2 = client2.get("/api/v1/projects").json()
        assert len(projects2) == 1
        assert projects2[0]["id"] == projects1[0]["id"]


def test_hsl_bridge_seed_into_graph_idempotency() -> None:
    cfg = Settings.from_env()
    bridge = HSLBridge(cfg.hsl_bridge_config_path, cfg.agentsea_manifest_path)
    driver = InProcessGraphDriver()
    science = GraphScienceService(degree_invariant_max=6)

    first = bridge.seed_into_graph(driver, science_service=science, max_junctions=4)
    nodes_after_1 = len(driver.get_subgraph(limit=1000)[0])
    edges_after_1 = len(driver.get_edges(limit=5000))

    second = bridge.seed_into_graph(driver, science_service=science, max_junctions=4)
    nodes_after_2 = len(driver.get_subgraph(limit=1000)[0])
    edges_after_2 = len(driver.get_edges(limit=5000))

    assert nodes_after_1 == nodes_after_2
    assert edges_after_1 == edges_after_2
    assert second["edges_seeded"] == 0
    if bridge.loaded and bridge.get_normalized_junctions():
        assert first["edges_seeded"] >= 1
    snap = science.build_snapshot(driver, lens="degree_audit")
    assert snap.metrics.invariant_ok is True


async def test_local_worker_word_boundaries_resume_offload_and_full_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offline_client = LocalWorkerClient(Settings(local_worker_enabled=False))

    # Word-boundary precision: "build" != "ui", "rapid" != "api", "padding" != "add", "relationship" != "ship"
    c_build = await offline_client.classify_and_extract("Build scheduler crud routes")
    assert c_build.kind == "project_task"
    assert "ui" not in c_build.concept_tags
    assert "scheduler" in c_build.concept_tags

    c_false_pos = await offline_client.classify_and_extract(
        "Rapid padding relationship suffix"
    )
    assert c_false_pos.kind == "spark_idea"
    assert "api" not in c_false_pos.concept_tags

    # All 3 ports offline with local_worker_enabled=True -> deterministic_fallback + embed fallback + summarize fallback
    class _AlwaysOfflineClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs.get("trust_env") is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            raise httpx.ConnectError("offline")

        async def post(self, url: str, json: dict[str, Any]):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "AsyncClient", _AlwaysOfflineClient)
    enabled_client = LocalWorkerClient(Settings(local_worker_enabled=True))
    res_offline = await enabled_client.classify_and_extract(
        "Implement graph router #customtag"
    )
    assert res_offline.inference_source == "deterministic_fallback"
    assert "customtag" in res_offline.concept_tags

    vecs, emb_src = await enabled_client.embed(["tidal rhythm"])
    assert emb_src == "deterministic_fallback"
    assert len(vecs) == 1 and len(vecs[0]) == EMBEDDING_DIM

    cards_offline = await enabled_client.summarize_resume_card(
        "Reef", "Built router", "Run tests", ["Spark A"]
    )
    assert len(cards_offline) == 3
    assert cards_offline[0].startswith("Last (Reef):")

    # Ollama valid JSON for classify (with markdown fences, non-int energy_cost, hashtag merge) and summarize_resume_card
    class _FakeResp:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class _MockOllamaAndStubChatClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs.get("trust_env") is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, json: dict[str, Any]):
            prompt = str(json.get("prompt") or "")
            if "11434" in url and "card_lines" in prompt:
                return _FakeResp(
                    200,
                    {
                        "response": (
                            '```json\n{"card_lines": ['
                            '"Last (Reef): Shipped graph routes",'
                            '"Next: Run parity suite",'
                            '"Sparks: Spark A"'
                            "]}\n```"
                        )
                    },
                )
            if "11434" in url:
                return _FakeResp(
                    200,
                    {
                        "response": (
                            '```json\n{"kind": "project_task", "energy_cost": "high", '
                            '"concept_tags": ["graph"], '
                            '"suggested_micro_step": "Verify route"}\n```'
                        )
                    },
                )
            return _FakeResp(404, {})

    monkeypatch.setattr(httpx, "AsyncClient", _MockOllamaAndStubChatClient)
    llm_cls = await enabled_client.classify_and_extract(
        "Check routes #tidal"
    )
    assert llm_cls.inference_source == "ollama"
    assert llm_cls.energy_cost == 2
    assert "tidal" in llm_cls.concept_tags
    assert "graph" in llm_cls.concept_tags

    cards_ollama = await enabled_client.summarize_resume_card(
        "Reef", "Shipped graph routes", "Run parity suite", ["Spark A"]
    )
    assert cards_ollama == [
        "Last (Reef): Shipped graph routes",
        "Next: Run parity suite",
        "Sparks: Spark A",
    ]

    # Stub rejection in summarize_resume_card
    class _StubOnlyClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, json: dict[str, Any]):
            if "11434" in url:
                raise httpx.ConnectError("offline")
            return _FakeResp(
                200,
                {
                    "choices": [
                        {"message": {"content": "<GLYPH:det> OBELISK_14B_DET_OK len=22"}}
                    ]
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", _StubOnlyClient)
    cards_stub_rejected = await enabled_client.summarize_resume_card(
        "Reef", "Action", "Micro", []
    )
    assert len(cards_stub_rejected) == 3
    assert all("OBELISK_14B_DET_OK" not in line for line in cards_stub_rejected)


async def test_cross_project_triage_sweep_global_now_uniqueness_and_routes(
    api_client,
) -> None:
    client, backend, _ = api_client
    p_a = (await client.post("/api/v1/projects", json={"name": "Project A", "tags": ["a"]})).json()["id"]
    p_b = (await client.post("/api/v1/projects", json={"name": "Project B", "tags": ["b"]})).json()["id"]

    # First thought on Project A claims global "now"
    th_a = (
        await client.post(
            "/api/v1/thoughts/capture",
            json={"text": "Implement A core task", "kind": "project_task", "project_id": p_a},
        )
    ).json()["thought"]
    assert th_a["status"] == "now"

    # Capture task on Project B (gets "next")
    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Blocked on B setup", "kind": "blocker", "project_id": p_b},
    )

    # Triage sweep on Project B must demote Project A's "now" so global Now <= 1
    sweep_b = await client.post("/api/v1/triage/sweep", json={"project_id": p_b})
    assert sweep_b.status_code == 200
    assert len(sweep_b.json()["now"]) == 1

    all_now = (await client.get("/api/v1/thoughts?status=now")).json()
    assert len(all_now) == 1
    assert all_now[0]["project_id"] == p_b

    # Unknown project_id in triage_sweep returns 404
    missing_sweep = await client.post("/api/v1/triage/sweep", json={"project_id": "proj_missing"})
    assert missing_sweep.status_code == 404

    # GET /api/v1/thoughts filters
    b_blockers = (
        await client.get(f"/api/v1/thoughts?project_id={p_b}&kind=blocker")
    ).json()
    assert len(b_blockers) == 1

    # Disconnected shortest path and self-path
    disc_path = (
        await client.get(f"/api/v1/graph/path?source_id={p_a}&target_id={p_b}")
    ).json()
    assert disc_path["found"] is False

    self_path = (
        await client.get(f"/api/v1/graph/path?source_id={p_a}&target_id={p_a}")
    ).json()
    assert self_path["found"] is True
    assert self_path["hop_count"] == 0

    # Snapshot with lens=path
    snap_path = (
        await client.get(f"/api/v1/graph/snapshot?lens=path&focus_id={p_a}&target_id={th_a['id']}")
    )
    assert snap_path.status_code == 200
    assert snap_path.json()["active_path"]["found"] is True

    # GET /api/v1/graph/hsl and idempotent POST /api/v1/graph/hsl/seed
    hsl_get = await client.get("/api/v1/graph/hsl")
    assert hsl_get.status_code == 200
    seed_1 = await client.post("/api/v1/graph/hsl/seed?max_junctions=4")
    assert seed_1.status_code == 200
    edge_count_1 = len(backend.get_edges(limit=5000))
    seed_2 = await client.post("/api/v1/graph/hsl/seed?max_junctions=4")
    assert seed_2.status_code == 200
    assert seed_2.json()["edges_seeded"] == 0
    assert len(backend.get_edges(limit=5000)) == edge_count_1


def test_science_edge_cases_weights_quotes_and_subhub() -> None:
    science = GraphScienceService(degree_invariant_max=6)
    nodes = [{"id": "n1", "labels": ["Project"], "properties": {}}, {"id": "n2", "labels": ["Thought"], "properties": {}}]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2", "rel_type": "LINKS", "properties": {"weight": None}},
        {"id": "e2", "source": "n2", "target": "n1", "rel_type": "LINKS", "properties": {"weight": "bad"}},
    ]
    raw_pr, norm_pr = science.compute_pagerank(nodes, edges)
    assert abs(sum(raw_pr.values()) - 1.0) < 1e-4
    assert set(norm_pr.keys()) == {"n1", "n2"}

    cypher = science.gds_cypher_preview("path", source_id="a'b", target_id="c'd")
    assert "a\\'b" in cypher
    assert "c\\'d" in cypher

    # Anchorless / externally saturated capped node still obeys deg <= 6 cleanly
    drv = InProcessGraphDriver()
    drv.upsert_node("Project", {"id": "p_sat", "name": "Saturated"})
    for i in range(6):
        tid = f"th_ext_{i}"
        drv.upsert_node("Thought", {"id": tid, "text": f"t{i}"})
        drv.upsert_edge(tid, "BELONGS_TO", "p_sat", {"weight": 1.0})

    drv.upsert_node("Thought", {"id": "th_extra", "text": "overflow"})
    edge, routed, subhub = science.link_with_hexactine_invariant(
        drv, "th_extra", "BELONGS_TO", "p_sat"
    )
    assert routed is True
    assert subhub is not None
    assert drv.get_node_degree("p_sat") == 6
    assert edge["rel_type"] == "ROUTED_THROUGH"


async def test_breadcrumb_multi_close_and_resume_sparks_priority(api_client) -> None:
    client, backend, app = api_client
    proj = (
        await client.post("/api/v1/projects", json={"name": "Spark Priority"})
    ).json()
    pid = proj["id"]

    # Seed two pre-existing unclosed breadcrumbs directly in graph store
    backend.upsert_node(
        "Breadcrumb",
        {
            "id": "bc_old_1",
            "project_id": pid,
            "last_action": "Old 1",
            "next_micro_step": "Step 1",
            "recorded_at": "2026-11-19T08:00:00+00:00",
            "closed_at": None,
        },
    )
    backend.upsert_node(
        "Breadcrumb",
        {
            "id": "bc_old_2",
            "project_id": pid,
            "last_action": "Old 2",
            "next_micro_step": "Step 2",
            "recorded_at": "2026-11-19T08:05:00+00:00",
            "closed_at": None,
        },
    )

    bc_new = (
        await client.post(
            "/api/v1/breadcrumbs",
            json={
                "project_id": pid,
                "last_action": "Consolidated",
                "next_step": "Continue",
            },
        )
    ).json()
    assert bc_new["supersedes_id"] == "bc_old_2"
    assert backend.get_node("bc_old_1")["properties"]["closed_at"] is not None
    assert backend.get_node("bc_old_2")["properties"]["closed_at"] is not None

    # Capture older thought, mark done, then capture newer active thoughts
    th_done = (
        await client.post(
            "/api/v1/thoughts/capture",
            json={"text": "Done older item", "project_id": pid},
        )
    ).json()["thought"]["id"]
    backend.upsert_node("Thought", {"id": th_done, "status": "done"})

    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "First active spark", "project_id": pid},
    )
    await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Latest active spark", "project_id": pid},
    )

    resume = (await client.get(f"/api/v1/momentum/resume?project_id={pid}")).json()
    sparks = resume["resume_card"]["linked_sparks"]
    assert "Done older item" not in sparks
    assert sparks[0] == "Latest active spark"


def test_neo4j_query_nodes_filter_before_limit_cypher() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeNeo4jDriver:
        def execute_query(self, cypher: str, parameters_: dict[str, Any], database_: str):
            calls.append((cypher, dict(parameters_)))
            rows = [
                {"id": "th_01", "labels": ["Thought", "TideNode"], "props": {"id": "th_01", "status": "next"}},
                {"id": "th_02", "labels": ["Thought", "TideNode"], "props": {"id": "th_02", "status": "now"}},
            ]
            return rows, None, None

    drv = Neo4jGDSDriver.__new__(Neo4jGDSDriver)
    drv.uri = "bolt://127.0.0.1:7687"
    drv.database = "neo4j"
    drv._driver = _FakeNeo4jDriver()

    res = drv.query_nodes("Thought", {"status": "now"}, limit=1)
    assert len(res) == 1
    assert res[0]["id"] == "th_02"
    assert "LIMIT" not in calls[0][0]


async def test_local_worker_classify_normalizes_concept_tags_and_infinite_energy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload_queue: list[dict[str, Any]] = [
        {
            "kind": "spark_idea",
            "concept_tags": 123,
            "energy_cost": float("inf"),
            "suggested_micro_step": "Sketch node layout",
        },
        {
            "kind": "project_task",
            "concept_tags": "graph, neo4j , ",
            "energy_cost": 4,
            "suggested_micro_step": "Run graph query",
        },
    ]

    class _FakeResp:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.status_code = 200
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, json: dict[str, Any]):
            if "11434" in url:
                return _FakeResp({"response": globals_json_dumps(payload_queue.pop(0))})
            return _FakeResp({})

    globals_json_dumps = json.dumps
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    client = LocalWorkerClient(Settings(local_worker_enabled=True))

    res_scalar = await client.classify_and_extract("Quick spark without hashtags")
    assert res_scalar.inference_source == "ollama"
    assert res_scalar.kind == "spark_idea"
    assert res_scalar.concept_tags == ["spark_idea"]
    assert res_scalar.energy_cost == 2

    res_csv = await client.classify_and_extract("Inspect schema links")
    assert res_csv.inference_source == "ollama"
    assert res_csv.kind == "project_task"
    assert res_csv.concept_tags == ["graph", "neo4j"]
    assert res_csv.energy_cost == 4


async def test_promote_thought_404_preserves_existing_now_slot(api_client) -> None:
    client, backend, _ = api_client
    first = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Keep focus on primary task"},
    )
    assert first.status_code == 201
    now_id = first.json()["thought"]["id"]
    assert first.json()["thought"]["status"] == "now"

    parked = await client.post(
        "/api/v1/thoughts/capture",
        json={"text": "Side quest candidate", "auto_park": True},
    )
    assert parked.status_code == 201
    parked_id = parked.json()["thought"]["id"]
    assert parked.json()["thought"]["status"] == "parked"

    bad_promote = await client.post(
        f"/api/v1/thoughts/{parked_id}/promote",
        json={"target_slot": "now", "project_id": "proj_does_not_exist"},
    )
    assert bad_promote.status_code == 404

    now_node = backend.get_node(now_id)
    parked_node = backend.get_node(parked_id)
    assert now_node is not None and now_node["properties"]["status"] == "now"
    assert parked_node is not None and parked_node["properties"]["status"] == "parked"


def test_compute_pagerank_rejects_infinite_edge_weight() -> None:
    science = GraphScienceService(degree_invariant_max=6)
    nodes = [
        {"id": "a", "labels": ["Project"], "properties": {}},
        {"id": "b", "labels": ["Thought"], "properties": {}},
        {"id": "c", "labels": ["ConceptTag"], "properties": {}},
    ]
    edges = [
        {"id": "e1", "source": "a", "target": "b", "rel_type": "LINKS", "properties": {"weight": float("inf")}},
        {"id": "e2", "source": "b", "target": "c", "rel_type": "LINKS", "properties": {"weight": 2.0}},
        {"id": "e3", "source": "c", "target": "a", "rel_type": "LINKS", "properties": {"weight": float("-inf")}},
    ]
    raw_pr, norm_pr = science.compute_pagerank(nodes, edges)
    assert all(math.isfinite(score) for score in raw_pr.values())
    assert all(math.isfinite(score) for score in norm_pr.values())
    assert abs(sum(raw_pr.values()) - 1.0) < 1e-4

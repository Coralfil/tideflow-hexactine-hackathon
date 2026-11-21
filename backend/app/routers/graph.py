"""Graph Science snapshot, shortest-path, and read-only HSL bridge router."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.schemas import (
    GraphLens,
    GraphSnapshotResponse,
    HSLSummaryResponse,
    ShortestPathResult,
)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/snapshot", response_model=GraphSnapshotResponse)
async def get_graph_snapshot(
    request: Request,
    lens: GraphLens = Query(default="pagerank"),
    focus_id: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> GraphSnapshotResponse:
    state = request.app.state
    return state.graph_science.build_snapshot(
        state.graph_backend,
        lens=lens,
        focus_id=focus_id,
        source_id=source_id,
        target_id=target_id,
        limit=limit,
    )


@router.get("/path", response_model=ShortestPathResult)
async def get_shortest_path(
    request: Request,
    source_id: str = Query(..., min_length=1),
    target_id: str = Query(..., min_length=1),
    directed: bool = Query(default=False),
) -> ShortestPathResult:
    state = request.app.state
    nodes, edges = state.graph_backend.get_subgraph(focus_id=source_id, limit=1000)
    return state.graph_science.compute_shortest_path(
        nodes, edges, source_id=source_id, target_id=target_id, directed=directed
    )


@router.get("/hsl", response_model=HSLSummaryResponse)
async def get_hsl_summary(request: Request) -> HSLSummaryResponse:
    return request.app.state.hsl_bridge.summary()


@router.post("/hsl/seed")
async def seed_hsl_lattice(
    request: Request,
    max_junctions: int = Query(default=4, ge=0, le=20),
) -> dict[str, int]:
    state = request.app.state
    return state.hsl_bridge.seed_into_graph(
        state.graph_backend,
        science_service=state.graph_science,
        max_junctions=max_junctions,
    )

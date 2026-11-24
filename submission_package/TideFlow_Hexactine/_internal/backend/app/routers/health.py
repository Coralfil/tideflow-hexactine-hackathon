"""Health and runtime capability probe router."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import resolve_cadence_window
from app.graph.backend import probe_backend_status
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health(request: Request) -> HealthResponse:
    state = request.app.state
    settings = state.settings
    backend = state.graph_backend
    now = state.clock()

    scheduler = getattr(state, "scheduler", None)
    if scheduler is not None and hasattr(scheduler, "active_cadence"):
        active_cadence = scheduler.active_cadence(now)
    else:
        active_cadence = resolve_cadence_window(now)

    probe = probe_backend_status(settings)
    relate_available = probe["relate_available"] or (backend.backend_name == "relate")
    neo4j_available = probe["neo4j_available"] or (backend.backend_name == "neo4j")
    local_worker_available = await state.local_worker.probe_health()

    return HealthResponse(
        status="ok",
        backend_mode=backend.backend_name,
        relate_available=relate_available,
        neo4j_available=neo4j_available,
        local_worker_available=local_worker_available,
        active_cadence=active_cadence,
        degree_invariant_max=settings.degree_invariant_max,
        hsl_bridge_loaded=state.hsl_bridge.loaded,
    )

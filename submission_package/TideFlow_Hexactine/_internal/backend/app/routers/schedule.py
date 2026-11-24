"""Deterministic Cadence Scheduler router."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, status

from app.models.schemas import (
    CadenceWindow,
    MomentumPromptsResponse,
    ScheduleBlockCreateRequest,
    ScheduleBlockStatus,
    ScheduleBlockUpdateRequest,
    ScheduleBlockView,
)
from app.services.scheduler import (
    ScheduleConflictError,
    SchedulerService,
    ScheduleValidationError,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])


def init_service(app: FastAPI) -> SchedulerService:
    """Attach SchedulerService to app.state.scheduler for health and route handlers."""
    service = SchedulerService(
        backend=app.state.graph_backend,
        science=app.state.graph_science,
        clock=app.state.clock,
    )
    app.state.scheduler = service
    return service


@router.get("/blocks", response_model=list[ScheduleBlockView])
async def list_schedule_blocks(
    request: Request,
    cadence_window: CadenceWindow | None = Query(default=None),
    block_status: ScheduleBlockStatus | None = Query(default=None, alias="status"),
) -> list[ScheduleBlockView]:
    return request.app.state.scheduler.list_blocks(
        cadence_window=cadence_window,
        status=block_status,
    )


@router.post(
    "/blocks",
    response_model=ScheduleBlockView,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_block(
    payload: ScheduleBlockCreateRequest, request: Request
) -> ScheduleBlockView:
    try:
        return request.app.state.scheduler.create_block(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/blocks/{block_id}", response_model=ScheduleBlockView)
async def update_schedule_block(
    block_id: str,
    payload: ScheduleBlockUpdateRequest,
    request: Request,
) -> ScheduleBlockView:
    try:
        return request.app.state.scheduler.update_block(block_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/blocks/{block_id}")
async def delete_schedule_block(block_id: str, request: Request) -> dict[str, object]:
    try:
        request.app.state.scheduler.delete_block(block_id)
        return {"deleted": True, "id": block_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/prompts", response_model=MomentumPromptsResponse)
async def get_schedule_prompts(
    request: Request,
    now_iso: str | None = Query(default=None),
    energy: int = Query(default=3, ge=1, le=5),
    minutes: int = Query(default=25, ge=1, le=480),
) -> MomentumPromptsResponse:
    try:
        return request.app.state.scheduler.get_prompts(
            now_iso=now_iso,
            energy=energy,
            minutes=minutes,
        )
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

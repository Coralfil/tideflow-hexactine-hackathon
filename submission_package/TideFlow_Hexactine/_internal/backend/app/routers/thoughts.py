"""ADD thought capture, park, and slot-promotion router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.schemas import (
    ThoughtCaptureRequest,
    ThoughtCaptureResponse,
    ThoughtKind,
    ThoughtParkRequest,
    ThoughtPromoteRequest,
    ThoughtStatus,
    ThoughtTransitionResponse,
    ThoughtView,
)

router = APIRouter(prefix="/thoughts", tags=["thoughts"])


@router.post(
    "/capture",
    response_model=ThoughtCaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_thought(
    payload: ThoughtCaptureRequest, request: Request
) -> ThoughtCaptureResponse:
    try:
        return await request.app.state.momentum_engine.capture_thought(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[ThoughtView])
async def list_thoughts(
    request: Request,
    status_filter: ThoughtStatus | None = Query(default=None, alias="status"),
    project_id: str | None = Query(default=None),
    kind: ThoughtKind | None = Query(default=None),
) -> list[ThoughtView]:
    return request.app.state.momentum_engine.list_thoughts(
        status=status_filter, project_id=project_id, kind=kind
    )


@router.post("/{thought_id}/park", response_model=ThoughtTransitionResponse)
async def park_thought(
    thought_id: str,
    request: Request,
    payload: ThoughtParkRequest | None = None,
) -> ThoughtTransitionResponse:
    try:
        return request.app.state.momentum_engine.park_thought(
            thought_id, payload or ThoughtParkRequest()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{thought_id}/promote", response_model=ThoughtTransitionResponse)
async def promote_thought(
    thought_id: str,
    request: Request,
    payload: ThoughtPromoteRequest | None = None,
) -> ThoughtTransitionResponse:
    try:
        return request.app.state.momentum_engine.promote_thought(
            thought_id, payload or ThoughtPromoteRequest()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

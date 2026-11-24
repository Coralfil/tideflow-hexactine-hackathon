"""Bitemporal breadcrumbs, momentum resume, and 3-slot triage sweep router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.schemas import (
    BreadcrumbCreateRequest,
    BreadcrumbView,
    MomentumResumeResponse,
    TriageSweepRequest,
    TriageSweepResponse,
)

router = APIRouter(tags=["momentum"])


@router.post(
    "/breadcrumbs",
    response_model=BreadcrumbView,
    status_code=status.HTTP_201_CREATED,
)
async def create_breadcrumb(
    payload: BreadcrumbCreateRequest, request: Request
) -> BreadcrumbView:
    try:
        return request.app.state.momentum_engine.create_breadcrumb(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/momentum/resume", response_model=MomentumResumeResponse)
async def resume_momentum(
    request: Request,
    project_id: str | None = Query(default=None),
) -> MomentumResumeResponse:
    try:
        return await request.app.state.momentum_engine.resume_momentum(
            project_id=project_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/triage/sweep", response_model=TriageSweepResponse)
async def triage_sweep(
    request: Request,
    payload: TriageSweepRequest | None = None,
) -> TriageSweepResponse:
    try:
        return request.app.state.momentum_engine.triage_sweep(
            payload or TriageSweepRequest()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

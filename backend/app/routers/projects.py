"""Projects CRUD router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.models.schemas import ProjectCreateRequest, ProjectView

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectView, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest, request: Request
) -> ProjectView:
    return request.app.state.momentum_engine.create_project(payload)


@router.get("", response_model=list[ProjectView])
async def list_projects(request: Request) -> list[ProjectView]:
    return request.app.state.momentum_engine.list_projects()


@router.get("/{project_id}", response_model=ProjectView)
async def get_project(project_id: str, request: Request) -> ProjectView:
    try:
        return request.app.state.momentum_engine.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

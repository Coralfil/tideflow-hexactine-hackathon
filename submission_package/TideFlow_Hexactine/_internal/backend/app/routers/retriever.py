"""Permission-gated Nemoclaw Retriever router."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Request

from app.models.schemas import (
    AuditEntryView,
    RetrieverExecuteRequest,
    RetrieverExecuteResponse,
    RetrieverPermissionsUpdateRequest,
    RetrieverPermissionsView,
)
from app.services.nemoclaw_retriever import (
    NemoclawRetriever,
    PermissionDeniedError,
    RetrieverExecutionError,
)

router = APIRouter(prefix="/retriever", tags=["retriever"])


def init_service(app: FastAPI) -> NemoclawRetriever:
    """Attach NemoclawRetriever to app.state.retriever on app creation."""
    service = NemoclawRetriever(
        backend=app.state.graph_backend,
        science=app.state.graph_science,
        settings=app.state.settings,
        clock=app.state.clock,
    )
    app.state.retriever = service
    return service


@router.get("/permissions", response_model=RetrieverPermissionsView)
async def get_retriever_permissions(request: Request) -> RetrieverPermissionsView:
    return request.app.state.retriever.get_permissions()


@router.put("/permissions", response_model=RetrieverPermissionsView)
async def update_retriever_permissions(
    payload: RetrieverPermissionsUpdateRequest, request: Request
) -> RetrieverPermissionsView:
    return request.app.state.retriever.update_permissions(payload)


@router.post("/execute", response_model=RetrieverExecuteResponse)
async def execute_retriever(
    payload: RetrieverExecuteRequest, request: Request
) -> RetrieverExecuteResponse:
    try:
        return await request.app.state.retriever.execute(payload)
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "message": exc.reason,
                "verdict": "DENIED",
                "audit_entry": exc.audit_entry.model_dump(),
            },
        ) from exc
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrieverExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEntryView])
async def list_retriever_audit(request: Request) -> list[AuditEntryView]:
    return request.app.state.retriever.list_audit()

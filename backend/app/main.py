"""FastAPI application factory for TideFlow Hexactine."""

from __future__ import annotations

import importlib
import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.graph.backend import GraphBackend, create_graph_backend
from app.graph.hsl_bridge import HSLBridge
from app.graph.science import GraphScienceService
from app.models.schemas import ProjectCreateRequest
from app.routers import graph, health, momentum, projects, thoughts
from app.services.local_worker_client import LocalWorkerClient
from app.services.momentum_engine import MomentumEngine


def _mount_optional_m3_routers(app: FastAPI, api_prefix: str) -> None:
    """Mount M3 scheduler and retriever routers when present without modifying M2."""
    for module_name in ("app.routers.scheduler", "app.routers.retriever"):
        if importlib.util.find_spec(module_name) is not None:
            mod = importlib.import_module(module_name)
            sub_router = getattr(mod, "router", None)
            if sub_router is not None:
                app.include_router(sub_router, prefix=api_prefix)
            init_fn = getattr(mod, "init_service", None)
            if callable(init_fn):
                init_fn(app)


def create_app(
    settings: Settings | None = None,
    graph_backend: GraphBackend | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create configured FastAPI app with injectable backend and deterministic clock."""
    cfg = settings or Settings.from_env()
    time_fn = clock or (lambda: datetime.now(timezone.utc))
    backend = graph_backend if graph_backend is not None else create_graph_backend(cfg)
    hsl_bridge = HSLBridge(
        bridge_config_path=cfg.hsl_bridge_config_path,
        manifest_path=cfg.agentsea_manifest_path,
    )
    science = GraphScienceService(degree_invariant_max=cfg.degree_invariant_max)
    local_worker = LocalWorkerClient(cfg)
    engine = MomentumEngine(
        backend=backend,
        science=science,
        local_worker=local_worker,
        clock=time_fn,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if cfg.seed_default_project and not engine.list_projects():
            engine.create_project(
                ProjectCreateRequest(
                    name="TideFlow Hexactine Cockpit",
                    description="Active workspace hub for ADD-minded capture, rhythm scheduling, and graph science.",
                    cadence_preference="deep_tide",
                    priority=5,
                    tags=["hexactine", "rhythm"],
                )
            )
        try:
            yield
        finally:
            if graph_backend is None:
                backend.close()

    app = FastAPI(
        title=cfg.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = cfg
    app.state.clock = time_fn
    app.state.graph_backend = backend
    app.state.hsl_bridge = hsl_bridge
    app.state.graph_science = science
    app.state.local_worker = local_worker
    app.state.momentum_engine = engine

    app.include_router(health.router, prefix=cfg.api_prefix)
    app.include_router(projects.router, prefix=cfg.api_prefix)
    app.include_router(thoughts.router, prefix=cfg.api_prefix)
    app.include_router(momentum.router, prefix=cfg.api_prefix)
    app.include_router(graph.router, prefix=cfg.api_prefix)

    _mount_optional_m3_routers(app, cfg.api_prefix)
    return app


app = create_app()

"""Auto-mount bridge re-exporting schedule router and service initializer."""

from app.routers.schedule import init_service, router

__all__ = ["init_service", "router"]

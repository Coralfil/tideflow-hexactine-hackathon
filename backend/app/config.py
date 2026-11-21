"""Configuration and tidal cadence window helpers for TideFlow Hexactine."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

CadenceWindow = Literal["deep_tide", "creative_swell", "shallow_drift", "recovery_ebb"]
GraphMode = Literal["auto", "relate", "inprocess", "neo4j"]

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value.strip())
    except ValueError:
        return default
    return parsed if parsed > 0.0 else default


def resolve_cadence_window(now: datetime | None = None) -> CadenceWindow:
    """Resolve the canonical 4 Tidal Cadence Windows from local hour.

    06:00-11:59 -> deep_tide
    12:00-15:59 -> creative_swell
    16:00-20:59 -> shallow_drift
    21:00-05:59 -> recovery_ebb
    """
    current = now or datetime.now(timezone.utc)
    hour = current.hour
    if 6 <= hour <= 11:
        return "deep_tide"
    if 12 <= hour <= 15:
        return "creative_swell"
    if 16 <= hour <= 20:
        return "shallow_drift"
    return "recovery_ebb"


class Settings(BaseModel):
    """Application settings loaded from defaults and environment variables."""

    app_name: str = "TideFlow Hexactine API"
    api_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8010
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )

    graph_mode: GraphMode = "auto"
    relate_db_path: str = str(_REPO_ROOT / "data" / "tideflow_memory.rl")
    relate_bin: str = "relate"
    relate_timeout_secs: float = 10.0

    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    degree_invariant_max: int = 6
    seed_default_project: bool = True

    hsl_bridge_config_path: str = str(
        _REPO_ROOT / ".agents" / "hsl_bridge" / "bridge_config.json"
    )
    agentsea_manifest_path: str = str(
        _REPO_ROOT / ".agents" / "agentsea" / "manifest.json"
    )

    local_worker_enabled: bool = True
    local_worker_chat_url: str = "http://127.0.0.1:8000/v1"
    local_worker_embeddings_url: str = "http://127.0.0.1:8001/embeddings"
    local_worker_rerank_url: str = "http://127.0.0.1:8001/rerank"
    local_worker_embeddings_health_url: str = "http://127.0.0.1:8001/health"
    local_worker_glyph_url: str = "http://127.0.0.1:8003/v1/glyph"
    local_ollama_url: str = "http://127.0.0.1:11434"
    local_ollama_model: str = "qwen2.5:7b-instruct"
    local_worker_probe_timeout: float = 0.4
    local_worker_infer_timeout: float = 2.0

    @classmethod
    def from_env(cls) -> "Settings":
        """Build Settings with optional TIDEFLOW_* and NEO4J_* env overrides."""
        defaults = cls()
        raw_mode = os.getenv("TIDEFLOW_GRAPH_MODE", defaults.graph_mode).strip().lower()
        graph_mode: GraphMode = (
            raw_mode if raw_mode in {"auto", "relate", "inprocess", "neo4j"} else defaults.graph_mode  # type: ignore[assignment]
        )

        raw_port = os.getenv("TIDEFLOW_PORT")
        port = int(raw_port) if raw_port and raw_port.isdigit() else defaults.port

        raw_cors = os.getenv("TIDEFLOW_CORS_ORIGINS")
        cors_origins = (
            [item.strip() for item in raw_cors.split(",") if item.strip()]
            if raw_cors
            else defaults.cors_origins
        )

        return cls(
            host=os.getenv("TIDEFLOW_HOST", defaults.host),
            port=port,
            cors_origins=cors_origins,
            graph_mode=graph_mode,
            relate_db_path=os.getenv("TIDEFLOW_RELATE_DB_PATH", defaults.relate_db_path),
            relate_bin=os.getenv("TIDEFLOW_RELATE_BIN", defaults.relate_bin),
            neo4j_uri=os.getenv("TIDEFLOW_NEO4J_URI")
            or os.getenv("NEO4J_URI", defaults.neo4j_uri),
            neo4j_user=os.getenv("TIDEFLOW_NEO4J_USER")
            or os.getenv("NEO4J_USER", defaults.neo4j_user),
            neo4j_password=os.getenv("TIDEFLOW_NEO4J_PASSWORD")
            or os.getenv("NEO4J_PASSWORD", defaults.neo4j_password),
            neo4j_database=os.getenv("TIDEFLOW_NEO4J_DATABASE")
            or os.getenv("NEO4J_DATABASE", defaults.neo4j_database),
            seed_default_project=_parse_bool(
                os.getenv("TIDEFLOW_SEED_DEFAULT_PROJECT"),
                defaults.seed_default_project,
            ),
            hsl_bridge_config_path=os.getenv(
                "TIDEFLOW_HSL_BRIDGE_CONFIG", defaults.hsl_bridge_config_path
            ),
            agentsea_manifest_path=os.getenv(
                "TIDEFLOW_AGENTSEA_MANIFEST", defaults.agentsea_manifest_path
            ),
            local_worker_enabled=_parse_bool(
                os.getenv("TIDEFLOW_LOCAL_WORKER_ENABLED"),
                defaults.local_worker_enabled,
            ),
            local_worker_chat_url=os.getenv(
                "TIDEFLOW_LOCAL_WORKER_CHAT_URL", defaults.local_worker_chat_url
            ),
            local_worker_embeddings_url=os.getenv(
                "TIDEFLOW_LOCAL_WORKER_EMBEDDINGS_URL",
                defaults.local_worker_embeddings_url,
            ),
            local_worker_rerank_url=os.getenv(
                "TIDEFLOW_LOCAL_WORKER_RERANK_URL", defaults.local_worker_rerank_url
            ),
            local_worker_glyph_url=os.getenv(
                "TIDEFLOW_LOCAL_WORKER_GLYPH_URL", defaults.local_worker_glyph_url
            ),
            local_ollama_url=os.getenv(
                "TIDEFLOW_LOCAL_OLLAMA_URL", defaults.local_ollama_url
            ),
            local_ollama_model=os.getenv(
                "TIDEFLOW_LOCAL_OLLAMA_MODEL", defaults.local_ollama_model
            ),
            local_worker_probe_timeout=_parse_float(
                os.getenv("TIDEFLOW_LOCAL_WORKER_PROBE_TIMEOUT"),
                defaults.local_worker_probe_timeout,
            ),
            local_worker_infer_timeout=_parse_float(
                os.getenv("TIDEFLOW_LOCAL_WORKER_INFER_TIMEOUT"),
                defaults.local_worker_infer_timeout,
            ),
        )

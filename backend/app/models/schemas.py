"""Pydantic v2 schemas for TideFlow Hexactine backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ThoughtKind = Literal["spark_idea", "project_task", "side_quest", "blocker"]
ThoughtStatus = Literal["now", "next", "parked", "done"]
ProjectStatus = Literal["active", "paused", "completed"]
GraphLens = Literal["pagerank", "communities", "path", "degree_audit"]
BackendMode = Literal["relate", "inprocess", "neo4j"]
CadenceWindow = Literal["deep_tide", "creative_swell", "shallow_drift", "recovery_ebb"]
InferenceSource = Literal["local_worker", "ollama", "deterministic_fallback"]
ScheduleBlockStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]
CapabilityName = Literal[
    "local_fs_read",
    "repo_git_scan",
    "web_fetch_public",
    "local_llm_ollama",
]
AuditDecision = Literal["ALLOWED", "DENIED"]


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp string and normalize to UTC."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Timestamp must not be empty")
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_iso_utc(dt: datetime) -> str:
    """Format a datetime as canonical UTC ISO-8601 with trailing Z."""
    normalized = (
        dt.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None
        else dt.astimezone(timezone.utc)
    )
    return normalized.isoformat().replace("+00:00", "Z")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    backend_mode: BackendMode
    relate_available: bool
    neo4j_available: bool
    local_worker_available: bool
    active_cadence: CadenceWindow
    degree_invariant_max: int = 6
    hsl_bridge_loaded: bool


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    cadence_preference: CadenceWindow = "deep_tide"
    priority: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("name")
    @classmethod
    def _validate_name_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Project name must not be empty or whitespace-only")
        return stripped


class ProjectView(BaseModel):
    id: str
    name: str
    description: str = ""
    status: ProjectStatus = "active"
    cadence_preference: CadenceWindow = "deep_tide"
    priority: int = 3
    tags: list[str] = Field(default_factory=list)
    degree: int = 0
    active_wip_count: int = 0
    parked_count: int = 0
    latest_breadcrumb_id: str | None = None
    created_at: str
    updated_at: str


class ThoughtClassification(BaseModel):
    kind: ThoughtKind
    energy_cost: int = Field(default=2, ge=1, le=5)
    concept_tags: list[str] = Field(default_factory=list)
    suggested_micro_step: str
    inference_source: InferenceSource = "deterministic_fallback"


class ThoughtCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    kind: ThoughtKind | None = None
    project_id: str | None = None
    energy_cost: int | None = Field(default=None, ge=1, le=5)
    auto_park: bool = False
    concept_tags: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("text")
    @classmethod
    def _validate_text_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Thought text must not be empty or whitespace-only")
        return stripped


class ThoughtView(BaseModel):
    id: str
    text: str
    kind: ThoughtKind
    status: ThoughtStatus
    project_id: str | None = None
    energy_cost: int
    concept_tags: list[str] = Field(default_factory=list)
    suggested_micro_step: str
    inference_source: InferenceSource = "deterministic_fallback"
    park_reason: str | None = None
    routed_via_subhub: bool = False
    subhub_id: str | None = None
    created_at: str
    updated_at: str
    parked_at: str | None = None


class ThoughtCaptureResponse(BaseModel):
    thought: ThoughtView
    linked_tags: list[str] = Field(default_factory=list)
    routed_via_subhub: bool = False
    subhub_id: str | None = None
    active_wip_count: int
    overwhelm_warning: bool
    overwhelm_message: str | None = None


class ThoughtParkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class ThoughtPromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_slot: Literal["now", "next"] = "now"
    project_id: str | None = None


class ThoughtTransitionResponse(BaseModel):
    thought: ThoughtView
    demoted_thought_id: str | None = None
    active_wip_count: int
    overwhelm_warning: bool
    overwhelm_message: str | None = None


class BreadcrumbCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=120)
    last_action: str = Field(min_length=1, max_length=500)
    next_micro_step: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("next_micro_step", "next_step"),
    )
    blocker_note: str | None = Field(default=None, max_length=500)
    linked_thought_ids: list[str] = Field(default_factory=list)
    valid_from: str | None = None

    @field_validator("project_id", "last_action", "next_micro_step")
    @classmethod
    def _validate_required_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped


class BreadcrumbView(BaseModel):
    id: str
    project_id: str
    last_action: str
    next_micro_step: str
    blocker_note: str | None = None
    linked_thought_ids: list[str] = Field(default_factory=list)
    supersedes_id: str | None = None
    valid_from: str
    valid_to: str | None = None
    recorded_at: str
    closed_at: str | None = None


class GraphEdgeView(BaseModel):
    id: str
    source: str
    target: str
    rel_type: str
    weight: float = 1.0
    routed_via_subhub: bool = False
    in_active_path: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphNodeView(BaseModel):
    id: str
    labels: list[str]
    label: str
    title: str
    status: str | None = None
    kind: str | None = None
    degree: int = 0
    pagerank: float = 0.0
    normalized_pagerank: float = 0.0
    community_id: int = 0
    hexactine_compliant: bool = True
    in_active_path: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class DegreeViolation(BaseModel):
    node_id: str
    labels: list[str]
    degree: int
    max_allowed: int = 6
    exceeded_by: int


class ShortestPathResult(BaseModel):
    found: bool
    source_id: str
    target_id: str
    node_ids: list[str] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    total_cost: float | None = None
    hop_count: int = 0
    gds_cypher_preview: str = ""


class GraphScienceMetrics(BaseModel):
    node_count: int
    edge_count: int
    community_count: int
    modularity: float
    max_degree_allowed: int = 6
    max_observed_degree: int
    sub_hub_count: int
    degree_violations: list[DegreeViolation] = Field(default_factory=list)
    invariant_ok: bool
    top_pagerank_ids: list[str] = Field(default_factory=list)


class GraphSnapshotResponse(BaseModel):
    lens: GraphLens
    focus_id: str | None = None
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]
    metrics: GraphScienceMetrics
    active_path: ShortestPathResult | None = None
    gds_cypher_preview: str


class ContextResumeCard(BaseModel):
    last_action: str
    next_micro_step: str
    linked_sparks: list[str] = Field(default_factory=list)
    card_lines: list[str] = Field(min_length=3, max_length=3)


class MomentumResumeResponse(BaseModel):
    project: ProjectView
    active_breadcrumb: BreadcrumbView | None = None
    chain_depth: int = 0
    resume_card: ContextResumeCard
    path_bridge: ShortestPathResult | None = None
    gds_cypher_preview: str


class TriageSweepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    max_now: int = Field(default=1, ge=1, le=1)
    max_next: int = Field(default=2, ge=1, le=2)


class TriageSweepResponse(BaseModel):
    now: list[ThoughtView]
    next: list[ThoughtView]
    parked_count: int
    newly_parked_ids: list[str] = Field(default_factory=list)
    pre_sweep_active_count: int
    overwhelm_index: float
    recommendation: str


class HSLSummaryResponse(BaseModel):
    loaded: bool
    read_only: bool = True
    schema_version: str | None = None
    degree_invariant_max: int = 6
    status: str | None = None
    orthogonal_rays: dict[str, str] = Field(default_factory=dict)
    orchestral_sections: list[dict[str, Any]] = Field(default_factory=list)
    spicule_count: int = 0
    schema_a_count: int = 0
    schema_b_count: int = 0
    squad_count: int = 0
    agent_count: int = 0
    skill_count: int = 0
    sample_junctions: list[dict[str, Any]] = Field(default_factory=list)


class ScheduleBlockCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    thought_id: str | None = None
    cadence_window: CadenceWindow = "deep_tide"
    start_iso: str = Field(min_length=1, max_length=64)
    end_iso: str = Field(min_length=1, max_length=64)
    energy_required: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default="", max_length=1000)

    @field_validator("title")
    @classmethod
    def _validate_title_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Schedule block title must not be empty")
        return stripped

    @field_validator("start_iso", "end_iso")
    @classmethod
    def _validate_iso_timestamp(cls, value: str) -> str:
        return format_iso_utc(parse_iso_utc(value))

    @model_validator(mode="after")
    def _validate_time_order(self) -> "ScheduleBlockCreateRequest":
        if parse_iso_utc(self.end_iso) <= parse_iso_utc(self.start_iso):
            raise ValueError("end_iso must be strictly after start_iso")
        return self


class ScheduleBlockUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: str | None = None
    thought_id: str | None = None
    cadence_window: CadenceWindow | None = None
    start_iso: str | None = Field(default=None, min_length=1, max_length=64)
    end_iso: str | None = Field(default=None, min_length=1, max_length=64)
    status: ScheduleBlockStatus | None = None
    energy_required: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def _validate_optional_title_non_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Schedule block title must not be empty")
        return stripped

    @field_validator("start_iso", "end_iso")
    @classmethod
    def _validate_optional_iso(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return format_iso_utc(parse_iso_utc(value))

    @model_validator(mode="after")
    def _validate_optional_time_order(self) -> "ScheduleBlockUpdateRequest":
        if self.start_iso is not None and self.end_iso is not None:
            if parse_iso_utc(self.end_iso) <= parse_iso_utc(self.start_iso):
                raise ValueError("end_iso must be strictly after start_iso")
        return self


class ScheduleBlockView(BaseModel):
    id: str
    title: str
    project_id: str | None = None
    thought_id: str | None = None
    cadence_window: CadenceWindow
    start_iso: str
    end_iso: str
    status: ScheduleBlockStatus = "scheduled"
    energy_required: int = 3
    notes: str = ""
    routed_via_subhub: bool = False
    subhub_id: str | None = None
    created_at: str
    updated_at: str


class MomentumPromptItem(BaseModel):
    id: str
    source_type: Literal["thought", "schedule_block", "cadence_ritual"]
    source_id: str | None = None
    title: str
    micro_step: str
    cadence_window: CadenceWindow
    energy_required: int
    estimated_minutes: int
    score: float
    reason: str


class MomentumPromptsResponse(BaseModel):
    now_iso: str
    active_cadence: CadenceWindow
    energy: int
    minutes: int
    prompts: list[MomentumPromptItem]


class RetrieverPermissionsView(BaseModel):
    local_fs_read: bool = False
    repo_git_scan: bool = False
    web_fetch_public: bool = False
    local_llm_ollama: bool = False
    allowed_paths: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    updated_at: str


class RetrieverPermissionsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_fs_read: bool | None = None
    repo_git_scan: bool | None = None
    web_fetch_public: bool | None = None
    local_llm_ollama: bool | None = None
    allowed_paths: list[str] | None = None
    allowed_domains: list[str] | None = None


class RetrieverExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=1000)
    query: str | None = Field(default=None, max_length=1000)
    project_id: str | None = None
    thought_id: str | None = None

    @field_validator("capability", "target")
    @classmethod
    def _validate_exec_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped


class RetrievalArtifactView(BaseModel):
    id: str
    title: str
    label: str = "RetrievalArtifact"
    capability: str
    target: str
    summary: str
    excerpt: str
    source_ref: str
    grounded_node_id: str | None = None
    routed_via_subhub: bool = False
    subhub_id: str | None = None
    inference_source: InferenceSource = "deterministic_fallback"
    created_at: str


class AuditEntryView(BaseModel):
    id: str
    trace_id: str
    service: str = "nemoclaw-retriever"
    capability: str
    target: str
    verdict: AuditDecision
    decision: AuditDecision
    reason: str
    artifact_id: str | None = None
    timestamp: str


class RetrieverExecuteResponse(BaseModel):
    job_id: str
    verdict: Literal["ALLOWED"] = "ALLOWED"
    decision: Literal["ALLOWED"] = "ALLOWED"
    artifact: RetrievalArtifactView
    audit_entry: AuditEntryView
    grounded_edge_id: str | None = None

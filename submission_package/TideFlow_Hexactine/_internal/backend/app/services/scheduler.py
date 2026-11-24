"""Deterministic Cadence Scheduler with injectable clock and Hexactine linking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.config import CadenceWindow, resolve_cadence_window
from app.graph.backend import GraphBackend
from app.graph.science import GraphScienceService
from app.models.schemas import (
    MomentumPromptItem,
    MomentumPromptsResponse,
    ScheduleBlockCreateRequest,
    ScheduleBlockStatus,
    ScheduleBlockUpdateRequest,
    ScheduleBlockView,
    ThoughtKind,
    format_iso_utc,
    parse_iso_utc,
)


class ScheduleConflictError(Exception):
    """Raised when a schedule block overlaps an existing active block."""


class ScheduleValidationError(ValueError):
    """Raised when schedule parameters or timestamps fail validation."""


_CADENCE_KIND_WEIGHTS: dict[CadenceWindow, dict[ThoughtKind, int]] = {
    "deep_tide": {
        "project_task": 24,
        "blocker": 20,
        "spark_idea": 8,
        "side_quest": 2,
    },
    "creative_swell": {
        "spark_idea": 24,
        "project_task": 16,
        "side_quest": 14,
        "blocker": 8,
    },
    "shallow_drift": {
        "blocker": 20,
        "project_task": 16,
        "spark_idea": 12,
        "side_quest": 10,
    },
    "recovery_ebb": {
        "side_quest": 20,
        "spark_idea": 16,
        "project_task": 6,
        "blocker": 4,
    },
}

_CADENCE_RITUALS: dict[CadenceWindow, tuple[str, str, int]] = {
    "deep_tide": (
        "Deep Tide Anchor Sprint",
        "Close secondary tabs and execute one 25-minute single-thread build step.",
        4,
    ),
    "creative_swell": (
        "Creative Swell Synthesis",
        "Connect two open sparks on the graph and write one testable micro-hypothesis.",
        3,
    ),
    "shallow_drift": (
        "Shallow Drift Triage Sweep",
        "Park low-leverage tangents and clear one small blocker or review note.",
        2,
    ),
    "recovery_ebb": (
        "Recovery Ebb Breadcrumb Reset",
        "Record a 3-line breadcrumb for tomorrow and step away guilt-free.",
        1,
    ),
}


class SchedulerService:
    """Manages ScheduleBlock persistence, overlap checks, and deterministic prompts."""

    def __init__(
        self,
        backend: GraphBackend,
        science: GraphScienceService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.backend = backend
        self.science = science
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now_iso(self) -> str:
        return format_iso_utc(self._clock())

    def active_cadence(self, now: datetime | None = None) -> CadenceWindow:
        """Return active tidal cadence window for health and dial integration."""
        return resolve_cadence_window(now or self._clock())

    def _node_to_block(self, node: dict) -> ScheduleBlockView:
        props = node.get("properties") or {}
        return ScheduleBlockView(
            id=node["id"],
            title=str(props.get("title") or ""),
            project_id=props.get("project_id"),
            thought_id=props.get("thought_id"),
            cadence_window=props.get("cadence_window") or "deep_tide",
            start_iso=str(props.get("start_iso") or ""),
            end_iso=str(props.get("end_iso") or ""),
            status=props.get("status") or "scheduled",
            energy_required=int(props.get("energy_required") or 3),
            notes=str(props.get("notes") or ""),
            routed_via_subhub=bool(props.get("routed_via_subhub", False)),
            subhub_id=props.get("subhub_id"),
            created_at=str(props.get("created_at") or ""),
            updated_at=str(props.get("updated_at") or ""),
        )

    def _validate_target_refs(
        self, project_id: str | None, thought_id: str | None
    ) -> None:
        if project_id is not None:
            proj = self.backend.get_node(project_id)
            if proj is None or "Project" not in proj.get("labels", []):
                raise KeyError(f"Project not found: {project_id}")
        if thought_id is not None:
            thought = self.backend.get_node(thought_id)
            if thought is None or "Thought" not in thought.get("labels", []):
                raise KeyError(f"Thought not found: {thought_id}")

    def _check_overlap(
        self,
        start_dt: datetime,
        end_dt: datetime,
        exclude_block_id: str | None = None,
    ) -> None:
        existing_nodes = self.backend.query_nodes("ScheduleBlock", limit=2000)
        for node in existing_nodes:
            if exclude_block_id is not None and node["id"] == exclude_block_id:
                continue
            props = node.get("properties") or {}
            if props.get("status") == "cancelled":
                continue
            raw_start = str(props.get("start_iso") or "")
            raw_end = str(props.get("end_iso") or "")
            if not raw_start or not raw_end:
                continue
            existing_start = parse_iso_utc(raw_start)
            existing_end = parse_iso_utc(raw_end)
            if existing_start < end_dt and start_dt < existing_end:
                title = str(props.get("title") or node["id"])
                raise ScheduleConflictError(
                    f"Schedule overlap conflict with '{title}' ({raw_start} to {raw_end})"
                )

    def _link_block_targets(
        self,
        block_id: str,
        project_id: str | None,
        thought_id: str | None,
    ) -> tuple[bool, str | None]:
        routed_via_subhub = False
        subhub_id: str | None = None
        if project_id is not None:
            _, routed, hub_id = self.science.link_with_hexactine_invariant(
                self.backend,
                block_id,
                "SCHEDULED_FOR",
                project_id,
                edge_props={"weight": 1.0},
            )
            routed_via_subhub = routed_via_subhub or routed
            subhub_id = hub_id or subhub_id
        if thought_id is not None:
            _, routed_t, hub_t = self.science.link_with_hexactine_invariant(
                self.backend,
                block_id,
                "TARGETS_THOUGHT",
                thought_id,
                edge_props={"weight": 1.0},
            )
            routed_via_subhub = routed_via_subhub or routed_t
            subhub_id = subhub_id or hub_t
        return routed_via_subhub, subhub_id

    def create_block(self, payload: ScheduleBlockCreateRequest) -> ScheduleBlockView:
        """Create and persist a non-overlapping ScheduleBlock node."""
        self._validate_target_refs(payload.project_id, payload.thought_id)
        start_dt = parse_iso_utc(payload.start_iso)
        end_dt = parse_iso_utc(payload.end_iso)
        if end_dt <= start_dt:
            raise ScheduleValidationError("end_iso must be strictly after start_iso")
        self._check_overlap(start_dt, end_dt)

        now_iso = self._now_iso()
        block_id = f"blk_{uuid4().hex[:10]}"
        props = {
            "id": block_id,
            "title": payload.title,
            "project_id": payload.project_id,
            "thought_id": payload.thought_id,
            "cadence_window": payload.cadence_window,
            "start_iso": format_iso_utc(start_dt),
            "end_iso": format_iso_utc(end_dt),
            "status": "scheduled",
            "energy_required": payload.energy_required,
            "notes": payload.notes,
            "routed_via_subhub": False,
            "subhub_id": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        node = self.backend.upsert_node("ScheduleBlock", props)
        routed, subhub_id = self._link_block_targets(
            block_id, payload.project_id, payload.thought_id
        )
        if routed or subhub_id is not None:
            node = self.backend.upsert_node(
                "ScheduleBlock",
                {
                    "id": block_id,
                    "routed_via_subhub": routed,
                    "subhub_id": subhub_id,
                },
            )
        return self._node_to_block(node)

    def list_blocks(
        self,
        cadence_window: CadenceWindow | None = None,
        status: ScheduleBlockStatus | None = None,
    ) -> list[ScheduleBlockView]:
        """List ScheduleBlock nodes ordered deterministically by start_iso and id."""
        filters: dict[str, object] = {}
        if cadence_window is not None:
            filters["cadence_window"] = cadence_window
        if status is not None:
            filters["status"] = status
        nodes = self.backend.query_nodes("ScheduleBlock", filters=filters or None, limit=2000)
        blocks = [self._node_to_block(n) for n in nodes]
        blocks.sort(key=lambda b: (b.start_iso, b.id))
        return blocks

    def get_block(self, block_id: str) -> ScheduleBlockView:
        node = self.backend.get_node(block_id)
        if node is None or "ScheduleBlock" not in node.get("labels", []):
            raise KeyError(f"ScheduleBlock not found: {block_id}")
        return self._node_to_block(node)

    def update_block(
        self, block_id: str, payload: ScheduleBlockUpdateRequest
    ) -> ScheduleBlockView:
        """Update ScheduleBlock fields with overlap and time-order validation."""
        node = self.backend.get_node(block_id)
        if node is None or "ScheduleBlock" not in node.get("labels", []):
            raise KeyError(f"ScheduleBlock not found: {block_id}")
        props = dict(node.get("properties") or {})

        new_project_id = (
            payload.project_id
            if "project_id" in payload.model_fields_set
            else props.get("project_id")
        )
        new_thought_id = (
            payload.thought_id
            if "thought_id" in payload.model_fields_set
            else props.get("thought_id")
        )
        self._validate_target_refs(new_project_id, new_thought_id)

        new_start_iso = payload.start_iso or str(props.get("start_iso") or "")
        new_end_iso = payload.end_iso or str(props.get("end_iso") or "")
        start_dt = parse_iso_utc(new_start_iso)
        end_dt = parse_iso_utc(new_end_iso)
        if end_dt <= start_dt:
            raise ScheduleValidationError("end_iso must be strictly after start_iso")

        new_status = payload.status or props.get("status") or "scheduled"
        if new_status != "cancelled":
            self._check_overlap(start_dt, end_dt, exclude_block_id=block_id)

        update_props: dict[str, object] = {
            "id": block_id,
            "title": payload.title if payload.title is not None else props.get("title"),
            "project_id": new_project_id,
            "thought_id": new_thought_id,
            "cadence_window": (
                payload.cadence_window
                if payload.cadence_window is not None
                else props.get("cadence_window")
            ),
            "start_iso": format_iso_utc(start_dt),
            "end_iso": format_iso_utc(end_dt),
            "status": new_status,
            "energy_required": (
                payload.energy_required
                if payload.energy_required is not None
                else props.get("energy_required", 3)
            ),
            "notes": (
                payload.notes
                if payload.notes is not None
                else props.get("notes", "")
            ),
            "updated_at": self._now_iso(),
        }
        updated_node = self.backend.upsert_node("ScheduleBlock", update_props)
        routed, subhub_id = self._link_block_targets(
            block_id, new_project_id, new_thought_id
        )
        if routed or subhub_id is not None:
            updated_node = self.backend.upsert_node(
                "ScheduleBlock",
                {
                    "id": block_id,
                    "routed_via_subhub": routed,
                    "subhub_id": subhub_id,
                },
            )
        return self._node_to_block(updated_node)

    def delete_block(self, block_id: str) -> None:
        """Delete a ScheduleBlock node and its incident edges."""
        node = self.backend.get_node(block_id)
        if node is None or "ScheduleBlock" not in node.get("labels", []):
            raise KeyError(f"ScheduleBlock not found: {block_id}")
        deleted = self.backend.delete_node(block_id)
        if not deleted:
            raise KeyError(f"ScheduleBlock not found: {block_id}")

    def get_prompts(
        self,
        now_iso: str | None = None,
        energy: int = 3,
        minutes: int = 25,
    ) -> MomentumPromptsResponse:
        """Deterministically score thoughts, blocks, and cadence rituals for now_iso/energy/minutes."""
        if energy < 1 or energy > 5:
            raise ScheduleValidationError("energy must be between 1 and 5")
        if minutes < 1 or minutes > 480:
            raise ScheduleValidationError("minutes must be between 1 and 480")

        if now_iso is not None:
            try:
                parsed_now = parse_iso_utc(now_iso)
            except ValueError as exc:
                raise ScheduleValidationError(f"Invalid now_iso timestamp: {now_iso}") from exc
        else:
            parsed_now = self._clock()
            if parsed_now.tzinfo is None:
                parsed_now = parsed_now.replace(tzinfo=timezone.utc)
            else:
                parsed_now = parsed_now.astimezone(timezone.utc)

        normalized_now = format_iso_utc(parsed_now)
        active_cadence = resolve_cadence_window(parsed_now)
        kind_weights = _CADENCE_KIND_WEIGHTS[active_cadence]

        candidates: list[MomentumPromptItem] = []

        block_nodes = self.backend.query_nodes("ScheduleBlock", limit=500)
        for node in block_nodes:
            props = node.get("properties") or {}
            status = str(props.get("status") or "scheduled")
            if status not in {"scheduled", "in_progress"}:
                continue
            b_start = parse_iso_utc(str(props.get("start_iso") or normalized_now))
            b_end = parse_iso_utc(str(props.get("end_iso") or normalized_now))
            b_minutes = max(5, min(240, int((b_end - b_start).total_seconds() // 60)))
            b_cadence: CadenceWindow = props.get("cadence_window") or active_cadence
            b_energy = max(1, min(5, int(props.get("energy_required") or 3)))

            score = 35.0
            if b_start <= parsed_now < b_end:
                score += 40.0
            if b_cadence == active_cadence:
                score += 18.0
            score += max(0.0, 15.0 - abs(energy - b_energy) * 4.0)
            if b_minutes <= minutes:
                score += 10.0

            candidates.append(
                MomentumPromptItem(
                    id=f"prompt_blk_{node['id']}",
                    source_type="schedule_block",
                    source_id=node["id"],
                    title=str(props.get("title") or node["id"]),
                    micro_step=f"Start scheduled block ({b_minutes}m) in {b_cadence} window.",
                    cadence_window=b_cadence,
                    energy_required=b_energy,
                    estimated_minutes=min(minutes, b_minutes),
                    score=round(score, 2),
                    reason=f"Aligned with {active_cadence} schedule and energy {energy}/5.",
                )
            )

        thought_nodes = self.backend.query_nodes("Thought", limit=500)
        for node in thought_nodes:
            props = node.get("properties") or {}
            status = str(props.get("status") or "next")
            if status not in {"now", "next", "parked"}:
                continue
            kind: ThoughtKind = props.get("kind") or "spark_idea"
            t_energy = max(1, min(5, int(props.get("energy_cost") or 2)))
            est_minutes = max(5, min(60, t_energy * 10))

            status_score = 30.0 if status == "now" else (20.0 if status == "next" else 5.0)
            kind_score = float(kind_weights.get(kind, 10))
            energy_fit = max(0.0, 20.0 - abs(energy - t_energy) * 5.0)
            if t_energy <= energy:
                energy_fit += 6.0
            time_fit = 10.0 if est_minutes <= minutes else 2.0
            score = status_score + kind_score + energy_fit + time_fit

            micro_step = str(props.get("suggested_micro_step") or "").strip()
            if not micro_step:
                micro_step = f"Spend {min(minutes, est_minutes)}m advancing this {kind}."

            candidates.append(
                MomentumPromptItem(
                    id=f"prompt_th_{node['id']}",
                    source_type="thought",
                    source_id=node["id"],
                    title=str(props.get("text") or node["id"])[:120],
                    micro_step=micro_step,
                    cadence_window=active_cadence,
                    energy_required=t_energy,
                    estimated_minutes=min(minutes, est_minutes),
                    score=round(score, 2),
                    reason=f"Slot={status}, kind={kind}, energy={t_energy}/5 for {active_cadence}.",
                )
            )

        ritual_title, ritual_step, ritual_energy = _CADENCE_RITUALS[active_cadence]
        ritual_score = 22.0 + max(0.0, 12.0 - abs(energy - ritual_energy) * 3.0)
        candidates.append(
            MomentumPromptItem(
                id=f"prompt_ritual_{active_cadence}",
                source_type="cadence_ritual",
                source_id=None,
                title=ritual_title,
                micro_step=ritual_step,
                cadence_window=active_cadence,
                energy_required=ritual_energy,
                estimated_minutes=min(minutes, 25),
                score=round(ritual_score, 2),
                reason=f"Cadence baseline ritual for {active_cadence} ({minutes}m budget).",
            )
        )

        candidates.sort(key=lambda item: (-item.score, item.id))
        return MomentumPromptsResponse(
            now_iso=normalized_now,
            active_cadence=active_cadence,
            energy=energy,
            minutes=minutes,
            prompts=candidates[:5],
        )

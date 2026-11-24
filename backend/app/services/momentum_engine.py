"""ADD-minded Momentum Engine (Projects, Capture, Park/Promote, Breadcrumbs, Triage)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.graph.backend import GraphBackend
from app.graph.science import EXCLUDED_DEGREE_REL_TYPES, GraphScienceService
from app.models.schemas import (
    BreadcrumbCreateRequest,
    BreadcrumbView,
    ContextResumeCard,
    MomentumResumeResponse,
    ProjectCreateRequest,
    ProjectView,
    ThoughtCaptureRequest,
    ThoughtCaptureResponse,
    ThoughtKind,
    ThoughtParkRequest,
    ThoughtPromoteRequest,
    ThoughtStatus,
    ThoughtTransitionResponse,
    ThoughtView,
    TriageSweepRequest,
    TriageSweepResponse,
)
from app.services.local_worker_client import LocalWorkerClient


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "item"


_KIND_WEIGHT: dict[ThoughtKind, int] = {
    "blocker": 30,
    "project_task": 20,
    "spark_idea": 10,
    "side_quest": 0,
}


class MomentumEngine:
    """Coordinates ADD thought capture, guilt-free parking, breadcrumbs, and 3-slot triage."""

    def __init__(
        self,
        backend: GraphBackend,
        science: GraphScienceService,
        local_worker: LocalWorkerClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.backend = backend
        self.science = science
        self.local_worker = local_worker
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now_iso(self) -> str:
        return self._clock().isoformat()

    def _ensure_concept_tag(self, raw_tag: str) -> dict:
        slug = _slugify(raw_tag)
        tag_id = f"tag_{slug}"
        return self.backend.upsert_node(
            "ConceptTag",
            {
                "id": tag_id,
                "key": slug,
                "name": slug,
            },
        )

    def _node_to_thought(self, node: dict) -> ThoughtView:
        props = node.get("properties") or {}
        return ThoughtView(
            id=node["id"],
            text=str(props.get("text") or ""),
            kind=props.get("kind") or "spark_idea",
            status=props.get("status") or "next",
            project_id=props.get("project_id"),
            energy_cost=int(props.get("energy_cost") or 2),
            concept_tags=list(props.get("concept_tags") or []),
            suggested_micro_step=str(props.get("suggested_micro_step") or ""),
            inference_source=props.get("inference_source") or "deterministic_fallback",
            park_reason=props.get("park_reason"),
            routed_via_subhub=bool(props.get("routed_via_subhub", False)),
            subhub_id=props.get("subhub_id"),
            created_at=str(props.get("created_at") or ""),
            updated_at=str(props.get("updated_at") or ""),
            parked_at=props.get("parked_at"),
            agent_analysis=props.get("agent_analysis"),
        )

    def _node_to_breadcrumb(self, node: dict) -> BreadcrumbView:
        props = node.get("properties") or {}
        return BreadcrumbView(
            id=node["id"],
            project_id=str(props.get("project_id") or ""),
            last_action=str(props.get("last_action") or ""),
            next_micro_step=str(props.get("next_micro_step") or ""),
            blocker_note=props.get("blocker_note"),
            linked_thought_ids=list(props.get("linked_thought_ids") or []),
            supersedes_id=props.get("supersedes_id"),
            valid_from=str(props.get("valid_from") or ""),
            valid_to=props.get("valid_to"),
            recorded_at=str(props.get("recorded_at") or ""),
            closed_at=props.get("closed_at"),
        )

    def _build_project_view(self, node: dict) -> ProjectView:
        props = node.get("properties") or {}
        pid = node["id"]
        project_thoughts = self.backend.query_nodes("Thought", {"project_id": pid})
        active_wip = sum(
            1
            for t in project_thoughts
            if (t.get("properties") or {}).get("status") in {"now", "next"}
        )
        parked = sum(
            1
            for t in project_thoughts
            if (t.get("properties") or {}).get("status") == "parked"
        )
        breadcrumbs = self.backend.query_nodes("Breadcrumb", {"project_id": pid})
        active_bc = next(
            (
                b
                for b in breadcrumbs
                if (b.get("properties") or {}).get("closed_at") is None
            ),
            None,
        )
        degree = self.backend.get_node_degree(
            pid, excluded_rel_types=set(EXCLUDED_DEGREE_REL_TYPES)
        )
        return ProjectView(
            id=pid,
            name=str(props.get("name") or pid),
            description=str(props.get("description") or ""),
            status=props.get("status") or "active",
            cadence_preference=props.get("cadence_preference") or "deep_tide",
            priority=int(props.get("priority") or 3),
            tags=list(props.get("tags") or []),
            degree=degree,
            active_wip_count=active_wip,
            parked_count=parked,
            latest_breadcrumb_id=active_bc["id"] if active_bc else None,
            created_at=str(props.get("created_at") or ""),
            updated_at=str(props.get("updated_at") or ""),
        )

    def _active_wip_thoughts(self, project_id: str | None = None) -> list[dict]:
        filters = {"project_id": project_id} if project_id else None
        thoughts = self.backend.query_nodes("Thought", filters=filters, limit=1000)
        return [
            t
            for t in thoughts
            if (t.get("properties") or {}).get("status") in {"now", "next"}
        ]

    def _overwhelm_state(self, active_wip_count: int) -> tuple[bool, str | None]:
        if active_wip_count > 3:
            return (
                True,
                f"Active WIP is {active_wip_count} (> 3). Run /api/v1/triage/sweep or park side quests to protect focus.",
            )
        return False, None

    def create_project(self, req: ProjectCreateRequest) -> ProjectView:
        now_iso = self._now_iso()
        proj_id = f"proj_{_slugify(req.name)[:24]}_{uuid4().hex[:6]}"
        clean_tags = list(dict.fromkeys(_slugify(t) for t in req.tags if t.strip()))[:3]

        node = self.backend.upsert_node(
            "Project",
            {
                "id": proj_id,
                "name": req.name.strip(),
                "description": req.description.strip(),
                "status": "active",
                "cadence_preference": req.cadence_preference,
                "priority": req.priority,
                "tags": clean_tags,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        )
        for tag_slug in clean_tags:
            tag_node = self._ensure_concept_tag(tag_slug)
            self.science.link_with_hexactine_invariant(
                self.backend,
                proj_id,
                "TAGGED_WITH",
                tag_node["id"],
                concept_tags=clean_tags,
                edge_props={"weight": 1.0},
            )
        return self._build_project_view(node)

    def list_projects(self) -> list[ProjectView]:
        nodes = self.backend.query_nodes("Project", limit=500)
        views = [self._build_project_view(n) for n in nodes]
        views.sort(key=lambda p: (-p.priority, p.created_at, p.id))
        return views

    def get_project(self, project_id: str) -> ProjectView:
        node = self.backend.get_node(project_id)
        if node is None or "Project" not in (node.get("labels") or []):
            raise KeyError(f"Project not found: {project_id}")
        return self._build_project_view(node)

    async def capture_thought(
        self, req: ThoughtCaptureRequest
    ) -> ThoughtCaptureResponse:
        if req.project_id is not None:
            proj = self.backend.get_node(req.project_id)
            if proj is None or "Project" not in (proj.get("labels") or []):
                raise KeyError(f"Project not found: {req.project_id}")

        classification = await self.local_worker.classify_and_extract(
            req.text,
            explicit_kind=req.kind,
            explicit_tags=req.concept_tags or None,
        )
        energy = req.energy_cost if req.energy_cost is not None else classification.energy_cost
        now_iso = self._now_iso()

        current_now = [
            t
            for t in self.backend.query_nodes("Thought", limit=1000)
            if (t.get("properties") or {}).get("status") == "now"
        ]
        if req.auto_park or (
            classification.kind == "side_quest" and req.project_id is None
        ):
            status: ThoughtStatus = "parked"
            parked_at: str | None = now_iso
            park_reason: str | None = (
                "auto_park" if req.auto_park else "side_quest_parking_lot"
            )
        elif not current_now:
            status = "now"
            parked_at = None
            park_reason = None
        else:
            status = "next"
            parked_at = None
            park_reason = None

        thought_id = f"th_{uuid4().hex[:8]}"
        
        agent_analysis_data = None
        if classification.agent_analysis:
            agent_analysis_data = classification.agent_analysis.model_dump()

        self.backend.upsert_node(
            "Thought",
            {
                "id": thought_id,
                "text": req.text.strip(),
                "kind": classification.kind,
                "status": status,
                "project_id": req.project_id,
                "energy_cost": energy,
                "concept_tags": classification.concept_tags,
                "suggested_micro_step": classification.suggested_micro_step,
                "inference_source": classification.inference_source,
                "agent_analysis": agent_analysis_data,
                "park_reason": park_reason,
                "routed_via_subhub": False,
                "subhub_id": None,
                "created_at": now_iso,
                "updated_at": now_iso,
                "parked_at": parked_at,
            },
        )

        routed_via_subhub = False
        subhub_id: str | None = None

        if req.project_id is not None:
            _, proj_routed, proj_hub = self.science.link_with_hexactine_invariant(
                self.backend,
                thought_id,
                "BELONGS_TO",
                req.project_id,
                concept_tags=classification.concept_tags,
                edge_props={"weight": 1.0},
            )
            if proj_routed:
                routed_via_subhub = True
                subhub_id = proj_hub

        linked_tags: list[str] = []
        for tag_slug in classification.concept_tags[:3]:
            tag_node = self._ensure_concept_tag(tag_slug)
            _, tag_routed, tag_hub = self.science.link_with_hexactine_invariant(
                self.backend,
                thought_id,
                "TAGGED_WITH",
                tag_node["id"],
                concept_tags=classification.concept_tags,
                edge_props={"weight": 0.9},
            )
            linked_tags.append(tag_slug)
            if tag_routed and not routed_via_subhub:
                routed_via_subhub = True
                subhub_id = tag_hub

        updated_node = self.backend.upsert_node(
            "Thought",
            {
                "id": thought_id,
                "routed_via_subhub": routed_via_subhub,
                "subhub_id": subhub_id,
            },
        )

        active_wip = len(self._active_wip_thoughts())
        overwhelm_warning, overwhelm_message = self._overwhelm_state(active_wip)

        return ThoughtCaptureResponse(
            thought=self._node_to_thought(updated_node),
            linked_tags=linked_tags,
            routed_via_subhub=routed_via_subhub,
            subhub_id=subhub_id,
            active_wip_count=active_wip,
            overwhelm_warning=overwhelm_warning,
            overwhelm_message=overwhelm_message,
        )

    def list_thoughts(
        self,
        status: ThoughtStatus | None = None,
        project_id: str | None = None,
        kind: ThoughtKind | None = None,
    ) -> list[ThoughtView]:
        filters: dict[str, object] = {}
        if status is not None:
            filters["status"] = status
        if project_id is not None:
            filters["project_id"] = project_id
        if kind is not None:
            filters["kind"] = kind
        nodes = self.backend.query_nodes("Thought", filters=filters or None, limit=1000)
        views = [self._node_to_thought(n) for n in nodes]
        views.sort(key=lambda t: (t.created_at, t.id))
        return views

    def park_thought(
        self, thought_id: str, req: ThoughtParkRequest
    ) -> ThoughtTransitionResponse:
        node = self.backend.get_node(thought_id)
        if node is None or "Thought" not in (node.get("labels") or []):
            raise KeyError(f"Thought not found: {thought_id}")

        now_iso = self._now_iso()
        updated = self.backend.upsert_node(
            "Thought",
            {
                "id": thought_id,
                "status": "parked",
                "park_reason": req.reason or "guilt_free_parked",
                "parked_at": now_iso,
                "updated_at": now_iso,
            },
        )
        active_wip = len(self._active_wip_thoughts())
        overwhelm_warning, overwhelm_message = self._overwhelm_state(active_wip)
        return ThoughtTransitionResponse(
            thought=self._node_to_thought(updated),
            demoted_thought_id=None,
            active_wip_count=active_wip,
            overwhelm_warning=overwhelm_warning,
            overwhelm_message=overwhelm_message,
        )

    def promote_thought(
        self, thought_id: str, req: ThoughtPromoteRequest
    ) -> ThoughtTransitionResponse:
        node = self.backend.get_node(thought_id)
        if node is None or "Thought" not in (node.get("labels") or []):
            raise KeyError(f"Thought not found: {thought_id}")

        if req.project_id is not None:
            proj = self.backend.get_node(req.project_id)
            if proj is None or "Project" not in (proj.get("labels") or []):
                raise KeyError(f"Project not found: {req.project_id}")

        now_iso = self._now_iso()
        demoted_id: str | None = None

        if req.target_slot == "now":
            existing_now = self.backend.query_nodes("Thought", {"status": "now"}, limit=50)
            for other in existing_now:
                if other["id"] != thought_id:
                    demoted_id = other["id"]
                    self.backend.upsert_node(
                        "Thought",
                        {
                            "id": other["id"],
                            "status": "next",
                            "updated_at": now_iso,
                        },
                    )

        props_update: dict[str, object] = {
            "id": thought_id,
            "status": req.target_slot,
            "parked_at": None,
            "park_reason": None,
            "updated_at": now_iso,
        }

        if req.project_id is not None:
            props_update["project_id"] = req.project_id
            tags = list((node.get("properties") or {}).get("concept_tags") or [])
            _, routed, subhub = self.science.link_with_hexactine_invariant(
                self.backend,
                thought_id,
                "BELONGS_TO",
                req.project_id,
                concept_tags=tags,
                edge_props={"weight": 1.0},
            )
            if routed:
                props_update["routed_via_subhub"] = True
                props_update["subhub_id"] = subhub

        updated = self.backend.upsert_node("Thought", props_update)
        active_wip = len(self._active_wip_thoughts())
        overwhelm_warning, overwhelm_message = self._overwhelm_state(active_wip)
        return ThoughtTransitionResponse(
            thought=self._node_to_thought(updated),
            demoted_thought_id=demoted_id,
            active_wip_count=active_wip,
            overwhelm_warning=overwhelm_warning,
            overwhelm_message=overwhelm_message,
        )

    def create_breadcrumb(self, req: BreadcrumbCreateRequest) -> BreadcrumbView:
        proj = self.backend.get_node(req.project_id)
        if proj is None or "Project" not in (proj.get("labels") or []):
            raise KeyError(f"Project not found: {req.project_id}")

        now_iso = self._now_iso()
        existing = self.backend.query_nodes("Breadcrumb", {"project_id": req.project_id})
        existing.sort(
            key=lambda b: (
                str((b.get("properties") or {}).get("recorded_at") or ""),
                b["id"],
            )
        )
        unclosed = [
            b
            for b in existing
            if (b.get("properties") or {}).get("closed_at") is None
        ]
        active_prev = unclosed[-1] if unclosed else None

        crumb_id = f"bc_{uuid4().hex[:8]}"
        valid_from = req.valid_from or now_iso
        prev_id = active_prev["id"] if active_prev else None

        crumb_node = self.backend.upsert_node(
            "Breadcrumb",
            {
                "id": crumb_id,
                "project_id": req.project_id,
                "last_action": req.last_action.strip(),
                "next_micro_step": req.next_micro_step.strip(),
                "blocker_note": req.blocker_note.strip() if req.blocker_note else None,
                "linked_thought_ids": list(req.linked_thought_ids),
                "supersedes_id": prev_id,
                "valid_from": valid_from,
                "valid_to": None,
                "recorded_at": now_iso,
                "closed_at": None,
            },
        )

        if unclosed:
            for prev_bc in unclosed:
                self.backend.upsert_node(
                    "Breadcrumb",
                    {
                        "id": prev_bc["id"],
                        "valid_to": now_iso,
                        "closed_at": now_iso,
                    },
                )
            assert active_prev is not None
            self.backend.upsert_edge(
                crumb_id,
                "SUPERSEDES",
                active_prev["id"],
                {"at": now_iso, "weight": 1.0},
            )
        else:
            self.science.link_with_hexactine_invariant(
                self.backend,
                crumb_id,
                "HAS_BREADCRUMB",
                req.project_id,
                concept_tags=[],
                edge_props={"weight": 1.0},
            )

        for th_id in req.linked_thought_ids[:4]:
            th_node = self.backend.get_node(th_id)
            if th_node is not None:
                self.backend.upsert_edge(
                    crumb_id,
                    "RESUMES_FROM",
                    th_id,
                    {"weight": 0.8},
                )

        return self._node_to_breadcrumb(crumb_node)

    async def resume_momentum(
        self, project_id: str | None = None
    ) -> MomentumResumeResponse:
        target_project_id = project_id
        if target_project_id is None:
            now_thoughts = self.backend.query_nodes("Thought", {"status": "now"}, limit=10)
            for th in now_thoughts:
                pid = (th.get("properties") or {}).get("project_id")
                if pid:
                    target_project_id = str(pid)
                    break

        if target_project_id is None:
            projects = self.list_projects()
            if not projects:
                raise KeyError("No active projects found to resume")
            target_project_id = projects[0].id

        project = self.get_project(target_project_id)
        breadcrumbs = self.backend.query_nodes(
            "Breadcrumb", {"project_id": target_project_id}, limit=500
        )
        breadcrumbs.sort(
            key=lambda b: str((b.get("properties") or {}).get("recorded_at") or "")
        )
        active_bc_node = next(
            (
                b
                for b in reversed(breadcrumbs)
                if (b.get("properties") or {}).get("closed_at") is None
            ),
            breadcrumbs[-1] if breadcrumbs else None,
        )
        active_bc = (
            self._node_to_breadcrumb(active_bc_node) if active_bc_node else None
        )

        project_thoughts = self.list_thoughts(project_id=target_project_id)
        prioritized_sparks = sorted(
            [t for t in project_thoughts if t.status != "done"],
            key=lambda t: (1 if t.status in {"now", "next"} else 0, t.created_at, t.id),
            reverse=True,
        )
        linked_sparks = [t.text[:60] for t in prioritized_sparks[:3]]
        if not linked_sparks and project.tags:
            all_thoughts = sorted(
                self.list_thoughts(),
                key=lambda t: (1 if t.status != "done" else 0, t.created_at, t.id),
                reverse=True,
            )
            for th in all_thoughts:
                if set(th.concept_tags) & set(project.tags):
                    linked_sparks.append(th.text[:60])
                if len(linked_sparks) >= 3:
                    break

        if active_bc is not None:
            last_action = active_bc.last_action
            next_micro_step = active_bc.next_micro_step
        elif prioritized_sparks:
            lead_th = prioritized_sparks[0]
            last_action = f"Captured {lead_th.kind}: {lead_th.text[:60]}"
            next_micro_step = lead_th.suggested_micro_step
        elif project_thoughts:
            first_th = project_thoughts[-1]
            last_action = f"Captured {first_th.kind}: {first_th.text[:60]}"
            next_micro_step = first_th.suggested_micro_step
        else:
            last_action = f"Initialized project {project.name}"
            next_micro_step = "Capture your first thought or drop a breadcrumb"

        card_lines = await self.local_worker.summarize_resume_card(
            project.name, last_action, next_micro_step, linked_sparks
        )
        resume_card = ContextResumeCard(
            last_action=last_action,
            next_micro_step=next_micro_step,
            linked_sparks=linked_sparks,
            card_lines=card_lines,
        )

        anchor_id = (
            active_bc.id
            if active_bc is not None
            else (
                prioritized_sparks[0].id
                if prioritized_sparks
                else (project_thoughts[0].id if project_thoughts else project.id)
            )
        )
        raw_nodes, raw_edges = self.backend.get_subgraph(
            focus_id=project.id, limit=200
        )
        path_bridge = self.science.compute_shortest_path(
            raw_nodes, raw_edges, anchor_id, project.id
        )

        return MomentumResumeResponse(
            project=project,
            active_breadcrumb=active_bc,
            chain_depth=len(breadcrumbs),
            resume_card=resume_card,
            path_bridge=path_bridge,
            gds_cypher_preview=path_bridge.gds_cypher_preview,
        )

    def triage_sweep(self, req: TriageSweepRequest) -> TriageSweepResponse:
        if req.project_id is not None:
            proj = self.backend.get_node(req.project_id)
            if proj is None or "Project" not in (proj.get("labels") or []):
                raise KeyError(f"Project not found: {req.project_id}")

        now_iso = self._now_iso()
        active_nodes = self._active_wip_thoughts(project_id=req.project_id)
        pre_sweep_count = len(active_nodes)

        def _score_key(node: dict) -> tuple[int, str, str]:
            props = node.get("properties") or {}
            kind: ThoughtKind = props.get("kind") or "spark_idea"
            slot = props.get("status") or "next"
            energy = int(props.get("energy_cost") or 3)
            score = (
                _KIND_WEIGHT.get(kind, 10)
                + (5 if slot == "now" else 0)
                + (6 - energy) * 2
            )
            return (-score, str(props.get("created_at") or ""), node["id"])

        ranked = sorted(active_nodes, key=_score_key)
        now_views: list[ThoughtView] = []
        next_views: list[ThoughtView] = []
        newly_parked_ids: list[str] = []

        for idx, node in enumerate(ranked):
            nid = node["id"]
            if idx < req.max_now:
                updated = self.backend.upsert_node(
                    "Thought",
                    {
                        "id": nid,
                        "status": "now",
                        "parked_at": None,
                        "park_reason": None,
                        "updated_at": now_iso,
                    },
                )
                now_views.append(self._node_to_thought(updated))
            elif idx < req.max_now + req.max_next:
                updated = self.backend.upsert_node(
                    "Thought",
                    {
                        "id": nid,
                        "status": "next",
                        "parked_at": None,
                        "park_reason": None,
                        "updated_at": now_iso,
                    },
                )
                next_views.append(self._node_to_thought(updated))
            else:
                self.backend.upsert_node(
                    "Thought",
                    {
                        "id": nid,
                        "status": "parked",
                        "park_reason": "triage_sweep_3_slot_horizon",
                        "parked_at": now_iso,
                        "updated_at": now_iso,
                    },
                )
                newly_parked_ids.append(nid)

        if now_views:
            claimed_now_id = now_views[0].id
            existing_now = self.backend.query_nodes("Thought", {"status": "now"}, limit=50)
            for other in existing_now:
                if other["id"] != claimed_now_id:
                    self.backend.upsert_node(
                        "Thought",
                        {
                            "id": other["id"],
                            "status": "next",
                            "updated_at": now_iso,
                        },
                    )

        all_parked = self.backend.query_nodes(
            "Thought",
            filters=(
                {"status": "parked", "project_id": req.project_id}
                if req.project_id
                else {"status": "parked"}
            ),
            limit=1000,
        )
        overwhelm_index = round(min(1.0, pre_sweep_count / 6.0), 3)

        if pre_sweep_count == 0:
            recommendation = "Horizon is clear. Capture one concrete task to begin."
        elif newly_parked_ids:
            recommendation = (
                f"Parked {len(newly_parked_ids)} overflow item(s) cleanly. "
                f"Focus on your single Now slot ({now_views[0].text[:48]})."
            )
        else:
            recommendation = (
                "Focus horizon is within the 3-slot limit (Now <= 1, Next <= 2)."
            )

        return TriageSweepResponse(
            now=now_views,
            next=next_views,
            parked_count=len(all_parked),
            newly_parked_ids=newly_parked_ids,
            pre_sweep_active_count=pre_sweep_count,
            overwhelm_index=overwhelm_index,
            recommendation=recommendation,
        )

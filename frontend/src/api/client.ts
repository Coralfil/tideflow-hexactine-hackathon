export type ThoughtKind = 'spark_idea' | 'project_task' | 'side_quest' | 'blocker';
export type ThoughtStatus = 'now' | 'next' | 'parked' | 'done';
export type GraphLens = 'pagerank' | 'communities' | 'path' | 'degree_audit';
export type CadenceWindow = 'deep_tide' | 'creative_swell' | 'shallow_drift' | 'recovery_ebb';
export type CapabilityName =
  | 'local_fs_read'
  | 'repo_git_scan'
  | 'web_fetch_public'
  | 'local_llm_ollama';

export interface HealthResponse {
  status: 'ok' | 'degraded';
  backend_mode: 'relate' | 'inprocess' | 'neo4j';
  relate_available: boolean;
  neo4j_available: boolean;
  local_worker_available: boolean;
  active_cadence: CadenceWindow;
  degree_invariant_max: number;
  hsl_bridge_loaded: boolean;
}

export interface ProjectView {
  id: string;
  name: string;
  description: string;
  status: string;
  cadence_preference: CadenceWindow;
  priority: number;
  tags: string[];
  degree: number;
  active_wip_count: number;
  parked_count: number;
  latest_breadcrumb_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentOffloadAnalysis {
  usability: string;
  difficulty: string;
  workload: string;
  compatibility: string;
  net_benefit: string;
  can_offload: boolean;
  go_nogo_report: string;
}

export interface ThoughtView {
  id: string;
  text: string;
  kind: ThoughtKind;
  status: ThoughtStatus;
  project_id: string | null;
  energy_cost: number;
  concept_tags: string[];
  suggested_micro_step: string;
  inference_source: string;
  park_reason: string | null;
  routed_via_subhub: boolean;
  subhub_id: string | null;
  created_at: string;
  updated_at: string;
  parked_at: string | null;
  agent_analysis?: AgentOffloadAnalysis;
}

export interface ThoughtCaptureResponse {
  thought: ThoughtView;
  linked_tags: string[];
  routed_via_subhub: boolean;
  subhub_id: string | null;
  active_wip_count: number;
  overwhelm_warning: boolean;
  overwhelm_message: string | null;
}

export interface TriageSweepResponse {
  now: ThoughtView[];
  next: ThoughtView[];
  parked_count: number;
  newly_parked_ids: string[];
  pre_sweep_active_count: number;
  overwhelm_index: number;
  recommendation: string;
}

export interface BreadcrumbView {
  id: string;
  project_id: string;
  last_action: string;
  next_micro_step: string;
  blocker_note: string | null;
  linked_thought_ids: string[];
  supersedes_id: string | null;
  valid_from: string;
  valid_to: string | null;
  recorded_at: string;
  closed_at: string | null;
}

export interface ContextResumeCard {
  last_action: string;
  next_micro_step: string;
  linked_sparks: string[];
  card_lines: string[];
}

export interface GraphNodeView {
  id: string;
  labels: string[];
  label: string;
  title: string;
  status: string | null;
  kind: string | null;
  degree: number;
  pagerank: number;
  normalized_pagerank: number;
  community_id: number;
  hexactine_compliant: boolean;
  in_active_path: boolean;
}

export interface GraphEdgeView {
  id: string;
  source: string;
  target: string;
  rel_type: string;
  weight: number;
  routed_via_subhub: boolean;
  in_active_path: boolean;
}

export interface ShortestPathResult {
  found: boolean;
  source_id: string;
  target_id: string;
  node_ids: string[];
  edges: GraphEdgeView[];
  total_cost: number | null;
  hop_count: number;
  gds_cypher_preview: string;
}

export interface MomentumResumeResponse {
  project: ProjectView;
  active_breadcrumb: BreadcrumbView | null;
  chain_depth: number;
  resume_card: ContextResumeCard;
  path_bridge: ShortestPathResult | null;
  gds_cypher_preview: string;
}

export interface GraphScienceMetrics {
  node_count: number;
  edge_count: number;
  community_count: number;
  modularity: number;
  max_degree_allowed: number;
  max_observed_degree: number;
  sub_hub_count: number;
  invariant_ok: boolean;
  top_pagerank_ids: string[];
}

export interface GraphSnapshotResponse {
  lens: GraphLens;
  focus_id: string | null;
  nodes: GraphNodeView[];
  edges: GraphEdgeView[];
  metrics: GraphScienceMetrics;
  active_path: ShortestPathResult | null;
  gds_cypher_preview: string;
}

export interface ScheduleBlockView {
  id: string;
  title: string;
  project_id: string | null;
  thought_id: string | null;
  cadence_window: CadenceWindow;
  start_iso: string;
  end_iso: string;
  status: string;
  energy_required: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface MomentumPromptItem {
  id: string;
  source_type: string;
  source_id: string | null;
  title: string;
  micro_step: string;
  cadence_window: CadenceWindow;
  energy_required: number;
  estimated_minutes: number;
  score: number;
  reason: string;
}

export interface MomentumPromptsResponse {
  now_iso: string;
  active_cadence: CadenceWindow;
  energy: number;
  minutes: number;
  prompts: MomentumPromptItem[];
}

export interface RetrieverPermissionsView {
  local_fs_read: boolean;
  repo_git_scan: boolean;
  web_fetch_public: boolean;
  local_llm_ollama: boolean;
  allowed_paths: string[];
  allowed_domains: string[];
  updated_at: string;
}

export interface RetrievalArtifactView {
  id: string;
  title: string;
  label: string;
  capability: string;
  target: string;
  summary: string;
  excerpt: string;
  source_ref: string;
  grounded_node_id: string | null;
  inference_source: string;
  created_at: string;
}

export interface AuditEntryView {
  id: string;
  trace_id: string;
  service: string;
  capability: string;
  target: string;
  verdict: 'ALLOWED' | 'DENIED';
  decision: 'ALLOWED' | 'DENIED';
  reason: string;
  artifact_id: string | null;
  timestamp: string;
}

export interface RetrieverExecuteResponse {
  job_id: string;
  verdict: 'ALLOWED';
  decision: 'ALLOWED';
  artifact: RetrievalArtifactView;
  audit_entry: AuditEntryView;
  grounded_edge_id: string | null;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  const text = await resp.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    if (parsed && typeof parsed === 'object') {
      const obj = parsed as Record<string, unknown>;
      if (obj.detail && typeof obj.detail === 'object') {
        const det = obj.detail as Record<string, unknown>;
        msg = String(det.message || msg);
      } else if (typeof obj.detail === 'string') {
        msg = obj.detail;
      }
    }
    throw new ApiError(resp.status, msg, parsed);
  }

  return parsed as T;
}

export const api = {
  getHealth: () => requestJson<HealthResponse>('/health'),
  listProjects: () => requestJson<ProjectView[]>('/projects'),
  createProject: (payload: {
    name: string;
    description?: string;
    cadence_preference?: CadenceWindow;
    priority?: number;
  }) =>
    requestJson<ProjectView>('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listThoughts: (projectId?: string) =>
    requestJson<ThoughtView[]>(
      projectId ? `/thoughts?project_id=${encodeURIComponent(projectId)}` : '/thoughts'
    ),
  captureThought: (payload: {
    text: string;
    kind?: ThoughtKind;
    project_id?: string | null;
    energy_cost?: number;
    auto_park?: boolean;
  }) =>
    requestJson<ThoughtCaptureResponse>('/thoughts/capture', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  parkThought: (thoughtId: string, reason?: string) =>
    requestJson<unknown>(`/thoughts/${encodeURIComponent(thoughtId)}/park`, {
      method: 'POST',
      body: JSON.stringify(reason ? { reason } : {}),
    }),
  promoteThought: (thoughtId: string, targetSlot: 'now' | 'next' = 'now') =>
    requestJson<unknown>(`/thoughts/${encodeURIComponent(thoughtId)}/promote`, {
      method: 'POST',
      body: JSON.stringify({ target_slot: targetSlot }),
    }),

  triageSweep: (projectId?: string) =>
    requestJson<TriageSweepResponse>('/triage/sweep', {
      method: 'POST',
      body: JSON.stringify(projectId ? { project_id: projectId } : {}),
    }),
  createBreadcrumb: (payload: {
    project_id: string;
    last_action: string;
    next_micro_step: string;
  }) =>
    requestJson<BreadcrumbView>('/breadcrumbs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  resumeMomentum: (projectId?: string) =>
    requestJson<MomentumResumeResponse>(
      projectId ? `/momentum/resume?project_id=${encodeURIComponent(projectId)}` : '/momentum/resume'
    ),

  getGraphSnapshot: (params: {
    lens: GraphLens;
    focusId?: string;
    sourceId?: string;
    targetId?: string;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    qs.set('lens', params.lens);
    if (params.focusId) qs.set('focus_id', params.focusId);
    if (params.sourceId) qs.set('source_id', params.sourceId);
    if (params.targetId) qs.set('target_id', params.targetId);
    qs.set('limit', String(params.limit ?? 180));
    return requestJson<GraphSnapshotResponse>(`/graph/snapshot?${qs.toString()}`);
  },
  getShortestPath: (sourceId: string, targetId: string) => {
    const qs = new URLSearchParams({ source_id: sourceId, target_id: targetId });
    return requestJson<ShortestPathResult>(`/graph/path?${qs.toString()}`);
  },

  listScheduleBlocks: () => requestJson<ScheduleBlockView[]>('/schedule/blocks'),
  createScheduleBlock: (payload: {
    title: string;
    start_iso: string;
    end_iso: string;
    cadence_window: CadenceWindow;
    project_id?: string | null;
    energy_required?: number;
  }) =>
    requestJson<ScheduleBlockView>('/schedule/blocks', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateScheduleBlock: (
    blockId: string,
    payload: { status?: string; title?: string; cadence_window?: CadenceWindow }
  ) =>
    requestJson<ScheduleBlockView>(`/schedule/blocks/${encodeURIComponent(blockId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteScheduleBlock: (blockId: string) =>
    requestJson<{ deleted: boolean; id: string }>(
      `/schedule/blocks/${encodeURIComponent(blockId)}`,
      { method: 'DELETE' }
    ),
  getSchedulePrompts: (params: { nowIso?: string; energy: number; minutes: number }) => {
    const qs = new URLSearchParams();
    if (params.nowIso) qs.set('now_iso', params.nowIso);
    qs.set('energy', String(params.energy));
    qs.set('minutes', String(params.minutes));
    return requestJson<MomentumPromptsResponse>(`/schedule/prompts?${qs.toString()}`);
  },

  getRetrieverPermissions: () => requestJson<RetrieverPermissionsView>('/retriever/permissions'),
  updateRetrieverPermissions: (payload: Partial<Record<CapabilityName, boolean>>) =>
    requestJson<RetrieverPermissionsView>('/retriever/permissions', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  executeRetriever: (payload: {
    capability: string;
    target: string;
    query?: string;
    project_id?: string | null;
  }) =>
    requestJson<RetrieverExecuteResponse>('/retriever/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listRetrieverAudit: () => requestJson<AuditEntryView[]>('/retriever/audit'),
};

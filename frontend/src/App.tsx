import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Cpu, Plus, Sparkles } from 'lucide-react';
import {
  api,
  ApiError,
  type AuditEntryView,
  type CapabilityName,
  type GraphLens,
  type GraphSnapshotResponse,
  type HealthResponse,
  type MomentumPromptsResponse,
  type MomentumResumeResponse,
  type ProjectView,
  type RetrieverExecuteResponse,
  type RetrieverPermissionsView,
  type ScheduleBlockView,
  type ShortestPathResult,
  type ThoughtKind,
  type ThoughtView,
  type TriageSweepResponse,
} from './api/client';
import { BrainDumpModal } from './components/BrainDumpModal';
import { FocusHorizon } from './components/FocusHorizon';
import { GraphCanvas } from './components/GraphCanvas';
import { NemoclawConsole } from './components/NemoclawConsole';
import { RhythmDialAndScheduler } from './components/RhythmDialAndScheduler';
import { applyHoudiniTokens, initHoudiniLayer } from './utils/houdini';

export const App: React.FC = () => {
  const [reducedMotion] = useState<boolean>(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
  );

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [offlineBanner, setOfflineBanner] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectView[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [newProjectName, setNewProjectName] = useState('');

  const [thoughts, setThoughts] = useState<ThoughtView[]>([]);
  const [triage, setTriage] = useState<TriageSweepResponse | null>(null);
  const [resumeData, setResumeData] = useState<MomentumResumeResponse | null>(null);

  const [activeLens, setActiveLens] = useState<GraphLens>('pagerank');
  const [snapshot, setSnapshot] = useState<GraphSnapshotResponse | null>(null);
  const [pathResult, setPathResult] = useState<ShortestPathResult | null>(null);
  const snapshotSeqRef = useRef(0);

  const [energy, setEnergy] = useState<number>(3);
  const [minutes, setMinutes] = useState<number>(25);
  const [bpm, setBpm] = useState<number>(68);
  const [blocks, setBlocks] = useState<ScheduleBlockView[]>([]);
  const [prompts, setPrompts] = useState<MomentumPromptsResponse | null>(null);

  const [permissions, setPermissions] = useState<RetrieverPermissionsView | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditEntryView[]>([]);
  const [lastArtifact, setLastArtifact] = useState<RetrieverExecuteResponse | null>(null);

  const [brainDumpOpen, setBrainDumpOpen] = useState<boolean>(false);

  const selectedProjectRef = useRef(selectedProjectId);
  selectedProjectRef.current = selectedProjectId;
  const activeLensRef = useRef(activeLens);
  activeLensRef.current = activeLens;
  const energyRef = useRef(energy);
  energyRef.current = energy;
  const minutesRef = useRef(minutes);
  minutesRef.current = minutes;

  const activeCadence = health?.active_cadence ?? 'deep_tide';
  const activeCount = thoughts.filter((t) => t.status === 'now' || t.status === 'next').length;
  const derivedOverwhelm = Math.min(1, Number((activeCount / 5).toFixed(3)));
  const overwhelmIndex = triage?.overwhelm_index ?? derivedOverwhelm;

  useEffect(() => {
    initHoudiniLayer(reducedMotion);
    const updated = applyHoudiniTokens({
      energy,
      overwhelmIndex,
      cadence: activeCadence,
    });
    setBpm(updated.bpm);
  }, [reducedMotion, energy, overwhelmIndex, activeCadence]);

  useEffect(() => {
    const onKeyDown = (evt: KeyboardEvent) => {
      if ((evt.ctrlKey || evt.metaKey) && evt.key.toLowerCase() === 'k') {
        evt.preventDefault();
        setBrainDumpOpen((prev) => !prev);
      } else if (evt.key === 'Escape') {
        setBrainDumpOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const loadGraphSnapshot = useCallback(async (lens: GraphLens, focusId?: string) => {
    const seq = ++snapshotSeqRef.current;
    try {
      const data = await api.getGraphSnapshot({ lens, focusId: focusId || undefined, limit: 80 });
      if (seq === snapshotSeqRef.current) {
        setSnapshot(data);
      }
    } catch {
      // Handled by global health indicator.
    }
  }, []);

  const loadWorkspaceData = useCallback(
    async (projectIdOverride?: string) => {
      try {
        const [healthRes, projList, thoughtList, blockList, promptRes, permRes, auditList] =
          await Promise.all([
            api.getHealth(),
            api.listProjects(),
            api.listThoughts(),
            api.listScheduleBlocks(),
            api.getSchedulePrompts({ energy: energyRef.current, minutes: minutesRef.current }),
            api.getRetrieverPermissions(),
            api.listRetrieverAudit(),
          ]);

        setOfflineBanner(null);
        setHealth(healthRes);
        setProjects(projList);
        const activeProjId =
          projectIdOverride || selectedProjectRef.current || projList[0]?.id || '';
        if (activeProjId) {
          setSelectedProjectId(activeProjId);
        }
        setThoughts(
          activeProjId
            ? thoughtList.filter((t) => !t.project_id || t.project_id === activeProjId)
            : thoughtList
        );
        setBlocks(blockList);
        setPrompts(promptRes);
        setPermissions(permRes);
        setAuditEntries(auditList);

        await loadGraphSnapshot(activeLensRef.current, activeProjId || undefined);

        if (activeProjId) {
          try {
            const resCard = await api.resumeMomentum(activeProjId);
            setResumeData(resCard);
          } catch {
            setResumeData(null);
          }
        }
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'Backend service unreachable on :8010.';
        setOfflineBanner(`Offline fallback active: ${msg}`);
      }
    },
    [loadGraphSnapshot]
  );

  const bootStartedRef = useRef(false);
  useEffect(() => {
    if (bootStartedRef.current) {
      return;
    }
    bootStartedRef.current = true;
    void loadWorkspaceData();
  }, [loadWorkspaceData]);

  const handleSelectLens = (lens: GraphLens) => {
    setActiveLens(lens);
    void loadGraphSnapshot(lens, selectedProjectRef.current || undefined);
  };

  const handleEnergyChange = (nextEnergy: number) => {
    setEnergy(nextEnergy);
    const tokens = applyHoudiniTokens({
      energy: nextEnergy,
      overwhelmIndex,
      cadence: activeCadence,
      phaseOffsetDeg: nextEnergy * 18,
    });
    setBpm(tokens.bpm);
    void api
      .getSchedulePrompts({ energy: nextEnergy, minutes })
      .then((res) => setPrompts(res))
      .catch(() => {});
  };

  const handleMinutesChange = (nextMinutes: number) => {
    setMinutes(nextMinutes);
    void api
      .getSchedulePrompts({ energy, minutes: nextMinutes })
      .then((res) => setPrompts(res))
      .catch(() => {});
  };

  const handleCreateProject = async (evt: React.FormEvent) => {
    evt.preventDefault();
    const cleaned = newProjectName.trim();
    if (!cleaned) {
      return;
    }
    const created = await api.createProject({ name: cleaned });
    setNewProjectName('');
    setSelectedProjectId(created.id);
    await loadWorkspaceData(created.id);
  };

  const selectedProject = projects.find((p) => p.id === selectedProjectId) ?? projects[0] ?? null;

  return (
    <div className="tideflow-shell">
      <header className="topbar">
        <div className="brand-group">
          <div className="brand-mark" aria-hidden="true">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="brand-title">TideFlow Hexactine</h1>
            <p className="brand-sub">
              ADD Momentum Cockpit, Tidal Cadence Scheduler, and Nemoclaw Graph Lattice
            </p>
          </div>
        </div>

        <div className="status-pills">
          <span className={`pill ${health ? 'pill-ok' : 'pill-danger'}`}>
            <Activity size={13} />
            Backend: {health ? health.backend_mode : 'offline'}
          </span>
          <span className="pill pill-accent">Cadence: {activeCadence}</span>
          <span className="pill">
            <Cpu size={13} />
            Neo4j: {health?.neo4j_available ? 'live' : 'fallback'}
          </span>
        </div>

        <div className="topbar-controls">
          <form onSubmit={handleCreateProject} style={{ display: 'flex', gap: 6 }}>
            <select
              aria-label="Active project"
              className="select"
              style={{ width: 175 }}
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                void loadWorkspaceData(e.target.value);
              }}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              type="text"
              className="input"
              style={{ width: 130 }}
              aria-label="New project name"
              placeholder="New hub..."
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
            />
            <button type="submit" className="btn btn-sm" aria-label="Add project">
              <Plus size={14} />
            </button>
          </form>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setBrainDumpOpen(true)}
          >
            Brain Dump (Ctrl+K)
          </button>
        </div>
      </header>

      {offlineBanner && (
        <div className="alert-banner alert-error" role="status" style={{ marginBottom: 14 }}>
          {offlineBanner}
        </div>
      )}

      <main className="cockpit-grid">
        <div className="col-span-6">
          <FocusHorizon
            selectedProject={selectedProject}
            thoughts={thoughts}
            triage={triage}
            resumeData={resumeData}
            reducedMotion={reducedMotion}
            onOpenBrainDump={() => setBrainDumpOpen(true)}
            onRunSweep={async () => {
              const res = await api.triageSweep(selectedProject?.id);
              setTriage(res);
              const refreshed = await api.listThoughts(selectedProject?.id);
              setThoughts(refreshed);
            }}
            onParkThought={async (thoughtId) => {
              await api.parkThought(thoughtId, 'Parked from Focus Horizon');
              await loadWorkspaceData(selectedProject?.id);
            }}
            onPromoteThought={async (thoughtId) => {
              await api.promoteThought(thoughtId, 'now');
              await loadWorkspaceData(selectedProject?.id);
            }}
            onSaveBreadcrumb={async (lastAction, nextStep) => {
              if (!selectedProject) {
                throw new Error('Select or create a project first.');
              }
              await api.createBreadcrumb({
                project_id: selectedProject.id,
                last_action: lastAction,
                next_micro_step: nextStep,
              });
              const resumed = await api.resumeMomentum(selectedProject.id);
              setResumeData(resumed);
              await loadGraphSnapshot(activeLens, selectedProject.id);
            }}
            onResumeContext={async () => {
              if (!selectedProject) {
                throw new Error('Select or create a project first.');
              }
              const resumed = await api.resumeMomentum(selectedProject.id);
              setResumeData(resumed);
            }}
          />
        </div>

        <div className="col-span-6">
          <GraphCanvas
            snapshot={snapshot}
            activeLens={activeLens}
            pathResult={pathResult}
            reducedMotion={reducedMotion}
            onSelectLens={handleSelectLens}
            onTracePath={async (src, dst) => {
              const path = await api.getShortestPath(src, dst);
              setPathResult(path);
              const updated = await api.getGraphSnapshot({
                lens: 'path',
                sourceId: src,
                targetId: dst,
                limit: 80,
              });
              setActiveLens('path');
              setSnapshot(updated);
            }}
          />
        </div>

        <div className="col-span-6">
          <RhythmDialAndScheduler
            activeCadence={activeCadence}
            bpm={bpm}
            energy={energy}
            minutes={minutes}
            blocks={blocks}
            prompts={prompts}
            reducedMotion={reducedMotion}
            onEnergyChange={handleEnergyChange}
            onMinutesChange={handleMinutesChange}
            onRefreshPrompts={async (eVal, mVal) => {
              const res = await api.getSchedulePrompts({ energy: eVal, minutes: mVal });
              setPrompts(res);
            }}
            onCreateBlock={async (payload) => {
              try {
                await api.createScheduleBlock({
                  ...payload,
                  project_id: selectedProject?.id ?? null,
                });
                const updated = await api.listScheduleBlocks();
                setBlocks(updated);
              } catch (err) {
                if (err instanceof ApiError && err.status === 409) {
                  throw new Error(
                    `Schedule conflict (409): block overlaps an existing window (${err.message})`
                  );
                }
                throw err;
              }
            }}
            onCompleteBlock={async (blockId) => {
              await api.updateScheduleBlock(blockId, { status: 'completed' });
              setBlocks(await api.listScheduleBlocks());
            }}
            onDeleteBlock={async (blockId) => {
              await api.deleteScheduleBlock(blockId);
              setBlocks(await api.listScheduleBlocks());
            }}
          />
        </div>

        <div className="col-span-6">
          <NemoclawConsole
            permissions={permissions}
            auditEntries={auditEntries}
            selectedProject={selectedProject}
            lastArtifact={lastArtifact}
            onTogglePermission={async (cap, enabled) => {
              const nextPerms = await api.updateRetrieverPermissions({ [cap]: enabled });
              setPermissions(nextPerms);
            }}
            onExecute={async (payload) => {
              try {
                const res = await api.executeRetriever(payload);
                setLastArtifact(res);
                setAuditEntries(await api.listRetrieverAudit());
                await loadGraphSnapshot(activeLens, selectedProject?.id);
              } catch (err) {
                setAuditEntries(await api.listRetrieverAudit().catch(() => auditEntries));
                if (err instanceof ApiError && err.status === 403) {
                  throw new Error(`Permission denied (403): ${err.message}`);
                }
                throw err;
              }
            }}
          />
        </div>
      </main>

      <BrainDumpModal
        isOpen={brainDumpOpen}
        projects={projects}
        selectedProjectId={selectedProject?.id ?? ''}
        reducedMotion={reducedMotion}
        onClose={() => setBrainDumpOpen(false)}
        onCapture={async (payload: {
          text: string;
          kind: ThoughtKind;
          project_id: string | null;
          energy_cost: number;
          auto_park: boolean;
        }) => {
          try {
            await api.captureThought(payload);
            await loadWorkspaceData(payload.project_id || selectedProject?.id);
          } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unable to capture thought.';
            setOfflineBanner(`Offline fallback active: ${msg}`);
          }
        }}
      />
    </div>
  );
};

export default App;

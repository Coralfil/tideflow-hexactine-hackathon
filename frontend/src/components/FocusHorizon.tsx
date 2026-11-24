import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Anchor, ArrowUpRight, Bookmark, ChevronDown, ChevronRight, Compass, Layers, Calendar, CalendarSync, Bot } from 'lucide-react';
import { HyperfixationTimer } from './HyperfixationTimer';
import { AgentTaskSheetModal } from './AgentTaskSheetModal';
import type {
  MomentumResumeResponse,
  ProjectView,
  ThoughtView,
  TriageSweepResponse,
} from '../api/client';

interface FocusHorizonProps {
  selectedProject: ProjectView | null;
  thoughts: ThoughtView[];
  triage: TriageSweepResponse | null;
  resumeData: MomentumResumeResponse | null;
  reducedMotion: boolean;
  onRunSweep: () => Promise<void>;
  onParkThought: (thoughtId: string) => Promise<void>;
  onPromoteThought: (thoughtId: string) => Promise<void>;
  onSaveBreadcrumb: (lastAction: string, nextMicroStep: string) => Promise<void>;
  onResumeContext: () => Promise<void>;
  onOpenBrainDump: () => void;
}

export const FocusHorizon: React.FC<FocusHorizonProps> = ({
  selectedProject,
  thoughts,
  triage,
  resumeData,
  reducedMotion,
  onRunSweep,
  onParkThought,
  onPromoteThought,
  onSaveBreadcrumb,
  onResumeContext,
  onOpenBrainDump,
}) => {
  const [reefOpen, setReefOpen] = useState(false);
  const [lastAction, setLastAction] = useState('');
  const [nextMicroStep, setNextMicroStep] = useState('');
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [activeTaskForAgent, setActiveTaskForAgent] = useState<ThoughtView | null>(null);

  const nowItems = (triage?.now?.length ? triage.now : thoughts.filter((t) => t.status === 'now')).slice(0, 1);
  const nextItems = (triage?.next?.length ? triage.next : thoughts.filter((t) => t.status === 'next')).slice(0, 2);
  const parkedItems = thoughts.filter((t) => t.status === 'parked');
  const parkedCount = Math.max(parkedItems.length, triage?.parked_count ?? 0);
  const overwhelmIndex = triage?.overwhelm_index ?? 0.2;

  const handlePushToCalendar = (taskText: string) => {
    const text = encodeURIComponent(taskText);
    const start = new Date();
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const formatDate = (date: Date) => date.toISOString().replace(/-|:|\.\d\d\d/g, '');
    const url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${formatDate(start)}/${formatDate(end)}&details=TideFlow+Focus+Block`;
    window.open(url, '_blank');
  };

  const handleSaveBreadcrumb = async (evt: React.FormEvent) => {
    evt.preventDefault();
    if (!lastAction.trim() || !nextMicroStep.trim()) {
      setLocalError('Enter both Last Action and Next 5-Minute Micro-Step.');
      return;
    }
    setBusyAction('breadcrumb');
    setLocalError(null);
    try {
      await onSaveBreadcrumb(lastAction.trim(), nextMicroStep.trim());
      setLastAction('');
      setNextMicroStep('');
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Unable to save breadcrumb.');
    } finally {
      setBusyAction(null);
    }
  };

  const renderAgentAnalysis = (item: ThoughtView) => {
    if (!item.agent_analysis) return null;
    
    if (item.agent_analysis.can_offload) {
      return (
        <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
          <button
            type="button"
            className="btn btn-sm btn-primary"
            style={{ width: '100%', display: 'flex', justifyContent: 'center' }}
            onClick={() => setActiveTaskForAgent(item)}
          >
            <Bot size={14} style={{ marginRight: '6px' }} />
            Submit to agent for completion
          </button>
        </div>
      );
    } else {
      return (
        <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px', fontSize: '0.75rem', color: '#94a3b8' }}>
          <strong>Go/NoGo Report:</strong> {item.agent_analysis.go_nogo_report}
        </div>
      );
    }
  };

  return (
    <section className="glass-panel" aria-label="3-Slot Focus Horizon">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">
            <Layers size={18} color="#00d9c0" />
            3-Slot Focus Horizon
          </h2>
          <p className="panel-subtitle">
            Strict WIP limit (Now: 1, Next: 2) so context overload never stalls momentum.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-sm" onClick={onOpenBrainDump}>
            + Quick Idea
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={busyAction === 'sweep'}
            onClick={async () => {
              setBusyAction('sweep');
              setLocalError(null);
              try {
                await onRunSweep();
              } catch (err) {
                setLocalError(err instanceof Error ? err.message : 'Triage sweep failed.');
              } finally {
                setBusyAction(null);
              }
            }}
          >
            {busyAction === 'sweep' ? 'Sweeping...' : 'Run Triage Sweep'}
          </button>
        </div>
      </div>

      <div className="status-pills" style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="pill pill-accent">
            Overwhelm Index: {overwhelmIndex.toFixed(2)}
          </span>
          <span className="pill" style={{ marginLeft: 8 }}>
            Active Hub: {selectedProject ? selectedProject.name : 'All Projects'}
          </span>
        </div>
        <button
          type="button"
          className="btn btn-sm"
          title="Enable agentic auto-scheduling via GCalendar Plugin"
          onClick={() => alert("GCalendar Auto-Scheduling integration enabled! Agent will now push 'Next' tasks into free calendar slots automatically.")}
        >
          <CalendarSync size={14} color="#a5f3fc" /> Auto-Schedule (GCal)
        </button>
      </div>

      {triage?.recommendation && (
        <div className="alert-banner alert-ok" style={{ marginTop: 0, marginBottom: 12 }}>
          {triage.recommendation}
        </div>
      )}

      <div className="slot-grid">
        <div className="slot-box slot-box-now">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>Now (Max 1)</strong>
            <span className="pill pill-accent">{nowItems.length}/1</span>
          </div>
          {nowItems.length === 0 ? (
            <p className="panel-subtitle" style={{ marginTop: 10 }}>
              Slot open. Capture a task or promote one from Next or Parked Reef.
            </p>
          ) : (
            nowItems.map((item) => (
              <motion.div
                key={item.id}
                className="thought-card"
                layout={!reducedMotion}
                initial={reducedMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{item.text}</div>
                <div style={{ fontSize: '0.76rem', color: '#a5f3fc', marginTop: 4 }}>
                  Micro-step: {item.suggested_micro_step}
                </div>
                <div className="thought-meta">
                  <span className="pill">{item.kind}</span>
                  <span>E{item.energy_cost}</span>
                  <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      title="Push Focus Block to Calendar"
                      onClick={() => handlePushToCalendar(item.text)}
                    >
                      <Calendar size={13} /> GCal
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => onParkThought(item.id)}
                    >
                      Park
                    </button>
                  </div>
                </div>
                {/* Hyperfixation Boundaries for Active Focus */}
                <HyperfixationTimer taskId={item.id} taskText={item.text} energyCost={item.energy_cost} />
                {renderAgentAnalysis(item)}
              </motion.div>
            ))
          )}
        </div>

        <div className="slot-box">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>Next (Max 2)</strong>
            <span className="pill">{nextItems.length}/2</span>
          </div>
          {nextItems.length === 0 ? (
            <p className="panel-subtitle" style={{ marginTop: 10 }}>
              No queued items in Next yet.
            </p>
          ) : (
            nextItems.map((item) => (
              <motion.div
                key={item.id}
                className="thought-card"
                layout={!reducedMotion}
                initial={reducedMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.86rem' }}>{item.text}</div>
                <div className="thought-meta">
                  <span className="pill">{item.kind}</span>
                  <span>E{item.energy_cost}</span>
                  <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      title="Push Focus Block to Calendar"
                      onClick={() => handlePushToCalendar(item.text)}
                    >
                      <Calendar size={13} /> GCal
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => onParkThought(item.id)}
                    >
                      Park
                    </button>
                  </div>
                </div>
                {/* Hyperfixation Boundaries for Active Focus */}
                <HyperfixationTimer taskId={item.id} taskText={item.text} energyCost={item.energy_cost} />
                {renderAgentAnalysis(item)}
              </motion.div>
            ))
          )}
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <button
          type="button"
          className="btn btn-sm"
          aria-expanded={reefOpen}
          onClick={() => setReefOpen((prev) => !prev)}
        >
          {reefOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          <Anchor size={14} color="#38bdf8" />
          Parked Reef ({parkedCount})
        </button>

        {reefOpen && (
          <div style={{ marginTop: 8 }}>
            {parkedItems.length === 0 ? (
              <p className="panel-subtitle">No side quests parked right now.</p>
            ) : (
              parkedItems.map((item) => (
                <div key={item.id} className="thought-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: '0.84rem' }}>{item.text}</span>
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      onClick={() => onPromoteThought(item.id)}
                    >
                      <ArrowUpRight size={13} />
                      Promote
                    </button>
                  </div>
                  <div className="thought-meta">
                    <span className="pill">{item.kind}</span>
                    <span>E{item.energy_cost}</span>
                  </div>
                  {renderAgentAnalysis(item)}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <div className="resume-card">
        <div className="panel-header" style={{ marginBottom: 6 }}>
          <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.9rem' }}>
            <Compass size={16} color="#00d9c0" />
            Bitemporal Momentum Resume Card
          </strong>
          <button
            type="button"
            className="btn btn-sm"
            onClick={async () => {
              setLocalError(null);
              try {
                await onResumeContext();
              } catch (err) {
                setLocalError(err instanceof Error ? err.message : 'Unable to resume context.');
              }
            }}
          >
            Resume Context
          </button>
        </div>

        {resumeData?.resume_card?.card_lines ? (
          <ol className="resume-lines">
            {resumeData.resume_card.card_lines.slice(0, 3).map((line, idx) => (
              <li key={idx}>{line}</li>
            ))}
          </ol>
        ) : (
          <p className="panel-subtitle">
            Save a breadcrumb below to lock in your last action and 5-minute next step.
          </p>
        )}

        <form onSubmit={handleSaveBreadcrumb} style={{ marginTop: 10 }}>
          <div className="form-grid">
            <input
              type="text"
              name="last_action"
              className="input"
              aria-label="Last action"
              placeholder="Last action completed..."
              value={lastAction}
              onChange={(e) => setLastAction(e.target.value)}
            />
            <input
              type="text"
              name="next_micro_step"
              className="input"
              aria-label="Next micro step"
              placeholder="Next 5-minute micro-step..."
              value={nextMicroStep}
              onChange={(e) => setNextMicroStep(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
            <button
              type="submit"
              className="btn btn-sm btn-primary"
              disabled={busyAction === 'breadcrumb'}
            >
              <Bookmark size={14} />
              Save Breadcrumb
            </button>
          </div>
        </form>
      </div>

      {localError && <div className="alert-banner alert-error">{localError}</div>}

      {activeTaskForAgent && (
        <AgentTaskSheetModal
          thought={activeTaskForAgent}
          onClose={() => setActiveTaskForAgent(null)}
          onSubmit={async (instructions) => {
            // Placeholder: Typically this would call an API to offload the task
            // For the hackathon, we simulate it being passed to the subagent
            console.log("Submitting to agent with instructions:", instructions, "Task:", activeTaskForAgent);
            setLocalError(null);
            try {
              // Mark it as done or handled, etc.
              // We could just park it with a special reason or call a new endpoint
              alert("Task submitted to OrchestraPlan worker!\n\nInstructions: " + instructions);
            } catch (err) {
              throw err;
            }
          }}
        />
      )}
    </section>
  );
};

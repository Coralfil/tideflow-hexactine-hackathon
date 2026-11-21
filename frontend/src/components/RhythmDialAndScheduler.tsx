import React, { useEffect, useState } from 'react';
import { CalendarClock, Play, Pause, RotateCcw, Trash2, Waves } from 'lucide-react';
import type {
  CadenceWindow,
  MomentumPromptsResponse,
  ScheduleBlockView,
} from '../api/client';

interface RhythmDialAndSchedulerProps {
  activeCadence: CadenceWindow;
  bpm: number;
  energy: number;
  minutes: number;
  blocks: ScheduleBlockView[];
  prompts: MomentumPromptsResponse | null;
  reducedMotion: boolean;
  onEnergyChange: (energy: number) => void;
  onMinutesChange: (minutes: number) => void;
  onRefreshPrompts: (energy: number, minutes: number) => Promise<void>;
  onCreateBlock: (payload: {
    title: string;
    start_iso: string;
    end_iso: string;
    cadence_window: CadenceWindow;
    energy_required: number;
  }) => Promise<void>;
  onCompleteBlock: (blockId: string) => Promise<void>;
  onDeleteBlock: (blockId: string) => Promise<void>;
}

const CADENCE_WINDOWS: Array<{ value: CadenceWindow; label: string }> = [
  { value: 'deep_tide', label: 'deep_tide (Deep Focus)' },
  { value: 'creative_swell', label: 'creative_swell (Build & Ideate)' },
  { value: 'shallow_drift', label: 'shallow_drift (Maintenance)' },
  { value: 'recovery_ebb', label: 'recovery_ebb (Wind Down)' },
];

export const RhythmDialAndScheduler: React.FC<RhythmDialAndSchedulerProps> = ({
  activeCadence,
  bpm,
  energy,
  minutes,
  blocks,
  prompts,
  reducedMotion,
  onEnergyChange,
  onMinutesChange,
  onRefreshPrompts,
  onCreateBlock,
  onCompleteBlock,
  onDeleteBlock,
}) => {
  const [title, setTitle] = useState('');
  const [startIso, setStartIso] = useState('2026-11-21T09:00:00Z');
  const [endIso, setEndIso] = useState('2026-11-21T09:45:00Z');
  const [cadenceWindow, setCadenceWindow] = useState<CadenceWindow>('deep_tide');
  const [schedError, setSchedError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [timerRunning, setTimerRunning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(minutes * 60);

  useEffect(() => {
    if (!timerRunning) {
      setRemainingSeconds(minutes * 60);
    }
  }, [minutes, timerRunning]);

  useEffect(() => {
    if (!timerRunning) {
      return;
    }
    const id = window.setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          setTimerRunning(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [timerRunning]);

  const mm = String(Math.floor(remainingSeconds / 60)).padStart(2, '0');
  const ss = String(remainingSeconds % 60).padStart(2, '0');

  const handleSubmitBlock = async (evt: React.FormEvent) => {
    evt.preventDefault();
    if (!title.trim()) {
      setSchedError('Enter a block title before adding.');
      return;
    }
    setSubmitting(true);
    setSchedError(null);
    try {
      await onCreateBlock({
        title: title.trim(),
        start_iso: startIso.trim(),
        end_iso: endIso.trim(),
        cadence_window: cadenceWindow,
        energy_required: energy,
      });
      setTitle('');
    } catch (err) {
      setSchedError(
        err instanceof Error ? err.message : 'Schedule conflict or invalid time range.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="glass-panel" aria-label="Cadence Scheduler and Rhythm Dial">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">
            <Waves size={18} color="#00d9c0" />
            Rhythm Dial &amp; Cadence Scheduler
          </h2>
          <p className="panel-subtitle">
            Tidal cadence window: {activeCadence} synced to CSS Houdini pulse tokens.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-sm"
          onClick={() => onRefreshPrompts(energy, minutes)}
        >
          Refresh Prompts
        </button>
      </div>

      <div className="slot-grid" style={{ alignItems: 'center', marginBottom: 14 }}>
        <div
          className="rhythm-dial-ring"
          style={{
            transform: !reducedMotion && timerRunning ? 'scale(1.03)' : 'scale(1)',
            transition: reducedMotion ? 'none' : 'transform 0.3s ease',
          }}
        >
          <div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>{bpm} BPM</div>
            <div style={{ fontSize: '0.78rem', color: '#a5f3fc' }}>
              {mm}:{ss} sprint
            </div>
            <div style={{ fontSize: '0.72rem', color: '#93b3c8' }}>Energy {energy}/5</div>
          </div>
        </div>

        <div>
          <label
            htmlFor="energy-rhythm-dial"
            style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 6 }}
          >
            Energy Rhythm Dial (1 to 5): {energy}
          </label>
          <input
            id="energy-rhythm-dial"
            type="range"
            min={1}
            max={5}
            step={1}
            aria-label="Energy Rhythm BPM Dial"
            value={energy}
            onChange={(e) => onEnergyChange(Number(e.target.value))}
            style={{ width: '100%', accentColor: '#00d9c0', cursor: 'pointer' }}
          />

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            {[15, 25, 45, 60].map((m) => (
              <button
                key={m}
                type="button"
                className={`btn btn-sm ${minutes === m ? 'btn-active' : ''}`}
                onClick={() => onMinutesChange(m)}
              >
                {m}m
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() => setTimerRunning((prev) => !prev)}
            >
              {timerRunning ? <Pause size={13} /> : <Play size={13} />}
              {timerRunning ? 'Pause' : 'Start Tide'}
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                setTimerRunning(false);
                setRemainingSeconds(minutes * 60);
              }}
            >
              <RotateCcw size={13} />
              Reset
            </button>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <strong style={{ fontSize: '0.84rem' }}>Deterministic Momentum Prompts</strong>
        {(prompts?.prompts ?? []).slice(0, 3).map((item) => (
          <div key={item.id} className="thought-card">
            <div style={{ fontWeight: 600, fontSize: '0.84rem' }}>{item.title}</div>
            <div style={{ fontSize: '0.76rem', color: '#a5f3fc', marginTop: 2 }}>
              {item.micro_step}
            </div>
            <div className="thought-meta">
              <span className="pill">{item.cadence_window}</span>
              <span>Score {item.score.toFixed(1)}</span>
              <span>{item.estimated_minutes}m</span>
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmitBlock}>
        <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.84rem' }}>
          <CalendarClock size={15} color="#38bdf8" />
          Schedule Block
        </strong>
        <div className="form-grid" style={{ marginTop: 8 }}>
          <input
            type="text"
            name="title"
            className="input"
            aria-label="Block title"
            placeholder="Block title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <select
            name="cadence_window"
            className="select"
            aria-label="Cadence window"
            value={cadenceWindow}
            onChange={(e) => setCadenceWindow(e.target.value as CadenceWindow)}
          >
            {CADENCE_WINDOWS.map((w) => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            name="start_iso"
            className="input"
            aria-label="Start ISO"
            placeholder="2026-11-21T09:00:00Z"
            value={startIso}
            onChange={(e) => setStartIso(e.target.value)}
          />
          <input
            type="text"
            name="end_iso"
            className="input"
            aria-label="End ISO"
            placeholder="2026-11-21T09:45:00Z"
            value={endIso}
            onChange={(e) => setEndIso(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="submit" className="btn btn-sm btn-primary" disabled={submitting}>
            {submitting ? 'Adding...' : 'Add Block'}
          </button>
        </div>
      </form>

      {schedError && <div className="alert-banner alert-error">{schedError}</div>}

      <div className="audit-list" style={{ marginTop: 10 }}>
        {blocks.map((block) => (
          <div key={block.id} className="audit-row">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
              <strong>{block.title}</strong>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span className="pill">{block.cadence_window}</span>
                {block.status !== 'completed' && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => onCompleteBlock(block.id)}
                  >
                    Done
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-label={`Delete ${block.title}`}
                  onClick={() => onDeleteBlock(block.id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
            <div style={{ color: '#93b3c8', marginTop: 3 }}>
              {block.start_iso} to {block.end_iso} ({block.status})
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

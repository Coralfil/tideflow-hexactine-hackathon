import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, X } from 'lucide-react';
import type { ProjectView, ThoughtKind } from '../api/client';

interface BrainDumpModalProps {
  isOpen: boolean;
  projects: ProjectView[];
  selectedProjectId: string;
  reducedMotion: boolean;
  onClose: () => void;
  onCapture: (payload: {
    text: string;
    kind: ThoughtKind;
    project_id: string | null;
    energy_cost: number;
    auto_park: boolean;
  }) => Promise<void>;
}

const THOUGHT_KINDS: Array<{ value: ThoughtKind; label: string }> = [
  { value: 'project_task', label: 'Project Task' },
  { value: 'spark_idea', label: 'Spark Idea' },
  { value: 'side_quest', label: 'Side Quest' },
  { value: 'blocker', label: 'Blocker' },
];

export const BrainDumpModal: React.FC<BrainDumpModalProps> = ({
  isOpen,
  projects,
  selectedProjectId,
  reducedMotion,
  onClose,
  onCapture,
}) => {
  const [text, setText] = useState('');
  const [kind, setKind] = useState<ThoughtKind>('project_task');
  const [projectId, setProjectId] = useState<string>(selectedProjectId);
  const [energyCost, setEnergyCost] = useState<number>(3);
  const [autoPark, setAutoPark] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setProjectId(selectedProjectId);
      setErrorMsg(null);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 20);
    }
  }, [isOpen, selectedProjectId]);

  const handleSubmit = (evt: React.FormEvent) => {
    evt.preventDefault();
    const cleaned = text.trim();
    if (!cleaned) {
      setErrorMsg('Enter a short thought before capturing.');
      return;
    }
    setErrorMsg(null);
    setText('');
    setAutoPark(false);
    onClose();
    void onCapture({
      text: cleaned,
      kind,
      project_id: projectId || null,
      energy_cost: energyCost,
      auto_park: autoPark,
    });
  };

  if (!isOpen) {
    return null;
  }

  return (
    <motion.div
      className="modal-backdrop"
      initial={reducedMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Brain Dump"
        className="modal-panel"
        initial={reducedMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
            <div className="panel-header">
              <h2 className="panel-title">
                <Sparkles size={18} color="#00d9c0" />
                Brain Dump Capture
              </h2>
              <button
                type="button"
                className="btn btn-sm"
                aria-label="Close modal"
                onClick={onClose}
              >
                <X size={15} />
                Esc
              </button>
            </div>
            <p className="panel-subtitle" style={{ marginBottom: 12 }}>
              Unload an idea or side quest with #tags in two seconds without losing your place.
            </p>

            <form onSubmit={handleSubmit}>
              <label style={{ display: 'block', fontSize: '0.78rem', marginBottom: 4 }}>
                Thought or #concept tag
              </label>
              <textarea
                ref={inputRef}
                name="thought_text"
                rows={3}
                className="textarea"
                placeholder="e.g. Draft graph snapshot cache check #perf"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />

              <div className="form-grid" style={{ marginTop: 10 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', marginBottom: 4 }}>
                    Kind
                  </label>
                  <select
                    name="kind"
                    className="select"
                    value={kind}
                    onChange={(e) => setKind(e.target.value as ThoughtKind)}
                  >
                    {THOUGHT_KINDS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', marginBottom: 4 }}>
                    Project Hub
                  </label>
                  <select
                    name="project_id"
                    className="select"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">Auto-route to active</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', marginBottom: 4 }}>
                    Energy Cost (1 to 5)
                  </label>
                  <select
                    name="energy_cost"
                    className="select"
                    value={energyCost}
                    onChange={(e) => setEnergyCost(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((lvl) => (
                      <option key={lvl} value={lvl}>
                        Level {lvl}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  marginTop: 12,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  name="auto_park"
                  checked={autoPark}
                  onChange={(e) => setAutoPark(e.target.checked)}
                />
                Auto-Park in Parked Reef (keep focus untouched)
              </label>

              {errorMsg && <div className="alert-banner alert-error">{errorMsg}</div>}

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 8,
                  marginTop: 14,
                }}
              >
                <button type="button" className="btn" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!text.trim()}
                >
                  Capture Thought
                </button>
              </div>
            </form>
      </motion.div>
    </motion.div>
  );
};

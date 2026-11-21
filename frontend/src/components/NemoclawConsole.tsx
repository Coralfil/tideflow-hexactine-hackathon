import React, { useState } from 'react';
import { Lock, Play, ShieldAlert, Terminal } from 'lucide-react';
import type {
  AuditEntryView,
  CapabilityName,
  ProjectView,
  RetrieverExecuteResponse,
  RetrieverPermissionsView,
} from '../api/client';

interface NemoclawConsoleProps {
  permissions: RetrieverPermissionsView | null;
  auditEntries: AuditEntryView[];
  selectedProject: ProjectView | null;
  lastArtifact: RetrieverExecuteResponse | null;
  onTogglePermission: (cap: CapabilityName, enabled: boolean) => Promise<void>;
  onExecute: (payload: {
    capability: CapabilityName;
    target: string;
    query?: string;
    project_id?: string | null;
  }) => Promise<void>;
}

const CAPABILITIES: Array<{ key: CapabilityName; hint: string }> = [
  { key: 'local_fs_read', hint: 'Read allowlisted workspace files' },
  { key: 'repo_git_scan', hint: 'Inspect git status and recent commits' },
  { key: 'web_fetch_public', hint: 'Fetch public HTTPS docs (SSRF guarded)' },
  { key: 'local_llm_ollama', hint: 'Query local RTX 3060 / Ollama model' },
];

export const NemoclawConsole: React.FC<NemoclawConsoleProps> = ({
  permissions,
  auditEntries,
  selectedProject,
  lastArtifact,
  onTogglePermission,
  onExecute,
}) => {
  const [capability, setCapability] = useState<CapabilityName>('local_fs_read');
  const [target, setTarget] = useState('README.md');
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [execError, setExecError] = useState<string | null>(null);

  const handleRun = async (evt: React.FormEvent) => {
    evt.preventDefault();
    setRunning(true);
    setExecError(null);
    try {
      await onExecute({
        capability,
        target: target.trim() || 'README.md',
        query: query.trim() || undefined,
        project_id: selectedProject?.id ?? null,
      });
    } catch (err) {
      setExecError(
        err instanceof Error
          ? err.message
          : 'Permission denied (403): enable capability before running.'
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="glass-panel" aria-label="Nemoclaw Retriever Permission Console">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">
            <Lock size={18} color="#f472b6" />
            Nemoclaw Retriever &amp; Permission Matrix
          </h2>
          <p className="panel-subtitle">
            Default-deny gate: actions stay blocked (HTTP 403) until you enable each capability.
          </p>
        </div>
        <span className="pill">
          Allowed Paths: {permissions?.allowed_paths?.length ?? 0}
        </span>
      </div>

      <div className="perm-grid">
        {CAPABILITIES.map((cap) => {
          const enabled = Boolean(permissions?.[cap.key]);
          return (
            <label key={cap.key} className="perm-card" data-capability={cap.key}>
              <div>
                <div style={{ fontWeight: 600 }}>{cap.key}</div>
                <div style={{ fontSize: '0.72rem', color: '#93b3c8' }}>{cap.hint}</div>
              </div>
              <input
                type="checkbox"
                name={cap.key}
                checked={enabled}
                onChange={(e) => onTogglePermission(cap.key, e.target.checked)}
              />
            </label>
          );
        })}
      </div>

      <form onSubmit={handleRun} style={{ marginTop: 12 }}>
        <div className="form-grid">
          <select
            name="capability"
            aria-label="Retriever capability"
            className="select"
            value={capability}
            onChange={(e) => setCapability(e.target.value as CapabilityName)}
          >
            {CAPABILITIES.map((c) => (
              <option key={c.key} value={c.key}>
                {c.key}
              </option>
            ))}
          </select>

          <input
            type="text"
            name="target"
            aria-label="Retrieval target"
            className="input"
            placeholder="Target path or URL (e.g. README.md)"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />

          <input
            type="text"
            name="query"
            aria-label="Optional query"
            className="input"
            placeholder="Optional summary prompt..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="submit" className="btn btn-sm btn-primary" disabled={running}>
            <Play size={14} />
            {running ? 'Running...' : 'Execute'}
          </button>
        </div>
      </form>

      {execError && (
        <div className="alert-banner alert-error" role="alert">
          <ShieldAlert size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          {execError}
        </div>
      )}

      {lastArtifact && (
        <div className="resume-card" style={{ marginTop: 10 }}>
          <strong style={{ fontSize: '0.84rem' }}>
            Artifact ({lastArtifact.artifact.label}): {lastArtifact.artifact.title}
          </strong>
          <pre className="cypher-box" style={{ marginTop: 6 }}>
            {lastArtifact.artifact.excerpt.slice(0, 420)}
          </pre>
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.86rem' }}>
          <Terminal size={15} color="#38bdf8" />
          Audit Console ({auditEntries.length})
        </strong>
        <div className="audit-list">
          {auditEntries.length === 0 ? (
            <p className="panel-subtitle">No retriever executions recorded yet.</p>
          ) : (
            [...auditEntries].reverse().slice(0, 12).map((entry) => (
              <div key={entry.id} className="audit-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span>
                    <strong>{entry.capability}</strong> ({entry.target})
                  </span>
                  <span
                    className={`pill ${
                      entry.verdict === 'ALLOWED' ? 'pill-ok' : 'pill-danger'
                    }`}
                  >
                    {entry.verdict}
                  </span>
                </div>
                <div style={{ color: '#93b3c8', marginTop: 3 }}>{entry.reason}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
};

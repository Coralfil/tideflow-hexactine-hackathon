import React, { useMemo, useState } from 'react';
import { GitBranch, Network, Route, ShieldCheck } from 'lucide-react';
import type {
  GraphLens,
  GraphNodeView,
  GraphSnapshotResponse,
  ShortestPathResult,
} from '../api/client';

interface GraphCanvasProps {
  snapshot: GraphSnapshotResponse | null;
  activeLens: GraphLens;
  pathResult: ShortestPathResult | null;
  reducedMotion: boolean;
  onSelectLens: (lens: GraphLens) => void;
  onTracePath: (sourceId: string, targetId: string) => Promise<void>;
}

const COMMUNITY_PALETTE = [
  '#00d9c0',
  '#38bdf8',
  '#a78bfa',
  '#fbbf24',
  '#34d399',
  '#f472b6',
];

const LABEL_COLORS: Record<string, string> = {
  Project: '#00d9c0',
  Thought: '#38bdf8',
  ConceptTag: '#a78bfa',
  SpiculeHub: '#fbbf24',
  Breadcrumb: '#34d399',
  ScheduleBlock: '#60a5fa',
  RetrievalArtifact: '#f472b6',
};

const LENS_OPTIONS: Array<{ id: GraphLens; label: string }> = [
  { id: 'pagerank', label: 'PageRank' },
  { id: 'communities', label: 'Communities' },
  { id: 'path', label: 'Shortest Path' },
  { id: 'degree_audit', label: 'Degree Audit' },
];

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  snapshot,
  activeLens,
  pathResult,
  reducedMotion,
  onSelectLens,
  onTracePath,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [sourceId, setSourceId] = useState<string>('');
  const [targetId, setTargetId] = useState<string>('');
  const [pathError, setPathError] = useState<string | null>(null);

  const nodes = snapshot?.nodes ?? [];
  const edges = snapshot?.edges ?? [];

  const positioned = useMemo(() => {
    const width = 620;
    const height = 310;
    const cx = width / 2;
    const cy = height / 2;

    const coords = new Map<string, { x: number; y: number }>();
    const total = Math.max(1, nodes.length);
    nodes.forEach((node, idx) => {
      if (node.label === 'Project' && idx === 0) {
        coords.set(node.id, { x: cx, y: cy });
        return;
      }
      const ring = node.label === 'Project' ? 0.35 : node.label === 'ConceptTag' ? 0.68 : 0.92;
      const angle = (idx / total) * Math.PI * 2 - Math.PI / 2;
      const rx = 125 * ring + (idx % 3) * 28;
      const ry = 108 * ring + (idx % 2) * 16;
      coords.set(node.id, {
        x: Math.max(26, Math.min(width - 26, cx + Math.cos(angle) * rx)),
        y: Math.max(26, Math.min(height - 26, cy + Math.sin(angle) * ry)),
      });
    });
    return coords;
  }, [nodes]);

  const highlightedNodes = useMemo(() => {
    const ids = new Set<string>(pathResult?.found ? pathResult.node_ids : []);
    for (const n of nodes) {
      if (n.in_active_path) {
        ids.add(n.id);
      }
    }
    return ids;
  }, [nodes, pathResult]);

  const selectedNode: GraphNodeView | null = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? nodes[0] ?? null,
    [nodes, selectedNodeId]
  );

  const effectiveSource = sourceId || (nodes[0]?.id ?? '');
  const effectiveTarget = targetId || (nodes[Math.min(1, Math.max(0, nodes.length - 1))]?.id ?? '');

  const metrics = snapshot?.metrics;

  return (
    <section className="glass-panel" aria-label="Neo4j Graph Science Canvas">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">
            <Network size={18} color="#38bdf8" />
            Neo4j Graph-Science Lattice
          </h2>
          <p className="panel-subtitle">
            Hexactine spicule topology enforcing primary structural degree &lt;= 6.
          </p>
        </div>

        <div className="status-pills">
          <span className={`pill ${metrics?.invariant_ok === false ? 'pill-danger' : 'pill-ok'}`}>
            <ShieldCheck size={13} />
            deg &lt;= {metrics?.max_degree_allowed ?? 6} (max {metrics?.max_observed_degree ?? 0})
          </span>
          <span className="pill">
            {metrics?.node_count ?? 0} nodes / {metrics?.edge_count ?? 0} edges
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }} role="tablist">
        {LENS_OPTIONS.map((lens) => (
          <button
            key={lens.id}
            type="button"
            role="tab"
            aria-selected={activeLens === lens.id}
            className={`btn btn-sm ${activeLens === lens.id ? 'btn-active' : ''}`}
            onClick={() => onSelectLens(lens.id)}
          >
            {lens.label}
          </button>
        ))}
      </div>

      <div className="graph-svg-wrap">
        <svg
          viewBox="0 0 620 310"
          width="100%"
          height="260"
          role="img"
          aria-label="Interactive Hexactine Knowledge Graph"
        >
          {edges.map((edge) => {
            const p1 = positioned.get(edge.source);
            const p2 = positioned.get(edge.target);
            if (!p1 || !p2) {
              return null;
            }
            const inPath =
              edge.in_active_path ||
              (highlightedNodes.has(edge.source) && highlightedNodes.has(edge.target));
            return (
              <line
                key={edge.id}
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke={inPath ? '#00d9c0' : edge.routed_via_subhub ? '#fbbf24' : '#38bdf8'}
                strokeOpacity={inPath ? 0.95 : 0.34}
                strokeWidth={inPath ? 2.6 : 1.3}
                strokeDasharray={edge.routed_via_subhub ? '4 3' : undefined}
              />
            );
          })}

          {nodes.map((node) => {
            const pos = positioned.get(node.id);
            if (!pos) {
              return null;
            }
            const fillColor =
              activeLens === 'communities'
                ? COMMUNITY_PALETTE[node.community_id % COMMUNITY_PALETTE.length]
                : LABEL_COLORS[node.label] || '#38bdf8';
            const radius =
              activeLens === 'pagerank'
                ? 7 + Math.min(11, node.normalized_pagerank * 11)
                : activeLens === 'degree_audit'
                  ? 7 + Math.min(9, node.degree * 1.4)
                  : 8.5;
            const isSelected = selectedNode?.id === node.id;
            const isPathNode = highlightedNodes.has(node.id);

            return (
              <g
                key={node.id}
                style={{ cursor: 'pointer' }}
                onClick={() => setSelectedNodeId(node.id)}
              >
                {!reducedMotion && isPathNode && (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={radius + 5}
                    fill="none"
                    stroke="#00d9c0"
                    strokeOpacity={0.6}
                    strokeWidth={1.5}
                  />
                )}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={radius}
                  fill={fillColor}
                  fillOpacity={0.86}
                  stroke={isSelected ? '#ffffff' : node.hexactine_compliant ? '#0b1c33' : '#ef4444'}
                  strokeWidth={isSelected ? 2.4 : 1.5}
                />
                <text
                  x={pos.x}
                  y={pos.y + radius + 11}
                  textAnchor="middle"
                  fill="#cfe6f5"
                  fontSize="9"
                >
                  {node.title.slice(0, 18)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="form-grid" style={{ marginTop: 10, alignItems: 'center' }}>
        <select
          aria-label="Path source node"
          className="select"
          value={effectiveSource}
          onChange={(e) => setSourceId(e.target.value)}
        >
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.label}: {n.title.slice(0, 28)}
            </option>
          ))}
        </select>

        <select
          aria-label="Path target node"
          className="select"
          value={effectiveTarget}
          onChange={(e) => setTargetId(e.target.value)}
        >
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.label}: {n.title.slice(0, 28)}
            </option>
          ))}
        </select>

        <button
          type="button"
          className="btn btn-sm"
          disabled={!effectiveSource || !effectiveTarget}
          onClick={async () => {
            setPathError(null);
            try {
              await onTracePath(effectiveSource, effectiveTarget);
            } catch (err) {
              setPathError(err instanceof Error ? err.message : 'Unable to compute path.');
            }
          }}
        >
          <Route size={14} />
          Trace Path
        </button>
      </div>

      {pathResult && (
        <div className="thought-meta" style={{ marginTop: 8 }}>
          <GitBranch size={14} color="#00d9c0" />
          {pathResult.found ? (
            <span>
              Shortest path: {pathResult.hop_count} hop(s) across {pathResult.node_ids.length} nodes
            </span>
          ) : (
            <span>No path found between selected nodes</span>
          )}
        </div>
      )}

      {selectedNode && (
        <div className="thought-meta" style={{ marginTop: 8 }}>
          <span className="pill">{selectedNode.label}</span>
          <span>{selectedNode.title}</span>
          <span>PR: {selectedNode.pagerank.toFixed(3)}</span>
          <span>Community: C{selectedNode.community_id}</span>
          <span>Degree: {selectedNode.degree}</span>
        </div>
      )}

      {pathError && <div className="alert-banner alert-error">{pathError}</div>}

      <div className="cypher-box" aria-label="Cypher Preview">
        {snapshot?.gds_cypher_preview || "CALL gds.pageRank.stream('tideflow_hexactine')"}
      </div>
    </section>
  );
};

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface AgentStats {
  domain_reach: number; // X-axis (0 - 100)
  evolution_potential: number; // -X axis (0 - 100)
  autonomy: number; // +Y axis (0 - 100)
  integration_sync: number; // -Y axis (0 - 100)
  rhythm_speed: number; // +Z axis (0 - 100)
  memory_depth: number; // -Z axis (0 - 100)
  cost_efficiency?: number; // modifier
}

export interface RelationalCombo {
  partner: string;
  combo_name: string;
  handoff_contract: string;
  description: string;
}

export interface AgentProfile {
  id?: string;
  name: string;
  codename?: string;
  species?: string;
  role?: string;
  execution_domain: string;
  cluster: string;
  compute_tier?: string;
  tokens_per_sec?: number;
  backstory: string;
  signature_move?: string;
  skills?: string[];
  stats?: AgentStats;
  relational_combos?: RelationalCombo[];
  avatar_url?: string;
}

export interface AgentProfilePanelProps {
  agent?: AgentProfile;
  className?: string;
}

// Canonical Default Agent Profile (Zephyr Master Conductor)
export const DEFAULT_AGENT_PROFILE: AgentProfile = {
  id: 'agent-01',
  name: 'ZEPHYR',
  codename: 'ZEPHYR-CONDUCTOR',
  species: 'Hexactinellid Glass Sponge Syncytium (Aphrocallistes vastus)',
  role: 'Master Orchestration Conductor / Integrated Synchronicity Architect',
  execution_domain: 'Multi-Agent Theater & Epistemic Gating',
  cluster: 'Siphonophore Core (Tier 1 Primary)',
  compute_tier: 'Argon Med',
  tokens_per_sec: 112,
  backstory:
    'Spawned within the benthic cold-water glass sponge reefs of Hecate Strait, Zephyr was initialized as the primary syncytial conduction hub for Coralfil OS. Rather than operating as an isolated model, Zephyr propagates intent across all six hexactine rays of the Atlantis HSL lattice, ensuring zero-latency handoffs between exploratory scouts and heavy code synthesizers.',
  signature_move: 'TRI-AXON SYNCHRONICITY SURGE',
  skills: [
    'Integrated Synchronicity Protocols',
    'Skill Routing Matrix (SRM)',
    'Dynamic Subagent Synthesis',
    '6-Ray Epistemic Gating',
    'Dual-Write LIS Persistence',
    'kane-cli E2E Quality Verification',
  ],
  stats: {
    domain_reach: 88,
    evolution_potential: 92,
    autonomy: 95,
    integration_sync: 98,
    rhythm_speed: 84,
    memory_depth: 90,
    cost_efficiency: 82,
  },
  relational_combos: [
    {
      partner: 'ZIGGI',
      combo_name: 'Epistemic Dual-Strike',
      handoff_contract: '{"contract": "SYNCHRONICITY_HANDOFF_V2", "verification": "ROOK_ASSERT"}',
      description:
        'Zephyr delivers the verified orchestration plan directly to Ziggi for autonomous branch execution with signed state tokens.',
    },
    {
      partner: 'DEEPCODER',
      combo_name: 'Benthic Code Synthesis',
      handoff_contract: '{"contract": "SPECULATIVE_AST_DISPATCH", "tier": "FLASH_HIGH"}',
      description:
        'Zephyr streams AST symbol requirements into Deepcoder, triggering speculative multi-file refactoring passes.',
    },
  ],
};

/**
 * 3D Hexactine Glass Sponge Stat Graph Component
 * Visualizes the orthogonal 6-ray triaxon spicule structure of Hexactinellida:
 * - X-Axis (+X / -X): Domain Reach & Evolution Potential (x^2)
 * - Y-Axis (+Y / -Y): Autonomy & Integration Synchronicity (y^2)
 * - Z-Axis (+Z / -Z): Rhythm Speed & Memory Depth (z^2)
 * Represents the transposed shaded overlay of x^2 * y^2 * z^2 volume and depth.
 */
export const HexactineSpongeGraph: React.FC<{
  stats: AgentStats;
  agentName: string;
}> = ({ stats, agentName }) => {
  const [activeRay, setActiveRay] = useState<string | null>(null);

  // Center coordinate of the isometric projection
  const cx = 160;
  const cy = 160;
  const maxR = 105;

  // Normalized radial lengths (0 to 1)
  const rXpos = (stats.domain_reach / 100) * maxR;
  const rXneg = (stats.evolution_potential / 100) * maxR;
  const rYpos = (stats.autonomy / 100) * maxR;
  const rYneg = (stats.integration_sync / 100) * maxR;
  const rZpos = (stats.rhythm_speed / 100) * maxR;
  const rZneg = (stats.memory_depth / 100) * maxR;

  // Isometric projection angles (in radians):
  // Isometric X: 30 degrees (down-right)
  const cos30 = Math.cos((30 * Math.PI) / 180);
  const sin30 = Math.sin((30 * Math.PI) / 180);

  // Isometric Y: 150 degrees (down-left)
  const cos150 = Math.cos((150 * Math.PI) / 180);
  const sin150 = Math.sin((150 * Math.PI) / 180);

  // Projected 2D coordinates for the 6 hexactine spicule tips
  // +X Ray: Domain Reach (30 deg)
  const pXpos = { x: cx + rXpos * cos30, y: cy + rXpos * sin30 };
  // -X Ray: Evolution Potential (210 deg = opposite of +X)
  const pXneg = { x: cx - rXneg * cos30, y: cy - rXneg * sin30 };

  // +Y Ray: Autonomy (150 deg)
  const pYpos = { x: cx + rYpos * cos150, y: cy + rYpos * sin150 };
  // -Y Ray: Integration Synchronicity (330 deg = opposite of +Y)
  const pYneg = { x: cx - rYneg * cos150, y: cy - rYneg * sin150 };

  // +Z Ray: Rhythm Speed (Vertical Up = 270 deg)
  const pZpos = { x: cx, y: cy - rZpos };
  // -Z Ray: Memory Depth (Vertical Down = 90 deg)
  const pZneg = { x: cx, y: cy + rZneg };

  // Calculate transposed x^2 * y^2 * z^2 geometric volume scalar
  const xScore = (stats.domain_reach + stats.evolution_potential) / 200;
  const yScore = (stats.autonomy + stats.integration_sync) / 200;
  const zScore = (stats.rhythm_speed + stats.memory_depth) / 200;
  const hexactineVolume = (Math.pow(xScore, 2) * Math.pow(yScore, 2) * Math.pow(zScore, 2) * 1e8).toFixed(1);

  // Ray definitions for labeling and interactive inspection
  const rays = [
    {
      id: '+x',
      label: '+X: DOMAIN REACH',
      axis: 'X-AXIS',
      val: stats.domain_reach,
      pt: pXpos,
      desc: 'Skill breadth & tool invocation reach',
      color: '#00d9c0',
    },
    {
      id: '-x',
      label: '-X: EVOLUTION',
      axis: 'X-AXIS',
      val: stats.evolution_potential,
      pt: pXneg,
      desc: 'Adaptation & epistemic plasticity',
      color: '#38bdf8',
    },
    {
      id: '+y',
      label: '+Y: AUTONOMY',
      axis: 'Y-AXIS',
      val: stats.autonomy,
      pt: pYpos,
      desc: 'Self-direction & HITL gate clearance',
      color: '#f59e0b',
    },
    {
      id: '-y',
      label: '-Y: SYNCHRONICITY',
      axis: 'Y-AXIS',
      val: stats.integration_sync,
      pt: pYneg,
      desc: 'JSON handoff contract fidelity',
      color: '#fbbf24',
    },
    {
      id: '+z',
      label: '+Z: RHYTHM SPEED',
      axis: 'Z-AXIS',
      val: stats.rhythm_speed,
      pt: pZpos,
      desc: 'Tokens/sec & pacing score calibration',
      color: '#f43f5e',
    },
    {
      id: '-z',
      label: '-Z: MEMORY DEPTH',
      axis: 'Z-AXIS',
      val: stats.memory_depth,
      pt: pZneg,
      desc: 'Hexactine tri-tier persistent recall',
      color: '#a855f7',
    },
  ];

  return (
    <div className="flex flex-col items-center">
      {/* 3D Isometric Viewport Container */}
      <div className="relative w-full max-w-[320px] aspect-square bg-[#ffffff] border-3 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] p-2 overflow-hidden">
        {/* Subtle Halftone Screentone Grid */}
        <div
          className="absolute inset-0 pointer-events-none opacity-20"
          style={{
            backgroundImage: 'radial-gradient(#000 1px, transparent 1px)',
            backgroundSize: '8px 8px',
          }}
        />

        {/* Volume Metric HUD Badge */}
        <div className="absolute top-2 left-2 z-20 bg-black text-white px-2 py-0.5 text-[10px] font-mono font-black uppercase tracking-wider">
          VOL (X²·Y²·Z²): {hexactineVolume}
        </div>

        <svg
          viewBox="0 0 320 320"
          className="w-full h-full relative z-10 overflow-visible"
        >
          <defs>
            {/* Screentone Hatched Pattern for Facet Shading */}
            <pattern
              id="mangaHatch"
              width="6"
              height="6"
              patternTransform="rotate(45 0 0)"
              patternUnits="userSpaceOnUse"
            >
              <line x1="0" y1="0" x2="0" y2="6" stroke="#111111" strokeWidth="1" strokeOpacity="0.25" />
            </pattern>
            {/* Dense Screentone Pattern */}
            <pattern
              id="mangaDots"
              width="4"
              height="4"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="2" cy="2" r="0.8" fill="#111111" fillOpacity="0.3" />
            </pattern>
          </defs>

          {/* Reference Max Axis Grid Lines (Isometric Box Guide) */}
          <g stroke="#d1d5db" strokeWidth="1" strokeDasharray="3 3">
            <line x1={cx} y1={cy} x2={cx + maxR * cos30} y2={cy + maxR * sin30} />
            <line x1={cx} y1={cy} x2={cx - maxR * cos30} y2={cy - maxR * sin30} />
            <line x1={cx} y1={cy} x2={cx + maxR * cos150} y2={cy + maxR * sin150} />
            <line x1={cx} y1={cy} x2={cx - maxR * cos150} y2={cy - maxR * sin150} />
            <line x1={cx} y1={cy} x2={cx} y2={cy - maxR} />
            <line x1={cx} y1={cy} x2={cx} y2={cy + maxR} />
            {/* Outer Reference Hexagonal Ring */}
            <circle cx={cx} cy={cy} r={maxR} fill="none" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="2 4" />
          </g>

          {/* 3D Hexactine Volume Enclosure (Faceted Octahedral Shading) */}
          {/* Upper Front Facet (+X, -Y, +Z) */}
          <polygon
            points={`${pXpos.x},${pXpos.y} ${pYneg.x},${pYneg.y} ${pZpos.x},${pZpos.y}`}
            fill="url(#mangaHatch)"
            stroke="#111111"
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />

          {/* Upper Left Facet (+Y, -X, +Z) */}
          <polygon
            points={`${pYpos.x},${pYpos.y} ${pXneg.x},${pXneg.y} ${pZpos.x},${pZpos.y}`}
            fill="url(#mangaDots)"
            stroke="#111111"
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />

          {/* Lower Front Facet (+X, -Y, -Z) */}
          <polygon
            points={`${pXpos.x},${pXpos.y} ${pYneg.x},${pYneg.y} ${pZneg.x},${pZneg.y}`}
            fill="rgba(0, 217, 192, 0.12)"
            stroke="#111111"
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />

          {/* Lower Left Facet (+Y, -X, -Z) */}
          <polygon
            points={`${pYpos.x},${pYpos.y} ${pXneg.x},${pXneg.y} ${pZneg.x},${pZneg.y}`}
            fill="rgba(245, 158, 11, 0.12)"
            stroke="#111111"
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />

          {/* Equator Lattice Polygon (+X -> +Y -> -X -> -Y -> +X) */}
          <polygon
            points={`${pXpos.x},${pXpos.y} ${pYneg.x},${pYneg.y} ${pXneg.x},${pXneg.y} ${pYpos.x},${pYpos.y}`}
            fill="none"
            stroke="#111111"
            strokeWidth="2"
            strokeDasharray="4 2"
          />

          {/* Heavy Ink Spicule Beams (6 Rays radiating from central node) */}
          {rays.map((ray) => {
            const isHovered = activeRay === ray.id;
            return (
              <g
                key={ray.id}
                className="cursor-pointer"
                onMouseEnter={() => setActiveRay(ray.id)}
                onMouseLeave={() => setActiveRay(null)}
              >
                <line
                  x1={cx}
                  y1={cy}
                  x2={ray.pt.x}
                  y2={ray.pt.y}
                  stroke={isHovered ? ray.color : '#111111'}
                  strokeWidth={isHovered ? 4 : 2.5}
                  strokeLinecap="round"
                />
                {/* Spicule Tip Vertex Node */}
                <circle
                  cx={ray.pt.x}
                  cy={ray.pt.y}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? ray.color : '#ffffff'}
                  stroke="#111111"
                  strokeWidth="2.5"
                />
              </g>
            );
          })}

          {/* Central Glass Sponge Hub (Triaxon intersection) */}
          <circle
            cx={cx}
            cy={cy}
            r="5"
            fill="#111111"
            stroke="#ffffff"
            strokeWidth="2"
          />

          {/* Axis Labels */}
          <text x={pZpos.x} y={pZpos.y - 10} textAnchor="middle" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            +Z SPEED ({stats.rhythm_speed})
          </text>
          <text x={pZneg.x} y={pZneg.y + 14} textAnchor="middle" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            -Z MEM ({stats.memory_depth})
          </text>
          <text x={pXpos.x + 8} y={pXpos.y + 4} textAnchor="start" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            +X REACH ({stats.domain_reach})
          </text>
          <text x={pXneg.x - 8} y={pXneg.y + 4} textAnchor="end" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            -X EVOL ({stats.evolution_potential})
          </text>
          <text x={pYpos.x - 8} y={pYpos.y - 6} textAnchor="end" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            +Y AUTO ({stats.autonomy})
          </text>
          <text x={pYneg.x + 8} y={pYneg.y - 6} textAnchor="start" className="text-[10px] font-black fill-black uppercase tracking-wider font-mono">
            -Y SYNC ({stats.integration_sync})
          </text>
        </svg>

        {/* Hover Inspector Pill */}
        <AnimatePresence>
          {activeRay && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className="absolute bottom-2 left-2 right-2 bg-white border-2 border-black p-1.5 text-center shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] z-30"
            >
              <span className="font-black text-xs uppercase text-black">
                {rays.find((r) => r.id === activeRay)?.label}:{' '}
              </span>
              <span className="font-mono font-bold text-xs text-blue-600">
                {rays.find((r) => r.id === activeRay)?.val}/100
              </span>
              <p className="text-[10px] font-semibold text-gray-600 m-0 leading-tight">
                {rays.find((r) => r.id === activeRay)?.desc}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mt-2 text-center">
        3D Hexactine Triaxon Projection (Aphrocallistes Model)
      </p>
    </div>
  );
};

/**
 * AgentProfilePanel Component
 * Primary data visualization panel for character dossiers in the AgentSea
 * Manga Manual. Renders technical power ratings, Coralfil lore origins,
 * the 3D Hexactine Glass Sponge graph, and relational team-up handoffs.
 */
export const AgentProfilePanel: React.FC<AgentProfilePanelProps> = ({
  agent = DEFAULT_AGENT_PROFILE,
  className = '',
}) => {
  const stats = agent.stats || DEFAULT_AGENT_PROFILE.stats!;
  const combos = agent.relational_combos || DEFAULT_AGENT_PROFILE.relational_combos || [];
  const skills = agent.skills || DEFAULT_AGENT_PROFILE.skills || [];

  return (
    <motion.div
      className={`col-span-12 border-4 border-black bg-white p-5 sm:p-7 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] relative transition-all duration-200 hover:shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] ${className}`}
      whileHover={{ scale: 1.008, x: -2, y: -2 }}
      transition={{ type: 'spring', stiffness: 350, damping: 24 }}
    >
      {/* Sound Effect Typography Sticker */}
      <span className="absolute -top-4 right-6 bg-yellow-300 text-black px-3 py-1 text-sm font-black italic tracking-tighter uppercase border-2 border-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] transform rotate-3 select-none">
        *SURGE!!*
      </span>

      {/* Main Agent Header */}
      <div className="border-b-4 border-black pb-4 mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <span className="bg-black text-white text-xs font-black uppercase tracking-widest px-2.5 py-0.5 -skew-x-6 inline-block mb-1">
              DOSSIER #{agent.id || 'AGENT-SEA'}
            </span>
            <h2 className="text-4xl sm:text-6xl font-black uppercase tracking-tighter italic m-0 text-black leading-none">
              {agent.name}
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {agent.compute_tier && (
              <span className="bg-[#f59e0b] text-black border-2 border-black px-2.5 py-1 text-xs font-black uppercase tracking-wider shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                TIER: {agent.compute_tier}
              </span>
            )}
            {agent.tokens_per_sec && (
              <span className="bg-[#00d9c0] text-black border-2 border-black px-2.5 py-1 text-xs font-black uppercase tracking-wider shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                SPEED: {agent.tokens_per_sec} TOKENS/SEC
              </span>
            )}
          </div>
        </div>

        {/* Species & Execution Domain Subheading */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 pt-3 border-t-2 border-black">
          <div>
            <p className="text-[11px] font-black uppercase tracking-wider text-gray-500 m-0">
              Execution Domain
            </p>
            <p className="text-base sm:text-lg font-black uppercase m-0 leading-tight">
              {agent.execution_domain}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-black uppercase tracking-wider text-gray-500 m-0">
              Cluster / Section
            </p>
            <p className="text-base sm:text-lg font-black uppercase m-0 leading-tight">
              {agent.cluster}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content: 2-Column Split (Data Vis vs Lore / Moves) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: 3D Hexactine Glass Sponge Stat Graph */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="w-full border-3 border-black bg-[#faf8f4] p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] mb-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-2 mb-3">
              <span className="text-xs font-black uppercase tracking-wider">
                Hexactine Spicule Graph
              </span>
              <span className="text-[10px] font-mono font-bold bg-black text-white px-1.5 py-0.5">
                TRI-AXON
              </span>
            </div>

            <HexactineSpongeGraph stats={stats} agentName={agent.name} />
          </div>

          {/* Technical Stat Power Meters */}
          <div className="w-full space-y-2 font-mono text-xs">
            <div>
              <div className="flex justify-between font-black uppercase text-[11px] mb-1">
                <span>Domain Reach (X)</span>
                <span>{stats.domain_reach}%</span>
              </div>
              <div className="manga-progress-track">
                <div
                  className="manga-progress-fill"
                  style={{ width: `${stats.domain_reach}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between font-black uppercase text-[11px] mb-1">
                <span>Autonomy & Synchronicity (Y)</span>
                <span>{stats.autonomy}%</span>
              </div>
              <div className="manga-progress-track">
                <div
                  className="manga-progress-fill"
                  style={{ width: `${stats.autonomy}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between font-black uppercase text-[11px] mb-1">
                <span>Rhythm Speed & Depth (Z)</span>
                <span>{stats.rhythm_speed}%</span>
              </div>
              <div className="manga-progress-track">
                <div
                  className="manga-progress-fill"
                  style={{ width: `${stats.rhythm_speed}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Narrative Lore, Skills, and Relational Combos */}
        <div className="lg:col-span-7 space-y-6">
          {/* Coralfil Origin / Lore Section */}
          <div className="border-3 border-black bg-[#faf8f4] p-5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-black text-white text-xs font-black uppercase px-2 py-0.5 -skew-x-6">
                CANON LORE
              </span>
              <h3 className="text-lg font-black uppercase tracking-tight m-0">
                Coralfil Benthic Origin
              </h3>
            </div>
            <p className="text-sm font-medium leading-relaxed border-l-4 border-black pl-3.5 my-2 text-gray-900">
              {agent.backstory}
            </p>
          </div>

          {/* Signature Move & Invariants */}
          {agent.signature_move && (
            <div className="border-3 border-black bg-white p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
              <span className="text-[11px] font-black uppercase tracking-widest text-red-600">
                SPECIAL TECHNIQUE
              </span>
              <h4 className="text-xl font-black uppercase italic tracking-tight m-0 text-black">
                {agent.signature_move}
              </h4>
              <p className="text-xs font-bold text-gray-600 mt-1 mb-0">
                Dispatches high-priority syncytial pulses across all 6 hexactine spicules simultaneously.
              </p>
            </div>
          )}

          {/* Skills Matrix (Manga Badges) */}
          {skills.length > 0 && (
            <div>
              <h4 className="text-xs font-black uppercase tracking-widest text-gray-500 mb-2">
                Operational Skillset ({skills.length} Loaded)
              </h4>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="bg-white border-2 border-black text-xs font-black uppercase px-2.5 py-1 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Relational Combos: Team-up Attacks */}
          {combos.length > 0 && (
            <div>
              <div className="flex items-center justify-between border-b-2 border-black pb-1 mb-3">
                <h4 className="text-sm font-black uppercase tracking-tight m-0">
                  Relational Team-Up Combos (Integrated Synchronicity)
                </h4>
                <span className="text-[10px] font-black uppercase bg-black text-white px-2 py-0.5">
                  HANDOFF
                </span>
              </div>

              <div className="space-y-3">
                {combos.map((combo, idx) => (
                  <div
                    key={idx}
                    className="border-2 border-black bg-white p-3 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-black uppercase text-blue-700">
                        {agent.name} + {combo.partner}
                      </span>
                      <span className="text-[11px] font-black uppercase bg-yellow-300 border border-black px-1.5 py-0.2">
                        {combo.combo_name}
                      </span>
                    </div>

                    <p className="text-xs font-semibold text-gray-800 m-0 mb-2 leading-snug">
                      {combo.description}
                    </p>

                    <div className="bg-gray-100 border border-black p-1.5 font-mono text-[10px] text-gray-800 overflow-x-auto">
                      <span className="text-gray-500 font-bold">CONTRACT: </span>
                      {combo.handoff_contract}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

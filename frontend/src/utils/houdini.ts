import type { CadenceWindow } from '../api/client';

const CADENCE_COLORS: Record<CadenceWindow, string> = {
  deep_tide: '#00d9c0',
  creative_swell: '#38bdf8',
  shallow_drift: '#f59e0b',
  recovery_ebb: '#818cf8',
};

const CADENCE_PHASES: Record<CadenceWindow, number> = {
  deep_tide: 24,
  creative_swell: 112,
  shallow_drift: 204,
  recovery_ebb: 312,
};

let initialized = false;

export function computeRhythmBpm(energy: number, overwhelmIndex: number): number {
  const clampedEnergy = Math.min(5, Math.max(1, Math.round(energy)));
  const clampedOverwhelm = Math.min(1, Math.max(0, overwhelmIndex));
  return Math.min(
    180,
    Math.max(36, Math.round(48 + (clampedEnergy - 1) * 10 + clampedOverwhelm * 8))
  );
}

export function initHoudiniLayer(reducedMotion: boolean): void {
  if (typeof window === 'undefined' || typeof CSS === 'undefined') {
    return;
  }

  if (!initialized && typeof CSS.registerProperty === 'function') {
    const defs: Array<{
      name: string;
      syntax: string;
      inherits: boolean;
      initialValue: string;
    }> = [
      { name: '--rhythm-bpm', syntax: '<number>', inherits: true, initialValue: '68' },
      { name: '--overwhelm-index', syntax: '<number>', inherits: true, initialValue: '0.2' },
      { name: '--focus-depth', syntax: '<percentage>', inherits: true, initialValue: '60%' },
      { name: '--cadence-color', syntax: '<color>', inherits: true, initialValue: '#00d9c0' },
      { name: '--lattice-phase', syntax: '<angle>', inherits: true, initialValue: '0deg' },
    ];
    for (const def of defs) {
      try {
        CSS.registerProperty(def);
      } catch {
        // Ignore if already registered via @property or hot reload.
      }
    }
  }

  if (!initialized && !reducedMotion) {
    const cssAny = CSS as unknown as {
      paintWorklet?: { addModule: (url: string) => Promise<void> };
    };
    if (cssAny.paintWorklet && typeof cssAny.paintWorklet.addModule === 'function') {
      Promise.all([
        cssAny.paintWorklet.addModule('/worklets/rhythm-lattice-paint.js'),
        cssAny.paintWorklet.addModule('/worklets/biolum-pulse-paint.js'),
      ]).catch(() => {
        // Fallback CSS gradients remain active when worklets cannot load.
      });
    }
  }

  initialized = true;
}

export interface HoudiniTokenInput {
  energy: number;
  overwhelmIndex: number;
  cadence: CadenceWindow;
  phaseOffsetDeg?: number;
}

export function applyHoudiniTokens(input: HoudiniTokenInput): {
  bpm: number;
  overwhelm: number;
  focusDepth: string;
  cadenceColor: string;
  latticePhase: string;
} {
  const bpm = computeRhythmBpm(input.energy, input.overwhelmIndex);
  const overwhelm = Number(Math.min(1, Math.max(0, input.overwhelmIndex)).toFixed(3));
  const focusDepthPct = Math.min(100, Math.max(20, Math.round(input.energy * 20)));
  const focusDepth = `${focusDepthPct}%`;
  const cadenceColor = CADENCE_COLORS[input.cadence] || '#00d9c0';
  const basePhase = CADENCE_PHASES[input.cadence] ?? 0;
  const phaseDeg = Math.round((basePhase + (input.phaseOffsetDeg ?? 0)) % 360);
  const latticePhase = `${phaseDeg}deg`;

  if (typeof document !== 'undefined') {
    const root = document.documentElement;
    const typedWin = window as unknown as {
      CSS?: {
        number?: (v: number) => unknown;
        percent?: (v: number) => unknown;
        deg?: (v: number) => unknown;
      };
    };

    const styleMap = (root as unknown as {
      attributeStyleMap?: { set: (prop: string, val: unknown) => void };
    }).attributeStyleMap;

    if (
      styleMap &&
      typeof styleMap.set === 'function' &&
      typedWin.CSS &&
      typeof typedWin.CSS.number === 'function' &&
      typeof typedWin.CSS.percent === 'function' &&
      typeof typedWin.CSS.deg === 'function'
    ) {
      try {
        styleMap.set('--rhythm-bpm', typedWin.CSS.number(bpm));
        styleMap.set('--overwhelm-index', typedWin.CSS.number(overwhelm));
        styleMap.set('--focus-depth', typedWin.CSS.percent(focusDepthPct));
        styleMap.set('--lattice-phase', typedWin.CSS.deg(phaseDeg));
      } catch {
        // Fallback to string property assignment below.
      }
    }

    root.style.setProperty('--rhythm-bpm', String(bpm));
    root.style.setProperty('--overwhelm-index', String(overwhelm));
    root.style.setProperty('--focus-depth', focusDepth);
    root.style.setProperty('--cadence-color', cadenceColor);
    root.style.setProperty('--lattice-phase', latticePhase);
  }

  return {
    bpm,
    overwhelm,
    focusDepth,
    cadenceColor,
    latticePhase,
  };
}

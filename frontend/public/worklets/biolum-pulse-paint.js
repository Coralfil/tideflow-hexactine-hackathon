class BiolumPulsePainter {
  static get inputProperties() {
    return [
      '--rhythm-bpm',
      '--overwhelm-index',
      '--focus-depth',
      '--cadence-color',
      '--lattice-phase',
    ];
  }

  paint(ctx, geom, props) {
    const width = geom.width;
    const height = geom.height;
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.max(18, Math.min(width, height) * 0.44);

    const bpm = parseFloat(String(props.get('--rhythm-bpm') || '68')) || 68;
    const overwhelm = Math.min(
      1,
      Math.max(0, parseFloat(String(props.get('--overwhelm-index') || '0.2')) || 0.2)
    );
    const focusRaw = parseFloat(String(props.get('--focus-depth') || '60')) || 60;
    const focusNorm = Math.min(1, Math.max(0.1, focusRaw / 100));
    const cadenceColor = String(props.get('--cadence-color') || '#00d9c0').trim() || '#00d9c0';
    const phaseDeg = parseFloat(String(props.get('--lattice-phase') || '0')) || 0;
    const phaseRad = (phaseDeg * Math.PI) / 180;

    // Concentric harmonic cadence rings
    const ringCount = 4;
    for (let i = 1; i <= ringCount; i++) {
      const r = (radius * i) / ringCount;
      ctx.strokeStyle = cadenceColor;
      ctx.globalAlpha = i === ringCount ? 0.42 : 0.14 + (ringCount - i) * 0.05;
      ctx.lineWidth = i === ringCount ? 2 : 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // 6-ray hexactine compass ticks modulated by BPM
    const tickCount = 12;
    ctx.globalAlpha = 0.35;
    for (let t = 0; t < tickCount; t++) {
      const angle = (t * Math.PI * 2) / tickCount + phaseRad * 0.25;
      const innerR = t % 2 === 0 ? radius * 0.72 : radius * 0.84;
      const outerR = radius * 0.96;
      ctx.strokeStyle = t % 2 === 0 ? cadenceColor : '#94a3b8';
      ctx.lineWidth = t % 2 === 0 ? 1.8 : 1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * innerR, cy + Math.sin(angle) * innerR);
      ctx.lineTo(cx + Math.cos(angle) * outerR, cy + Math.sin(angle) * outerR);
      ctx.stroke();
    }

    // Focus depth arc
    const startAngle = -Math.PI / 2 + phaseRad * 0.15;
    const sweep = Math.PI * 2 * focusNorm;
    ctx.globalAlpha = 0.88;
    ctx.strokeStyle = cadenceColor;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 0.86, startAngle, startAngle + sweep);
    ctx.stroke();

    // Overwhelm tension halo when WIP rises
    if (overwhelm > 0.05) {
      const speedFactor = Math.min(1.5, bpm / 90);
      ctx.globalAlpha = Math.min(0.45, overwhelm * 0.45 * speedFactor);
      ctx.strokeStyle = overwhelm > 0.65 ? '#ef4444' : '#f59e0b';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 0.6, startAngle, startAngle + Math.PI * 2 * overwhelm);
      ctx.stroke();
    }

    ctx.globalAlpha = 1;
  }
}

registerPaint('biolum-pulse', BiolumPulsePainter);

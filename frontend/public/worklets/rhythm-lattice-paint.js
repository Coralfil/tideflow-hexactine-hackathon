class RhythmLatticePainter {
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
    const bpm = parseFloat(String(props.get('--rhythm-bpm') || '68')) || 68;
    const overwhelm = Math.min(
      1,
      Math.max(0, parseFloat(String(props.get('--overwhelm-index') || '0.2')) || 0.2)
    );
    const focusRaw = parseFloat(String(props.get('--focus-depth') || '60')) || 60;
    const focusNorm = Math.min(1, Math.max(0.15, focusRaw / 100));
    const cadenceColor = String(props.get('--cadence-color') || '#00d9c0').trim() || '#00d9c0';
    const phaseDeg = parseFloat(String(props.get('--lattice-phase') || '0')) || 0;
    const phaseRad = (phaseDeg * Math.PI) / 180;

    // Abyssal base gradient
    const bg = ctx.createLinearGradient(0, 0, width, height);
    bg.addColorStop(0, '#030b16');
    bg.addColorStop(0.55, '#07172b');
    bg.addColorStop(1, '#040e1c');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, width, height);

    // Subtle tidal current streamlines
    const streamCount = 6;
    const amplitude = 6 + overwhelm * 14 + ((bpm - 48) / 80) * 6;
    ctx.lineWidth = 1;
    for (let s = 0; s < streamCount; s++) {
      const baseY = ((s + 0.5) / streamCount) * height;
      ctx.strokeStyle =
        s % 2 === 0 ? 'rgba(0, 217, 192, 0.08)' : 'rgba(56, 189, 248, 0.06)';
      ctx.beginPath();
      for (let x = 0; x <= width; x += 28) {
        const y =
          baseY +
          Math.sin(x * 0.009 + phaseRad + s * 1.1) * amplitude * focusNorm;
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // Hexactinellid 6-ray spicule nodes
    const spacingX = 148;
    const spacingY = 128;
    const rayLen = 22 + focusNorm * 12;
    const nodeAlpha = 0.14 + focusNorm * 0.14;

    ctx.lineWidth = 1.1;
    for (let row = 0; row * spacingY < height + spacingY; row++) {
      const y = row * spacingY + 36;
      const offsetX = row % 2 === 0 ? 0 : spacingX / 2;
      for (let col = 0; col * spacingX < width + spacingX; col++) {
        const x = col * spacingX + offsetX + 24;
        const localPhase = phaseRad * 0.5 + (row + col) * 0.45;
        const pulse = 0.75 + 0.25 * Math.sin(localPhase);

        ctx.strokeStyle = `rgba(148, 226, 232, ${(nodeAlpha * 0.65 * pulse).toFixed(3)})`;
        for (let ray = 0; ray < 6; ray++) {
          const angle = (ray * Math.PI) / 3 + localPhase * 0.12;
          const rx = x + Math.cos(angle) * rayLen;
          const ry = y + Math.sin(angle) * rayLen;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(rx, ry);
          ctx.stroke();
        }

        ctx.fillStyle = cadenceColor;
        ctx.globalAlpha = Math.min(0.45, nodeAlpha * pulse);
        ctx.beginPath();
        ctx.arc(x, y, 2.1, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    }
  }
}

registerPaint('rhythm-lattice', RhythmLatticePainter);

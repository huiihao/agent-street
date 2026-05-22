class Leaderboard {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.personas = [];
    this.colors = {};
  }

  setColors(colors) { this.colors = colors; }

  update(states) {
    this.personas = states.map(s => ({ ...s })).sort((a, b) => b.pnl - a.pnl);
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    ctx.clearRect(0, 0, w, this.canvas.height);
    if (this.personas.length === 0) return;

    const rowH = 20;
    const pad = 3;
    const barL = 54;  // bar left — after rank + ID, no overlap
    const barR = w - 3;
    const barMax = barR - barL;
    const maxAbs = Math.max(Math.abs(this.personas[0]?.pnl || 1), 0.01);

    this.personas.forEach((p, i) => {
      const y = 6 + i * rowH;
      if (y + rowH > this.canvas.height) return;
      const pnl = p.pnl || 0;
      const isPos = pnl >= 0;

      // Row bg
      ctx.fillStyle = i % 2 ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.02)';
      ctx.fillRect(0, y, w, rowH);

      // Rank
      ctx.fillStyle = i < 3 ? '#f0c040' : '#666';
      ctx.font = '7px "Press Start 2P"';
      ctx.textAlign = 'left';
      ctx.fillText(String(i + 1), pad, y + 13);

      // ID — padded well into its own column
      ctx.fillStyle = this.colors[p.id] || '#ccc';
      ctx.font = '7px "Press Start 2P"';
      ctx.fillText(p.id, 14, y + 13);

      // Bar track
      const barY = y + 5;
      const barH = 8;
      ctx.fillStyle = '#111';
      ctx.fillRect(barL, barY, barMax, barH);

      // Bar fill — clamped
      const wPct = Math.min(1, Math.abs(pnl) / maxAbs);
      const barW = Math.max(1, Math.floor(wPct * barMax));
      if (isPos) {
        ctx.fillStyle = '#4ecca3';
        ctx.fillRect(barL, barY, barW, barH);
      } else {
        // Negative: right-aligned from barR, never goes past barR - barMax
        const x = barR - barW;
        ctx.fillStyle = '#e94560';
        ctx.fillRect(x, barY, barW, barH);
      }

      // PnL value inside bar, white, always visible
      const val = Math.abs(pnl).toFixed(0);
      const txt = (pnl >= 0 ? '+$' : '-$') + val;
      ctx.fillStyle = '#fff';
      ctx.font = '6px "Press Start 2P"';
      ctx.textAlign = 'right';
      ctx.fillText(txt, barR - 3, y + 13);
    });
  }
}

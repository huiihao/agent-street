class Leaderboard {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.personas = [];
    this.colors = {};
  }

  setColors(colors) {
    this.colors = colors;
  }

  update(states) {
    this.personas = states
      .map(s => ({ ...s }))
      .sort((a, b) => b.pnl - a.pnl);
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (this.personas.length === 0) return;

    const rowH = 20;
    const nameW = 50;    // width for rank + ID
    const pnlW = 54;     // width for PnL text
    const barX = nameW;
    const maxBarW = w - nameW - pnlW - 4;
    const startY = 6;

    this.personas.forEach((p, i) => {
      const y = startY + i * rowH;
      if (y + rowH > h) return;

      const pnl = p.pnl || 0;
      const pnlStr = (pnl >= 0 ? '+' : '') + pnl.toFixed(0);
      const isPositive = pnl >= 0;

      // Row background (subtle zebra)
      ctx.fillStyle = i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.1)';
      ctx.fillRect(0, y, w, rowH);

      // Rank
      ctx.fillStyle = i < 3 ? '#f0c040' : '#888';
      ctx.font = '6px "Press Start 2P"';
      ctx.textAlign = 'left';
      ctx.fillText(String(i + 1).padStart(2, '0'), 2, y + 12);

      // Agent ID
      ctx.fillStyle = this.colors[p.id] || '#e0e0e0';
      ctx.fillText(p.id, 18, y + 12);

      // P&L bar background
      const barH = 10;
      const barY = y + 4;
      const maxAbs = Math.max(Math.abs(this.personas[0]?.pnl || 1), 1);
      let barW = Math.floor((Math.abs(pnl) / maxAbs) * maxBarW);
      if (barW < 2 && Math.abs(pnl) > 0.01) barW = 2; // minimum visible bar

      ctx.fillStyle = '#1a1a30';
      ctx.fillRect(barX, barY, maxBarW, barH);

      // P&L bar fill
      if (isPositive) {
        ctx.fillStyle = '#4ecca3';
        ctx.fillRect(barX, barY, barW, barH);
      } else {
        ctx.fillStyle = '#e94560';
        ctx.fillRect(barX + maxBarW - barW, barY, barW, barH);
      }

      // P&L text — drawn AFTER bar, outside bar area, in its own column
      ctx.fillStyle = isPositive ? '#4ecca3' : '#e94560';
      ctx.font = '6px "Press Start 2P"';
      ctx.textAlign = 'right';
      ctx.fillText(pnlStr, w - 2, y + 12);

      // Divider
      ctx.fillStyle = 'rgba(255,255,255,0.04)';
      ctx.fillRect(0, y + rowH - 1, w, 1);
    });
  }
}

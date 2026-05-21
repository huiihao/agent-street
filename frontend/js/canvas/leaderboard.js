class Leaderboard {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.personas = [];
    this.colors = {};
  }

  setColors(colors) {
    this.colors = colors; // id -> color hex
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

    const barH = 16;
    const gap = 3;
    const startY = 10;
    const maxBarW = w - 65;

    this.personas.forEach((p, i) => {
      const y = startY + i * (barH + gap);
      if (y + barH > h) return;

      // Rank
      ctx.fillStyle = '#888';
      ctx.font = '6px "Press Start 2P"';
      ctx.textAlign = 'left';
      ctx.fillText((i + 1).toString().padStart(2, '0'), 2, y + 11);

      // Name
      ctx.fillStyle = '#e0e0e0';
      ctx.fillText(p.id, 18, y + 11);

      // P&L bar background
      const barX = 52;
      ctx.fillStyle = '#1a1a30';
      ctx.fillRect(barX, y + 4, maxBarW, 10);

      // P&L bar fill
      const maxAbsPnl = Math.max(Math.abs(this.personas[0]?.pnl || 1), 1);
      const barW = Math.min(maxBarW, (Math.abs(p.pnl) / maxAbsPnl) * maxBarW);
      ctx.fillStyle = p.pnl >= 0 ? '#4ecca3' : '#e94560';
      if (p.pnl >= 0) {
        ctx.fillRect(barX, y + 4, barW, 10);
      } else {
        ctx.fillRect(barX + maxBarW - barW, y + 4, barW, 10);
      }

      // P&L text
      ctx.fillStyle = p.pnl >= 0 ? '#4ecca3' : '#e94560';
      ctx.textAlign = 'right';
      const pnlStr = (p.pnl >= 0 ? '+' : '') + p.pnl.toFixed(0);
      ctx.fillText(pnlStr, w - 2, y + 11);
    });
  }
}

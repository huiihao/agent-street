class PersonaGrid {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.personaDefs = {}; // id -> {name, color, motto, params}
    this.personaStates = {}; // id -> {cash, pnl, positions, mood}
    this.cols = 4;
    this.cellW = 80;
    this.cellH = 100;
  }

  setDefs(defs) {
    defs.forEach(d => { this.personaDefs[d.id] = d; });
  }

  update(states) {
    states.forEach(s => { this.personaStates[s.id] = s; });
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const ids = Object.keys(this.personaDefs);
    if (ids.length === 0) return;

    ids.forEach((pid, i) => {
      const col = i % this.cols;
      const row = Math.floor(i / this.cols);
      const cx = col * this.cellW + 8;
      const cy = row * this.cellH + 15;
      const def = this.personaDefs[pid] || {};
      const state = this.personaStates[pid] || {};

      // Background card
      const cardX = col * this.cellW + 4;
      const cardY = row * this.cellH + 4;
      ctx.fillStyle = '#1a1a30';
      ctx.fillRect(cardX, cardY, this.cellW - 8, this.cellH - 8);
      ctx.strokeStyle = def.color || '#444';
      ctx.lineWidth = 2;
      ctx.strokeRect(cardX, cardY, this.cellW - 8, this.cellH - 8);

      // Sprite
      const mood = state.mood || 'calm';
      const hairSeed = hairSeedFromId(pid);
      drawPersonaSprite(ctx, cx, cy, mood, def.color || '#888', hairSeed);

      // Name
      ctx.fillStyle = '#e0e0e0';
      ctx.font = '6px "Press Start 2P"';
      ctx.textAlign = 'center';
      ctx.fillText(pid, cx + 24, cy + 55);

      // P&L
      const pnl = state.pnl || 0;
      const pnlStr = (pnl >= 0 ? '+' : '') + pnl.toFixed(0);
      ctx.fillStyle = pnl >= 0 ? '#4ecca3' : '#e94560';
      ctx.fillText(pnlStr, cx + 24, cy + 65);

      // Mood indicator bar
      const barW = 48;
      const barH = 4;
      const barX = cx;
      const barY = cy + 70;
      ctx.fillStyle = '#222';
      ctx.fillRect(barX, barY, barW, barH);
      const moodColors = {
        confident: '#4ecca3',
        calm: '#6baed6',
        worried: '#f0a040',
        excited: '#f0c040',
        panicked: '#e94560',
      };
      ctx.fillStyle = moodColors[mood] || '#888';
      ctx.fillRect(barX, barY, barW * 0.6, barH);
    });
  }

  getPersonaAt(mx, my) {
    const col = Math.floor(mx / this.cellW);
    const row = Math.floor(my / this.cellH);
    const idx = row * this.cols + col;
    const ids = Object.keys(this.personaDefs);
    if (idx >= 0 && idx < ids.length) {
      return {
        id: ids[idx],
        ...this.personaDefs[ids[idx]],
        state: this.personaStates[ids[idx]],
      };
    }
    return null;
  }
}

class StockChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.series = {};
    this.basePrices = {};
    this.maxPoints = 150;
    // Wide margins to prevent any text overflow
    this.margin = { top: 14, right: 46, bottom: 18, left: 42 };
    this.symbolColors = {
      AAPL: '#a0a0a0', GOOGL: '#4285F4', MSFT: '#34A853',
      TSLA: '#EA4335', AMZN: '#FF9900',
    };
    this.lastPrices = {};
    this.lastTick = 0;
  }

  addTick(prices, tick) {
    for (const [sym, price] of Object.entries(prices)) {
      if (!this.series[sym]) { this.series[sym] = []; this.basePrices[sym] = price; }
      this.series[sym].push({ price, tick });
      if (this.series[sym].length > this.maxPoints) this.series[sym].shift();
      this.lastPrices[sym] = price;
    }
    this.lastTick = tick;
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const m = this.margin;
    const pw = w - m.left - m.right;
    const ph = h - m.top - m.bottom;

    // Clipping region for plot area — nothing drawn outside
    ctx.save();
    ctx.beginPath();
    ctx.rect(m.left - 1, m.top - 1, pw + 2, ph + 2);
    ctx.clip();

    // Grid lines
    ctx.strokeStyle = '#1a1a30';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = m.top + (ph / 4) * i;
      ctx.beginPath(); ctx.moveTo(m.left, y); ctx.lineTo(w - m.right, y);
      ctx.stroke();
    }

    // Collect percentage data
    const allPcts = [];
    const pointMap = {};
    for (const [sym, pts] of Object.entries(this.series)) {
      if (pts.length < 2) continue;
      const base = this.basePrices[sym] || pts[0]?.price || 100;
      pointMap[sym] = pts.map(p => ({ pct: (p.price - base) / base * 100, tick: p.tick }));
      for (const p of pointMap[sym]) allPcts.push(p.pct);
    }
    if (allPcts.length < 2) { ctx.restore(); return; }

    const minP = Math.min(...allPcts);
    const maxP = Math.max(...allPcts);
    const range = Math.max(maxP - minP, 0.15);

    // Y axis labels (clipped inside plot)
    ctx.fillStyle = '#666';
    ctx.font = '6px "Press Start 2P"';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const p = maxP - (range / 4) * i;
      const y = m.top + (ph / 4) * i;
      ctx.fillText(p.toFixed(1) + '%', m.left - 3, y + 2);
    }

    // Draw series
    const allTicks = Object.values(pointMap).flatMap(p => p.map(q => q.tick));
    const minT = Math.min(...allTicks);
    const maxT = Math.max(...allTicks);
    const tRange = maxT - minT || 1;

    for (const [sym, pts] of Object.entries(pointMap)) {
      if (pts.length < 2) continue;
      ctx.strokeStyle = this.symbolColors[sym] || '#fff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      pts.forEach((p, i) => {
        const x = m.left + ((p.tick - minT) / tRange) * pw;
        const y = m.top + ph - ((p.pct - minP) / range) * ph;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
      // Last dot
      const lp = pts[pts.length - 1];
      const lx = m.left + ((lp.tick - minT) / tRange) * pw;
      const ly = m.top + ph - ((lp.pct - minP) / range) * ph;
      ctx.fillStyle = this.symbolColors[sym] || '#fff';
      ctx.fillRect(lx - 1.5, ly - 1.5, 3, 3);
    }

    ctx.restore(); // remove clip

    // Legend — drawn OUTSIDE plot area, at the top-right corner of canvas
    ctx.textAlign = 'left';
    ctx.font = '5px "Press Start 2P"';
    let lx = m.left + 4;
    let ly = 4;
    for (const [sym, color] of Object.entries(this.symbolColors)) {
      const lp = this.lastPrices[sym];
      const txt = lp ? sym + ' ' + lp.toFixed(0) : sym;
      // Measure to avoid overflow
      const tw = ctx.measureText(txt).width;
      if (lx + tw + 4 > w - 2) { lx = m.left + 4; ly += 8; }
      ctx.fillStyle = color;
      ctx.fillText(txt, lx, ly + 5);
      lx += tw + 10;
    }

    // Tick label — bottom-right
    ctx.fillStyle = '#444';
    ctx.font = '5px "Press Start 2P"';
    ctx.textAlign = 'right';
    ctx.fillText('T+' + this.lastTick, w - 3, h - 3);
  }
}

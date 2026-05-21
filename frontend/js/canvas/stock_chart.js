class StockChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.series = {}; // symbol -> [{price, tick}]
    this.basePrices = {}; // first price per symbol for % calc
    this.maxPoints = 180;
    this.margin = { top: 16, right: 55, bottom: 26, left: 48 };
    this.symbolColors = {
      AAPL: '#a0a0a0',
      GOOGL: '#4285F4',
      MSFT: '#34A853',
      TSLA: '#EA4335',
      AMZN: '#FF9900',
    };
    this.lastPrices = {};
  }

  addTick(prices, tick) {
    for (const [sym, price] of Object.entries(prices)) {
      if (!this.series[sym]) {
        this.series[sym] = [];
        this.basePrices[sym] = price;
      }
      this.series[sym].push({ price, tick });
      if (this.series[sym].length > this.maxPoints) {
        this.series[sym].shift();
      }
      this.lastPrices[sym] = price;
    }
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const plotW = w - this.margin.left - this.margin.right;
    const plotH = h - this.margin.top - this.margin.bottom;

    // Background grid
    ctx.strokeStyle = '#1a1a30';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = this.margin.top + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(this.margin.left, y);
      ctx.lineTo(w - this.margin.right, y);
      ctx.stroke();
    }

    // Compute % changes relative to base
    const allPcts = [];
    const pointMap = {}; // symbol -> [{pct, tick}]
    for (const [sym, points] of Object.entries(this.series)) {
      const base = this.basePrices[sym] || points[0]?.price || 100;
      if (points.length < 2) continue;
      pointMap[sym] = points.map(p => ({ pct: (p.price - base) / base * 100, tick: p.tick }));
      for (const p of pointMap[sym]) {
        allPcts.push(p.pct);
      }
    }
    if (allPcts.length < 2) return;

    const minPct = Math.min(...allPcts);
    const maxPct = Math.max(...allPcts);
    const range = Math.max(maxPct - minPct, 0.1);

    // Y axis — percentage
    ctx.fillStyle = '#888';
    ctx.font = '7px "Press Start 2P"';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const p = maxPct - (range / 4) * i;
      const y = this.margin.top + (plotH / 4) * i;
      ctx.fillText(p.toFixed(1) + '%', this.margin.left - 4, y + 2);
    }

    // Legend + last price
    let ly = this.margin.top;
    ctx.textAlign = 'left';
    for (const [sym, color] of Object.entries(this.symbolColors)) {
      const lp = this.lastPrices[sym];
      ctx.fillStyle = color;
      ctx.fillText(sym + (lp ? ' $' + lp.toFixed(0) : ''), w - this.margin.right + 4, ly);
      ly += 11;
    }

    // Draw each series
    const allTicks = Object.values(pointMap).flatMap(p => p.map(q => q.tick));
    if (allTicks.length === 0) return;
    const minTick = Math.min(...allTicks);
    const maxTick = Math.max(...allTicks);
    const tickRange = maxTick - minTick || 1;

    for (const [sym, points] of Object.entries(pointMap)) {
      if (points.length < 2) continue;
      ctx.strokeStyle = this.symbolColors[sym] || '#fff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = this.margin.left + ((p.tick - minTick) / tickRange) * plotW;
        const y = this.margin.top + plotH - ((p.pct - minPct) / range) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Last dot
      const last = points[points.length - 1];
      const lx = this.margin.left + ((last.tick - minTick) / tickRange) * plotW;
      const ly2 = this.margin.top + plotH - ((last.pct - minPct) / range) * plotH;
      ctx.fillStyle = this.symbolColors[sym] || '#fff';
      ctx.fillRect(lx - 2, ly2 - 2, 4, 4);
    }

    // Tick label on x-axis
    ctx.fillStyle = '#666';
    ctx.font = '5px "Press Start 2P"';
    ctx.textAlign = 'right';
    ctx.fillText('T' + maxTick, w - this.margin.right, h - 4);
  }
}

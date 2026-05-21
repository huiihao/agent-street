class StockChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.series = {}; // symbol -> [{price, tick}]
    this.maxPoints = 200;
    this.margin = { top: 20, right: 60, bottom: 30, left: 50 };
    this.symbolColors = {
      AAPL: '#a0a0a0',
      GOOGL: '#4285F4',
      MSFT: '#34A853',
      TSLA: '#EA4335',
      AMZN: '#FF9900',
    };
  }

  addTick(prices, tick) {
    for (const [sym, price] of Object.entries(prices)) {
      if (!this.series[sym]) this.series[sym] = [];
      this.series[sym].push({ price, tick });
      if (this.series[sym].length > this.maxPoints) {
        this.series[sym].shift();
      }
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

    // Collect all prices to determine scale
    const allPrices = [];
    for (const points of Object.values(this.series)) {
      for (const p of points) {
        allPrices.push(p.price);
      }
    }
    if (allPrices.length < 2) return;

    const minPrice = Math.min(...allPrices) * 0.995;
    const maxPrice = Math.max(...allPrices) * 1.005;
    const priceRange = maxPrice - minPrice || 1;

    // Y axis labels
    ctx.fillStyle = '#888';
    ctx.font = '7px "Press Start 2P"';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const price = maxPrice - (priceRange / 4) * i;
      const y = this.margin.top + (plotH / 4) * i;
      ctx.fillText('$' + price.toFixed(0), this.margin.left - 5, y + 2);
    }

    // Legend
    let legendX = w - this.margin.right + 5;
    let legendY = this.margin.top;
    ctx.textAlign = 'left';
    for (const [sym, color] of Object.entries(this.symbolColors)) {
      ctx.fillStyle = color;
      ctx.fillText(sym, legendX, legendY);
      legendY += 12;
    }

    // Draw each series
    for (const [sym, points] of Object.entries(this.series)) {
      if (points.length < 2) continue;
      const color = this.symbolColors[sym] || '#fff';

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      const allTicks = points.map(p => p.tick);
      const minTick = Math.min(...allTicks);
      const maxTick = Math.max(...allTicks);
      const tickRange = maxTick - minTick || 1;

      points.forEach((p, i) => {
        const x = this.margin.left + ((p.tick - minTick) / tickRange) * plotW;
        const y = this.margin.top + plotH - ((p.price - minPrice) / priceRange) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Draw last price dot
      const last = points[points.length - 1];
      const lx = this.margin.left + ((last.tick - minTick) / tickRange) * plotW;
      const ly = this.margin.top + plotH - ((last.price - minPrice) / priceRange) * plotH;
      ctx.fillStyle = color;
      ctx.fillRect(lx - 2, ly - 2, 4, 4);
    }
  }
}

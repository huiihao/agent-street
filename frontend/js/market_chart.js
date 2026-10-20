// A crisp, crosshair-driven market chart.
//
// Two views share one time axis:
//   Candles — OHLC + volume + MA(9)/MA(21) for the selected symbol
//   Compare — every symbol normalised to % change from the window start
//
// The palette is the validated dark categorical palette (see utils.js), and a
// legend plus direct end labels keep identity from relying on colour alone.

import {
  STATUS,
  clamp,
  dateKey,
  dateLabel,
  dateTimeLabel,
  formatCompact,
  formatPct,
  formatPrice,
  STRATEGY_FAMILIES,
  registerSymbolColors,
  strategyMeta,
  symbolColor,
  timeLabel,
} from './utils.js';

const MAX_ROWS = 300;
const MA_FAST = 9;
const MA_SLOW = 21;
const MONO = '"JetBrains Mono", "SFMono-Regular", Consolas, monospace';
const SANS = 'Sora, "Segoe UI", sans-serif';

export class MarketChart {
  constructor(container, { symbols = [], initialCash = 10000, onSymbolChange = null } = {}) {
    this.container = container;
    this.initialCash = initialCash;
    this.onSymbolChange = onSymbolChange;
    this.symbols = [];
    this.selected = null;
    this.mode = 'candles';
    this.times = [];
    this.series = new Map();
    this.agents = [];
    this.ecosystem = null;
    this.hover = null;
    this.guildHover = null;
    this._guildPoints = [];
    this.dirty = false;
    this._raf = null;
    this._lastDraw = 0;

    this._buildDom();
    this.setSymbols(symbols);
    this._bind();
    this._resize();

    this._loop = () => {
      if (this.dirty) {
        this.dirty = false;
        this._draw();
      }
      this._raf = requestAnimationFrame(this._loop);
    };
    this._raf = requestAnimationFrame(this._loop);
  }

  // ── DOM ──────────────────────────────────────────────────

  _buildDom() {
    this.container.classList.add('market-chart');
    this.container.replaceChildren();

    this.toolbar = document.createElement('div');
    this.toolbar.className = 'chart-toolbar';

    this.tabs = document.createElement('div');
    this.tabs.className = 'chart-tabs';
    this.tabs.setAttribute('role', 'tablist');
    this.tabCandles = this._button('Candles', 'chart-tab is-active');
    this.tabCompare = this._button('Compare', 'chart-tab');
    this.tabGuilds = this._button('Guilds', 'chart-tab');
    this.tabCandles.dataset.mode = 'candles';
    this.tabCompare.dataset.mode = 'compare';
    this.tabGuilds.dataset.mode = 'guilds';
    this.tabs.append(this.tabCandles, this.tabCompare, this.tabGuilds);

    this.chips = document.createElement('div');
    this.chips.className = 'chart-symbols';

    this.toolbar.append(this.tabs, this.chips);
    this.container.appendChild(this.toolbar);

    this.legend = document.createElement('div');
    this.legend.className = 'chart-legend';
    this.container.appendChild(this.legend);

    this.canvasWrap = document.createElement('div');
    this.canvasWrap.className = 'chart-canvas-wrap';
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'market-canvas';
    this.canvas.setAttribute('role', 'img');
    this.canvas.setAttribute('aria-label', 'Market price chart. Hover for details.');
    this.canvasWrap.appendChild(this.canvas);
    this.container.appendChild(this.canvasWrap);

    this.tooltip = document.createElement('div');
    this.tooltip.className = 'chart-tooltip';
    this.tooltip.hidden = true;
    this.canvasWrap.appendChild(this.tooltip);

    this.empty = document.createElement('div');
    this.empty.className = 'chart-empty';
    this.empty.textContent = 'Waiting for market data…';
    this.canvasWrap.appendChild(this.empty);

    this.ctx = this.canvas.getContext('2d');
  }

  _button(text, className) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.textContent = text;
    return btn;
  }

  _bind() {
    this.tabs.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-mode]');
      if (!btn) return;
      this.mode = btn.dataset.mode;
      for (const tab of this.tabs.querySelectorAll('[data-mode]')) {
        tab.classList.toggle('is-active', tab.dataset.mode === this.mode);
      }
      this.chips.hidden = this.mode !== 'candles';
      this.hover = null;
      this.guildHover = null;
      this.tooltip.hidden = true;
      this._updateLegend();
      this.dirty = true;
    });

    this.canvas.addEventListener('pointermove', (event) => this._pointerMove(event));
    this.canvas.addEventListener('pointerleave', () => {
      this.hover = null;
      this.guildHover = null;
      this.tooltip.hidden = true;
      this.dirty = true;
    });

    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(this.canvasWrap);
    window.addEventListener('resize', () => this._resize());
  }

  _resize() {
    const rect = this.canvasWrap.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    if (width === this._width && height === this._height) return;
    this._width = width;
    this._height = height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this._dpr = dpr;
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.dirty = true;
  }

  // ── data ─────────────────────────────────────────────────

  setSymbols(symbols) {
    this.symbols = [...symbols];
    registerSymbolColors(this.symbols);
    if (!this.selected || !this.symbols.includes(this.selected)) {
      this.selected = this.symbols[0] || null;
    }
    this._renderChips();
    this._updateLegend();
    this.dirty = true;
  }

  _renderChips() {
    this.chips.replaceChildren();
    for (const symbol of this.symbols) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chart-chip';
      btn.dataset.symbol = symbol;
      btn.classList.toggle('is-active', symbol === this.selected);
      const dot = document.createElement('span');
      dot.className = 'chart-dot';
      dot.style.background = symbolColor(symbol);
      const label = document.createElement('span');
      label.textContent = symbol;
      btn.append(dot, label);
      btn.addEventListener('click', () => {
        if (this.mode !== 'candles') {
          this.mode = 'candles';
          this.tabCandles.classList.add('is-active');
          this.tabCompare.classList.remove('is-active');
          this.tabGuilds.classList.remove('is-active');
          this.chips.hidden = false;
        }
        this.setSelected(symbol);
      });
      this.chips.appendChild(btn);
    }
  }

  setSelected(symbol) {
    if (!this.symbols.includes(symbol)) return;
    this.selected = symbol;
    for (const btn of this.chips.querySelectorAll('[data-symbol]')) {
      btn.classList.toggle('is-active', btn.dataset.symbol === symbol);
    }
    this._updateLegend();
    this.dirty = true;
    if (this.onSymbolChange) this.onSymbolChange(symbol);
  }

  setHistory(history) {
    this.times = [];
    this.series = new Map(this.symbols.map((s) => [s, []]));
    if (!history || !history.times) {
      this.dirty = true;
      return;
    }
    const times = history.times.slice(-MAX_ROWS);
    const skip = Math.max(0, (history.times.length - times.length));
    this.times = times;
    for (const symbol of this.symbols) {
      const rows = history.bars?.[symbol] || [];
      this.series.set(symbol, rows.slice(skip, skip + times.length));
    }
    this.empty.hidden = this.times.length > 0;
    this._updateLegend();
    this.dirty = true;
  }

  clear() {
    this.times = [];
    this.series = new Map(this.symbols.map((s) => [s, []]));
    this.agents = [];
    this.ecosystem = null;
    this.hover = null;
    this.guildHover = null;
    this._guildPoints = [];
    this.tooltip.hidden = true;
    this.empty.hidden = false;
    this._updateLegend();
    this.dirty = true;
  }

  setAgents(agents, ecosystem = null) {
    this.agents = (agents || []).filter(
      (agent) => !agent.isObserver && agent.strategy && agent.strategy.weights,
    );
    this.ecosystem = ecosystem || null;
    if (this.mode === 'guilds') {
      this._updateLegend();
      this.dirty = true;
    }
  }

  pushFrame(frame) {
    if (!frame || !frame.bars) return;
    if (frame.looped) {
      this.clear();
      return;
    }
    const symbols = Object.keys(frame.bars);
    if (!symbols.length) return;

    const firstBar = frame.bars[symbols[0]];
    if (!firstBar) return;
    const time = firstBar.t;
    const lastTime = this.times[this.times.length - 1];

    if (!lastTime) {
      this.times = [time];
      for (const symbol of this.symbols) {
        const bar = frame.bars[symbol];
        this.series.set(symbol, bar ? [bar] : []);
      }
    } else if (time === lastTime) {
      for (const symbol of this.symbols) {
        const bar = frame.bars[symbol];
        const rows = this.series.get(symbol) || [];
        if (bar) rows[rows.length - 1] = bar;
        this.series.set(symbol, rows);
      }
    } else {
      this.times.push(time);
      for (const symbol of this.symbols) {
        const bar = frame.bars[symbol];
        const rows = this.series.get(symbol) || [];
        rows.push(bar || rows[rows.length - 1] || null);
        this.series.set(symbol, rows);
      }
      while (this.times.length > MAX_ROWS) {
        this.times.shift();
        for (const symbol of this.symbols) {
          this.series.get(symbol)?.shift();
        }
      }
    }
    this.empty.hidden = this.times.length > 0;
    this._updateLegend();
    this.dirty = true;
  }

  _updateLegend() {
    this.legend.replaceChildren();
    if (!this.times.length) {
      this.legend.hidden = true;
      return;
    }
    this.legend.hidden = false;

    if (this.mode === 'guilds') {
      const guilds = this.ecosystem?.guilds || [];
      for (const guild of guilds) {
        const meta = strategyMeta(guild.family);
        const wrap = document.createElement('span');
        wrap.className = 'legend-item';
        const dot = document.createElement('span');
        dot.className = 'legend-dot';
        dot.style.background = meta.color;
        const label = document.createElement('span');
        label.className = 'legend-label';
        label.textContent = meta.label;
        const value = document.createElement('strong');
        value.textContent = `${guild.count} · ${formatPct(guild.avgFitness || 0, 1, true)}`;
        wrap.append(dot, label, value);
        this.legend.appendChild(wrap);
      }
      const latest = this.ecosystem?.adaptations?.[0];
      if (latest) {
        const note = document.createElement('span');
        note.className = 'legend-note';
        note.textContent = `Latest: ${latest.agent} — ${latest.text}`;
        this.legend.appendChild(note);
      }
      return;
    }

    if (this.mode === 'candles') {
      const symbol = this.selected;
      const rows = this.series.get(symbol) || [];
      const bar = rows[rows.length - 1];
      if (!bar) {
        this.legend.hidden = true;
        return;
      }
      const prev = rows.length > 1 ? rows[rows.length - 2] : null;
      const change = prev ? (bar.c - prev.c) / prev.c : 0;
      const item = (label, value, cls = '') => {
        const wrap = document.createElement('span');
        wrap.className = `legend-item ${cls}`;
        const key = document.createElement('span');
        key.className = 'legend-key';
        key.style.background = symbolColor(symbol);
        const l = document.createElement('span');
        l.className = 'legend-label';
        l.textContent = label;
        const v = document.createElement('strong');
        v.textContent = value;
        wrap.append(key, l, v);
        return wrap;
      };
      this.legend.append(
        item(`${symbol}`, `$${formatPrice(bar.c)}`),
        item('Change', `${change >= 0 ? '▲' : '▼'} ${formatPct(change, 2, false)}`, change >= 0 ? 'is-up' : 'is-down'),
        item('Volume', formatCompact(bar.v)),
        item(`MA${MA_FAST}`, formatPrice(sma(rows, MA_FAST))),
        item(`MA${MA_SLOW}`, formatPrice(sma(rows, MA_SLOW))),
      );
    } else {
      for (const symbol of this.symbols) {
        const rows = this.series.get(symbol) || [];
        const pct = this._normalisedAt(rows, rows.length - 1);
        const wrap = document.createElement('span');
        wrap.className = `legend-item ${pct >= 0 ? 'is-up' : 'is-down'}`;
        const key = document.createElement('span');
        key.className = 'legend-key';
        key.style.background = symbolColor(symbol);
        const label = document.createElement('span');
        label.className = 'legend-label';
        label.textContent = symbol;
        const value = document.createElement('strong');
        value.textContent = pct === null ? '—' : formatPct(pct, 2, true);
        wrap.append(key, label, value);
        this.legend.appendChild(wrap);
      }
    }
  }

  // ── drawing ──────────────────────────────────────────────

  _draw() {
    const ctx = this.ctx;
    const width = this._width || 0;
    const height = this._height || 0;
    if (!width || !height) return;
    ctx.clearRect(0, 0, width, height);
    if (!this.times.length) {
      return;
    }
    if (this.mode === 'candles') this._drawCandles(ctx, width, height);
    else if (this.mode === 'guilds') this._drawGuilds(ctx, width, height);
    else this._drawCompare(ctx, width, height);
    if (this.hover) this._drawCrosshair(ctx, width, height);
  }

  _layout(width, height) {
    const margin = { top: 10, right: 58, bottom: 20, left: 8 };
    const plotW = Math.max(20, width - margin.left - margin.right);
    const plotH = Math.max(40, height - margin.top - margin.bottom);
    const volH = Math.max(24, Math.round(plotH * 0.18));
    const gap = 8;
    const priceH = plotH - volH - gap;
    return {
      margin,
      plotW,
      plotH,
      priceTop: margin.top,
      priceBottom: margin.top + priceH,
      priceH,
      volTop: margin.top + priceH + gap,
      volH,
      right: margin.left + plotW,
    };
  }

  _visibleCount(plotW) {
    return Math.max(24, Math.min(this.times.length, Math.floor(plotW / 7)));
  }

  _drawCandles(ctx, width, height) {
    const L = this._layout(width, height);
    const symbol = this.selected;
    const rows = this.series.get(symbol) || [];
    if (!rows.length) {
      this._drawEmptyMessage(ctx, width, height);
      return;
    }
    const n = this._visibleCount(L.plotW);
    const start = Math.max(0, rows.length - n);
    const visible = rows.slice(start);
    const slot = L.plotW / visible.length;

    let min = Infinity;
    let max = -Infinity;
    let maxVol = 0;
    for (const bar of visible) {
      if (!bar) continue;
      min = Math.min(min, bar.l);
      max = Math.max(max, bar.h);
      maxVol = Math.max(maxVol, bar.v || 0);
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
      this._drawEmptyMessage(ctx, width, height);
      return;
    }
    const pad = (max - min) * 0.08;
    min -= pad;
    max += pad;
    const priceToY = (price) => L.priceBottom - ((price - min) / (max - min)) * L.priceH;

    this._drawGrid(ctx, L, min, max, (value) => formatPrice(value));
    this._drawTimeAxis(ctx, L, start, n, slot);
    this._drawSessions(ctx, L, start, n, slot);

    // Volume bars.
    for (let i = 0; i < visible.length; i += 1) {
      const bar = visible[i];
      if (!bar) continue;
      const x = L.margin.left + (i + 0.5) * slot;
      const h = maxVol > 0 ? (bar.v / maxVol) * L.volH : 0;
      const up = bar.c >= bar.o;
      ctx.fillStyle = up ? 'rgba(12,163,12,0.36)' : 'rgba(208,59,59,0.36)';
      ctx.fillRect(x - Math.max(1, slot * 0.3), L.volTop + L.volH - h, Math.max(1.5, slot * 0.6), h);
    }
    ctx.fillStyle = 'rgba(255,255,255,0.25)';
    ctx.font = `500 8px ${MONO}`;
    ctx.textAlign = 'left';
    ctx.fillText('VOL', L.margin.left, L.volTop + 8);

    // Moving averages (computed over the full series, drawn over the window).
    this._drawMA(ctx, rows, start, visible.length, slot, L, priceToY, MA_FAST, '#f0b429');
    this._drawMA(ctx, rows, start, visible.length, slot, L, priceToY, MA_SLOW, '#5aa9ff');

    // Candles.
    const bodyW = clamp(slot * 0.62, 1.5, 11);
    for (let i = 0; i < visible.length; i += 1) {
      const bar = visible[i];
      if (!bar) continue;
      const x = L.margin.left + (i + 0.5) * slot;
      const up = bar.c >= bar.o;
      const color = up ? STATUS.good : STATUS.critical;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = Math.max(1, Math.min(1.4, slot * 0.14));
      ctx.beginPath();
      ctx.moveTo(x, priceToY(bar.h));
      ctx.lineTo(x, priceToY(bar.l));
      ctx.stroke();
      const yOpen = priceToY(bar.o);
      const yClose = priceToY(bar.c);
      const bodyTop = Math.min(yOpen, yClose);
      const bodyH = Math.max(1, Math.abs(yClose - yOpen));
      if (up) {
        // Hollow up candles add a second channel for colour-blind readers.
        ctx.fillStyle = 'rgba(8,18,30,0.9)';
        ctx.fillRect(x - bodyW / 2, bodyTop, bodyW, bodyH);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.strokeRect(x - bodyW / 2 + 0.5, bodyTop + 0.5, Math.max(1, bodyW - 1), Math.max(1, bodyH - 1));
      } else {
        ctx.fillRect(x - bodyW / 2, bodyTop, bodyW, bodyH);
      }
    }

    // Last price tag.
    const last = visible[visible.length - 1];
    if (last) {
      const y = priceToY(last.c);
      const prev = visible.length > 1 ? visible[visible.length - 2] : null;
      const change = prev ? (last.c - prev.c) / prev.c : 0;
      ctx.strokeStyle = 'rgba(232,238,252,0.28)';
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(L.margin.left, y);
      ctx.lineTo(L.right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      const color = change >= 0 ? STATUS.good : STATUS.critical;
      const label = formatPrice(last.c);
      ctx.font = `600 10px ${MONO}`;
      const tw = ctx.measureText(label).width + 14;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(L.right + 4, y - 9, Math.min(tw, L.margin.right - 6), 18, 4);
      ctx.fill();
      ctx.fillStyle = '#f7fbff';
      ctx.textAlign = 'left';
      ctx.fillText(label, L.right + 10, y + 3.6);
    }
  }

  _drawMA(ctx, rows, start, count, slot, L, priceToY, period, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < count; i += 1) {
      const idx = start + i;
      const value = sma(rows, period, idx);
      if (value === null) continue;
      const x = L.margin.left + (i + 0.5) * slot;
      const y = priceToY(value);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    if (started) ctx.stroke();
  }

  _drawCompare(ctx, width, height) {
    const L = this._layout(width, height);
    const n = this._visibleCount(L.plotW);
    const start = Math.max(0, this.times.length - n);
    const count = this.times.length - start;
    const slot = L.plotW / count;

    const values = new Map();
    let min = 0;
    let max = 0;
    let hasData = false;
    for (const symbol of this.symbols) {
      const rows = this.series.get(symbol) || [];
      const seriesValues = [];
      for (let i = 0; i < count; i += 1) {
        const value = this._normalisedAt(rows, start + i, start);
        seriesValues.push(value);
        if (value !== null) {
          hasData = true;
          min = Math.min(min, value);
          max = Math.max(max, value);
        }
      }
      values.set(symbol, seriesValues);
    }
    if (!hasData) {
      this._drawEmptyMessage(ctx, width, height);
      return;
    }
    const pad = Math.max(0.0015, (max - min) * 0.15);
    min -= pad;
    max += pad;
    const yFor = (value) => L.priceBottom - ((value - min) / (max - min)) * L.priceH;

    this._drawGrid(ctx, L, min, max, (value) => formatPct(value, 2, true));
    this._drawTimeAxis(ctx, L, start, count, slot);
    this._drawSessions(ctx, L, start, count, slot);

    // Zero baseline.
    if (min < 0 && max > 0) {
      const y = yFor(0);
      ctx.strokeStyle = 'rgba(232,238,252,0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(L.margin.left, y);
      ctx.lineTo(L.right, y);
      ctx.stroke();
    }

    const endLabels = [];
    for (const symbol of this.symbols) {
      const seriesValues = values.get(symbol) || [];
      ctx.strokeStyle = symbolColor(symbol);
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < seriesValues.length; i += 1) {
        const value = seriesValues[i];
        if (value === null) {
          started = false;
          continue;
        }
        const x = L.margin.left + (i + 0.5) * slot;
        const y = yFor(value);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      const lastIdx = seriesValues.length - 1;
      if (lastIdx >= 0 && seriesValues[lastIdx] !== null) {
        const x = L.margin.left + (lastIdx + 0.5) * slot;
        const y = yFor(seriesValues[lastIdx]);
        // Surface ring keeps the end dot legible where lines overlap.
        ctx.fillStyle = '#0b1220';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = symbolColor(symbol);
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
        endLabels.push({ symbol, y, value: seriesValues[lastIdx] });
      }
    }

    // Direct end labels: symbol only, colour carried by a short line key.
    ctx.font = `600 9px ${MONO}`;
    ctx.textBaseline = 'middle';
    endLabels.sort((a, b) => a.y - b.y);
    let lastY = -Infinity;
    for (const label of endLabels) {
      let y = label.y;
      if (y - lastY < 11) y = lastY + 11;
      lastY = y;
      ctx.strokeStyle = symbolColor(label.symbol);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(L.right + 5, y);
      ctx.lineTo(L.right + 13, y);
      ctx.stroke();
      ctx.fillStyle = '#e8eefc';
      ctx.textAlign = 'left';
      ctx.fillText(label.symbol, L.right + 17, y + 0.5);
    }
  }

  _normalisedAt(rows, index, baseIndex = 0) {
    if (!rows || !rows.length) return null;
    const base = rows[baseIndex];
    const bar = rows[index];
    if (!base || !bar || !base.c) return null;
    return (bar.c - base.c) / base.c;
  }

  _drawGrid(ctx, L, min, max, formatter) {
    ctx.font = `500 9px ${MONO}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i += 1) {
      const ratio = i / 4;
      const y = L.priceTop + ratio * L.priceH;
      ctx.strokeStyle = 'rgba(255,255,255,0.065)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(L.margin.left, y + 0.5);
      ctx.lineTo(L.right, y + 0.5);
      ctx.stroke();
      const value = max - ratio * (max - min);
      ctx.fillStyle = STATUS.muted;
      ctx.fillText(formatter(value), L.right + 54, y);
    }
  }

  _drawTimeAxis(ctx, L, start, count, slot) {
    ctx.font = `500 9px ${MONO}`;
    ctx.fillStyle = STATUS.muted;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const step = Math.max(1, Math.ceil(count / 4));
    for (let i = 0; i < count; i += step) {
      const x = L.margin.left + (i + 0.5) * slot;
      const label = timeLabel(this.times[start + i]);
      if (!label) continue;
      ctx.fillText(label, x, L.volTop + L.volH + 5);
    }
    ctx.textAlign = 'right';
    ctx.fillText('ET', L.right, L.volTop + L.volH + 5);
  }

  _drawSessions(ctx, L, start, count, slot) {
    let lastKey = null;
    for (let i = 0; i < count; i += 1) {
      const key = dateKey(this.times[start + i]);
      if (lastKey !== null && key && key !== lastKey) {
        const x = L.margin.left + i * slot;
        ctx.strokeStyle = 'rgba(232, 238, 252, 0.13)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x + 0.5, L.priceTop);
        ctx.lineTo(x + 0.5, L.volTop + L.volH);
        ctx.stroke();
        ctx.fillStyle = 'rgba(195, 204, 221, 0.55)';
        ctx.font = `500 7px ${MONO}`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(dateLabel(this.times[start + i]).toUpperCase(), x + 4, L.priceTop + 2);
      }
      lastKey = key;
    }
  }

  _drawGuilds(ctx, width, height) {
    const agents = this.agents;
    if (!agents.length) {
      this._drawEmptyMessage(ctx, width, height, 'Waiting for the first strategies…');
      return;
    }
    const margin = { left: 38, right: 14, top: 24, bottom: 28 };
    const plotW = Math.max(20, width - margin.left - margin.right);
    const plotH = Math.max(30, height - margin.top - margin.bottom);
    const maxTrend = Math.max(...agents.map((a) => a.strategy.weights.trend || 0), 0.3);
    const maxRev = Math.max(...agents.map((a) => a.strategy.weights.reversion || 0), 0.3);
    const xMax = Math.min(0.8, Math.ceil(maxTrend * 1.18 * 20) / 20);
    const yMax = Math.min(0.8, Math.ceil(maxRev * 1.18 * 20) / 20);
    const xFor = (value) => margin.left + clamp(value / xMax, 0, 1) * plotW;
    const yFor = (value) => margin.top + plotH - clamp(value / yMax, 0, 1) * plotH;

    ctx.fillStyle = STATUS.muted;
    ctx.font = `600 8px ${MONO}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('STRATEGY FIELD', margin.left, 5);
    const gen = this.ecosystem?.generation ?? 0;
    const dominant = this.ecosystem?.dominant || 'balanced';
    ctx.textAlign = 'right';
    ctx.fillText(`GEN ${gen} · ${String(dominant).toUpperCase()}`, width - margin.right, 5);

    ctx.font = `500 7px ${MONO}`;
    ctx.textAlign = 'center';
    for (let i = 0; i <= 4; i += 1) {
      const x = margin.left + (plotW * i) / 4;
      const y = margin.top + plotH - (plotH * i) / 4;
      ctx.strokeStyle = 'rgba(255,255,255,0.055)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, margin.top);
      ctx.lineTo(x + 0.5, margin.top + plotH);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(margin.left, y + 0.5);
      ctx.lineTo(margin.left + plotW, y + 0.5);
      ctx.stroke();
      ctx.fillStyle = 'rgba(138,148,166,0.7)';
      ctx.fillText((xMax * i / 4).toFixed(2), x, margin.top + plotH + 6);
      if (i > 0) {
        ctx.textAlign = 'right';
        ctx.fillText((yMax * i / 4).toFixed(2), margin.left - 5, y + 3);
        ctx.textAlign = 'center';
      }
    }

    // Quadrant hints: bottom-right is trend-heavy, top-left is reversion-heavy.
    ctx.font = `600 6px ${MONO}`;
    ctx.fillStyle = 'rgba(138,148,166,0.34)';
    ctx.textAlign = 'right';
    ctx.fillText('MOMENTUM', margin.left + plotW - 4, margin.top + plotH - 8);
    ctx.textAlign = 'left';
    ctx.fillText('REVERSION', margin.left + 4, margin.top + 8);
    ctx.textAlign = 'right';
    ctx.fillText('HYBRID', margin.left + plotW - 4, margin.top + 8);

    const agentsByFitness = [...agents].sort(
      (a, b) => (b.strategy.fitness || 0) - (a.strategy.fitness || 0),
    );
    this._guildPoints = [];
    const placed = [];
    ctx.textBaseline = 'middle';
    for (const agent of agentsByFitness) {
      const meta = strategyMeta(agent.strategy.family);
      const x = xFor(agent.strategy.weights.trend || 0);
      const y = yFor(agent.strategy.weights.reversion || 0);
      const radius = 4 + Math.min(2, (agent.strategy.generation || 0) / 8);
      ctx.fillStyle = '#0b1220';
      ctx.beginPath();
      ctx.arc(x, y, radius + 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = meta.color;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
      this._guildPoints.push({ x, y, radius, agent });

      const label = agent.id;
      ctx.font = `600 7px ${MONO}`;
      const textW = ctx.measureText(label).width;
      const rect = { x: x + radius + 3, y: y - 5, w: textW + 2, h: 10 };
      const collides = placed.some((other) => (
        rect.x < other.x + other.w && rect.x + rect.w > other.x
        && rect.y < other.y + other.h && rect.y + rect.h > other.y
      ));
      if (!collides && rect.x + rect.w < width - 2) {
        ctx.fillStyle = 'rgba(232,238,252,0.82)';
        ctx.textAlign = 'left';
        ctx.fillText(label, rect.x, y + 0.5);
        placed.push(rect);
      }
    }

    const hovered = this._guildPoints.find((point) => point.agent.id === this.guildHover);
    if (hovered) {
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(hovered.x, hovered.y, hovered.radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.fillStyle = 'rgba(138,148,166,0.55)';
    ctx.font = `500 7px ${MONO}`;
    ctx.textAlign = 'center';
    ctx.fillText('TREND WEIGHT →', margin.left + plotW / 2, height - 7);
  }

  _drawEmptyMessage(ctx, width, height, message = 'Waiting for market data…') {
    ctx.fillStyle = STATUS.muted;
    ctx.font = `500 11px ${SANS}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(message, width / 2, height / 2);
  }

  _guildPointer(event) {
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let best = null;
    let bestDistance = 18;
    for (const point of this._guildPoints) {
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = point;
      }
    }
    this.guildHover = best ? best.agent.id : null;
    if (best) {
      this._populateGuildTooltip(best.agent, x, y);
    } else {
      this.tooltip.hidden = true;
    }
    this.dirty = true;
  }

  _populateGuildTooltip(agent, x, y) {
    const meta = strategyMeta(agent.strategy.family);
    this.tooltip.replaceChildren();
    const head = document.createElement('div');
    head.className = 'chart-tooltip-time';
    head.textContent = `${agent.id} · ${agent.name || agent.id}`;
    this.tooltip.appendChild(head);
    const grid = document.createElement('div');
    grid.className = 'chart-tooltip-grid';
    const add = (label, value) => {
      const l = document.createElement('span');
      l.className = 'tt-label';
      l.textContent = label;
      const v = document.createElement('strong');
      v.textContent = value;
      grid.append(l, v);
    };
    add('Guild', meta.label);
    add('Generation', String(agent.strategy.generation ?? 0));
    add('Fitness', formatPct(agent.strategy.fitness || 0, 2, true));
    add('Trend', `${Math.round((agent.strategy.weights.trend || 0) * 100)}%`);
    add('Reversion', `${Math.round((agent.strategy.weights.reversion || 0) * 100)}%`);
    add('Social', `${Math.round(((agent.strategy.weights.herding || 0) + (agent.strategy.weights.influence || 0) + (agent.strategy.weights.memory || 0)) * 100)}%`);
    if (agent.strategy.lastAdaptation) {
      const note = document.createElement('div');
      note.className = 'chart-tooltip-time';
      note.style.marginTop = '5px';
      note.style.marginBottom = '0';
      note.textContent = agent.strategy.lastAdaptation;
      this.tooltip.appendChild(grid);
      this.tooltip.appendChild(note);
    } else {
      this.tooltip.appendChild(grid);
    }
    const wrapRect = this.canvasWrap.getBoundingClientRect();
    const left = clamp(x + 14, 6, wrapRect.width - 206);
    const top = clamp(y - 10, 6, wrapRect.height - 150);
    this.tooltip.style.transform = `translate(${left}px, ${top}px)`;
    this.tooltip.hidden = false;
  }

  // ── hover ────────────────────────────────────────────────

  _pointerMove(event) {
    if (!this.times.length) return;
    if (this.mode === 'guilds') {
      this._guildPointer(event);
      return;
    }
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const L = this._layout(this._width, this._height);
    if (x < L.margin.left || x > L.right || y < L.priceTop || y > L.volTop + L.volH) {
      if (this.hover) {
        this.hover = null;
        this.tooltip.hidden = true;
        this.dirty = true;
      }
      return;
    }
    const count = this._visibleCount(L.plotW);
    const start = Math.max(0, this.times.length - count);
    const slot = L.plotW / Math.min(count, this.times.length - start);
    const offset = Math.floor((x - L.margin.left) / slot);
    const index = clamp(start + offset, start, this.times.length - 1);
    this.hover = { index, x, y, slot, start, count: Math.min(count, this.times.length - start) };
    this._populateTooltip(index, x, y);
    this.dirty = true;
  }

  _populateTooltip(index, x, y) {
    const time = this.times[index];
    this.tooltip.replaceChildren();
    const head = document.createElement('div');
    head.className = 'chart-tooltip-time';
    head.textContent = dateTimeLabel(time);
    this.tooltip.appendChild(head);

    if (this.mode === 'candles') {
      const rows = this.series.get(this.selected) || [];
      const bar = rows[index];
      if (!bar) {
        this.tooltip.hidden = true;
        return;
      }
      const prev = index > 0 ? rows[index - 1] : null;
      const change = prev ? (bar.c - prev.c) / prev.c : 0;
      const grid = document.createElement('div');
      grid.className = 'chart-tooltip-grid';
      const add = (label, value, cls = '') => {
        const l = document.createElement('span');
        l.className = 'tt-label';
        l.textContent = label;
        const v = document.createElement('strong');
        v.className = cls;
        v.textContent = value;
        grid.append(l, v);
      };
      add('Open', formatPrice(bar.o));
      add('High', formatPrice(bar.h));
      add('Low', formatPrice(bar.l));
      add('Close', formatPrice(bar.c));
      add('Change', formatPct(change, 2, true), change >= 0 ? 'pos' : 'neg');
      add('Volume', formatCompact(bar.v));
      add(`MA${MA_FAST}`, formatPrice(sma(rows, MA_FAST, index)));
      add(`MA${MA_SLOW}`, formatPrice(sma(rows, MA_SLOW, index)));
      this.tooltip.appendChild(grid);
    } else {
      const grid = document.createElement('div');
      grid.className = 'chart-tooltip-grid chart-tooltip-grid--compare';
      for (const symbol of this.symbols) {
        const rows = this.series.get(symbol) || [];
        const value = this._normalisedAt(rows, index, this.hover.start);
        const key = document.createElement('span');
        key.className = 'tt-key';
        key.style.background = symbolColor(symbol);
        const label = document.createElement('span');
        label.className = 'tt-label';
        label.textContent = symbol;
        const v = document.createElement('strong');
        v.className = value >= 0 ? 'pos' : 'neg';
        v.textContent = value === null ? '—' : formatPct(value, 2, true);
        grid.append(key, label, v);
      }
      this.tooltip.appendChild(grid);
    }

    const wrapRect = this.canvasWrap.getBoundingClientRect();
    const tipW = 190;
    const left = clamp(x + 14, 6, wrapRect.width - tipW - 6);
    const top = clamp(y - 10, 6, wrapRect.height - 170);
    this.tooltip.style.transform = `translate(${left}px, ${top}px)`;
    this.tooltip.hidden = false;
  }

  _drawCrosshair(ctx, width, height) {
    const L = this._layout(width, height);
    const count = this.hover.count;
    const x = L.margin.left + (this.hover.index - this.hover.start + 0.5) * this.hover.slot;
    ctx.save();
    ctx.strokeStyle = 'rgba(232,238,252,0.28)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x + 0.5, L.priceTop);
    ctx.lineTo(x + 0.5, L.volTop + L.volH);
    ctx.stroke();
    ctx.setLineDash([]);

    if (this.mode === 'candles') {
      const rows = this.series.get(this.selected) || [];
      const bar = rows[this.hover.index];
      if (bar) {
        const visible = rows.slice(this.hover.start, this.hover.start + count).filter(Boolean);
        let min = Infinity;
        let max = -Infinity;
        for (const b of visible) {
          min = Math.min(min, b.l);
          max = Math.max(max, b.h);
        }
        const pad = (max - min) * 0.08;
        min -= pad;
        max += pad;
        const y = L.priceBottom - ((bar.c - min) / (max - min)) * L.priceH;
        ctx.fillStyle = '#0b1220';
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = bar.c >= bar.o ? STATUS.good : STATUS.critical;
        ctx.beginPath();
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      for (const symbol of this.symbols) {
        const rows = this.series.get(symbol) || [];
        const value = this._normalisedAt(rows, this.hover.index, this.hover.start);
        if (value === null) continue;
        // Recompute the same y-scale used by the main pass.
        const allValues = [];
        for (const s of this.symbols) {
          const r = this.series.get(s) || [];
          for (let i = 0; i < count; i += 1) {
            const v = this._normalisedAt(r, this.hover.start + i, this.hover.start);
            if (v !== null) allValues.push(v);
          }
        }
        let min = Math.min(0, ...allValues);
        let max = Math.max(0, ...allValues);
        const pad = Math.max(0.0015, (max - min) * 0.15);
        min -= pad;
        max += pad;
        const y = L.priceBottom - ((value - min) / (max - min)) * L.priceH;
        ctx.fillStyle = '#0b1220';
        ctx.beginPath();
        ctx.arc(x, y, 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = symbolColor(symbol);
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }
}

function sma(rows, period, endIndex = null) {
  if (!rows || !rows.length) return null;
  const end = endIndex === null ? rows.length - 1 : endIndex;
  if (end < 0 || end >= rows.length) return null;
  const start = Math.max(0, end - period + 1);
  let sum = 0;
  let count = 0;
  for (let i = start; i <= end; i += 1) {
    const bar = rows[i];
    if (!bar) continue;
    sum += bar.c;
    count += 1;
  }
  if (!count) return null;
  return sum / count;
}

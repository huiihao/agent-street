// Agent inspector: accounting, positions, live signals and recent thoughts.

import {
  ACTIVITY_LABELS,
  MOOD_COLORS,
  formatMoney,
  formatPct,
  formatPrice,
  strategyMeta,
  symbolColor,
} from './utils.js';

const MAX_EQUITY_POINTS = 90;

export class AgentDetail {
  constructor(container, { initialCash = 10000, onLocate = null } = {}) {
    this.container = container;
    this.initialCash = initialCash;
    this.onLocate = onLocate;
    this.defs = new Map();
    this.states = new Map();
    this.history = new Map();
    this.currentId = null;
    this.tab = 'account';
    this.container.classList.add('agent-detail');
    this._placeholder();
  }

  reset() {
    this.states.clear();
    this.history.clear();
    this.currentId = null;
    this._placeholder();
  }

  setDefs(defs) {
    this.defs.clear();
    (defs || []).forEach((def) => this.defs.set(def.id, def));
  }

  updateStates(personas, tick = null) {
    for (const persona of personas || []) {
      this.states.set(persona.id, persona);
      const series = this.history.get(persona.id) || [];
      const last = series[series.length - 1];
      const key = tick ?? (last ? last.tick : 0);
      if (!last || last.tick !== key) {
        series.push({ tick: key, equity: persona.equity ?? this.initialCash });
        if (series.length > MAX_EQUITY_POINTS) series.shift();
        this.history.set(persona.id, series);
      }
    }
    if (this.currentId) this.render();
  }

  show(id) {
    this.currentId = id;
    if (!id) {
      this._placeholder();
      return;
    }
    this.render();
  }

  render() {
    const id = this.currentId;
    if (!id) {
      this._placeholder();
      return;
    }
    const def = this.defs.get(id) || {};
    let persona = this.states.get(id) || null;
    if (!persona) {
      if (def.id === undefined && !def.name) {
        this._placeholder();
        return;
      }
      // Before the first frame (paused / fresh page), show the static profile
      // with starting capital instead of an empty inspector.
      persona = {
        id,
        name: def.name || id,
        color: def.color || '#8a94a6',
        isObserver: Boolean(def.isObserver),
        location: 'Agent Street',
        activity: 'idle',
        mood: 'calm',
        equity: this.initialCash,
        cash: this.initialCash,
        returnPct: 0,
        realizedPnl: 0,
        unrealizedPnl: 0,
        positions: 0,
        maxDrawdown: 0,
        winRate: 0,
        totalSells: 0,
        thoughts: [],
        holdings: [],
        signals: {},
        strategy: null,
      };
    }
    const isObserver = Boolean(persona.isObserver);
    const strategy = persona.strategy;
    const scrollTop = this.container.scrollTop;
    this.container.replaceChildren();

    const header = document.createElement('div');
    header.className = 'ad-header';
    const dot = document.createElement('span');
    dot.className = 'ad-dot';
    dot.style.background = persona.color || '#8a94a6';
    const names = document.createElement('div');
    names.className = 'ad-names';
    const idLine = document.createElement('div');
    idLine.className = 'ad-id';
    idLine.textContent = isObserver ? persona.name : `${persona.id} · ${persona.name}`;
    const sub = document.createElement('div');
    sub.className = 'ad-sub';
    let subline = `${persona.location || 'Agent Street'} · ${ACTIVITY_LABELS[persona.activity] || persona.activity || 'Idle'}`;
    if (!isObserver && persona.strategy) {
      const meta = strategyMeta(persona.strategy.family);
      subline += ` · ${meta.short} GEN ${persona.strategy.generation ?? 0}`;
    }
    sub.textContent = subline;
    names.append(idLine, sub);
    header.append(dot, names);
    if (!isObserver) {
      const mood = document.createElement('span');
      mood.className = 'ad-mood';
      mood.textContent = persona.mood || 'calm';
      mood.style.color = MOOD_COLORS[persona.mood] || MOOD_COLORS.calm;
      mood.style.borderColor = `${MOOD_COLORS[persona.mood] || MOOD_COLORS.calm}55`;
      header.appendChild(mood);
    }
    if (this.onLocate) {
      const locate = document.createElement('button');
      locate.type = 'button';
      locate.className = 'ad-locate';
      locate.textContent = 'Locate';
      locate.title = 'Focus this agent on the map';
      locate.addEventListener('click', () => this.onLocate(id));
      header.appendChild(locate);
    }
    this.container.appendChild(header);

    if (def.motto) {
      const motto = document.createElement('div');
      motto.className = 'ad-motto';
      motto.textContent = `“${def.motto}”`;
      this.container.appendChild(motto);
    }
    if (def.backstory || persona.backstory) {
      const bio = document.createElement('div');
      bio.className = 'ad-bio';
      bio.textContent = def.backstory || persona.backstory;
      this.container.appendChild(bio);
    }

    if (!isObserver) {
      const hasStrategy = Boolean(strategy && strategy.weights);
      if (!hasStrategy) this.tab = 'account';
      const tabs = document.createElement('div');
      tabs.className = 'ad-tabs';
      const accountTab = document.createElement('button');
      accountTab.type = 'button';
      accountTab.className = 'ad-tab';
      accountTab.textContent = 'Account';
      const strategyTab = document.createElement('button');
      strategyTab.type = 'button';
      strategyTab.className = 'ad-tab';
      strategyTab.textContent = 'Strategy';
      strategyTab.disabled = !hasStrategy;
      accountTab.classList.toggle('is-active', this.tab === 'account');
      strategyTab.classList.toggle('is-active', this.tab === 'strategy');
      accountTab.addEventListener('click', () => {
        this.tab = 'account';
        this.render();
      });
      strategyTab.addEventListener('click', () => {
        if (!hasStrategy) return;
        this.tab = 'strategy';
        this.render();
      });
      tabs.append(accountTab, strategyTab);
      this.container.appendChild(tabs);
      if (this.tab === 'strategy' && hasStrategy) {
        this.container.appendChild(this._strategySection(strategy));
        this.container.scrollTop = 0;
        return;
      }
    }

    if (isObserver) {
      const note = document.createElement('div');
      note.className = 'ad-observer-note';
      note.textContent = 'Observer · does not trade. Publishes periodic interpretations of the system.';
      this.container.appendChild(note);
      this.container.scrollTop = scrollTop;
      return;
    }

    // Stats
    const stats = document.createElement('div');
    stats.className = 'ad-stats';
    const stat = (label, value, cls = '') => {
      const cell = document.createElement('div');
      cell.className = `ad-stat ${cls}`;
      const l = document.createElement('span');
      l.textContent = label;
      const v = document.createElement('strong');
      v.textContent = value;
      cell.append(l, v);
      stats.appendChild(cell);
    };
    stat('Equity', formatMoney(persona.equity ?? 0));
    stat('Return', formatPct(persona.returnPct || 0, 2, true), (persona.returnPct || 0) >= 0 ? 'pos' : 'neg');
    stat('Cash', formatMoney(persona.cash ?? 0, { compact: true }));
    stat('Realized', formatMoney(persona.realizedPnl ?? 0, { sign: true, compact: true }), (persona.realizedPnl || 0) >= 0 ? 'pos' : 'neg');
    stat('Unrealized', formatMoney(persona.unrealizedPnl ?? 0, { sign: true, compact: true }), (persona.unrealizedPnl || 0) >= 0 ? 'pos' : 'neg');
    stat('Positions', String(persona.positions ?? 0));
    stat(
      'Max DD',
      formatPct(persona.maxDrawdown || 0, 1, false),
      (persona.maxDrawdown || 0) < 0 ? 'neg' : '',
    );
    stat(
      'Win rate',
      persona.totalSells ? `${Math.round((persona.winRate || 0) * 100)}%` : '—',
    );
    stat('Closed', String(persona.totalSells || 0));
    this.container.appendChild(stats);

    // Equity sparkline
    const series = this.history.get(id) || [];
    if (series.length > 1) {
      const sparkWrap = document.createElement('div');
      sparkWrap.className = 'ad-spark-wrap';
      const label = document.createElement('span');
      label.className = 'ad-section-label';
      label.textContent = 'Equity';
      const canvas = document.createElement('canvas');
      canvas.className = 'ad-spark';
      sparkWrap.append(label, canvas);
      this.container.appendChild(sparkWrap);
      drawSparkline(canvas, series, this.initialCash);
    }

    // Signals
    const signals = persona.signals || {};
    const signalSymbols = Object.keys(signals);
    if (signalSymbols.length) {
      const signalWrap = document.createElement('div');
      signalWrap.className = 'ad-signals';
      const label = document.createElement('div');
      label.className = 'ad-section-label';
      label.textContent = 'Composite signal';
      signalWrap.appendChild(label);
      for (const symbol of signalSymbols) {
        const value = signals[symbol];
        const row = document.createElement('div');
        row.className = 'ad-signal';
        const sym = document.createElement('span');
        sym.className = 'ad-signal-sym';
        sym.textContent = symbol;
        const track = document.createElement('span');
        track.className = 'ad-signal-track';
        const zero = document.createElement('i');
        zero.className = 'ad-signal-zero';
        const fill = document.createElement('i');
        fill.className = value >= 0 ? 'ad-signal-fill pos' : 'ad-signal-fill neg';
        const half = Math.min(50, Math.abs(value) * 50);
        if (value >= 0) {
          fill.style.left = '50%';
          fill.style.width = `${half}%`;
        } else {
          fill.style.right = '50%';
          fill.style.width = `${half}%`;
        }
        track.append(zero, fill);
        const val = document.createElement('strong');
        val.className = value >= 0 ? 'pos' : 'neg';
        val.textContent = `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
        row.append(sym, track, val);
        signalWrap.appendChild(row);
      }
      this.container.appendChild(signalWrap);
    }

    // Holdings
    const holdings = persona.holdings || [];
    if (holdings.length) {
      const wrap = document.createElement('div');
      wrap.className = 'ad-holdings';
      const label = document.createElement('div');
      label.className = 'ad-section-label';
      label.textContent = 'Positions';
      wrap.appendChild(label);
      const table = document.createElement('div');
      table.className = 'ad-table';
      const head = document.createElement('div');
      head.className = 'ad-tr ad-th';
      for (const text of ['Symbol', 'Shares', 'Avg', 'Last', 'Value', 'P&L']) {
        const cell = document.createElement('span');
        cell.textContent = text;
        head.appendChild(cell);
      }
      table.appendChild(head);
      for (const h of holdings) {
        const row = document.createElement('div');
        row.className = 'ad-tr';
        const symbol = document.createElement('span');
        const key = document.createElement('i');
        key.className = 'ad-holding-key';
        key.style.background = symbolColor(h.symbol);
        const symText = document.createElement('span');
        symText.textContent = h.symbol;
        symbol.append(key, symText);
        const shares = document.createElement('span');
        shares.textContent = String(h.shares);
        const avg = document.createElement('span');
        avg.textContent = formatPrice(h.avgCost);
        const last = document.createElement('span');
        last.textContent = formatPrice(h.price);
        const value = document.createElement('span');
        value.textContent = formatMoney(h.marketValue, { compact: true });
        const pnl = document.createElement('span');
        pnl.className = h.unrealizedPnl >= 0 ? 'pos' : 'neg';
        pnl.textContent = formatMoney(h.unrealizedPnl, { sign: true, compact: true });
        row.append(symbol, shares, avg, last, value, pnl);
        table.appendChild(row);
      }
      wrap.appendChild(table);
      this.container.appendChild(wrap);
    }

    // Thoughts
    const thoughts = persona.thoughts || [];
    const thoughtsWrap = document.createElement('div');
    thoughtsWrap.className = 'ad-thoughts';
    const label = document.createElement('div');
    label.className = 'ad-section-label';
    label.textContent = 'Recent thoughts';
    thoughtsWrap.appendChild(label);
    if (!thoughts.length) {
      const empty = document.createElement('div');
      empty.className = 'ad-thought-empty';
      empty.textContent = 'Nothing on their mind yet.';
      thoughtsWrap.appendChild(empty);
    } else {
      for (const thought of thoughts.slice(-6)) {
        const line = document.createElement('div');
        line.className = 'ad-thought';
        line.textContent = thought;
        thoughtsWrap.appendChild(line);
      }
    }
    this.container.appendChild(thoughtsWrap);
    this.container.scrollTop = scrollTop;
  }

  _strategySection(strategy) {
    const meta = strategyMeta(strategy.family);
    const wrap = document.createElement('div');
    wrap.className = 'ad-strategy';
    const head = document.createElement('div');
    head.className = 'ad-strategy-head';
    const family = document.createElement('span');
    family.className = 'ad-family';
    family.style.borderColor = `${meta.color}66`;
    family.style.color = meta.color;
    const familyDot = document.createElement('i');
    familyDot.style.background = meta.color;
    family.append(familyDot, document.createTextNode(meta.label));
    const gen = document.createElement('span');
    gen.className = 'ad-gen';
    gen.textContent = `GEN ${strategy.generation ?? 0}`;
    const fitness = document.createElement('strong');
    fitness.className = `ad-fitness ${(strategy.fitness || 0) >= 0 ? 'pos' : 'neg'}`;
    fitness.textContent = `fitness ${formatPct(strategy.fitness || 0, 2, true)}`;
    head.append(family, gen, fitness);
    wrap.appendChild(head);

    const label = document.createElement('div');
    label.className = 'ad-section-label';
    label.textContent = 'Evolved signal weights';
    wrap.appendChild(label);
    const geneLabels = {
      trend: 'Trend', reversion: 'Reversion', rsi: 'RSI',
      herding: 'Herding', influence: 'Influence', memory: 'Memory',
    };
    for (const [gene, text] of Object.entries(geneLabels)) {
      const value = strategy.weights[gene] ?? 0;
      const row = document.createElement('div');
      row.className = 'ad-gene-row';
      const name = document.createElement('span');
      name.className = 'ad-gene-label';
      name.textContent = text;
      const track = document.createElement('span');
      track.className = 'ad-gene-track';
      const fill = document.createElement('i');
      fill.className = 'ad-gene-fill';
      fill.style.width = `${Math.min(100, Math.max(1, value * 100))}%`;
      track.appendChild(fill);
      const val = document.createElement('strong');
      val.className = 'ad-gene-value';
      val.textContent = `${Math.round(value * 100)}%`;
      row.append(name, track, val);
      wrap.appendChild(row);
    }
    const traits = strategy.traits || {};
    const chips = document.createElement('div');
    chips.className = 'ad-traits';
    for (const [gene, text] of Object.entries({
      risk: 'Risk', patience: 'Patience', contrarian: 'Contrarian', noise: 'Noise',
    })) {
      const chip = document.createElement('span');
      chip.className = 'ad-trait';
      chip.textContent = `${text} ${(traits[gene] ?? 0).toFixed(2)}`;
      chips.appendChild(chip);
    }
    wrap.appendChild(chips);
    if (strategy.lastAdaptation) {
      const note = document.createElement('div');
      note.className = 'ad-adaptation';
      note.textContent = strategy.lastAdaptation;
      wrap.appendChild(note);
    }
    return wrap;
  }

  _placeholder() {
    this.container.replaceChildren();
    const wrap = document.createElement('div');
    wrap.className = 'ad-placeholder';
    const title = document.createElement('div');
    title.className = 'ad-placeholder-title';
    title.textContent = 'Click an agent';
    const text = document.createElement('div');
    text.className = 'ad-placeholder-text';
    text.textContent = 'Inspect their book, live signals and what they have been thinking.';
    wrap.append(title, text);
    this.container.appendChild(wrap);
  }
}

function drawSparkline(canvas, series, initialCash) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(120, Math.floor(rect.width || 260));
  const height = Math.max(30, Math.floor(rect.height || 44));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const values = series.map((p) => p.equity);
  let min = Math.min(...values, initialCash);
  let max = Math.max(...values, initialCash);
  if (max - min < 1) {
    min -= 0.5;
    max += 0.5;
  }
  const pad = (max - min) * 0.12;
  min -= pad;
  max += pad;
  const xFor = (i) => 4 + (i / Math.max(1, values.length - 1)) * (width - 8);
  const yFor = (v) => height - 5 - ((v - min) / (max - min)) * (height - 10);

  const baseline = yFor(initialCash);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.setLineDash([2, 3]);
  ctx.beginPath();
  ctx.moveTo(4, baseline);
  ctx.lineTo(width - 4, baseline);
  ctx.stroke();
  ctx.setLineDash([]);

  const positive = values[values.length - 1] >= initialCash;
  ctx.strokeStyle = positive ? '#0ca30c' : '#d03b3b';
  ctx.lineWidth = 1.6;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  values.forEach((value, i) => {
    const x = xFor(i);
    const y = yFor(value);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  const lastX = xFor(values.length - 1);
  const lastY = yFor(values[values.length - 1]);
  ctx.fillStyle = '#0b1220';
  ctx.beginPath();
  ctx.arc(lastX, lastY, 3.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = positive ? '#0ca30c' : '#d03b3b';
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.2, 0, Math.PI * 2);
  ctx.fill();
}

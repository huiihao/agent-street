// P&L leaderboard as accessible DOM (not pixels): sortable, hoverable, clickable.

import { formatMoney, formatPct, strategyMeta } from './utils.js';

export class Leaderboard {
  constructor(container, { initialCash = 10000, onSelect = null } = {}) {
    this.container = container;
    this.initialCash = initialCash;
    this.onSelect = onSelect;
    this.rows = new Map();
    this.personas = [];
    this.selected = null;
    this._build();
  }

  _build() {
    this.container.classList.add('leaderboard');
    this.container.replaceChildren();

    this.summary = document.createElement('div');
    this.summary.className = 'lb-summary';
    this.summary.textContent = 'Waiting for traders…';
    this.container.appendChild(this.summary);

    this.list = document.createElement('div');
    this.list.className = 'lb-list';
    this.list.setAttribute('role', 'list');
    this.container.appendChild(this.list);
  }

  reset() {
    this.rows.forEach((row) => row.el.remove());
    this.rows.clear();
    this.personas = [];
    this.selected = null;
    this.summary.textContent = 'Waiting for traders…';
  }

  setSelected(id) {
    this.selected = id;
    for (const [rowId, row] of this.rows) {
      row.el.classList.toggle('is-selected', rowId === id);
    }
  }

  update(personas) {
    const traders = (personas || []).filter((p) => !p.isObserver);
    if (!traders.length) return;
    this.personas = traders;
    const sorted = [...traders].sort((a, b) => (b.returnPct || 0) - (a.returnPct || 0));
    const maxAbs = Math.max(0.005, ...traders.map((p) => Math.abs(p.returnPct || 0)));
    const avg = traders.reduce((sum, p) => sum + (p.returnPct || 0), 0) / traders.length;
    const positive = traders.filter((p) => (p.returnPct || 0) > 0).length;
    this.summary.textContent = `${traders.length} traders · ${positive} up · avg ${formatPct(avg, 2, true)}`;

    const live = new Set();
    sorted.forEach((persona, index) => {
      live.add(persona.id);
      let row = this.rows.get(persona.id);
      if (!row) {
        row = this._createRow(persona);
        this.rows.set(persona.id, row);
      }
      this._updateRow(row, persona, index, maxAbs);
      this.list.appendChild(row.el);
    });

    for (const [id, row] of [...this.rows]) {
      if (!live.has(id)) {
        row.el.remove();
        this.rows.delete(id);
      }
    }
  }

  _createRow(persona) {
    const el = document.createElement('div');
    el.className = 'lb-row';
    el.setAttribute('role', 'listitem');
    el.tabIndex = 0;
    el.dataset.id = persona.id;

    const rank = document.createElement('span');
    rank.className = 'lb-rank';
    const dot = document.createElement('span');
    dot.className = 'lb-dot';
    const id = document.createElement('span');
    id.className = 'lb-id';
    const name = document.createElement('span');
    name.className = 'lb-name';
    const equity = document.createElement('span');
    equity.className = 'lb-equity';
    const ret = document.createElement('span');
    ret.className = 'lb-ret';
    const bar = document.createElement('span');
    bar.className = 'lb-bar';
    const fill = document.createElement('i');
    bar.appendChild(fill);

    el.append(rank, dot, id, name, equity, ret, bar);
    const select = () => {
      this.setSelected(persona.id);
      if (this.onSelect) this.onSelect(persona.id);
    };
    el.addEventListener('click', select);
    el.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        select();
      }
    });

    return { el, rank, dot, id, name, equity, ret, fill };
  }

  _updateRow(row, persona, index, maxAbs) {
    row.el.classList.toggle('is-selected', persona.id === this.selected);
    row.el.classList.toggle('is-leader', index < 3);
    row.rank.textContent = String(index + 1);
    row.dot.style.background = persona.color || '#8a94a6';
    row.id.textContent = persona.id;
    row.id.style.color = persona.color || '#e8eefc';
    const meta = persona.strategy ? strategyMeta(persona.strategy.family) : null;
    row.name.textContent = meta
      ? `${persona.name || ''} · ${meta.short}`
      : (persona.name || '');
    row.equity.textContent = formatMoney(persona.equity ?? this.initialCash, { compact: true });
    const ret = persona.returnPct || 0;
    row.ret.textContent = formatPct(ret, 2, true);
    row.ret.classList.toggle('pos', ret >= 0);
    row.ret.classList.toggle('neg', ret < 0);

    const width = Math.min(100, (Math.abs(ret) / maxAbs) * 100);
    row.fill.style.width = `${Math.max(1, width)}%`;
    row.fill.classList.toggle('pos', ret >= 0);
    row.fill.classList.toggle('neg', ret < 0);
    const strategyTitle = meta
      ? ` · ${meta.label} gen ${persona.strategy.generation ?? 0} · fitness ${formatPct(persona.strategy.fitness || 0, 2, true)}`
      : '';
    row.el.title = `${persona.id} ${persona.name || ''} · ${formatMoney(persona.equity ?? 0)} · ${formatPct(ret, 2, true)}${strategyTitle}`;
  }
}

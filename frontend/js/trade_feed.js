// Live execution tape. A row is an agent-side fill; crosses show both sides.

import { formatMoney, formatPrice } from './utils.js';

const MAX_ROWS = 90;
const REASONS = {
  panic_sell: 'panic',
  profit_take: 'take profit',
  stop_loss: 'stop loss',
  trend_follow: 'trend',
  contrarian_buy: 'contrarian',
  contrarian_sell: 'contrarian',
  mean_reversion: 'mean reversion',
  rebalance: 'rebalance',
  test: 'manual',
};

export class TradeFeed {
  constructor(container) {
    this.container = container;
    this.container.classList.add('trade-feed-wrap');
    this.container.replaceChildren();
    this.seen = new Set();
    this.count = 0;
    this.pinned = false;

    this.list = document.createElement('div');
    this.list.className = 'trade-feed';
    this.list.setAttribute('role', 'log');
    this.list.setAttribute('aria-live', 'polite');
    this.container.appendChild(this.list);

    this.empty = document.createElement('div');
    this.empty.className = 'trade-empty';
    this.empty.textContent = 'No fills yet. The town is still finding its price.';
    this.container.appendChild(this.empty);

    this.jump = document.createElement('button');
    this.jump.type = 'button';
    this.jump.className = 'trade-jump';
    this.jump.textContent = '↓ latest';
    this.jump.hidden = true;
    this.jump.addEventListener('click', () => {
      this.list.scrollTop = this.list.scrollHeight;
      this.jump.hidden = true;
    });
    this.container.appendChild(this.jump);

    this.list.addEventListener('scroll', () => {
      const nearBottom = this.list.scrollHeight - this.list.scrollTop - this.list.clientHeight < 48;
      if (nearBottom) this.jump.hidden = true;
    });
  }

  append(trades, tick = 0) {
    if (!trades || !trades.length) return;
    this.empty.hidden = true;
    const nearBottom = this.list.scrollHeight - this.list.scrollTop - this.list.clientHeight < 48;
    let added = 0;
    for (const trade of trades) {
      const key = `${trade.id || `${tick}:${trade.persona}:${trade.side}`}:${trade.persona}`;
      if (this.seen.has(key)) continue;
      this.seen.add(key);
      this.list.appendChild(this._row(trade, trade.tick ?? tick));
      this.count += 1;
      added += 1;
    }
    while (this.list.children.length > MAX_ROWS) {
      this.list.firstElementChild.remove();
    }
    if (this.seen.size > MAX_ROWS * 4) {
      // Keep the dedupe set bounded across long runs.
      this.seen = new Set([...this.seen].slice(-MAX_ROWS * 2));
    }
    if (added && (nearBottom || this.count <= 4)) {
      this.list.scrollTop = this.list.scrollHeight;
      this.jump.hidden = true;
    } else if (added) {
      this.jump.hidden = false;
    }
  }

  _row(trade, tick) {
    const row = document.createElement('div');
    row.className = `trade-row ${trade.direction === 'BUY' ? 'is-buy' : 'is-sell'}`;

    const tickEl = document.createElement('span');
    tickEl.className = 'trade-tick';
    tickEl.textContent = `T${tick}`;

    const side = document.createElement('span');
    side.className = 'trade-side';
    side.textContent = trade.direction === 'BUY' ? 'BUY' : 'SELL';

    const body = document.createElement('span');
    body.className = 'trade-body';
    const who = document.createElement('strong');
    who.className = 'trade-who';
    who.textContent = trade.persona;
    const what = document.createElement('span');
    what.className = 'trade-what';
    what.textContent = `${trade.shares} ${trade.symbol} @ ${formatPrice(trade.price)}`;
    body.append(who, what);

    const meta = document.createElement('span');
    meta.className = 'trade-meta';
    const reason = document.createElement('span');
    reason.className = 'trade-reason';
    reason.textContent = REASONS[trade.reason] || trade.reason || 'signal';
    const counterparty = document.createElement('span');
    counterparty.className = 'trade-cp';
    counterparty.textContent = trade.counterparty === 'HOUSE' ? 'house' : `↔ ${trade.counterparty}`;
    meta.append(reason, counterparty);
    if (trade.fee) {
      const fee = document.createElement('span');
      fee.className = 'trade-fee';
      fee.textContent = `fee ${formatMoney(trade.fee, { compact: true })}`;
      meta.appendChild(fee);
    }
    if (trade.liquidity === 'cross') {
      const cross = document.createElement('span');
      cross.className = 'trade-cross';
      cross.textContent = 'cross';
      meta.appendChild(cross);
    }

    row.append(tickEl, side, body, meta);
    return row;
  }

  reset() {
    this.list.replaceChildren();
    this.seen.clear();
    this.count = 0;
    this.jump.hidden = true;
    this.empty.hidden = false;
  }
}

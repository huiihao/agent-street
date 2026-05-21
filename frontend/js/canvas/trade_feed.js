class TradeFeed {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.maxEntries = 50;
  }

  append(trades) {
    if (!trades || trades.length === 0) return;

    trades.forEach(t => {
      const entry = document.createElement('div');
      entry.className = 'trade-entry';

      const dirClass = t.direction === 'BUY' ? 'buy' : 'sell';
      const arrow = t.direction === 'BUY' ? '▲' : '▼';
      const name = t.personaName || t.persona;

      entry.innerHTML = `
        <span class="persona">[${t.persona}]</span>
        <span class="${dirClass}">${arrow} ${t.direction}</span>
        <span>${t.shares}</span>
        <span class="symbol">${t.symbol}</span>
        <span>@$${t.price.toFixed(2)}</span>
        <span style="color:#888">(${t.reason})</span>
        <span style="color:#666">vs ${t.counterparty}</span>
      `;

      this.container.prepend(entry);
    });

    // Trim old entries
    while (this.container.children.length > this.maxEntries) {
      this.container.lastChild.remove();
    }
  }
}

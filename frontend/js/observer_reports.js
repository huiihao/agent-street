// Four observer cards, each showing its latest dispatch.

const OBSERVERS = [
  { id: 'physicist', icon: '🔭', name: 'Physicist', color: '#7B9ECF', domain: 'statistical physics' },
  { id: 'mathematician', icon: '📐', name: 'Mathematician', color: '#9E7BCF', domain: 'graph theory' },
  { id: 'social_engineer', icon: '🧩', name: 'Social Engineer', color: '#7FC8B0', domain: 'social systems' },
  { id: 'mystic', icon: '🔮', name: 'Mystic', color: '#CF7BAE', domain: 'cosmic resonance' },
];

export class ObserverReports {
  constructor(container) {
    this.container = container;
    this.cards = new Map();
    this.container.classList.add('observer-reports');
    this._build();
  }

  _build() {
    this.container.replaceChildren();
    for (const observer of OBSERVERS) {
      const card = document.createElement('article');
      card.className = 'obs-card';
      card.style.setProperty('--obs-color', observer.color);

      const head = document.createElement('header');
      head.className = 'obs-head';
      const icon = document.createElement('span');
      icon.className = 'obs-icon';
      icon.textContent = observer.icon;
      const title = document.createElement('div');
      title.className = 'obs-title';
      const name = document.createElement('strong');
      name.textContent = observer.name;
      const domain = document.createElement('span');
      domain.textContent = observer.domain;
      title.append(name, domain);
      const tick = document.createElement('span');
      tick.className = 'obs-tick';
      tick.textContent = '—';
      head.append(icon, title, tick);
      card.appendChild(head);

      const reportTitle = document.createElement('div');
      reportTitle.className = 'obs-report-title';
      reportTitle.textContent = 'Awaiting first dispatch…';
      card.appendChild(reportTitle);

      const content = document.createElement('div');
      content.className = 'obs-content';
      content.textContent = 'The observer is still watching the town.';
      card.appendChild(content);

      const footer = document.createElement('footer');
      footer.className = 'obs-foot';
      const conf = document.createElement('span');
      conf.className = 'obs-conf';
      const bar = document.createElement('span');
      bar.className = 'obs-conf-track';
      const fill = document.createElement('i');
      fill.style.width = '0%';
      bar.appendChild(fill);
      const pct = document.createElement('span');
      pct.textContent = '—';
      conf.append('confidence', bar, pct);
      footer.appendChild(conf);
      card.appendChild(footer);

      this.cards.set(observer.id, {
        card, tick, reportTitle, content, fill, pct, lastTick: -1,
      });
      this.container.appendChild(card);
    }
  }

  append(reports) {
    if (!reports || !reports.length) return;
    for (const report of reports) {
      const card = this.cards.get(report.observerId);
      if (!card) continue;
      if (report.tick === card.lastTick) continue;
      card.lastTick = report.tick;
      card.tick.textContent = `T${report.tick}`;
      card.reportTitle.textContent = report.title || 'Dispatch';
      card.content.textContent = report.content || '';
      const confidence = Math.max(0, Math.min(1, report.confidence ?? 0));
      card.fill.style.width = `${Math.round(confidence * 100)}%`;
      card.fill.classList.toggle('low', confidence < 0.4);
      card.pct.textContent = `${Math.round(confidence * 100)}%`;
      card.card.classList.remove('is-new');
      // Restart the flash animation without forcing a layout on every report.
      void card.card.offsetWidth;
      card.card.classList.add('is-new');
    }
  }

  reset() {
    for (const card of this.cards.values()) {
      card.lastTick = -1;
      card.tick.textContent = '—';
      card.reportTitle.textContent = 'Awaiting first dispatch…';
      card.content.textContent = 'The observer is still watching the town.';
      card.fill.style.width = '0%';
      card.pct.textContent = '—';
      card.card.classList.remove('is-new');
    }
  }
}

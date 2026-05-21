// Observer Reports — renders reports from Physicist, Mathematician, Mystic

class ObserverReports {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.reports = []; // newest first
  }

  append(reports) {
    if (!reports || reports.length === 0) return;

    reports.forEach(r => {
      this.reports.unshift(r);
    });

    // Keep last 30
    if (this.reports.length > 30) {
      this.reports = this.reports.slice(0, 30);
    }

    this.render();
  }

  render() {
    if (this.reports.length === 0) return;

    const obsIcons = {
      physicist: '🔭',
      mathematician: '📐',
      mystic: '🔮',
    };

    const obsNames = {
      physicist: 'Physicist',
      mathematician: 'Mathematician',
      mystic: 'Mystic',
    };

    const obsColors = {
      physicist: '#7B9ECF',
      mathematician: '#9E7BCF',
      mystic: '#CF7BAE',
    };

    this.container.innerHTML = this.reports.slice(0, 5).map(r => {
      const icon = obsIcons[r.observerId] || '•';
      const name = obsNames[r.observerId] || r.observerId;
      const color = obsColors[r.observerId] || '#888';
      const confidenceBar = this._confidenceBar(r.confidence || 0.5, r.observerId);

      return `
        <div class="obs-report" style="border-left: 3px solid ${color}">
          <div class="obs-header">
            <span class="obs-icon">${icon}</span>
            <span class="obs-name" style="color:${color}">${name}</span>
            <span class="obs-tick">T+${r.tick}</span>
            ${confidenceBar}
          </div>
          <div class="obs-title">${this._escape(r.title)}</div>
          <div class="obs-content">${this._escape(r.content)}</div>
        </div>
      `;
    }).join('');
  }

  _confidenceBar(confidence, obsId) {
    const pct = Math.round(confidence * 100);
    const color = obsId === 'mystic'
      ? (confidence > 0.3 ? '#f0a040' : '#666')
      : (confidence > 0.7 ? '#4ecca3' : '#f0c040');
    const stars = obsId === 'mystic'
      ? this._mysticStars(confidence)
      : '';
    return `<span class="obs-confidence" style="color:${color}">${stars}${pct}% conf</span>`;
  }

  _mysticStars(confidence) {
    const n = Math.round(confidence * 5);
    return '⭐'.repeat(n) + '·'.repeat(5 - n) + ' ';
  }

  _escape(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

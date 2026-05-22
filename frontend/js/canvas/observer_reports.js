// Observer Reports — side-by-side layout, newest report per observer

class ObserverReports {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.latest = {}; // observerId -> report
  }

  append(reports) {
    if (!reports || reports.length === 0) return;
    for (const r of reports) {
      this.latest[r.observerId] = r;
    }
    this.render();
  }

  render() {
    const icons = { physicist: '🔭', mathematician: '📐', mystic: '🔮' };
    const names = { physicist: 'Physicist', mathematician: 'Mathematician', mystic: 'Mystic' };
    const colors = { physicist: '#7B9ECF', mathematician: '#9E7BCF', mystic: '#CF7BAE' };
    const order = ['physicist', 'mathematician', 'mystic'];

    let html = '';
    for (const oid of order) {
      const r = this.latest[oid];
      if (!r) continue;

      html += `
        <div class="obs-report" style="border-top-color:${colors[oid]}">
          <div class="obs-header">
            <span class="obs-icon">${icons[oid]}</span>
            <span class="obs-name" style="color:${colors[oid]}">${names[oid]}</span>
            <span class="obs-tick">T+${r.tick}</span>
            <span class="obs-confidence" style="color:${r.confidence > 0.5 ? '#4ecca3' : '#888'}">${Math.round(r.confidence*100)}%</span>
          </div>
          <div class="obs-title">${this._esc(r.title)}</div>
          <div class="obs-content">${this._esc(r.content)}</div>
        </div>
      `;
    }

    if (!html) {
      html = '<div class="obs-placeholder">Observers watching... first report at T+0</div>';
    }

    this.container.innerHTML = html;
  }

  _esc(t) {
    if (!t) return '';
    return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
}

class ObserverReports {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.latest = {};
    this._recvCount = 0;
  }

  append(reports) {
    if (!reports || reports.length === 0) return;
    this._recvCount += reports.length;
    for (const r of reports) {
      if (r && r.observerId) {
        this.latest[r.observerId] = r;
      }
    }
    this.render();
  }

  render() {
    const icons = { physicist: '🔭', mathematician: '📐', mystic: '🔮' };
    const names = { physicist: 'Physicist', mathematician: 'Mathematician', mystic: 'Mystic' };
    const colors = { physicist: '#7B9ECF', mathematician: '#9E7BCF', mystic: '#CF7BAE' };
    const order = ['physicist', 'mathematician', 'mystic'];

    try {
      let html = '';
      for (const oid of order) {
        const r = this.latest[oid];
        if (!r) continue;
        html +=
          '<div class="obs-report" style="border-top-color:' + (colors[oid] || '#888') + '">' +
            '<div class="obs-header">' +
              '<span class="obs-icon">' + (icons[oid] || '') + '</span>' +
              '<span class="obs-name" style="color:' + (colors[oid] || '#888') + '">' + (names[oid] || oid) + '</span>' +
              '<span class="obs-tick">T+' + (r.tick || 0) + '</span>' +
              '<span class="obs-confidence">' + Math.round((r.confidence || 0) * 100) + '%</span>' +
            '</div>' +
            '<div class="obs-title">' + this._esc(r.title) + '</div>' +
            '<div class="obs-content">' + this._esc(r.content) + '</div>' +
          '</div>';
      }
      if (!html) {
        html = '<div class="obs-placeholder">Waiting for reports... (rcvd: ' + this._recvCount + ')</div>';
      }
      this.container.innerHTML = html;
    } catch(e) {
      this.container.innerHTML = '<div class="obs-placeholder" style="color:red">ERR: ' + e.message + '</div>';
    }
  }

  _esc(t) {
    if (!t) return '';
    return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
}

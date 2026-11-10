// Rulebook dialog: edit config/interaction_rules.json through the rules API.
// The controls view is a convenience layer over the same JSON document; the
// raw view is the escape hatch for routines, templates and agent overrides.

const RULES_URL = '/api/interaction/rules';
const LLM_URL = '/api/llm/status';

const clone = (value) => JSON.parse(JSON.stringify(value));
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function getPath(root, path) {
  return path.split('.').reduce((node, key) => (
    node && typeof node === 'object' ? node[key] : undefined
  ), root);
}

function setPath(root, path, value) {
  const parts = path.split('.');
  let node = root;
  for (const part of parts.slice(0, -1)) {
    if (!isObject(node[part])) node[part] = {};
    node = node[part];
  }
  node[parts.at(-1)] = value;
}

async function requestJSON(url, options = {}, timeout = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { cache: 'no-store', ...options, signal: controller.signal });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.detail || `${url} -> ${response.status}`);
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export class RulesPanel {
  constructor({ trigger, onToast } = {}) {
    this.trigger = trigger || document.getElementById('btn-rules');
    this.onToast = onToast || (() => {});
    this.overlay = document.getElementById('rules-overlay');
    if (!this.overlay) return;

    this.panel = document.getElementById('rules-panel');
    this.body = document.getElementById('rules-body');
    this.loadingEl = document.getElementById('rules-loading');
    this.errorEl = document.getElementById('rules-error');
    this.errorText = document.getElementById('rules-error-text');
    this.retryBtn = document.getElementById('rules-retry');
    this.controlsView = document.getElementById('rules-view-controls');
    this.jsonView = document.getElementById('rules-view-json');
    this.jsonEditor = document.getElementById('rules-json');
    this.jsonState = document.getElementById('rules-json-state');
    this.formatBtn = document.getElementById('rules-format');
    this.closeBtn = document.getElementById('rules-close');
    this.dirtyBadge = document.getElementById('rules-dirty');
    this.statusEl = document.getElementById('rules-status');
    this.saveBtn = document.getElementById('rules-save');
    this.resetBtn = document.getElementById('rules-reset');
    this.confirmEl = document.getElementById('rules-confirm');
    this.confirmText = document.getElementById('rules-confirm-text');
    this.confirmOk = document.getElementById('rules-confirm-ok');
    this.confirmCancel = document.getElementById('rules-confirm-cancel');
    this.sourceEl = document.getElementById('rules-source');
    this.llmState = document.getElementById('rules-llm-state');
    this.llmDetail = document.getElementById('rules-llm-detail');
    this.llmMeta = document.getElementById('rules-llm-meta');
    this.llmFill = document.getElementById('rules-llm-fill');
    this.tabs = [...this.overlay.querySelectorAll('[data-rules-tab]')];
    this.views = {
      controls: this.controlsView,
      json: this.jsonView,
    };

    this.state = {
      open: false,
      loaded: false,
      loading: false,
      saving: false,
      dirty: false,
      tab: 'controls',
      rules: null,
      baseline: null,
      source: '',
      llm: null,
      jsonValid: true,
      jsonError: '',
      pending: null,
      lastFocus: null,
      closeTimer: null,
    };

    this.bind();
    this.updateJsonStatus();
    this.updateDirty();
  }

  // ── events ─────────────────────────────────────────────────

  bind() {
    this.trigger?.addEventListener('click', () => this.open());
    this.closeBtn?.addEventListener('click', () => this.requestClose());
    this.overlay.querySelectorAll('[data-rules-close]').forEach((node) => {
      node.addEventListener('click', () => this.requestClose());
    });
    this.overlay.addEventListener('click', (event) => this.closeConfirmOnBackdrop(event));
    this.tabs.forEach((tab) => {
      tab.addEventListener('click', () => this.switchTab(tab.dataset.rulesTab));
    });

    this.saveBtn?.addEventListener('click', () => this.save());
    this.resetBtn?.addEventListener('click', () => this.requestReset());
    this.formatBtn?.addEventListener('click', () => this.formatRaw());
    this.retryBtn?.addEventListener('click', () => this.load());
    this.confirmCancel?.addEventListener('click', () => this.hideConfirm());
    this.confirmOk?.addEventListener('click', () => this.confirmPending());

    this.controlsView?.addEventListener('input', (event) => {
      const input = event.target.closest?.('[data-rule-path]');
      if (input) this.onFieldInput(input);
    });

    this.jsonEditor?.addEventListener('input', () => this.onRawInput());

    document.addEventListener('keydown', (event) => this.onKeydown(event), true);
  }

  closeConfirmOnBackdrop(event) {
    if (event.target === this.overlay) this.requestClose();
  }

  // ── open / close ───────────────────────────────────────────

  open() {
    if (this.state.open) return;
    this.state.open = true;
    this.state.lastFocus = document.activeElement;
    clearTimeout(this.state.closeTimer);
    this.hideConfirm();
    this.overlay.hidden = false;
    document.body.classList.add('rules-open');
    document.querySelector('.app')?.setAttribute('inert', '');
    requestAnimationFrame(() => this.overlay.classList.add('is-open'));
    this.state.tab = 'controls';
    this.load();
  }

  requestClose() {
    if (this.state.saving) return;
    if (this.state.dirty) {
      this.showConfirm('close');
      return;
    }
    this.close();
  }

  close() {
    this.state.open = false;
    this.hideConfirm();
    this.overlay.classList.remove('is-open');
    document.body.classList.remove('rules-open');
    document.querySelector('.app')?.removeAttribute('inert');
    this.state.closeTimer = setTimeout(() => {
      this.overlay.hidden = true;
    }, 260);
    if (this.state.lastFocus?.focus) this.state.lastFocus.focus();
  }

  // ── data ───────────────────────────────────────────────────

  async load() {
    this.state.loading = true;
    this.state.loaded = false;
    this.state.jsonValid = true;
    this.state.jsonError = '';
    this.setLoading(true);
    this.setStatus('Loading the rulebook…');
    try {
      const [rulesData, llmData] = await Promise.all([
        requestJSON(RULES_URL),
        requestJSON(LLM_URL).catch(() => null),
      ]);
      if (!isObject(rulesData?.rules)) throw new Error('Rules API returned no rule object.');
      this.state.rules = clone(rulesData.rules);
      this.state.baseline = clone(rulesData.rules);
      this.state.source = rulesData.source || '';
      this.state.llm = llmData;
      this.state.dirty = false;
      this.state.loaded = true;
      this.state.loading = false;
      this.setLoading(false);
      this.renderAll();
      this.setStatus('Synced with rulebook');
      requestAnimationFrame(() => this.closeBtn?.focus());
    } catch (error) {
      this.state.loading = false;
      this.state.loaded = false;
      this.setLoading(false);
      this.showError(error);
      this.closeBtn?.focus();
    }
  }

  setLoading(loading) {
    this.loadingEl.hidden = !loading;
    this.errorEl.hidden = true;
    if (loading) {
      this.controlsView.hidden = true;
      this.jsonView.hidden = true;
    }
    this.saveBtn.disabled = true;
    this.resetBtn.disabled = true;
    this.panel.setAttribute('aria-busy', String(loading));
  }

  showError(error) {
    this.loadingEl.hidden = true;
    this.controlsView.hidden = true;
    this.jsonView.hidden = true;
    this.errorEl.hidden = false;
    this.errorText.textContent = error?.message || 'The rules API did not respond.';
    this.setStatus('Could not load the rulebook', 'error');
    this.saveBtn.disabled = true;
    this.resetBtn.disabled = true;
  }

  renderAll() {
    this.renderSource();
    this.renderForm();
    this.syncRawText();
    this.renderLLM();
    this.renderTab(this.state.tab, { focus: false });
    this.updateJsonStatus();
    this.updateDirty();
  }

  renderSource() {
    const raw = String(this.state.source || 'config/interaction_rules.json');
    const normalized = raw.replace(/\\/g, '/');
    const index = normalized.lastIndexOf('config/');
    this.sourceEl.textContent = index >= 0 ? normalized.slice(index) : normalized;
    this.sourceEl.title = raw;
  }

  // ── controls form ──────────────────────────────────────────

  get formInputs() {
    return [...this.controlsView.querySelectorAll('[data-rule-path]')];
  }

  renderForm() {
    for (const input of this.formInputs) {
      const path = input.dataset.rulePath;
      const value = getPath(this.state.rules, path);
      const scale = Number(input.dataset.ruleScale || 1);
      input.classList.remove('is-invalid');
      input.removeAttribute('aria-invalid');
      if (value === undefined || value === null) {
        input.value = '';
        continue;
      }
      let display = Number(value) * scale;
      if (input.dataset.ruleType === 'int' || input.type === 'range') {
        display = Math.round(display);
      } else {
        const step = Number(input.step);
        const decimals = step > 0 && step < 1 ? Math.max(0, Math.ceil(-Math.log10(step))) : 2;
        display = Number(display.toFixed(decimals));
      }
      input.value = String(display);
      if (input.type === 'range') this.paintRange(input);
    }
    this.updateOutputs();
  }

  updateOutputs() {
    for (const output of this.controlsView.querySelectorAll('[data-rule-output]')) {
      const path = output.dataset.ruleOutput;
      const input = this.controlsView.querySelector(`[data-rule-path="${path}"]`);
      const value = getPath(this.state.rules, path);
      const scale = Number(input?.dataset.ruleScale || 1);
      output.textContent = value === undefined || value === null
        ? '—'
        : `${Math.round(Number(value) * scale)}%`;
    }
  }

  paintRange(input) {
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const value = Number(input.value || 0);
    const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;
    input.style.setProperty('--pct', `${Math.max(0, Math.min(100, pct))}%`);
  }

  onFieldInput(input) {
    const path = input.dataset.rulePath;
    if (!path) return;
    if (input.value.trim() === '') {
      input.classList.add('is-invalid');
      input.setAttribute('aria-invalid', 'true');
      this.refreshSaveState();
      this.setStatus('A field is empty — fill it before saving.', 'error');
      return;
    }
    const raw = Number(input.value);
    if (!Number.isFinite(raw)) {
      input.classList.add('is-invalid');
      input.setAttribute('aria-invalid', 'true');
      this.refreshSaveState();
      this.setStatus('A field contains an invalid number.', 'error');
      return;
    }
    let value = raw / Number(input.dataset.ruleScale || 1);
    if (input.dataset.ruleType === 'int') value = Math.round(value);
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');
    setPath(this.state.rules, path, value);
    if (input.type === 'range') this.paintRange(input);
    this.updateOutputs();
    this.state.jsonValid = true;
    this.state.jsonError = '';
    this.syncRawText();
    this.updateJsonStatus();
    this.updateDirty();
  }

  isFormValid() {
    return this.formInputs.every((input) => (
      input.value.trim() !== '' && input.checkValidity()
    ));
  }

  // ── raw JSON ───────────────────────────────────────────────

  syncRawText() {
    if (!this.state.rules) return;
    this.jsonEditor.value = JSON.stringify(this.state.rules, null, 2);
    this.jsonEditor.scrollTop = 0;
  }

  onRawInput() {
    const text = this.jsonEditor.value;
    try {
      const parsed = JSON.parse(text);
      if (!isObject(parsed)) throw new Error('The rulebook must be a JSON object.');
      this.state.rules = parsed;
      this.state.jsonValid = true;
      this.state.jsonError = '';
      this.renderForm();
      this.updateJsonStatus();
      this.updateDirty();
    } catch (error) {
      this.state.jsonValid = false;
      this.state.jsonError = error?.message || 'Invalid JSON.';
      this.updateJsonStatus();
      this.refreshSaveState();
      this.setStatus('Invalid JSON — fix it before saving.', 'error');
    }
  }

  formatRaw() {
    try {
      const parsed = JSON.parse(this.jsonEditor.value);
      if (!isObject(parsed)) throw new Error('The rulebook must be a JSON object.');
      this.state.rules = parsed;
      this.state.jsonValid = true;
      this.state.jsonError = '';
      this.syncRawText();
      this.renderForm();
      this.updateJsonStatus();
      this.updateDirty();
      this.setStatus('JSON formatted.');
    } catch (error) {
      this.state.jsonValid = false;
      this.state.jsonError = error?.message || 'Invalid JSON.';
      this.updateJsonStatus();
      this.refreshSaveState();
      this.setStatus('Cannot format invalid JSON.', 'error');
    }
  }

  updateJsonStatus() {
    this.jsonState.classList.toggle('is-invalid', !this.state.jsonValid);
    this.jsonState.title = this.state.jsonValid ? 'The rulebook parses cleanly.' : this.state.jsonError;
    this.jsonState.innerHTML = `<i></i>${this.state.jsonValid ? 'Valid JSON' : 'Invalid JSON'}`;
  }

  // ── tabs ───────────────────────────────────────────────────

  switchTab(tab, { focus = true } = {}) {
    if (!this.state.loaded) return;
    if (tab === 'controls' && !this.state.jsonValid) {
      this.setStatus('Fix the JSON before leaving the raw editor.', 'error');
      this.jsonEditor.focus();
      return;
    }
    this.renderTab(tab, { focus });
  }

  renderTab(tab, { focus = true } = {}) {
    this.state.tab = tab === 'json' ? 'json' : 'controls';
    for (const button of this.tabs) {
      const active = button.dataset.rulesTab === this.state.tab;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    }
    this.controlsView.hidden = this.state.tab !== 'controls';
    this.jsonView.hidden = this.state.tab !== 'json';
    if (this.state.tab === 'json') {
      this.syncRawText();
      if (focus) {
        this.jsonEditor.focus();
        this.jsonEditor.setSelectionRange(0, 0);
        this.jsonEditor.scrollTop = 0;
      }
    } else if (focus) {
      this.controlsView.querySelector('[data-rule-path]')?.focus();
    }
  }

  // ── save / reset ───────────────────────────────────────────

  updateDirty() {
    if (!this.state.rules || !this.state.baseline) {
      this.state.dirty = false;
      this.refreshSaveState();
      return;
    }
    this.state.dirty = JSON.stringify(this.state.rules) !== JSON.stringify(this.state.baseline);
    this.dirtyBadge.hidden = !this.state.dirty;
    this.refreshSaveState();
    if (this.state.saving || this.state.loading) return;
    if (!this.state.jsonValid) {
      this.setStatus('Invalid JSON — fix it before saving.', 'error');
    } else if (!this.isFormValid()) {
      this.setStatus('A field is empty or out of range.', 'error');
    } else if (this.state.dirty) {
      this.setStatus('Unsaved changes');
    } else {
      this.setStatus('Synced with rulebook');
    }
  }

  refreshSaveState() {
    const canSave = Boolean(
      this.state.loaded
      && this.state.dirty
      && this.state.jsonValid
      && !this.state.loading
      && !this.state.saving
      && this.isFormValid()
    );
    this.saveBtn.disabled = !canSave;
    this.resetBtn.disabled = this.state.loading || this.state.saving;
    this.dirtyBadge.hidden = !this.state.dirty;
  }

  async save() {
    if (this.saveBtn.disabled) return;
    if (!this.state.jsonValid) {
      this.switchTab('json');
      return;
    }
    if (!this.isFormValid()) {
      this.switchTab('controls');
      this.controlsView.querySelector('input:invalid')?.focus();
      return;
    }
    this.state.saving = true;
    this.saveBtn.textContent = 'Saving…';
    this.refreshSaveState();
    this.setStatus('Saving rulebook…');
    try {
      const data = await requestJSON(RULES_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.state.rules),
      });
      this.state.rules = clone(data.rules);
      this.state.baseline = clone(data.rules);
      this.state.source = data.source || this.state.source;
      this.state.dirty = false;
      this.state.jsonValid = true;
      this.state.jsonError = '';
      this.renderAll();
      this.setStatus(data.note ? 'Saved · routine changes apply on reset' : 'Synced with rulebook');
      this.onToast(data.note || 'Rulebook saved.', 'info', 4500);
    } catch (error) {
      this.setStatus(error?.message || 'Save failed.', 'error');
      this.onToast(error?.message || 'Could not save the rulebook.', 'error', 6000);
    } finally {
      this.state.saving = false;
      this.saveBtn.textContent = 'Save rules';
      this.refreshSaveState();
    }
  }

  requestReset() {
    this.showConfirm('reset');
  }

  async performReset() {
    this.state.saving = true;
    this.refreshSaveState();
    this.setStatus('Resetting to defaults…');
    try {
      const data = await requestJSON(`${RULES_URL}/reset`, { method: 'POST' });
      this.state.rules = clone(data.rules);
      this.state.baseline = clone(data.rules);
      this.state.source = data.source || this.state.source;
      this.state.dirty = false;
      this.state.jsonValid = true;
      this.state.jsonError = '';
      this.renderAll();
      this.setStatus('Factory defaults restored');
      this.onToast('Rulebook reset to defaults.', 'info', 4500);
    } catch (error) {
      this.setStatus(error?.message || 'Reset failed.', 'error');
      this.onToast(error?.message || 'Could not reset the rulebook.', 'error', 6000);
    } finally {
      this.state.saving = false;
      this.refreshSaveState();
    }
  }

  // ── confirmation / modal mechanics ─────────────────────────

  showConfirm(kind) {
    this.state.pending = kind;
    if (kind === 'reset') {
      this.confirmText.textContent = 'Reset to factory defaults? This deletes the saved rulebook file and cannot be undone.';
      this.confirmOk.textContent = 'Reset defaults';
    } else {
      this.confirmText.textContent = 'Discard unsaved rule changes?';
      this.confirmOk.textContent = 'Discard';
    }
    this.confirmEl.hidden = false;
    this.confirmCancel?.focus();
  }

  hideConfirm() {
    this.state.pending = null;
    this.confirmEl.hidden = true;
  }

  confirmPending() {
    const pending = this.state.pending;
    this.hideConfirm();
    if (pending === 'close') this.close();
    else if (pending === 'reset') this.performReset();
  }

  // ── LLM status ─────────────────────────────────────────────

  renderLLM() {
    const llm = this.state.llm;
    this.llmState.className = 'rules-llm-state';
    if (!llm) {
      this.llmState.classList.add('is-off');
      this.llmState.textContent = 'unknown';
      this.llmDetail.textContent = 'Status unavailable.';
      this.llmMeta.textContent = 'Configured by environment';
      this.llmFill.style.width = '0%';
      return;
    }
    const enabled = Boolean(llm.enabled);
    const available = Boolean(llm.available);
    const maxCalls = Number(llm.maxCallsPerRun || 0);
    const calls = Number(llm.calls || 0);
    const remaining = llm.remainingCalls;
    const failures = Number(llm.failures || 0);
    if (!enabled) {
      this.llmState.classList.add('is-off');
      this.llmState.textContent = 'off';
      this.llmDetail.textContent = 'Rule-only · no API spend.';
      this.llmMeta.textContent = 'Set LLM_ENABLED to opt in';
      this.llmFill.style.width = '0%';
      return;
    }
    if (!available) {
      this.llmState.classList.add('is-wait');
      this.llmState.textContent = 'waiting';
      this.llmDetail.textContent = `${llm.provider || 'provider'} · ${llm.model || 'model'}`;
      this.llmMeta.textContent = 'Key or endpoint missing';
      this.llmFill.style.width = '0%';
      return;
    }
    this.llmState.classList.add('is-ready');
    this.llmState.textContent = 'ready';
    this.llmDetail.textContent = `${llm.mode || 'all'} · ${llm.provider || 'provider'}/${llm.model || 'model'}`;
    const remainingLabel = maxCalls ? `${Math.max(0, remaining ?? maxCalls - calls)} left` : 'unlimited';
    this.llmMeta.textContent = `${calls} calls · ${remainingLabel}${failures ? ` · ${failures} fallback${failures === 1 ? '' : 's'}` : ''}`;
    this.llmFill.style.width = maxCalls ? `${Math.min(100, (calls / maxCalls) * 100)}%` : '0%';
  }

  // ── status / keyboard ──────────────────────────────────────

  setStatus(text, kind = '') {
    this.statusEl.className = `rules-status${kind ? ` is-${kind}` : ''}`;
    this.statusEl.textContent = text;
  }

  onKeydown(event) {
    if (!this.state.open) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      if (!this.confirmEl.hidden) this.hideConfirm();
      else this.requestClose();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      event.stopPropagation();
      this.save();
      return;
    }
    if (event.key === 'Tab') this.trapFocus(event);
  }

  trapFocus(event) {
    const nodes = [...this.panel.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
    )].filter((node) => node.offsetParent !== null);
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

// Application controller: bootstrap -> WebSocket -> render.

import { AgentDetail } from './agent_detail.js';
import { Leaderboard } from './leaderboard.js';
import { MarketChart } from './market_chart.js';
import { ObserverReports } from './observer_reports.js';
import { Town3D } from './town3d.js';
import { TradeFeed } from './trade_feed.js';
import { WSClient } from './ws_client.js';
import {
  dateTimeLabel,
  formatMoney,
  formatPct,
} from './utils.js';

const $ = (id) => document.getElementById(id);
const SPEEDS = [1, 2, 5, 20];

const els = {
  townContainer: $('town-container'),
  townLoading: $('town-loading'),
  townOverlay: $('town-overlay'),
  townSub: $('town-sub'),
  marketChart: $('market-chart'),
  marketSub: $('market-sub'),
  leaderboard: $('leaderboard'),
  lbAvg: $('lb-avg'),
  agentDetail: $('agent-detail'),
  observerReports: $('observer-reports'),
  tradeFeed: $('trade-feed'),
  sourcePill: $('source-pill'),
  sourceText: $('source-text'),
  marketTime: $('market-time'),
  tickPill: $('tick-pill'),
  regimePill: $('regime-pill'),
  statEquity: $('stat-equity'),
  statEquitySub: $('stat-equity-sub'),
  statSentiment: $('stat-sentiment'),
  sentimentFill: $('sentiment-fill'),
  statBreadth: $('stat-breadth'),
  statBreadthSub: $('stat-breadth-sub'),
  statFees: $('stat-fees'),
  statTrades: $('stat-trades'),
  btnStart: $('btn-start'),
  btnStop: $('btn-stop'),
  btnReset: $('btn-reset'),
  btnStartOverlay: $('btn-start-overlay'),
  speedBtn: $('speed-btn'),
  btnCamera: $('btn-camera'),
  btnRotate: $('btn-rotate'),
  btnLabels: $('btn-labels'),
  conn: document.querySelector('.status-conn'),
  connDot: $('conn-dot'),
  connText: $('conn-text'),
  barIndex: $('status-bar-index'),
  barProgress: $('bar-progress'),
  statusSource: $('status-source'),
  statusWarning: $('status-warning'),
  toasts: $('toasts'),
};

const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
const ws = new WSClient(wsUrl);

let bootstrap = null;
let symbols = [];
let initialCash = 10000;
let town = null;
let chart = null;
let leaderboard = null;
let tradeFeed = null;
let agentDetail = null;
let observers = null;

let lastTick = -1;
let lastFrame = null;
let runningState = false;
let currentSpeed = readSpeed();
let warnedSynthetic = false;
let warnedStale = false;
let hadConnection = false;
let bootAttempts = 0;

init();

function init() {
  bindControls();
  boot();
  ws.on('hello', (data) => {
    if (data?.status) applyStatus(data.status);
    if (data?.frame) applyFrame(data.frame, { force: true });
    if (data?.observerReports) observers?.append(data.observerReports);
    if (data?.recentTrades) tradeFeed?.append(data.recentTrades, data?.status?.tick || 0);
  });
  ws.on('tick', (frame) => applyFrame(frame));
  ws.on('sim_state', (data) => {
    updateSimState(Boolean(data?.running), data?.speed);
  });
  ws.on('reset', () => handleReset());
  ws.on('error', (data) => showToast(data?.message || 'The server rejected that action.', 'error'));
  ws.on('status', (data) => updateConnection(data));
  ws.connect();
}

// ── bootstrap ────────────────────────────────────────────────

async function boot(showLoading = true) {
  if (showLoading) els.townLoading.hidden = false;
  try {
    const data = await fetchJSON('/api/bootstrap', 120000);
    bootAttempts = 0;
    applyBootstrap(data);
    if (showLoading) els.townLoading.hidden = true;
    els.townContainer.classList.add('is-loaded');
  } catch (error) {
    console.error(error);
    bootAttempts += 1;
    if (bootAttempts <= 4) {
      els.townLoading.querySelector('span:last-child').textContent = `Loading market data… retry ${bootAttempts}`;
      setTimeout(boot, 1500 * bootAttempts);
    } else {
      els.townLoading.querySelector('span:last-child').textContent = 'Could not load market data. Is the server running?';
      showToast('Could not load /api/bootstrap. Retrying in the background.', 'error', 8000);
      setTimeout(boot, 10_000);
    }
  }
}

function createComponents(data) {
  symbols = data.symbols || [];
  initialCash = data.initialCash ?? 10000;

  town = new Town3D(els.townContainer, {
    onSelectAgent: (id) => selectAgent(id, { focus: false }),
    onHoverAgent: () => {},
  });
  town.setPersonas(data.personas);
  town.setTownData(data.town);

  chart = new MarketChart(els.marketChart, {
    symbols,
    initialCash,
    onSymbolChange: (symbol) => {
      els.marketSub.textContent = `${symbol} · ${symbols.length} symbols · ${data.status?.data?.interval || '5m'} bars`;
    },
  });
  chart.setHistory(data.history);

  leaderboard = new Leaderboard(els.leaderboard, {
    initialCash,
    onSelect: (id) => selectAgent(id, { focus: true }),
  });
  tradeFeed = new TradeFeed(els.tradeFeed);
  observers = new ObserverReports(els.observerReports);
  agentDetail = new AgentDetail(els.agentDetail, {
    initialCash,
    onLocate: (id) => {
      selectAgent(id, { focus: true });
    },
  });
  agentDetail.setDefs(data.personas);

  if (new URLSearchParams(window.location.search).has('debug')) {
    window.__agentStreet = {
      get town() { return town; },
      get chart() { return chart; },
      get frame() { return lastFrame; },
      get ws() { return ws; },
    };
  }
}

function applyBootstrap(data) {
  const first = !town;
  bootstrap = data;
  symbols = data.symbols || [];
  initialCash = data.initialCash ?? 10000;

  if (first) {
    createComponents(data);
  } else {
    chart?.setSymbols(symbols);
    town?.setPersonas(data.personas);
    agentDetail?.setDefs(data.personas);
    tradeFeed?.reset();
    observers?.reset();
    agentDetail?.reset();
    leaderboard?.reset();
    lastTick = -1;
    lastFrame = null;
    warnedSynthetic = false;
    warnedStale = false;
  }

  document.title = 'Agent Street — a living market diorama';
  if (data.town?.locations) {
    els.townSub.textContent = `${data.personas?.length || 19} agents · ${data.town.locations.length} locations · ${symbols.length} symbols`;
  }
  els.marketSub.textContent = `${symbols.length} symbols · ${data.status?.data?.interval || data.barInterval || '5m'} bars`;
  chart?.setHistory(data.history);

  if (data.observerReports) observers?.append(data.observerReports);
  if (data.recentTrades) tradeFeed?.append(data.recentTrades, data.status?.tick || 0);

  if (data.frame) {
    applyFrame(data.frame, { force: true });
  } else {
    const initial = (data.personas || []).map((p) => ({
      ...p,
      equity: initialCash,
      cash: initialCash,
      returnPct: 0,
      pnl: 0,
      positions: 0,
      mood: 'calm',
      activity: 'idle',
      thoughts: [],
      holdings: [],
      signals: {},
      isObserver: Boolean(p.isObserver),
    }));
    leaderboard?.update(initial);
    els.lbAvg.textContent = '0.00%';
  }

  applyStatus(data.status);
  updateSimState(Boolean(data.status?.running), data.status?.speed ?? currentSpeed);
  updateSource(data.status?.data || null);
}

// ── WS frames ────────────────────────────────────────────────

function applyFrame(frame, { force = false } = {}) {
  if (!frame || !town) return;
  if (!force && frame.tick === lastTick) return;
  lastTick = frame.tick;
  lastFrame = frame;

  if (frame.looped) {
    // A replay loop is a new simulation session: portfolios, guilds and
    // adaptation history reset. The town itself stays alive.
    tradeFeed?.reset();
    observers?.reset();
    agentDetail?.reset();
    leaderboard?.reset();
    town?.setSelected(null);
    showToast('A new replay session begins — portfolios and strategies reset to generation 0.', 'info', 5500);
  }

  try {
    town.updateFrame(frame);
  } catch (error) {
    console.error('town update failed', error);
  }
  chart?.pushFrame(frame);
  chart?.setAgents(frame.personas, frame.ecosystem);
  leaderboard?.update(frame.personas);
  agentDetail?.updateStates(frame.personas, frame.tick);
  tradeFeed?.append(frame.trades, frame.tick);
  observers?.append(frame.observerReports);

  updateFrameStatus(frame);

  if (frame.looped) {
    refreshHistory();
  }
  if (frame.dataSource === 'synthetic' && !warnedSynthetic) {
    warnedSynthetic = true;
    showToast('Live market data is unavailable. Running on clearly-labelled synthetic bars.', 'warn', 9000);
  }
  if (frame.sourceInfo?.stale && !warnedStale) {
    warnedStale = true;
    showToast('Using stale cached bars. The live source could not be reached.', 'warn', 7000);
  }
}

function resetStatsToInitial() {
  const traders = bootstrap?.personas?.length || 16;
  els.statEquity.textContent = formatMoney(initialCash * traders, { compact: true });
  els.statEquitySub.textContent = `0.00% all-time · ${traders} traders`;
  els.statSentiment.textContent = 'Neutral 0.00';
  els.sentimentFill.style.left = '50%';
  els.statBreadth.textContent = '0↑ 0↓';
  els.statBreadthSub.textContent = '0% net breadth';
  els.statFees.textContent = formatMoney(0, { compact: true });
  els.statTrades.textContent = '0 fills this tick · 0 positions';
  els.regimePill.textContent = '—';
  els.regimePill.style.color = '';
  els.lbAvg.textContent = '—';
}

function updateFrameStatus(frame) {
  const time = (frame.worldTime || '').split(' ');
  els.marketTime.textContent = `${time[1] || frame.worldTime || '--:--'} ET`;
  els.marketTime.title = dateTimeLabel(frame.worldTime);
  els.tickPill.textContent = `TICK ${frame.tick}`;
  els.townContainer.dataset.tick = String(frame.tick);
  if (frame.ambientHour !== undefined) els.townContainer.dataset.ambientHour = String(frame.ambientHour);
  if (frame.totalBars) {
    const pct = ((frame.barIndex + 1) / frame.totalBars) * 100;
    els.barProgress.style.width = `${Math.min(100, pct)}%`;
    els.barIndex.textContent = `BAR ${frame.barIndex + 1} / ${frame.totalBars}`;
  }

  const stats = frame.stats || {};
  const traders = (frame.personas || []).filter((p) => !p.isObserver).length || 16;
  els.statEquity.textContent = formatMoney(stats.totalEquity ?? initialCash * traders, { compact: true });
  els.statEquitySub.textContent = `${formatPct(stats.totalReturnPct ?? 0, 2, true)} all-time · ${traders} traders`;

  const sentiment = Number(frame.sentiment || 0);
  const label = sentiment > 0.15 ? 'Bullish' : sentiment < -0.15 ? 'Bearish' : 'Neutral';
  els.statSentiment.textContent = `${label} ${sentiment >= 0 ? '+' : ''}${sentiment.toFixed(2)}`;
  els.sentimentFill.style.left = `${Math.min(97, Math.max(3, ((sentiment + 1) / 2) * 100))}%`;

  const changeValues = Object.values(frame.changes || {});
  const up = changeValues.filter((value) => value > 0).length;
  const down = changeValues.filter((value) => value < 0).length;
  els.statBreadth.textContent = `${up}↑ ${down}↓`;
  const breadth = frame.metrics?.breadth ?? 0;
  els.statBreadthSub.textContent = `${breadth >= 0 ? '+' : ''}${(breadth * 100).toFixed(0)}% net breadth`;

  els.statFees.textContent = formatMoney(stats.fees ?? 0, { compact: true });
  els.statTrades.textContent = `${stats.tradesThisTick ?? 0} fills this tick · ${stats.activePositions ?? 0} positions`;

  if (frame.metrics?.regime) {
    const regime = frame.metrics.regime;
    els.regimePill.textContent = regime.toUpperCase();
    els.regimePill.style.color = {
      'risk-on': '#43d17c',
      'risk-off': '#ff6b6b',
      volatile: '#f0b429',
      calm: '#5ad1ff',
      mixed: '#a78bfa',
    }[regime] || '';
  }
  els.lbAvg.textContent = formatPct(stats.totalReturnPct ?? 0, 2, true);

  updateSource(frame.sourceInfo || null, frame.dataSource);
  els.statusSource.textContent = frame.dataSource === 'synthetic'
    ? 'SYNTHETIC BARS'
    : `${(frame.dataSource || '—').toUpperCase()} · BAR ${frame.barIndex + 1}`;

  if (frame.sourceInfo?.warnings?.length) {
    els.statusWarning.hidden = false;
    els.statusWarning.textContent = frame.sourceInfo.warnings[0];
    els.statusWarning.title = frame.sourceInfo.warnings.join('\n');
  } else {
    els.statusWarning.hidden = true;
  }

  if (frame.sourceInfo?.totalBars) {
    const days = frame.sourceInfo.daysBack || '';
    const interval = frame.sourceInfo.interval || '';
    els.marketSub.textContent = `${symbols.length} symbols · ${interval} bars${days ? ` · ${days}d` : ''}`;
  }
}

function applyStatus(status) {
  if (!status) return;
  updateSimState(Boolean(status.running), status.speed);
  updateSource(status.data || null);
  if (status.tick !== undefined) els.tickPill.textContent = `TICK ${status.tick}`;
  if (status.worldTime) {
    const parts = String(status.worldTime).split(' ');
    els.marketTime.textContent = `${parts[1] || status.worldTime} ET`;
    els.marketTime.title = dateTimeLabel(status.worldTime);
  }
  if (status.running === false && status.tick === 0) resetStatsToInitial();
  if (status.barIndex !== undefined && status.totalTicks) {
    els.barIndex.textContent = `BAR ${status.barIndex + 1} / ${status.totalTicks}`;
    els.barProgress.style.width = `${Math.min(100, ((status.barIndex + 1) / status.totalTicks) * 100)}%`;
  }
  if (status.data) {
    els.marketSub.textContent = `${symbols.length} symbols · ${status.data.interval || '5m'} bars`;
    els.statusSource.textContent = status.data.source === 'synthetic'
      ? 'SYNTHETIC BARS'
      : `${String(status.data.source || '—').toUpperCase()} · BAR ${(status.barIndex ?? 0) + 1}`;
  }
}

// ── controls & state ─────────────────────────────────────────

function bindControls() {
  els.btnStart.addEventListener('click', startSim);
  els.btnStartOverlay.addEventListener('click', startSim);
  els.btnStop.addEventListener('click', stopSim);
  els.btnReset.addEventListener('click', resetSim);
  els.speedBtn.addEventListener('click', cycleSpeed);
  els.btnCamera.addEventListener('click', () => town?.resetCamera());
  els.btnRotate.addEventListener('click', () => {
    if (!town) return;
    const active = town.toggleAutoRotate();
    els.btnRotate.classList.toggle('is-active', active);
  });
  els.btnLabels.addEventListener('click', () => {
    if (!town) return;
    const active = town.toggleLabels();
    els.btnLabels.classList.toggle('is-active', active);
    els.btnLabels.setAttribute('aria-pressed', String(active));
  });

  els.speedBtn.textContent = `${currentSpeed}×`;
  document.addEventListener('keydown', (event) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    if (event.target instanceof HTMLButtonElement) return;
    if (event.code === 'Space') {
      event.preventDefault();
      if (runningState) stopSim();
      else startSim();
    } else if (event.key.toLowerCase() === 'r') {
      resetSim();
    } else if (event.key.toLowerCase() === 'c') {
      town?.resetCamera();
    }
  });
  window.addEventListener('beforeunload', () => ws.close());
}

function startSim() {
  if (runningState) return;
  els.btnStart.disabled = true;
  els.btnStartOverlay.disabled = true;
  showToast('Starting the town…', 'info', 2200);
  if (!ws.send('start')) {
    fetchJSON('/api/sim/start', 30000, { method: 'POST' })
      .then((data) => updateSimState(Boolean(data.running), data.status?.speed ?? currentSpeed))
      .catch((error) => {
        console.error(error);
        els.btnStart.disabled = false;
        els.btnStartOverlay.disabled = false;
        showToast('Could not start the simulation. Check the server log.', 'error');
      });
  }
}

function stopSim() {
  if (ws.send('stop')) {
    updateSimState(false, currentSpeed);
    return;
  }
  fetchJSON('/api/sim/stop', 15000, { method: 'POST' })
    .then(() => updateSimState(false, currentSpeed))
    .catch((error) => {
      console.error(error);
      showToast('Could not stop the simulation.', 'error');
    });
}

function resetSim() {
  showToast('Resetting the town…', 'info', 2000);
  if (!ws.send('reset')) {
    fetchJSON('/api/sim/reset', 30000, { method: 'POST' })
      .then(() => handleReset())
      .catch((error) => {
        console.error(error);
        showToast('Reset failed. Check the server log.', 'error');
      });
  }
}

function cycleSpeed() {
  const currentIndex = SPEEDS.indexOf(currentSpeed);
  const next = SPEEDS[(currentIndex + 1 + SPEEDS.length) % SPEEDS.length];
  currentSpeed = next;
  els.speedBtn.textContent = `${next}×`;
  ws.send(`speed:${next}`);
  writeSpeed(next);
}

function readSpeed() {
  try {
    const raw = Number(localStorage.getItem('agentStreet.speed'));
    return SPEEDS.includes(raw) ? raw : 1;
  } catch {
    return 1;
  }
}

function writeSpeed(value) {
  try {
    localStorage.setItem('agentStreet.speed', String(value));
  } catch {
    /* noop */
  }
}

function updateSimState(running, speedValue) {
  runningState = Boolean(running);
  if (Number.isFinite(speedValue) && speedValue > 0) {
    const nearest = SPEEDS.reduce((best, value) => (
      Math.abs(value - speedValue) < Math.abs(best - speedValue) ? value : best
    ), SPEEDS[0]);
    currentSpeed = nearest;
    els.speedBtn.textContent = `${nearest}×`;
  }
  els.btnStart.disabled = runningState;
  els.btnStop.disabled = !runningState;
  els.btnStartOverlay.disabled = runningState;
  els.townContainer.classList.toggle('is-running', runningState);
  els.townOverlay.setAttribute('aria-hidden', runningState ? 'true' : 'false');
  if (runningState) els.townLoading.hidden = true;
}

function selectAgent(id, { focus = false } = {}) {
  agentDetail?.show(id);
  leaderboard?.setSelected(id);
  town?.setSelected(id);
  if (focus && id) town?.focusAgent(id);
}

// ── connection / source / reset ──────────────────────────────

function updateConnection(data) {
  if (!data) return;
  const state = data.state;
  els.conn.classList.remove('is-open', 'is-closed', 'is-connecting');
  if (state === 'open') {
    els.conn.classList.add('is-open');
    els.connText.textContent = 'Connected';
    if (hadConnection) {
      showToast('Reconnected to the town.', 'info', 3000);
      refreshHistory();
    }
    hadConnection = true;
    ws.send(`speed:${currentSpeed}`);
  } else if (state === 'connecting' || state === 'reconnecting') {
    els.conn.classList.add('is-connecting');
    els.connText.textContent = state === 'reconnecting' ? 'Reconnecting…' : 'Connecting…';
  } else {
    els.conn.classList.add('is-closed');
    els.connText.textContent = 'Disconnected';
    hadConnection = true;
  }
}

function updateSource(data, fallbackSource = null) {
  if (!data && !fallbackSource) {
    els.sourceText.textContent = 'loading';
    els.sourcePill.classList.remove('is-live', 'is-cache', 'is-synth', 'is-offline');
    return;
  }
  const info = data || { source: fallbackSource };
  const source = String(info.source || fallbackSource || 'unknown').toLowerCase();
  els.sourcePill.classList.remove('is-live', 'is-cache', 'is-synth', 'is-offline');

  if (source === 'unloaded' || source === 'unknown' || source === 'loading') {
    els.sourcePill.classList.add('is-offline');
    els.sourceText.textContent = 'loading';
    return;
  }
  if (source === 'synthetic') {
    els.sourcePill.classList.add('is-synth');
    els.sourceText.textContent = 'synthetic';
  } else if (info.stale) {
    els.sourcePill.classList.add('is-cache');
    els.sourceText.textContent = 'stale cache';
  } else if (info.fromCache) {
    els.sourcePill.classList.add('is-cache');
    els.sourceText.textContent = `cached · ${source}`;
  } else {
    els.sourcePill.classList.add('is-live');
    els.sourceText.textContent = `live · ${source}`;
  }
  const details = [];
  if (info.interval) details.push(`${info.interval} bars`);
  if (info.daysBack) details.push(`${info.daysBack} sessions`);
  if (info.loadedAt) details.push(`loaded ${dateTimeLabel(info.loadedAt)}`);
  if (info.warnings?.length) details.push(...info.warnings);
  els.sourcePill.title = details.join('\n') || 'Market data source';

  if (source === 'synthetic') {
    els.statusWarning.hidden = false;
    els.statusWarning.textContent = 'Synthetic bars — live market source unavailable';
  }
}

function handleReset() {
  lastTick = -1;
  lastFrame = null;
  chart?.clear();
  tradeFeed?.reset();
  observers?.reset();
  agentDetail?.reset();
  leaderboard?.reset();
  town?.resetAgentPositions();
  warnedSynthetic = false;
  warnedStale = false;
  updateSimState(false, currentSpeed);
  boot(false);
}

async function refreshHistory() {
  try {
    const history = await fetchJSON('/api/market/history?limit=180', 20000);
    chart?.setHistory(history);
    if (lastFrame) chart?.pushFrame(lastFrame);
  } catch (error) {
    console.warn('history refresh failed', error);
  }
}

// ── helpers ──────────────────────────────────────────────────

async function fetchJSON(url, timeout = 15000, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { cache: 'no-store', signal: controller.signal, ...options });
    if (!response.ok) throw new Error(`${url} -> ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function showToast(message, kind = 'info', duration = 5000) {
  if (!message) return;
  const toast = document.createElement('div');
  toast.className = `toast toast--${kind}`;
  toast.textContent = message;
  els.toasts.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(4px)';
    setTimeout(() => toast.remove(), 260);
  }, duration);
}

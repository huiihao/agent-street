// Shared helpers. No framework, no build step.

export const SYMBOL_COLORS = [
  '#3987e5', // blue
  '#d95926', // orange
  '#199e70', // aqua
  '#c98500', // yellow
  '#d55181', // magenta
  '#008300', // green
  '#9085e9', // violet
  '#e66767', // red
];

const symbolColorMap = new Map();

export function registerSymbolColors(symbols) {
  symbolColorMap.clear();
  symbols.forEach((symbol, index) => {
    symbolColorMap.set(symbol, SYMBOL_COLORS[index % SYMBOL_COLORS.length]);
  });
}

export function symbolColor(symbol) {
  return symbolColorMap.get(symbol) || '#8a94a6';
}

export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
  ink: '#e8eefc',
  muted: '#8a94a6',
};

export function clamp(value, lo, hi) {
  return Math.max(lo, Math.min(hi, value));
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

export function smoothstep(edge0, edge1, x) {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

export function damp(current, target, lambda, dt) {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}

export function formatMoney(value, { sign = false, compact = false } = {}) {
  if (!Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  let body;
  if (compact && abs >= 1_000_000) {
    body = `$${(abs / 1_000_000).toFixed(2)}M`;
  } else if (compact && abs >= 10_000) {
    body = `$${(abs / 1_000).toFixed(1)}K`;
  } else {
    body = `$${abs.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
  }
  if (sign) return `${value >= 0 ? '+' : '−'}${body}`;
  return value < 0 ? `−${body}` : body;
}

export function formatPct(value, digits = 2, sign = true) {
  if (!Number.isFinite(value)) return '—';
  const pct = value * 100;
  const prefix = sign && pct > 0 ? '+' : pct < 0 ? '' : '';
  return `${prefix}${pct.toFixed(digits)}%`;
}

export function formatPrice(value) {
  if (!Number.isFinite(value)) return '—';
  if (value >= 1000) return value.toFixed(1);
  if (value >= 100) return value.toFixed(2);
  return value.toFixed(2);
}

export function formatCompact(value) {
  if (!Number.isFinite(value)) return '—';
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

export function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== '' && text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

export function setText(node, text) {
  if (node && node.textContent !== String(text)) node.textContent = String(text);
}

export function hashString(value) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

const etTime = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const etDateTime = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const etDate = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'short',
  day: '2-digit',
});

const etDateKey = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

export function dateLabel(iso) {
  if (!iso) return '';
  try {
    return etDate.format(new Date(iso));
  } catch {
    return '';
  }
}

export function dateKey(iso) {
  if (!iso) return '';
  try {
    return etDateKey.format(new Date(iso));
  } catch {
    return '';
  }
}

export function timeLabel(iso) {
  if (!iso) return '';
  try {
    return etTime.format(new Date(iso));
  } catch {
    return '';
  }
}

export function dateTimeLabel(iso) {
  if (!iso) return '';
  try {
    return `${etDateTime.format(new Date(iso))} ET`;
  } catch {
    return '';
  }
}

export const STRATEGY_FAMILIES = {
  momentum: { label: 'Momentum', short: 'MOM', color: '#3987e5' },
  mean_reversion: { label: 'Mean reversion', short: 'REV', color: '#d95926' },
  sentiment: { label: 'Sentiment', short: 'SOC', color: '#199e70' },
  contrarian: { label: 'Contrarian', short: 'CTR', color: '#c98500' },
  balanced: { label: 'Balanced', short: 'BAL', color: '#9085e9' },
};

export function strategyMeta(family) {
  return STRATEGY_FAMILIES[family] || STRATEGY_FAMILIES.balanced;
}

export const MOOD_COLORS = {
  calm: '#5a9ed4',
  confident: '#4ecca3',
  excited: '#f0c840',
  worried: '#f0a040',
  panicked: '#e84855',
};

export const ACTIVITY_LABELS = {
  idle: 'Idle',
  moving: 'On the move',
  trading: 'Trading',
  chatting: 'Conversing',
  panicking: 'Panicking',
};

export function clampText(text, max = 80) {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function debounce(fn, wait = 120) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

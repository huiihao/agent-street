"""Central configuration.

Every value can be overridden with an environment variable, which makes the
simulation reproducible in CI and configurable without editing source.

    INITIAL_CASH=25000 SYMBOLS=AAPL,NVDA python run.py
"""

from __future__ import annotations

import os


def _env(name: str, default, cast=str):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return values or list(default)


# ── Portfolio / simulation ───────────────────────────────────
INITIAL_CASH = _env("INITIAL_CASH", 10_000.0, float)
SYMBOLS = _env_list("SYMBOLS", ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"])
TICK_INTERVAL_SEC = _env("TICK_INTERVAL_SEC", 1.5, float)
MAX_SPEED = _env("MAX_SPEED", 20.0, float)
MAX_PRICE_HISTORY = 300

# Signal thresholds (composite score is in [-1, 1])
BUY_THRESHOLD = _env("BUY_THRESHOLD", 0.12, float)
SELL_THRESHOLD = _env("SELL_THRESHOLD", -0.10, float)
MAX_POSITION_PCT = _env("MAX_POSITION_PCT", 0.32, float)

# Execution model
FEE_BPS = _env("FEE_BPS", 2.0, float)            # 2 bps per side
SLIPPAGE_BPS = _env("SLIPPAGE_BPS", 3.0, float)  # house spread each side
MIN_FEE = _env("MIN_FEE", 0.0, float)

# Determinism: 0 = non-deterministic
SIM_SEED = _env("SIM_SEED", 7, int)

# ── Market data ──────────────────────────────────────────────
# auto | yfinance | yahoo_chart | ifind | alphavantage | synthetic
DATA_SOURCE = _env("DATA_SOURCE", "auto").lower()
HIST_DAYS_BACK = _env("HIST_DAYS_BACK", 5, int)
HIST_INTERVAL = _env("HIST_INTERVAL", "5m")   # 1m, 5m, 15m, 30m, 1h
HIST_LOOP = _env("HIST_LOOP", "true").lower() in ("1", "true", "yes")
WARMUP_BARS = _env("WARMUP_BARS", 30, int)    # bars reserved before replay starts
CACHE_TTL_SEC = _env("CACHE_TTL_SEC", 900, int)
MARKET_TZ = _env("MARKET_TZ", "America/New_York")
DATA_FETCH_TIMEOUT_SEC = _env("DATA_FETCH_TIMEOUT_SEC", 90, int)
DATA_RETRIES = _env("DATA_RETRIES", 3, int)

# Alpha Vantage API key (optional): https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = _env("ALPHA_VANTAGE_API_KEY", "")

# iFinD / 同花顺 credentials (institutional subscription required)
IFIND_API_KEY = _env("IFIND_API_KEY", "")
IFIND_API_SECRET = _env("IFIND_API_SECRET", "")
IFIND_TZ = _env("IFIND_TZ", "Asia/Shanghai")

# ── Agents / society ─────────────────────────────────────────
CONVERSATION_RADIUS = _env("CONVERSATION_RADIUS", 4, int)
CONVERSATION_COOLDOWN_TICKS = _env("CONVERSATION_COOLDOWN_TICKS", 5, int)
CONVERSATION_CHANCE = _env("CONVERSATION_CHANCE", 0.30, float)
MAX_CONVERSATIONS_PER_TICK = _env("MAX_CONVERSATIONS_PER_TICK", 2, int)
REFLECTION_EVERY_N_TICKS = _env("REFLECTION_EVERY_N_TICKS", 5, int)
OBSERVATION_MAX = _env("OBSERVATION_MAX", 80, int)
REFLECTION_MAX = _env("REFLECTION_MAX", 40, int)
PANIC_COOLDOWN_TICKS = _env("PANIC_COOLDOWN_TICKS", 12, int)
OBSERVER_REPORT_EVERY_N_TICKS = _env("OBSERVER_REPORT_EVERY_N_TICKS", 20, int)

# ── LLM (optional) ───────────────────────────────────────────
LLM_ENABLED = _env("LLM_ENABLED", "false").lower() in ("1", "true", "yes")
LLM_API_KEY = _env("LLM_API_KEY", "")
LLM_BASE_URL = _env("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = _env("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = _env("LLM_MAX_TOKENS", 150, int)
LLM_TEMPERATURE = _env("LLM_TEMPERATURE", 0.9, float)
LLM_MAX_CONCURRENCY = _env("LLM_MAX_CONCURRENCY", 2, int)
LLM_TIMEOUT_SEC = _env("LLM_TIMEOUT_SEC", 10, int)
# Reflections are enriched in the background; this caps how many per batch.
LLM_REFLECTIONS_PER_BATCH = _env("LLM_REFLECTIONS_PER_BATCH", 2, int)
LLM_CONVERSATIONS = _env("LLM_CONVERSATIONS", "false").lower() in ("1", "true", "yes")

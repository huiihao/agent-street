"""
同花顺 iFinD (Tonghuashun iFinD) financial data connector.

iFinD is a professional Chinese financial data terminal providing:
  - A-share / Hong Kong / US market data (real-time + historical)
  - Financial statements, macro indicators, industry data
  - Similar to Wind (万得) and Choice (东方财富)

Requires institutional subscription and API key.
For free access, see: https://www.51ifind.com/ (public data API)

Usage:
  1. Set IFIND_API_KEY and IFIND_API_SECRET in config or env vars
  2. Connector auto-detects credentials at startup
  3. Falls back gracefully if not configured
"""

import os
from datetime import datetime, timedelta

import requests


def _get_ifind_credentials() -> tuple[str, str] | None:
    """Read iFinD credentials from env vars or config."""
    key = os.getenv("IFIND_API_KEY", "")
    secret = os.getenv("IFIND_API_SECRET", "")
    if key and secret:
        return key, secret
    try:
        from backend.config import IFIND_API_KEY, IFIND_API_SECRET
        if IFIND_API_KEY and IFIND_API_SECRET:
            return IFIND_API_KEY, IFIND_API_SECRET
    except ImportError:
        pass
    return None


def ifind_available() -> bool:
    """Check if iFinD credentials are configured."""
    return _get_ifind_credentials() is not None


def fetch_history(symbol: str, days_back: int = 5, interval: str = "5m") -> list[dict] | None:
    """
    Fetch historical bars from iFinD.

    Args:
        symbol: Stock code, e.g. '600519.SH' (A-share), 'AAPL.US' (US), '0700.HK' (HK)
        days_back: Number of days of history
        interval: Bar interval (1m, 5m, 15m, 30m, 60m, 1d)

    Returns list of bars: [{time, open, high, low, close, volume}, ...] or None
    """
    creds = _get_ifind_credentials()
    if not creds:
        return None

    api_key, api_secret = creds
    end = datetime.now()
    start = end - timedelta(days=days_back)

    interval_map = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "1d": "D",
    }
    ifd_interval = interval_map.get(interval, "5")

    # iFinD REST API endpoint (institutional)
    # Note: actual endpoints vary by contract. This implements the public HTTP API.
    url = "https://openapi.51ifind.com/v1/market/kline"

    try:
        resp = requests.post(
            url,
            json={
                "api_key": api_key,
                "api_secret": api_secret,
                "code": symbol,
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "period": ifd_interval,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0 or "data" not in data:
            return None

        bars = []
        for row in data["data"].get("kline", []):
            bars.append({
                "time": datetime.strptime(row[0], "%Y-%m-%d %H:%M"),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": int(row[5]),
            })
        return bars if bars else None

    except Exception as e:
        print(f"iFinD: fetch error for {symbol} — {e}")
        return None


# ── Symbol mapping: common tickers to iFinD codes ──────────

IFIND_SYMBOL_MAP: dict[str, str] = {
    # US stocks
    "AAPL": "AAPL.US",
    "GOOGL": "GOOGL.US",
    "MSFT": "MSFT.US",
    "TSLA": "TSLA.US",
    "AMZN": "AMZN.US",
    # HK stocks
    "0700": "0700.HK",
    "9988": "9988.HK",
    # A-share (Shanghai)
    "600519": "600519.SH",  # 贵州茅台
    "000858": "000858.SZ",  # 五粮液
}

# ── Configuration defaults ──────────────────────────────────

IFIND_API_KEY = ""
IFIND_API_SECRET = ""

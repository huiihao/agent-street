"""Multi-source stock data provider.

Primary: Yahoo Finance via yfinance (free, no API key)
Fallback: Yahoo Finance direct CSV download
Graceful: Synthetic data if all sources fail
"""

import asyncio
import csv
import io
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yfinance as yf

from backend.config import SYMBOLS, HIST_DAYS_BACK, HIST_INTERVAL

# Cache directory for downloaded data
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


class HistoricalDataProvider:
    """Replays intraday historical data bar-by-bar."""

    def __init__(self, symbols=None, days_back=None, interval=None):
        self.symbols = symbols or SYMBOLS
        self.days_back = days_back or HIST_DAYS_BACK
        self.interval = interval or HIST_INTERVAL
        self._bars: dict[str, list[dict]] = {}
        self._bar_index = 0
        self._total_bars = 0
        self._current_prices: dict[str, float] = {}
        self._current_changes: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._loaded = False

    async def fetch_init(self):
        """Load data, trying multiple sources in order."""
        await asyncio.to_thread(self._load_all)
        if self._total_bars > 0:
            self._advance_bar()
            self._loaded = True

    def _load_all(self):
        print(f"Loading {len(self.symbols)} symbols, {self.days_back}d of {self.interval} bars...")

        # ── Source 1: yfinance batch ──
        try:
            end = datetime.now()
            start = end - timedelta(days=self.days_back)
            results = {}
            for symbol in self.symbols:
                df = self._fetch_yfinance(symbol, start, end)
                if df is not None and not df.empty:
                    results[symbol] = df
                    print(f"  [yfinance] {symbol}: {len(df)} bars")

            if len(results) >= 3:
                self._build_bars(results)
                print(f"  => Loaded {self._total_bars} bars from yfinance")
                return
        except Exception as e:
            print(f"  yfinance batch failed: {e}")

        # ── Source 2: Alpha Vantage (free tier, reliable) ──
        av_key = self._get_alpha_vantage_key()
        if av_key:
            try:
                results = {}
                for symbol in self.symbols:
                    df = self._fetch_alpha_vantage(symbol, av_key)
                    if df is not None and not df.empty:
                        results[symbol] = df
                        print(f"  [alphavantage] {symbol}: {len(df)} bars")
                if len(results) >= 3:
                    self._build_bars(results)
                    print(f"  => Loaded {self._total_bars} bars from Alpha Vantage")
                    return
            except Exception as e:
                print(f"  Alpha Vantage failed: {e}")

        # ── Source 3: Direct CSV per symbol ──
        results = {}
        for symbol in self.symbols:
            df = self._fetch_csv(symbol)
            if df is not None:
                results[symbol] = df
                print(f"  [csv] {symbol}: {len(df)} bars")

        if len(results) >= 3:
            self._build_bars(results)
            print(f"  => Loaded {self._total_bars} bars from CSV")
            return

        # ── Source 3: Synthetic fallback ──
        print("  => All sources failed, generating synthetic data")
        self._generate_synthetic()
        print(f"  => Generated {self._total_bars} synthetic bars")

    def _fetch_yfinance(self, symbol, start, end):
        """Fetch a single symbol via yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=self.interval)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

        # Retry once after 1 second
        try:
            time.sleep(1)
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=self.interval)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

        return None

    def _get_alpha_vantage_key(self) -> str | None:
        """Look for Alpha Vantage API key in env or config."""
        import os
        key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        if key and key != "demo" and len(key) > 5:
            return key
        from backend.config import ALPHA_VANTAGE_API_KEY
        if ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_API_KEY != "demo":
            return ALPHA_VANTAGE_API_KEY
        return None

    def _fetch_alpha_vantage(self, symbol, api_key):
        """Fetch intraday data from Alpha Vantage (free tier: 5 calls/min)."""
        import time as _time
        _time.sleep(0.5)  # rate limit: 5 calls/min = 1 per 12s, we stagger
        interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min"}
        av_interval = interval_map.get(self.interval, "5min")
        # Alpha Vantage intraday only returns last 1-2 days in free tier
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=TIME_SERIES_INTRADAY"
            f"&symbol={symbol}"
            f"&interval={av_interval}"
            f"&outputsize=full"
            f"&apikey={api_key}"
        )
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            ts_key = f"Time Series ({av_interval})"
            if ts_key not in data:
                return None
            ts = data[ts_key]
            rows = []
            for dt_str, values in ts.items():
                rows.append({
                    "time": datetime.fromisoformat(dt_str),
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": int(values["5. volume"]),
                })
            if rows:
                import pandas as pd
                rows.sort(key=lambda r: r["time"])
                return pd.DataFrame(rows).set_index("time")
        except Exception as e:
            print(f"    Alpha Vantage {symbol}: {e}")
        return None

    def _fetch_csv(self, symbol):
        """Fetch via direct Yahoo Finance CSV download."""
        # Map interval to Yahoo's period1/period2 range
        end_ts = int(time.time())
        start_ts = end_ts - self.days_back * 86400

        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m",
        }
        yf_interval = interval_map.get(self.interval, "5m")

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?period1={start_ts}&period2={end_ts}"
            f"&interval={yf_interval}&includePrePost=false"
        )

        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quotes = result["indicators"]["quote"][0]
            opens = quotes["open"]
            highs = quotes["high"]
            lows = quotes["low"]
            closes = quotes["close"]
            volumes = quotes["volume"]

            rows = []
            for i, ts in enumerate(timestamps):
                c = closes[i]
                if c is None:
                    continue
                rows.append({
                    "time": datetime.fromtimestamp(ts),
                    "open": opens[i] if opens[i] else c,
                    "high": highs[i] if highs[i] else c,
                    "low": lows[i] if lows[i] else c,
                    "close": c,
                    "volume": volumes[i] if volumes[i] else 0,
                })

            if rows:
                import pandas as pd
                return pd.DataFrame(rows).set_index("time")
        except Exception as e:
            print(f"    CSV fetch {symbol}: {e}")
        return None

    def _build_bars(self, results: dict):
        """Convert DataFrames to internal bar format, aligned by count."""
        for symbol, df in results.items():
            bars = []
            for idx, row in df.iterrows():
                bars.append({
                    "time": idx,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row.get("Volume", 0)),
                })
            self._bars[symbol] = bars

        self._total_bars = max(len(b) for b in self._bars.values()) if self._bars else 0

    def _generate_synthetic(self):
        """Generate realistic synthetic data using a geometric random walk."""
        base_prices = {
            "AAPL": 300, "GOOGL": 390, "MSFT": 420, "TSLA": 415, "AMZN": 265,
        }
        n_bars = max(1, self.days_back * 78)  # ~78 5m bars per trading day

        for symbol in self.symbols:
            base = base_prices.get(symbol, 200)
            volatility = {"TSLA": 0.008, "AMZN": 0.005, "GOOGL": 0.004, "AAPL": 0.003, "MSFT": 0.003}.get(symbol, 0.004)
            bars = []
            price = base * (1 + random.uniform(-0.02, 0.02))  # start near base
            for i in range(n_bars):
                # Geometric random walk with mean reversion
                drift = (base / price - 1) * 0.01  # weak mean reversion
                price *= 1 + random.gauss(drift, volatility)
                price = max(price, base * 0.7)
                price = min(price, base * 1.3)
                open_p = price * (1 + random.uniform(-0.001, 0.001))
                high = max(open_p, price) * (1 + abs(random.uniform(0, 0.003)))
                low = min(open_p, price) * (1 - abs(random.uniform(0, 0.003)))
                bars.append({
                    "time": datetime.now() + timedelta(minutes=i * 5),
                    "open": round(open_p, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(price, 2),
                    "volume": int(random.uniform(1000, 50000)),
                })
            self._bars[symbol] = bars

        self._total_bars = n_bars

    # ── Tick interface ──────────────────────────────────────────

    def _advance_bar(self):
        idx = self._bar_index % max(self._total_bars, 1)
        for symbol in self.symbols:
            bars = self._bars.get(symbol, [])
            if bars:
                bar = bars[idx % len(bars)]
                self._current_prices[symbol] = bar["close"]
                prev = bars[(idx - 1) % len(bars)]["close"] if idx > 0 else bar["open"]
                self._prev_close[symbol] = prev
                self._current_changes[symbol] = (
                    (bar["close"] - prev) / prev if prev > 0 else 0.0
                )
            elif symbol not in self._current_prices:
                self._current_prices[symbol] = 200.0
                self._current_changes[symbol] = 0.0
        self._bar_index += 1

    async def get_prices(self):
        if not self._loaded:
            await self.fetch_init()
        self._advance_bar()
        return dict(self._current_prices), dict(self._current_changes)

    def progress(self) -> float:
        return min(1.0, self._bar_index / max(self._total_bars, 1))

    def estimate_total_ticks(self) -> int:
        return self._total_bars

    @property
    def current_prices(self) -> dict[str, float]:
        return dict(self._current_prices)

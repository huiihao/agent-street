import asyncio
import time
import yfinance as yf
from backend.config import SYMBOLS


class MarketDataProvider:
    def __init__(self, symbols: list[str] | None = None):
        self.symbols = symbols or SYMBOLS
        self._prices: dict[str, float] = {}
        self._changes: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._price_history: dict[str, list[float]] = {s: [] for s in self.symbols}
        self._last_fetch = 0.0
        self._lock = asyncio.Lock()

    async def get_prices(self) -> tuple[dict[str, float], dict[str, float]]:
        async with self._lock:
            if not self._prices or time.time() - self._last_fetch > 30:
                await self._fetch()
            return dict(self._prices), dict(self._changes)

    async def _fetch(self):
        try:
            tickers = yf.Tickers(" ".join(self.symbols))
            for s in self.symbols:
                try:
                    t = tickers.tickers.get(s)
                    if t is None:
                        continue
                    info = t.fast_info
                    price = info.get("lastPrice", 0) or info.get("regularMarketPrice", 0)
                    prev = info.get("regularMarketPreviousClose", 0) or info.get("previousClose", 0)
                    if price and price > 0:
                        self._prices[s] = float(price)
                        self._prev_close[s] = float(prev)
                        if prev and prev > 0:
                            self._changes[s] = (self._prices[s] - prev) / prev
                        else:
                            self._changes[s] = 0.0
                        self._price_history[s].append(self._prices[s])
                        if len(self._price_history[s]) > 300:
                            self._price_history[s] = self._price_history[s][-300:]
                except Exception as e:
                    print(f"MarketData: error for {s} — {e}")
                    continue
        except Exception as e:
            print(f"MarketData: fetch error — {e}")
        self._last_fetch = time.time()

    async def fetch_init(self):
        await self._fetch()
        if not self._prices:
            self._prices = {s: 180.0 + i * 20 for i, s in enumerate(self.symbols)}
            self._changes = {s: 0.0 for s in self.symbols}

    def get_history(self, symbol: str) -> list[float]:
        return self._price_history.get(symbol, [])

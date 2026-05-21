import random
import time
from datetime import datetime, timedelta
import yfinance as yf
from backend.config import SYMBOLS


class HistoricalDataProvider:
    """Loads intraday historical data and replays it bar-by-bar as simulation ticks."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        days_back: int = 3,
        interval: str = "5m",
    ):
        self.symbols = symbols or SYMBOLS
        self.days_back = days_back
        self.interval = interval
        self._bars: dict[str, list[dict]] = {}     # symbol -> [{time, open, high, low, close, volume}]
        self._bar_index: int = 0
        self._total_bars: int = 0
        self._current_prices: dict[str, float] = {}
        self._current_changes: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._loaded = False

    async def fetch_init(self):
        await self._load_history()
        if self._total_bars > 0:
            self._advance_bar()
            self._loaded = True

    async def _load_history(self):
        end = datetime.now()
        start = end - timedelta(days=self.days_back)

        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start, end=end, interval=self.interval)
                if df.empty:
                    continue
                bars = []
                for idx, row in df.iterrows():
                    bars.append({
                        "time": idx,
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]),
                    })
                self._bars[symbol] = bars
                if self._prev_close:
                    # Use the first bar's close as prev_close for change calc
                    pass
            except Exception as e:
                print(f"History load error for {symbol}: {e}")

        # Align all symbols to the same bar count
        if self._bars:
            self._total_bars = max(len(b) for b in self._bars.values())
        else:
            self._total_bars = 0

    def _advance_bar(self):
        idx = self._bar_index % max(self._total_bars, 1)
        for symbol in self.symbols:
            bars = self._bars.get(symbol, [])
            if bars:
                bar = bars[idx % len(bars)]
                self._current_prices[symbol] = bar["close"]
                prev = bars[(idx - 1) % len(bars)]["close"] if idx > 0 else bar["open"]
                self._prev_close[symbol] = prev
                self._current_changes[symbol] = (bar["close"] - prev) / prev if prev > 0 else 0.0
            else:
                # Symbol has no data — carry over last price or seed
                if symbol not in self._current_prices:
                    self._current_prices[symbol] = 200.0
                    self._current_changes[symbol] = 0.0

        self._bar_index += 1

    async def get_prices(self) -> tuple[dict[str, float], dict[str, float]]:
        """Advance to the next bar and return prices. Called once per simulation tick."""
        if not self._loaded:
            await self.fetch_init()
        self._advance_bar()
        return dict(self._current_prices), dict(self._current_changes)

    def progress(self) -> float:
        if self._total_bars == 0:
            return 1.0
        return min(1.0, self._bar_index / self._total_bars)

    def estimate_total_ticks(self) -> int:
        return self._total_bars

    @property
    def current_prices(self) -> dict[str, float]:
        return dict(self._current_prices)

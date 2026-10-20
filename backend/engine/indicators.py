"""Technical indicators computed once per tick, shared by every agent.

The previous implementation recomputed "momentum" from a module-level list that
every agent appended to, so the window length depended on how many agents had
asked, not on time. This engine keeps one time-indexed window per symbol and
exposes derived, dimensionless scores that agents can consume safely.

All indicators are computed incrementally from OHLCV bars. Scores are clipped to
[-1, 1] so they can be blended without one term dominating by scale.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from backend.engine.market_data import Bar

EPS = 1e-9


def _tanh(x: float, scale: float = 1.0) -> float:
    try:
        return math.tanh(x / max(scale, EPS))
    except (OverflowError, ValueError):
        return 0.0


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class SymbolMetrics:
    symbol: str
    close: float = 0.0
    ret: float = 0.0                 # last bar log return
    mom_5: float = 0.0               # 5-bar cumulative log return
    mom_20: float = 0.0              # 20-bar cumulative log return
    vol_20: float = 0.0              # per-bar stdev of log returns
    sma_20: float = 0.0
    ema_9: float = 0.0
    ema_21: float = 0.0
    rsi_14: float = 50.0
    atr_14: float = 0.0              # dollars
    atr_pct: float = 0.0
    zscore: float = 0.0              # (close - sma20) / atr
    trend_score: float = 0.0         # momentum / its own volatility, in [-1,1]
    reversion_score: float = 0.0     # -zscore, in [-1,1]
    rsi_score: float = 0.0           # (50 - rsi) / 50, in [-1,1]
    vwap_proxy: float = 0.0

    @property
    def trend_up(self) -> bool:
        return self.trend_score > 0.05


@dataclass
class MarketMetrics:
    symbols: dict[str, SymbolMetrics] = field(default_factory=dict)
    breadth: float = 0.0        # mean sign of bar returns, [-1,1]
    avg_return: float = 0.0     # cross-sectional mean log return
    dispersion: float = 0.0     # cross-sectional stdev of returns
    avg_vol: float = 0.0        # mean realized volatility
    regime: str = "calm"
    as_of: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "breadth": round(self.breadth, 4),
            "avgReturn": round(self.avg_return, 6),
            "dispersion": round(self.dispersion, 6),
            "avgVol": round(self.avg_vol, 6),
            "regime": self.regime,
            "asOf": self.as_of.isoformat() if self.as_of else None,
        }


class _SymbolWindow:
    """Rolling state for one symbol."""

    __slots__ = (
        "closes", "highs", "lows", "volumes", "returns", "last_time",
        "ema9", "ema21", "rsi_avg_gain", "rsi_avg_loss", "rsi_count",
        "atr", "atr_count", "prev_close",
    )

    def __init__(self, maxlen: int = 160):
        self.closes: deque[float] = deque(maxlen=maxlen)
        self.highs: deque[float] = deque(maxlen=maxlen)
        self.lows: deque[float] = deque(maxlen=maxlen)
        self.volumes: deque[float] = deque(maxlen=maxlen)
        self.returns: deque[float] = deque(maxlen=maxlen)
        self.last_time: datetime | None = None
        self.ema9: float | None = None
        self.ema21: float | None = None
        self.rsi_avg_gain: float | None = None
        self.rsi_avg_loss: float | None = None
        self.rsi_count = 0
        self.atr: float | None = None
        self.atr_count = 0
        self.prev_close: float | None = None


class IndicatorEngine:
    """Incremental indicator state for a fixed symbol universe."""

    def __init__(self, symbols: list[str], maxlen: int = 160):
        self.symbols = list(symbols)
        self.maxlen = maxlen
        self._windows: dict[str, _SymbolWindow] = {}
        self.reset()

    def reset(self) -> None:
        self._windows = {s: _SymbolWindow(self.maxlen) for s in self.symbols}

    def warmup(self, history: dict[str, list[Bar]]) -> None:
        """Feed historical bars, oldest first, without emitting metrics."""
        for symbol in self.symbols:
            for bar in history.get(symbol, []):
                self._ingest(symbol, bar)
        # Seed EMAs if there was no history at all (will be set on first bar).
        for window in self._windows.values():
            if window.closes and window.ema9 is None:
                window.ema9 = window.closes[-1]
                window.ema21 = window.closes[-1]

    def update(self, bars: dict[str, Bar]) -> MarketMetrics:
        """Ingest the current bar for every symbol and return metrics."""
        as_of = None
        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue
            as_of = bar.time if as_of is None else max(as_of, bar.time)
            self._ingest(symbol, bar)
        return self._metrics(as_of)

    # ── ingestion ────────────────────────────────────────────

    def _ingest(self, symbol: str, bar: Bar) -> None:
        window = self._windows.setdefault(symbol, _SymbolWindow(self.maxlen))
        # Replay loops and duplicate bootstrap frames must not double-count.
        if window.last_time is not None and bar.time <= window.last_time:
            return
        if not (math.isfinite(bar.close) and bar.close > 0):
            return

        close = float(bar.close)
        prev = window.prev_close

        if prev is not None and prev > 0:
            log_ret = math.log(close / prev)
            # A genuine 5-minute move above ~60% is almost certainly a bad print.
            if abs(log_ret) < 0.6:
                window.returns.append(log_ret)
            else:
                log_ret = 0.0

            # Wilder RSI
            gain = max(close - prev, 0.0)
            loss = max(prev - close, 0.0)
            window.rsi_count += 1
            if window.rsi_count <= 14:
                window.rsi_avg_gain = (window.rsi_avg_gain or 0.0) + gain / 14.0
                window.rsi_avg_loss = (window.rsi_avg_loss or 0.0) + loss / 14.0
            else:
                window.rsi_avg_gain = (window.rsi_avg_gain or 0.0) * 13.0 / 14.0 + gain / 14.0
                window.rsi_avg_loss = (window.rsi_avg_loss or 0.0) * 13.0 / 14.0 + loss / 14.0

            # Wilder ATR
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - prev),
                abs(bar.low - prev),
            )
            window.atr_count += 1
            if window.atr_count <= 14:
                window.atr = (window.atr or 0.0) + true_range / 14.0
            else:
                window.atr = (window.atr or true_range) * 13.0 / 14.0 + true_range / 14.0
        else:
            log_ret = 0.0

        # EMAs
        if window.ema9 is None:
            window.ema9 = close
            window.ema21 = close
        else:
            window.ema9 = window.ema9 + (close - window.ema9) * (2.0 / 10.0)
            window.ema21 = window.ema21 + (close - window.ema21) * (2.0 / 22.0)

        window.closes.append(close)
        window.highs.append(float(bar.high))
        window.lows.append(float(bar.low))
        window.volumes.append(float(bar.volume))
        window.prev_close = close
        window.last_time = bar.time

    # ── derived metrics ──────────────────────────────────────

    def _metrics(self, as_of: datetime | None) -> MarketMetrics:
        out: dict[str, SymbolMetrics] = {}
        rets: list[float] = []
        vols: list[float] = []

        for symbol in self.symbols:
            w = self._windows.get(symbol)
            if not w or not w.closes:
                out[symbol] = SymbolMetrics(symbol=symbol)
                continue

            closes = list(w.closes)
            volumes = list(w.volumes)
            close = closes[-1]
            ret = w.returns[-1] if w.returns else 0.0

            def cumulative(n: int) -> float:
                if not w.returns:
                    return 0.0
                return sum(list(w.returns)[-n:])

            mom5 = cumulative(5)
            mom20 = cumulative(20)

            ret_list = list(w.returns)
            vol20 = statistics.stdev(ret_list[-20:]) if len(ret_list) >= 2 else 0.0

            sma20 = statistics.fmean(closes[-20:]) if len(closes) >= 2 else close
            # Distance in ATR units is scale-free across symbols.
            atr = w.atr or (close * 0.005)
            z = (close - sma20) / max(atr, close * 1e-4)

            rsi = 50.0
            if w.rsi_avg_gain is not None and w.rsi_avg_loss is not None:
                if w.rsi_avg_loss <= EPS:
                    rsi = 100.0 if w.rsi_avg_gain > EPS else 50.0
                else:
                    rs = w.rsi_avg_gain / w.rsi_avg_loss
                    rsi = 100.0 - 100.0 / (1.0 + rs)

            # Momentum expressed in units of its own noise: a 0.5% move is
            # strong for a calm stock and ordinary for TSLA.
            mom_scale = max(vol20 * math.sqrt(5.0), 1e-5)
            trend = _clip(_tanh(mom5, mom_scale))
            reversion = _clip(-_tanh(z, 1.5))
            rsi_score = _clip((50.0 - rsi) / 50.0)

            out[symbol] = SymbolMetrics(
                symbol=symbol,
                close=close,
                ret=ret,
                mom_5=mom5,
                mom_20=mom20,
                vol_20=vol20,
                sma_20=sma20,
                ema_9=w.ema9 or close,
                ema_21=w.ema21 or close,
                rsi_14=rsi,
                atr_14=atr,
                atr_pct=atr / close if close else 0.0,
                zscore=z,
                trend_score=trend,
                reversion_score=reversion,
                rsi_score=rsi_score,
                vwap_proxy=(
                    sum(c * v for c, v in zip(closes[-20:], volumes[-20:]))
                    / max(sum(volumes[-20:]), EPS)
                ) if volumes else close,
            )
            rets.append(ret)
            vols.append(vol20)

        if rets:
            breadth = sum(1.0 if r > 0 else -1.0 if r < 0 else 0.0 for r in rets) / len(rets)
            avg_return = statistics.fmean(rets)
            dispersion = statistics.stdev(rets) if len(rets) >= 2 else 0.0
            avg_vol = statistics.fmean(vols) if vols else 0.0
        else:
            breadth = avg_return = dispersion = avg_vol = 0.0

        # Regime labels are descriptive, not predictive.
        if avg_vol <= 0:
            regime = "calm"
        elif avg_vol > 0.0035:
            regime = "volatile"
        elif breadth > 0.5:
            regime = "risk-on"
        elif breadth < -0.5:
            regime = "risk-off"
        else:
            regime = "mixed"

        return MarketMetrics(
            symbols=out,
            breadth=breadth,
            avg_return=avg_return,
            dispersion=dispersion,
            avg_vol=avg_vol,
            regime=regime,
            as_of=as_of,
        )

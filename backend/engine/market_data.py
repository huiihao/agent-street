"""Reliable historical market data with aligned multi-symbol bars.

Design goals
------------
1. **One clock.** Every symbol is replayed on a single, shared timeline. The old
   implementation wrapped each symbol with its own ``len(bars)``, so cross-asset
   moves drifted apart whenever one ticker had a gap.
2. **Validated data.** Non-finite prices, non-positive prices, OHLC
   contradictions, duplicate timestamps and obvious bad prints are removed.
3. **Graceful, visible degradation.** yfinance -> Yahoo chart API -> iFinD ->
   disk cache -> synthetic. The active source is surfaced to the UI so a
   synthetic demo is never mistaken for live data.
4. **No side effects on read.** ``snapshot()`` is pure; only the simulation loop
   calls ``advance()``.

Sources are fetched in a worker thread; the async API is safe to call from
FastAPI's event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from backend.config import (
    ALPHA_VANTAGE_API_KEY,
    CACHE_TTL_SEC,
    DATA_FETCH_TIMEOUT_SEC,
    DATA_RETRIES,
    DATA_SOURCE,
    HIST_DAYS_BACK,
    HIST_INTERVAL,
    HIST_LOOP,
    IFIND_TZ,
    MARKET_TZ,
    SIM_SEED,
    SYMBOLS,
    WARMUP_BARS,
)
from backend.engine.ifind_connector import fetch_history as ifind_fetch_history, ifind_available

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

INTERVAL_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
VALID_INTERVALS = set(INTERVAL_MINUTES)


@dataclass(frozen=True)
class Bar:
    time: datetime          # tz-aware, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_payload(self) -> dict:
        return {
            "t": self.time.isoformat(),
            "o": round(self.open, 4),
            "h": round(self.high, 4),
            "l": round(self.low, 4),
            "c": round(self.close, 4),
            "v": int(self.volume),
        }


@dataclass
class MarketSnapshot:
    index: int
    total_bars: int
    bars: dict[str, Bar]
    prev_close: dict[str, float]
    session_open: dict[str, float]
    changes: dict[str, float]          # close vs previous bar
    day_changes: dict[str, float]      # close vs session open
    world_time: datetime               # tz-aware in MARKET_TZ
    world_hour: float
    ambient_hour: float                # stylised 0-24 lighting clock
    weather_rain: bool
    source: str
    from_cache: bool
    stale: bool
    looped: bool
    finished: bool


class HistoricalDataProvider:
    def __init__(
        self,
        symbols: list[str] | None = None,
        days_back: int | None = None,
        interval: str | None = None,
    ):
        self._universe = list(symbols or SYMBOLS)
        self.symbols = list(self._universe)
        self.days_back = int(days_back or HIST_DAYS_BACK)
        self.interval = interval or HIST_INTERVAL
        if self.interval not in VALID_INTERVALS:
            self.interval = "5m"

        self._times: list[datetime] = []
        self._bars: dict[str, list[Bar]] = {}
        self._session_opens: dict[str, list[float]] = {}
        self._total_bars = 0
        self._index = 0
        self._start_offset = 0
        self._looped_index = -1
        self._finished = False
        self._bars_per_day = 78

        self.loaded = False
        self.loading = False
        self.source = "unloaded"
        self.from_cache = False
        self.served_from_cache = False
        self.stale = False
        self.loaded_at: float = 0.0
        self.warnings: list[str] = []
        self.dropped_symbols: list[str] = []

        self._market_tz = ZoneInfo(MARKET_TZ)

    # ── lifecycle ────────────────────────────────────────────

    async def fetch_init(self, force: bool = False) -> None:
        """Load (or reuse) data. Safe to call repeatedly."""
        if self.loaded and not force:
            return
        if self.loading:
            while self.loading:
                await asyncio.sleep(0.05)
            return

        self.loading = True
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._load_all, force),
                timeout=DATA_FETCH_TIMEOUT_SEC + 15,
            )
        except asyncio.TimeoutError:
            self.warnings.append("data fetch timed out; falling back")
            self._load_from_cache_or_synthetic(force)
        finally:
            self.loading = False

        if not self.loaded:
            self._generate_synthetic()
        self.served_from_cache = self.from_cache
        print(
            f"[market] source={self.source} bars={self._total_bars} "
            f"symbols={len(self._bars)} cache={self.from_cache} stale={self.stale}"
        )

    # ── public interface ─────────────────────────────────────

    @property
    def total_bars(self) -> int:
        return self._total_bars

    @property
    def index(self) -> int:
        return self._index

    @property
    def start_offset(self) -> int:
        return self._start_offset

    @property
    def bars_per_day(self) -> int:
        return self._bars_per_day

    def reset_index(self) -> None:
        """Rewind replay to the warm-up boundary without refetching."""
        self._index = self._start_offset if self._total_bars else 0
        self._looped_index = -1
        self._finished = False

    def advance(self) -> None:
        """Move to the next bar. Only the simulation loop should call this."""
        if not self._total_bars:
            return
        if self._index + 1 < self._total_bars:
            self._index += 1
            return
        if HIST_LOOP:
            self._index = self._start_offset
            self._looped_index = self._index
            self._finished = False
        else:
            self._finished = True

    def snapshot(self) -> MarketSnapshot | None:
        if not self.loaded or not self._times:
            return None
        i = max(0, min(self._index, self._total_bars - 1))
        current_time = self._times[i]
        bars: dict[str, Bar] = {}
        prev_close: dict[str, float] = {}
        session_open: dict[str, float] = {}
        changes: dict[str, float] = {}
        day_changes: dict[str, float] = {}

        for symbol in self.symbols:
            series = self._bars.get(symbol)
            if not series:
                continue
            bar = series[i]
            bars[symbol] = bar
            prev = series[i - 1].close if i > 0 else bar.open
            prev_close[symbol] = prev
            changes[symbol] = (bar.close - prev) / prev if prev > 0 else 0.0
            s_open = self._session_opens.get(symbol, [bar.open])[i]
            session_open[symbol] = s_open
            day_changes[symbol] = (bar.close - s_open) / s_open if s_open > 0 else 0.0

        local_time = current_time.astimezone(self._market_tz)
        world_hour = local_time.hour + local_time.minute / 60.0

        # Stylised ambience: each replay day runs dawn -> noon -> dusk -> night
        # while the market clock stays at its true session time.
        day_frac = (i % max(self._bars_per_day, 1)) / max(self._bars_per_day, 1)
        ambient_hour = 6.0 + 18.0 * day_frac

        # Deterministic weather blocks (changes every ~60 bars).
        weather_rng = random.Random((SIM_SEED or 0) * 100_003 + i // 60)
        rain = weather_rng.random() < 0.18 and ambient_hour > 5.5

        return MarketSnapshot(
            index=i,
            total_bars=self._total_bars,
            bars=bars,
            prev_close=prev_close,
            session_open=session_open,
            changes=changes,
            day_changes=day_changes,
            world_time=local_time,
            world_hour=world_hour,
            ambient_hour=ambient_hour,
            weather_rain=rain,
            source=self.source,
            from_cache=self.from_cache,
            stale=self.stale,
            looped=(i == self._looped_index),
            finished=self._finished,
        )

    def warmup_history(self) -> dict[str, list[Bar]]:
        """Bars before the replay start, used to prime indicators."""
        end = max(0, self._start_offset)
        out: dict[str, list[Bar]] = {}
        for symbol, series in self._bars.items():
            out[symbol] = series[:end]
        return out

    def history(self, limit: int = 240) -> dict:
        """Aligned bar history ending at the current replay index."""
        if not self._total_bars:
            return {"times": [], "bars": {}}
        end = max(0, min(self._index + 1, self._total_bars))
        start = max(0, end - max(1, limit))
        times = self._times[start:end]
        return {
            "times": [t.isoformat() for t in times],
            "bars": {
                symbol: [bar.to_payload() for bar in series[start:end]]
                for symbol, series in self._bars.items()
            },
            "index": self._index,
            "totalBars": self._total_bars,
        }

    def progress(self) -> float:
        if not self._total_bars:
            return 0.0
        span = max(self._total_bars - self._start_offset, 1)
        return min(1.0, max(0.0, (self._index - self._start_offset) / span))

    def load_snapshot(self, payload: dict, label: str | None = None) -> None:
        """Load a frozen, previously validated cache payload without network I/O."""
        original = str(payload.get("source", "unknown"))
        self._install_from_cache(payload, stale=False)
        if not self.loaded:
            raise RuntimeError("snapshot could not be installed")
        self.source = label or f"snapshot:{original}"
        self.from_cache = False
        self.stale = False
        self.warnings = []

    def source_info(self) -> dict:
        return {
            "source": self.source,
            "fromCache": self.from_cache,
            "stale": self.stale,
            "loadedAt": datetime.fromtimestamp(self.loaded_at, tz=timezone.utc).isoformat() if self.loaded_at else None,
            "warnings": list(self.warnings),
            "droppedSymbols": list(self.dropped_symbols),
            "interval": self.interval,
            "daysBack": self.days_back,
            "totalBars": self._total_bars,
            "barsPerDay": self._bars_per_day,
            "timezone": MARKET_TZ,
        }

    # ── load orchestration ───────────────────────────────────

    def _load_all(self, force: bool = False) -> None:
        cached = self._read_cache()
        requested = DATA_SOURCE if DATA_SOURCE in {"yfinance", "yahoo_chart", "ifind", "alphavantage", "synthetic", "auto"} else "auto"

        if requested == "synthetic":
            self._generate_synthetic()
            return

        # A fresh real cache makes startup instant and resilient to API outages.
        if (
            not force
            and cached
            and cached["source"] != "synthetic"
            and self._cache_age(cached) <= CACHE_TTL_SEC
            and requested == "auto"
        ):
            self._install_from_cache(cached, stale=False)
            return

        attempts: list[str] = []
        if requested == "auto":
            attempts = ["yfinance", "yahoo_chart"]
            if ifind_available():
                attempts.append("ifind")
        elif requested == "alphavantage" or (requested == "auto" and ALPHA_VANTAGE_API_KEY):
            attempts.append("alphavantage")
        else:
            attempts.append(requested)

        for source in attempts:
            try:
                if source == "yfinance":
                    self._load_yfinance()
                elif source == "yahoo_chart":
                    self._load_yahoo_chart()
                elif source == "ifind":
                    self._load_ifind()
                elif source == "alphavantage":
                    self._load_alpha_vantage()
                if self.loaded:
                    self._write_cache()
                    return
            except Exception as exc:  # noqa: BLE001 - fall through to next source
                self.warnings.append(f"{source}: {exc}")
                print(f"[market] {source} failed: {exc}")

        # Any cache beats synthetic, even if stale.
        if cached:
            self._install_from_cache(cached, stale=self._cache_age(cached) > CACHE_TTL_SEC)
            if self.loaded:
                return

        self._generate_synthetic()

    def _load_from_cache_or_synthetic(self, force: bool) -> None:
        cached = self._read_cache()
        if cached:
            self._install_from_cache(cached, stale=True)
        else:
            self._generate_synthetic()

    # ── real sources ─────────────────────────────────────────

    def _date_window(self) -> tuple[datetime, datetime]:
        end = datetime.now(tz=timezone.utc)
        # Intraday intervals cover fewer calendar days than trading days.
        calendar_days = int(self.days_back * 1.9) + 4
        if self.interval == "1m":
            calendar_days = min(calendar_days, 7)
        start = end - timedelta(days=calendar_days)
        return start, end

    def _fetch_with_retries(self, fn, label: str):
        last_err: Exception | None = None
        for attempt in range(max(1, DATA_RETRIES)):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                sleep_for = min(8.0, 0.8 * (2 ** attempt)) + random.uniform(0, 0.4)
                print(f"[market] {label} attempt {attempt + 1} failed: {exc}; retrying in {sleep_for:.1f}s")
                time.sleep(sleep_for)
        raise last_err or RuntimeError(f"{label} failed")

    def _load_yfinance(self) -> None:
        start, end = self._date_window()

        def fetch():
            return yf.download(
                tickers=" ".join(self.symbols),
                start=start,
                end=end,
                interval=self.interval,
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
                prepost=False,
            )

        df = self._fetch_with_retries(fetch, "yfinance")
        frames: dict[str, pd.DataFrame] = {}
        if df is None or df.empty:
            raise RuntimeError("empty frame")

        is_multi = isinstance(df.columns, pd.MultiIndex)
        for symbol in self.symbols:
            try:
                if is_multi:
                    if symbol not in df.columns.get_level_values(0):
                        continue
                    sub = df[symbol]
                else:
                    sub = df
                clean = self._clean_frame(sub, "UTC")
                if len(clean) >= 20:
                    frames[symbol] = clean
            except Exception as exc:  # noqa: BLE001
                self.warnings.append(f"{symbol}: {exc}")

        if len(frames) < min(3, len(self.symbols)):
            raise RuntimeError(f"only {len(frames)} symbols usable")
        self._install_from_frames(frames, "yfinance")

    def _load_yahoo_chart(self) -> None:
        start, end = self._date_window()
        period1 = int(start.timestamp())
        period2 = int(end.timestamp())
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m"}
        yf_interval = interval_map.get(self.interval, "5m")
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentStreet/2.0)"}

        frames: dict[str, pd.DataFrame] = {}
        for symbol in self.symbols:
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                f"?period1={period1}&period2={period2}"
                f"&interval={yf_interval}&includePrePost=false&events=div%2Csplits"
            )
            try:
                resp = requests.get(url, headers=headers, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                result = data["chart"]["result"][0]
                timestamps = result.get("timestamp") or []
                quote = result["indicators"]["quote"][0]
                rows = []
                for idx, ts in enumerate(timestamps):
                    close = quote["close"][idx]
                    if close is None:
                        continue
                    rows.append({
                        "time": datetime.fromtimestamp(ts, tz=timezone.utc),
                        "Open": quote["open"][idx] if quote["open"][idx] is not None else close,
                        "High": quote["high"][idx] if quote["high"][idx] is not None else close,
                        "Low": quote["low"][idx] if quote["low"][idx] is not None else close,
                        "Close": close,
                        "Volume": quote["volume"][idx] or 0,
                    })
                if len(rows) >= 20:
                    frame = pd.DataFrame(rows).set_index("time")
                    frames[symbol] = self._clean_frame(frame, "UTC")
            except Exception as exc:  # noqa: BLE001
                self.warnings.append(f"yahoo_chart {symbol}: {exc}")

        if len(frames) < min(3, len(self.symbols)):
            raise RuntimeError(f"only {len(frames)} symbols usable")
        self._install_from_frames(frames, "yahoo_chart")

    def _load_ifind(self) -> None:
        if not ifind_available():
            raise RuntimeError("credentials not configured")
        frames: dict[str, pd.DataFrame] = {}
        for symbol in self.symbols:
            bars = ifind_fetch_history(symbol, self.days_back, self.interval)
            if not bars:
                continue
            frame = pd.DataFrame([
                {
                    "time": b["time"],
                    "Open": b["open"], "High": b["high"], "Low": b["low"],
                    "Close": b["close"], "Volume": b["volume"],
                }
                for b in bars
            ]).set_index("time")
            frames[symbol] = self._clean_frame(frame, IFIND_TZ)
        if len(frames) < min(3, len(self.symbols)):
            raise RuntimeError(f"only {len(frames)} symbols usable")
        self._install_from_frames(frames, "ifind")

    def _load_alpha_vantage(self) -> None:
        key = ALPHA_VANTAGE_API_KEY
        if not key or key == "demo":
            raise RuntimeError("no API key")
        interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min"}
        av_interval = interval_map.get(self.interval, "5min")
        frames: dict[str, pd.DataFrame] = {}
        for idx, symbol in enumerate(self.symbols):
            if idx:
                time.sleep(1.0)
            url = (
                "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY"
                f"&symbol={symbol}&interval={av_interval}&outputsize=full&apikey={key}"
            )
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            series = payload.get(f"Time Series ({av_interval})")
            if not series:
                continue
            rows = [
                {
                    "time": datetime.fromisoformat(ts),
                    "Open": float(v["1. open"]), "High": float(v["2. high"]),
                    "Low": float(v["3. low"]), "Close": float(v["4. close"]),
                    "Volume": float(v["5. volume"]),
                }
                for ts, v in series.items()
            ]
            frame = pd.DataFrame(rows).set_index("time").sort_index()
            frames[symbol] = self._clean_frame(frame, MARKET_TZ)
        if len(frames) < min(3, len(self.symbols)):
            raise RuntimeError(f"only {len(frames)} symbols usable")
        self._install_from_frames(frames, "alphavantage")

    # ── cleaning & alignment ─────────────────────────────────

    def _clean_frame(self, df: pd.DataFrame, source_tz: str) -> pd.DataFrame:
        if df is None or df.empty:
            raise ValueError("empty frame")
        rename = {}
        for col in df.columns:
            key = str(col).strip().lower()
            if key in {"open", "high", "low", "close", "volume"}:
                rename[col] = key.capitalize()
        df = df.rename(columns=rename)
        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"missing columns {missing}")

        out = df[required].copy()
        out = out.apply(pd.to_numeric, errors="coerce")
        out = out.replace([float("inf"), float("-inf")], float("nan")).dropna()
        if out.empty:
            raise ValueError("no valid rows")

        index = pd.DatetimeIndex(out.index)
        if index.tz is None:
            index = index.tz_localize(source_tz)
        out.index = index.tz_convert(timezone.utc)
        out = out[~out.index.duplicated(keep="last")].sort_index()

        # Basic sanity filters.
        out = out[(out[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
        out = out[out["Volume"] >= 0]
        out["High"] = out[["Open", "High", "Low", "Close"]].max(axis=1)
        out["Low"] = out[["Open", "High", "Low", "Close"]].min(axis=1)
        # Rows whose wick is absurdly far from the body are bad prints.
        ratio_hi = out["High"] / out["Close"]
        ratio_lo = out["Low"] / out["Close"]
        out = out[(ratio_hi < 1.6) & (ratio_lo > 0.625)]
        if out.empty:
            raise ValueError("all rows filtered")
        return out

    def _install_from_frames(self, frames: dict[str, pd.DataFrame], source: str) -> None:
        indexes = [set(df.index) for df in frames.values()]
        common = sorted(set.intersection(*indexes))
        if len(common) < 20:
            # Rare gaps (halts, late starts): forward-fill at most two bars.
            union = sorted(set().union(*indexes))
            merged = {sym: df.reindex(union).ffill(limit=2) for sym, df in frames.items()}
            common = []
            for ts in union:
                if all(not merged[sym].loc[ts].isna().any() for sym in merged):
                    common.append(ts)
        if len(common) < 20:
            raise RuntimeError(f"only {len(common)} aligned bars")

        # Trim to the requested number of trading days.
        local_dates = sorted({ts.astimezone(self._market_tz).date() for ts in common})
        keep_dates = set(local_dates[-max(1, self.days_back):])
        times = [ts for ts in common if ts.astimezone(self._market_tz).date() in keep_dates]
        if len(times) < 20:
            times = common

        bars_by_symbol: dict[str, list[Bar]] = {}
        for symbol, df in frames.items():
            bars: list[Bar] = []
            for ts in times:
                row = df.loc[ts]
                bars.append(Bar(
                    time=ts.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                ))
            bars_by_symbol[symbol] = bars

        self._install(times, bars_by_symbol, source)

    def _install(
        self,
        times: list[datetime],
        bars_by_symbol: dict[str, list[Bar]],
        source: str,
        *,
        from_cache: bool = False,
        stale: bool = False,
        loaded_at: float | None = None,
    ) -> None:
        usable = {s: b for s, b in bars_by_symbol.items() if len(b) == len(times) and len(b) >= 20}
        if len(usable) < min(3, len(self.symbols)):
            raise RuntimeError(f"not enough usable symbols ({len(usable)})")

        self.dropped_symbols = [s for s in self.symbols if s not in usable]
        self.symbols = [s for s in self.symbols if s in usable]
        self._times = list(times)
        self._bars = usable
        self._total_bars = len(times)
        self._session_opens = {s: self._compute_session_opens(bars) for s, bars in usable.items()}
        self._bars_per_day = self._compute_bars_per_day(times)
        self._start_offset = min(WARMUP_BARS, max(0, self._total_bars - 2))
        self._index = self._start_offset
        self._looped_index = -1
        self._finished = False
        self.source = source
        self.from_cache = from_cache
        self.stale = stale
        self.loaded_at = loaded_at or time.time()
        self.loaded = True

    def _compute_session_opens(self, bars: list[Bar]) -> list[float]:
        opens: list[float] = []
        current_date = None
        current_open = bars[0].open if bars else 0.0
        for bar in bars:
            local_date = bar.time.astimezone(self._market_tz).date()
            if local_date != current_date:
                current_date = local_date
                current_open = bar.open
            opens.append(current_open)
        return opens

    def _compute_bars_per_day(self, times: list[datetime]) -> int:
        if not times:
            return 78
        counts: dict[Any, int] = {}
        for ts in times:
            day = ts.astimezone(self._market_tz).date()
            counts[day] = counts.get(day, 0) + 1
        values = sorted(counts.values())
        return values[len(values) // 2] if values else 78

    # ── cache ────────────────────────────────────────────────

    def _cache_path(self) -> Path:
        key = "|".join(self._universe) + f"|{self.interval}|{self.days_back}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return CACHE_DIR / f"bars_{self.interval}_{self.days_back}d_{digest}.json"

    def _cache_age(self, cached: dict) -> float:
        return max(0.0, time.time() - float(cached.get("created_at", 0)))

    def _read_cache(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") != 2:
                return None
            if payload.get("interval") != self.interval:
                return None
            if not payload.get("bars") or not payload.get("times"):
                return None
            return payload
        except Exception as exc:  # noqa: BLE001
            print(f"[market] cache read failed: {exc}")
            return None

    def _write_cache(self) -> None:
        try:
            payload = {
                "version": 2,
                "created_at": time.time(),
                "interval": self.interval,
                "days_back": self.days_back,
                "source": self.source,
                "symbols": self.symbols,
                "times": [t.isoformat() for t in self._times],
                "bars": {
                    symbol: [
                        [b.open, b.high, b.low, b.close, b.volume]
                        for b in series
                    ]
                    for symbol, series in self._bars.items()
                },
            }
            path = self._cache_path()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[market] cache write failed: {exc}")

    def _install_from_cache(self, cached: dict, stale: bool) -> None:
        try:
            times = [datetime.fromisoformat(t) for t in cached["times"]]
            bars_by_symbol: dict[str, list[Bar]] = {}
            for symbol, rows in cached["bars"].items():
                if len(rows) != len(times):
                    continue
                bars_by_symbol[symbol] = [
                    Bar(
                        time=times[i],
                        open=float(row[0]), high=float(row[1]),
                        low=float(row[2]), close=float(row[3]),
                        volume=float(row[4]),
                    )
                    for i, row in enumerate(rows)
                ]
            self._install(
                times, bars_by_symbol, cached.get("source", "cache"),
                from_cache=True, stale=stale,
                loaded_at=float(cached.get("created_at", time.time())),
            )
            if stale:
                self.warnings.append("using stale cached data")
        except Exception as exc:  # noqa: BLE001
            print(f"[market] cache install failed: {exc}")
            self.loaded = False

    # ── synthetic fallback ───────────────────────────────────

    def _generate_synthetic(self) -> None:
        """Correlated geometric random walk on real market-session timestamps.

        A single shared market-return series drives every symbol, so breadth,
        dispersion and correlated drawdowns behave like a real cross-section
        instead of five unrelated walks.
        """
        rng = random.Random(SIM_SEED or time.time_ns())
        minutes = INTERVAL_MINUTES.get(self.interval, 5)
        days = self._trading_days(self.days_back)
        times: list[datetime] = []
        for day in days:
            session_start = datetime(day.year, day.month, day.day, 9, 30, tzinfo=self._market_tz)
            session_end = datetime(day.year, day.month, day.day, 16, 0, tzinfo=self._market_tz)
            cursor = session_start
            while cursor < session_end:
                times.append(cursor.astimezone(timezone.utc))
                cursor += timedelta(minutes=minutes)

        # One shared market factor for the whole cross-section.
        market_returns: list[float] = []
        market_vols: list[float] = []
        u_shapes: list[float] = []
        market_vol = 0.0007
        drift = 0.0
        regime_left = 0
        for ts in times:
            if regime_left <= 0:
                regime_left = rng.randint(25, 90)
                market_vol = rng.choice([0.0006, 0.0008, 0.0011, 0.0015, 0.0022])
                drift = rng.gauss(0.0, 0.00004)
            regime_left -= 1

            local = ts.astimezone(self._market_tz)
            frac = (local.hour * 60 + local.minute - 570) / 390.0
            u_shape = 0.65 + 0.9 * (frac - 0.5) ** 2 * 4

            market_ret = rng.gauss(drift, market_vol * u_shape)
            if rng.random() < 0.004:
                market_ret += rng.gauss(0.0, 0.0015)
            market_returns.append(market_ret)
            market_vols.append(market_vol)
            u_shapes.append(u_shape)

        profiles = {
            "AAPL": (300, 1.15, 0.00040),
            "GOOGL": (390, 1.20, 0.00048),
            "MSFT": (420, 1.00, 0.00036),
            "TSLA": (415, 1.70, 0.00085),
            "AMZN": (265, 1.30, 0.00055),
            "NVDA": (1200, 1.80, 0.00095),
            "META": (600, 1.25, 0.00058),
        }

        bars_by_symbol: dict[str, list[Bar]] = {}
        for symbol_index, symbol in enumerate(self.symbols):
            base, beta, idio = profiles.get(
                symbol,
                (50 + (sum((i + 1) * ord(ch) for i, ch in enumerate(symbol)) % 400), 1.15, 0.00048),
            )
            sym_rng = random.Random((SIM_SEED or 0) * 7919 + symbol_index * 104729 + 17)
            price = float(base) * sym_rng.uniform(0.97, 1.03)
            bars: list[Bar] = []
            for i, ts in enumerate(times):
                ret = beta * market_returns[i] + sym_rng.gauss(0.0, idio * u_shapes[i])
                gap = sym_rng.gauss(0.0, 0.0003)
                open_p = price * (1.0 + gap)
                close_p = open_p * math.exp(ret)
                wick = abs(sym_rng.gauss(0.0, market_vols[i] * 0.9 + idio * 0.7))
                high = max(open_p, close_p) * (1.0 + wick)
                low = min(open_p, close_p) * (1.0 - wick)
                volume = int(
                    abs(sym_rng.gauss(1.0, 0.35)) * 90_000 * u_shapes[i]
                    * (1.0 + 6.0 * abs(ret) / 0.002)
                )
                volume = max(1000, min(volume, 5_000_000))
                price = close_p
                bars.append(Bar(
                    time=ts,
                    open=round(open_p, 4), high=round(high, 4),
                    low=round(max(low, 0.01), 4), close=round(close_p, 4),
                    volume=volume,
                ))
            bars_by_symbol[symbol] = bars

        self.warnings.append(
            "SYNTHETIC DATA — live market data could not be loaded. "
            "Prices are a correlated random walk for demonstration only."
        )
        self._install(times, bars_by_symbol, "synthetic")

    def _trading_days(self, count: int) -> list:
        day = datetime.now(tz=self._market_tz).date()
        out = []
        while len(out) < max(1, count):
            if day.weekday() < 5:
                out.append(day)
            day -= timedelta(days=1)
        return list(reversed(out))

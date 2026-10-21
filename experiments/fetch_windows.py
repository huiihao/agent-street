#!/usr/bin/env python
"""Freeze and validate the six held-out five-session market windows.

The script fetches each window from yfinance, cleans/aligns it with the
production provider, writes the snapshot in the same format as the discovery
window, and optionally re-fetches every symbol from the Yahoo chart endpoint
for an exact close-by-close cross-check.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import SYMBOLS  # noqa: E402
from backend.engine.market_data import HistoricalDataProvider  # noqa: E402

WINDOWS = [
    ("w1_2026_08_24", "2026-08-24", "2026-08-29"),
    ("w2_2026_08_31", "2026-08-31", "2026-09-05"),
    ("w3_2026_09_14", "2026-09-14", "2026-09-19"),
    ("w4_2026_09_21", "2026-09-21", "2026-09-26"),
    ("w5_2026_09_28", "2026-09-28", "2026-10-03"),
    ("w6_2026_10_05", "2026-10-05", "2026-10-10"),
]
DATA_DIR = ROOT / "experiments" / "data" / "windows"


def fetch_window(name: str, start: str, end: str):
    provider = HistoricalDataProvider(symbols=SYMBOLS, days_back=5, interval="5m")
    frame = yf.download(
        tickers=" ".join(SYMBOLS), start=start, end=end, interval="5m",
        group_by="ticker", auto_adjust=False, progress=False, threads=True,
        prepost=False,
    )
    if frame is None or frame.empty:
        raise RuntimeError("empty yfinance frame")
    frames = {}
    multi = isinstance(frame.columns, pd.MultiIndex)
    for symbol in SYMBOLS:
        try:
            sub = frame[symbol] if multi else frame
            clean = provider._clean_frame(sub, "UTC")
            if len(clean) >= 20:
                frames[symbol] = clean
        except Exception as exc:
            print(f"  {name} {symbol}: {exc}")
    if len(frames) < 3:
        raise RuntimeError(f"only {len(frames)} usable symbols")
    provider._install_from_frames(frames, f"yfinance:{name}")
    if not provider.loaded or provider.total_bars < 100:
        raise RuntimeError("alignment produced too few bars")

    times = provider._times
    bars = provider._bars
    closes = {
        symbol: [bar.close for bar in series]
        for symbol, series in bars.items()
    }
    equal_weight = [
        sum(closes[s][i] / closes[s][0] for s in closes) / len(closes)
        for i in range(len(times))
    ]
    returns = [
        (equal_weight[i] - equal_weight[i - 1]) / equal_weight[i - 1]
        for i in range(1, len(equal_weight))
    ]
    peak, max_drawdown = equal_weight[0], 0.0
    for value in equal_weight:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sessions = sorted({
        t.astimezone(provider._market_tz).date().isoformat() for t in times
    })
    payload = {
        "version": 2,
        "created_at": time.time(),
        "interval": "5m",
        "days_back": 5,
        "source": f"yfinance:{name}",
        "symbols": list(bars),
        "times": [t.isoformat() for t in times],
        "bars": {
            symbol: [[b.open, b.high, b.low, b.close, b.volume] for b in series]
            for symbol, series in bars.items()
        },
    }
    directory = DATA_DIR / name
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / "market_snapshot_5m_5d.json"
    snapshot.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()

    validation = {
        "bars": len(times),
        "sessions": sessions,
        "symbols": list(bars),
        "aligned_lengths": {s: len(v) for s, v in bars.items()},
        "monotonic_timestamps": all(
            times[i] < times[i + 1] for i in range(len(times) - 1)
        ),
        "duplicate_timestamps": len(times) - len(set(times)),
        "nonpositive_prices": 0,
        "ohlc_inconsistencies": 0,
        "negative_volumes": 0,
    }
    for series in bars.values():
        for bar in series:
            if not (bar.open > 0 and bar.high > 0 and bar.low > 0 and bar.close > 0):
                validation["nonpositive_prices"] += 1
            if not (
                bar.high >= max(bar.open, bar.close)
                and bar.low <= min(bar.open, bar.close)
            ):
                validation["ohlc_inconsistencies"] += 1
            if bar.volume < 0:
                validation["negative_volumes"] += 1
    meta = {
        "snapshot_file": str(snapshot.as_posix()),
        "sha256": digest,
        "source": f"yfinance:{name}",
        "interval": "5m",
        "days_back": 5,
        "bars": len(times),
        "first_utc": times[0].isoformat(),
        "last_utc": times[-1].isoformat(),
        "sessions": sessions,
        "equal_weight_return": equal_weight[-1] - 1.0,
        "equal_weight_max_drawdown": max_drawdown,
        "equal_weight_annualized_vol": volatility * (78 * 252) ** 0.5,
        "per_symbol_return": {
            symbol: closes[symbol][-1] / closes[symbol][0] - 1.0
            for symbol in closes
        },
        "validation": validation,
        "crosscheck": {},
    }
    (directory / "snapshot_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8",
    )
    print(
        f"{name}: bars={len(times)} sessions={len(sessions)} "
        f"ret={meta['equal_weight_return']:+.3%} dd={max_drawdown:.3%} "
        f"vol={meta['equal_weight_annualized_vol']:.2%}"
    )
    return meta, payload, provider


def crosscheck(meta, payload, provider):
    times = [datetime.fromisoformat(t) for t in payload["times"]]
    period1 = int(times[0].timestamp()) - 300
    period2 = int(times[-1].timestamp()) + 300
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentStreetResearch/1.0)"}
    for symbol in payload["symbols"]:
        local = {
            datetime.fromisoformat(t): row[3]
            for t, row in zip(payload["times"], payload["bars"][symbol])
        }
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            try:
                url = (
                    f"https://{host}/v8/finance/chart/{symbol}"
                    f"?period1={period1}&period2={period2}&interval=5m&includePrePost=false"
                )
                response = requests.get(url, headers=headers, timeout=25)
                response.raise_for_status()
                result = response.json()["chart"]["result"][0]
                ts = result.get("timestamp") or []
                remote_closes = result["indicators"]["quote"][0]["close"]
                remote = {
                    datetime.fromtimestamp(t, tz=timezone.utc): c
                    for t, c in zip(ts, remote_closes) if c is not None
                }
                common = sorted(set(local) & set(remote))
                differences = [
                    abs(remote[t] - local[t]) / local[t] for t in common
                ]
                meta["crosscheck"][symbol] = {
                    "common_bars": len(common),
                    "max_relative_difference": max(differences) if differences else None,
                }
                break
            except Exception as exc:
                time.sleep(1.0)
                meta["crosscheck"][symbol] = {"error": str(exc)}
    path = Path(meta["snapshot_file"]).parent / "snapshot_metadata.json"
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    exact = all(
        item.get("max_relative_difference") == 0.0
        for item in meta["crosscheck"].values()
    )
    print(f"  crosscheck exact={exact}")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, start, end in WINDOWS:
        try:
            meta, payload, provider = fetch_window(name, start, end)
            crosscheck(meta, payload, provider)
        except Exception as exc:
            print(f"{name}: FAILED {exc}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()

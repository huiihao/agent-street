import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from backend.engine.market_data import HistoricalDataProvider


def frame(times, base=100.0, step=0.1):
    rows = []
    price = base
    for i, ts in enumerate(times):
        o = price
        price = price + step
        rows.append({
            "Open": o, "High": max(o, price) + 0.05,
            "Low": min(o, price) - 0.05, "Close": price,
            "Volume": 1000 + i,
        })
    return pd.DataFrame(rows, index=pd.DatetimeIndex(times))


class MarketDataTests(unittest.TestCase):
    def test_clean_frame_fixes_ohlc_and_timezone(self):
        provider = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=1, interval="5m")
        times = pd.date_range("2026-01-05 09:30", periods=10, freq="5min")
        df = frame(times)
        df["High"] = df["Close"] - 1.0       # deliberately invalid
        df["Low"] = df["Close"] + 1.0        # deliberately invalid
        df.loc[times[2], "Close"] = float("nan")
        df = pd.concat([df, df.iloc[[3]]])   # duplicate timestamp

        clean = provider._clean_frame(df, "America/New_York")
        self.assertTrue(str(clean.index.tz) in {"UTC", "UTC+00:00"})
        self.assertEqual(clean.index.duplicated().sum(), 0)
        self.assertFalse(clean.isna().any().any())
        self.assertTrue((clean["High"] >= clean[["Open", "Close"]].max(axis=1)).all())
        self.assertTrue((clean["Low"] <= clean[["Open", "Close"]].min(axis=1)).all())

    def test_install_aligns_on_intersection(self):
        provider = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=1, interval="5m")
        times = pd.date_range("2026-01-05 09:30", periods=40, freq="5min", tz="UTC")
        missing = times.delete(10)
        frames = {
            "AAA": provider._clean_frame(frame(times), "UTC"),
            "BBB": provider._clean_frame(frame(missing), "UTC"),
            "CCC": provider._clean_frame(frame(times), "UTC"),
        }
        provider._install_from_frames(frames, "test")
        self.assertEqual(provider.total_bars, 39)
        snap = provider.snapshot()
        self.assertEqual(set(snap.bars), {"AAA", "BBB", "CCC"})
        for symbol_bars in provider._bars.values():
            self.assertEqual(len(symbol_bars), 39)
        # All symbols share exactly the same timestamps.
        stamps = [[b.time for b in bars] for bars in provider._bars.values()]
        self.assertTrue(all(stamps[0] == stamps[i] for i in range(1, len(stamps))))

    def test_synthetic_fallback_is_valid_and_aligned(self):
        provider = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=2, interval="5m")
        provider._generate_synthetic()
        self.assertTrue(provider.loaded)
        self.assertEqual(provider.source, "synthetic")
        self.assertEqual(provider.total_bars, 2 * 78)
        self.assertTrue(any("SYNTHETIC" in w for w in provider.warnings))
        snap = provider.snapshot()
        self.assertEqual(len(snap.bars), 3)
        for bar in snap.bars.values():
            self.assertGreater(bar.low, 0)
            self.assertGreaterEqual(bar.high, max(bar.open, bar.close))
            self.assertLessEqual(bar.low, min(bar.open, bar.close))
            self.assertGreaterEqual(bar.volume, 1000)
        self.assertAlmostEqual(sum(snap.day_changes.values()) / 3, 0.0, delta=0.2)

    def test_synthetic_has_correlated_cross_section(self):
        provider = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=3, interval="5m")
        provider._generate_synthetic()
        times = provider._times
        shared = 0
        total = 0
        for i in range(1, len(times)):
            rets = []
            for symbol in provider.symbols:
                bars = provider._bars[symbol]
                rets.append(math.log(bars[i].close / bars[i - 1].close))
            signs = [1 if r > 0 else -1 for r in rets]
            if len(set(signs)) == 1:
                shared += 1
            total += 1
        # A shared market factor should make all symbols move together far more
        # often than the ~25% expected from independent coin flips.
        self.assertGreater(shared / total, 0.35)

    def test_cache_roundtrip(self):
        provider = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=2, interval="5m")
        provider._generate_synthetic()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.json"
            provider._cache_path = lambda: path
            provider._write_cache()
            self.assertTrue(path.exists())
            cached = provider._read_cache()
            self.assertIsNotNone(cached)
            self.assertEqual(cached["source"], "synthetic")
            self.assertEqual(len(cached["times"]), provider.total_bars)

            restored = HistoricalDataProvider(symbols=["AAA", "BBB", "CCC"], days_back=2, interval="5m")
            restored._cache_path = lambda: path
            restored._install_from_cache(cached, stale=False)
            self.assertTrue(restored.loaded)
            self.assertTrue(restored.from_cache)
            self.assertEqual(restored.total_bars, provider.total_bars)


if __name__ == "__main__":
    unittest.main()

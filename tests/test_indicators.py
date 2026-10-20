import math
import unittest
from datetime import datetime, timedelta, timezone

from backend.engine.indicators import IndicatorEngine
from backend.engine.market_data import Bar


def make_bars(prices, start=None, spread=0.002):
    start = start or datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    bars = []
    prev = prices[0]
    for i, price in enumerate(prices):
        o = prev
        c = price
        h = max(o, c) * (1 + spread)
        l = min(o, c) * (1 - spread)
        bars.append(Bar(
            time=start + timedelta(minutes=5 * i),
            open=o, high=h, low=l, close=c, volume=1000 + i,
        ))
        prev = price
    return bars


class IndicatorTests(unittest.TestCase):
    def test_uptrend_has_positive_momentum(self):
        prices = [100 * math.exp(0.001 * i) for i in range(80)]
        engine = IndicatorEngine(["AAA"])
        bars = make_bars(prices)
        metrics = None
        for bar in bars:
            metrics = engine.update({"AAA": bar})
        m = metrics.symbols["AAA"]
        self.assertGreater(m.trend_score, 0.3)
        self.assertGreater(m.rsi_14, 50)
        self.assertGreater(m.mom_5, 0)
        self.assertBetween(m.trend_score, -1, 1)
        self.assertBetween(m.reversion_score, -1, 1)

    def test_downtrend_has_negative_momentum(self):
        prices = [100 * math.exp(-0.0015 * i) for i in range(80)]
        engine = IndicatorEngine(["AAA"])
        metrics = None
        for bar in make_bars(prices):
            metrics = engine.update({"AAA": bar})
        m = metrics.symbols["AAA"]
        self.assertLess(m.trend_score, -0.3)
        self.assertLess(m.rsi_14, 50)

    def test_duplicate_timestamp_is_ignored(self):
        prices = [100 + i * 0.2 for i in range(40)]
        engine = IndicatorEngine(["AAA"])
        bars = make_bars(prices)
        for bar in bars:
            engine.update({"AAA": bar})
        window = engine._windows["AAA"]
        before = len(window.closes)
        engine.update({"AAA": bars[-1]})  # same timestamp
        self.assertEqual(len(window.closes), before)

    def test_market_metrics_are_bounded(self):
        engine = IndicatorEngine(["AAA", "BBB", "CCC"])
        aaa = make_bars([100 + i * 0.1 for i in range(60)])
        bbb = make_bars([50 - i * 0.05 for i in range(60)])
        ccc = make_bars([75 + (i % 3) * 0.1 for i in range(60)])
        metrics = None
        for a, b, c in zip(aaa, bbb, ccc):
            metrics = engine.update({"AAA": a, "BBB": b, "CCC": c})
        self.assertBetween(metrics.breadth, -1, 1)
        self.assertGreaterEqual(metrics.dispersion, 0)
        self.assertIn(metrics.regime, {"calm", "volatile", "risk-on", "risk-off", "mixed"})

    def assertBetween(self, value, lo, hi):
        self.assertGreaterEqual(value, lo)
        self.assertLessEqual(value, hi)


if __name__ == "__main__":
    unittest.main()

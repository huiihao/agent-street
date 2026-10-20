import unittest
from datetime import datetime, timezone

from backend.engine.market_data import Bar, MarketSnapshot
from backend.engine.matching_engine import HouseState, MatchingEngine
from backend.models.portfolio import Holding, PersonaState, TradeIntent


T0 = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def snapshot(prices, changes=None):
    bars = {
        symbol: Bar(T0, price, price, price, price, 100_000)
        for symbol, price in prices.items()
    }
    return MarketSnapshot(
        index=0, total_bars=1, bars=bars,
        prev_close=dict(prices), session_open=dict(prices),
        changes=changes or {s: 0.0 for s in prices},
        day_changes={s: 0.0 for s in prices},
        world_time=T0, world_hour=12.0, ambient_hour=12.0,
        weather_rain=False, source="test", from_cache=False,
        stale=False, looped=False, finished=False,
    )


def persona(pid, cash=10_000.0, holdings=None):
    return PersonaState(
        persona_id=pid,
        cash=cash,
        holdings=holdings or {},
        trade_history=[],
        peak_equity=cash,
    )


def intent(pid, symbol, direction, shares, limit, reason="test", tick=0):
    return TradeIntent(pid, symbol, direction, shares, limit, reason, tick)


def wealth(personas, house, prices):
    agent = sum(
        p.cash + sum(h.shares * prices.get(h.symbol, h.avg_cost) for h in p.holdings.values())
        for p in personas.values()
    )
    h = house.cash + sum(q * prices.get(s, 0.0) for s, q in house.holdings.items())
    return agent + h + house.fees


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.engine = MatchingEngine(fee_bps=2.0, slippage_bps=3.0)
        self.house = HouseState()
        self.house.reset(["AAPL"])

    def test_cross_conserves_wealth_and_charges_fees(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 10, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 5, 101.0),
                intent("SELLER", "AAPL", "SELL", 5, 99.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(len(outcome.trades), 2)
        self.assertEqual(outcome.crossed_shares, 5)
        self.assertEqual(outcome.house_shares, 0)
        self.assertEqual(buyer.holdings["AAPL"].shares, 5)
        self.assertEqual(seller.holdings["AAPL"].shares, 5)
        self.assertAlmostEqual(buyer.holdings["AAPL"].avg_cost, 100.02)
        self.assertAlmostEqual(buyer.cash, 10_000 - 500 - 0.10, places=4)
        self.assertAlmostEqual(seller.cash, 10_000 + 500 - 0.10, places=4)
        self.assertAlmostEqual(seller.realized_pnl, -0.10, places=4)
        self.assertAlmostEqual(self.house.fees, 0.20, places=4)
        self.assertAlmostEqual(wealth(personas, self.house, {"AAPL": 100.0}), 21_000.0, places=4)

    def test_house_spread_and_invariant(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 10, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        buy_outcome = self.engine.match(
            [intent("BUYER", "AAPL", "BUY", 5, 101.0)],
            snap, personas, self.house,
        )
        sell_outcome = self.engine.match(
            [intent("SELLER", "AAPL", "SELL", 5, 99.0)],
            snap, personas, self.house,
        )

        self.assertEqual(buy_outcome.crossed_shares, 0)
        self.assertEqual(buy_outcome.house_shares, 5)
        self.assertEqual(sell_outcome.house_shares, 5)
        self.assertTrue(all(t.liquidity == "house" for t in buy_outcome.trades + sell_outcome.trades))
        self.assertEqual(buyer.holdings["AAPL"].shares, 5)
        self.assertEqual(seller.holdings["AAPL"].shares, 5)
        self.assertGreater(self.house.fees, 0)
        self.assertAlmostEqual(wealth(personas, self.house, {"AAPL": 100.0}), 21_000.0, places=4)

    def test_limit_outside_house_quote_is_rejected(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 10, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 5, 50.0),
                intent("SELLER", "AAPL", "SELL", 5, 150.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(outcome.trades, [])
        self.assertEqual(buyer.holdings, {})
        self.assertEqual(seller.holdings["AAPL"].shares, 10)
        self.assertEqual(outcome.rejected, 2)

    def test_partial_fill_limited_by_cash(self):
        buyer = persona("BUYER", cash=250.0)
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 10, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 10, 101.0),
                intent("SELLER", "AAPL", "SELL", 10, 99.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(buyer.holdings["AAPL"].shares, 2)
        self.assertNotIn("AAPL", seller.holdings)
        self.assertAlmostEqual(wealth(personas, self.house, {"AAPL": 100.0}), 11_250.0, places=4)

    def test_seller_never_oversells(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 3, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 10, 99.99),
                intent("SELLER", "AAPL", "SELL", 10, 99.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(buyer.holdings["AAPL"].shares, 3)
        self.assertNotIn("AAPL", seller.holdings)
        self.assertGreaterEqual(seller.cash, 10_000)

    def test_close_event_and_win_rate(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 10, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 5, 106.0),
                intent("SELLER", "AAPL", "SELL", 5, 104.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(len(outcome.closed_events), 1)
        event = outcome.closed_events[0]
        self.assertEqual(event.persona_id, "SELLER")
        self.assertEqual(event.symbol, "AAPL")
        self.assertEqual(event.shares, 5)
        self.assertAlmostEqual(event.entry_price, 100.0)
        self.assertAlmostEqual(event.exit_price, 105.0)
        self.assertGreater(event.realized_pnl, 0)
        self.assertEqual(seller.total_sells, 1)
        self.assertEqual(seller.winning_sells, 1)
        self.assertAlmostEqual(seller.realized_pnl, event.realized_pnl)

    def test_losing_close_is_not_a_win(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 5, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 5, 100.0),
                intent("SELLER", "AAPL", "SELL", 5, 98.0),
            ],
            snap, personas, self.house,
        )

        self.assertEqual(len(outcome.closed_events), 1)
        self.assertLess(outcome.closed_events[0].realized_pnl, 0)
        self.assertEqual(seller.total_sells, 1)
        self.assertEqual(seller.winning_sells, 0)

    def test_cross_executes_inside_both_limits(self):
        buyer = persona("BUYER")
        seller = persona("SELLER", holdings={"AAPL": Holding("AAPL", 5, 100.0)})
        personas = {"BUYER": buyer, "SELLER": seller}
        snap = snapshot({"AAPL": 100.0})

        outcome = self.engine.match(
            [
                intent("BUYER", "AAPL", "BUY", 5, 102.0),
                intent("SELLER", "AAPL", "SELL", 5, 98.0),
            ],
            snap, personas, self.house,
        )

        exec_prices = {t.price for t in outcome.trades}
        self.assertEqual(len(exec_prices), 1)
        price = exec_prices.pop()
        self.assertGreaterEqual(price, 98.0)
        self.assertLessEqual(price, 102.0)


if __name__ == "__main__":
    unittest.main()

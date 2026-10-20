import unittest
from types import SimpleNamespace

from backend.engine.strategy import (
    SIGNAL_GENES,
    StrategyEngine,
    genome_from_persona,
)
from backend.mbti.personas import PERSONA_DEFINITIONS


class StrategyTests(unittest.TestCase):
    def setUp(self):
        definition = PERSONA_DEFINITIONS["INTJ"]
        self.traits = definition["traits"]
        self.params = definition["params"]
        self.engine = StrategyEngine(10_000.0)
        self.genome = genome_from_persona(self.traits, self.params)
        self.engine.register("INTJ", self.genome)

    def test_prior_is_normalised_and_classified(self):
        self.assertAlmostEqual(sum(getattr(self.genome, gene) for gene in SIGNAL_GENES), 1.0, places=6)
        self.assertIn(
            self.genome.family,
            {"momentum", "mean_reversion", "sentiment", "contrarian", "balanced"},
        )
        self.assertEqual(self.genome.generation, 0)

    def test_profitable_trade_reinforces_supporting_signals(self):
        before = {gene: getattr(self.genome, gene) for gene in SIGNAL_GENES}
        event = SimpleNamespace(
            persona_id="INTJ",
            symbol="AAPL",
            shares=10,
            entry_price=100.0,
            realized_pnl=50.0,
            entry_context={
                "trend": 0.8,
                "reversion": 0.1,
                "rsi": 0.1,
                "herding": 0.0,
                "influence": 0.0,
                "memory": 0.0,
            },
        )
        self.engine.observe_closes([event], tick=7, locations={"INTJ": "lab"})
        self.assertGreater(self.genome.trend, before["trend"])
        self.assertEqual(self.genome.generation, 1)
        self.assertEqual(self.genome.adaptations, 1)
        self.assertGreater(self.genome.fitness, 0)
        self.assertEqual(self.genome.wins, 1)
        self.assertEqual(self.engine.closed_trades, 1)
        self.assertEqual(self.engine.total_adaptations, 1)
        self.assertAlmostEqual(sum(getattr(self.genome, gene) for gene in SIGNAL_GENES), 1.0, places=6)

    def test_losing_trade_downweights_supporting_signals(self):
        before = self.genome.trend
        event = SimpleNamespace(
            persona_id="INTJ",
            symbol="TSLA",
            shares=10,
            entry_price=100.0,
            realized_pnl=-50.0,
            entry_context={
                "trend": 0.8,
                "reversion": 0.0,
                "rsi": 0.0,
                "herding": 0.0,
                "influence": 0.0,
                "memory": 0.0,
            },
        )
        self.engine.observe_closes([event], tick=8, locations={"INTJ": "hall"})
        self.assertLess(self.genome.trend, before)
        self.assertEqual(self.genome.losses, 1)
        self.assertLess(self.genome.fitness, 0)

    def test_ecosystem_reports_guilds_and_adaptations(self):
        personas = {"INTJ": SimpleNamespace(equity=lambda prices: 10_100.0)}
        ecosystem = self.engine.ecosystem(personas, {"AAPL": 100.0})
        self.assertEqual(len(ecosystem["guilds"]), 1)
        self.assertEqual(ecosystem["guilds"][0]["count"], 1)
        self.assertEqual(ecosystem["dominant"], self.genome.family)
        self.assertIn("diversity", ecosystem)
        self.assertIn("generation", ecosystem)


if __name__ == "__main__":
    unittest.main()

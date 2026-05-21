"""Observer agents: Physicist, Mathematician, Mystic.

They don't trade. They watch the system and produce periodic reports
analyzing the coupling between agent behavior and market dynamics.
"""

import random
import math
from dataclasses import dataclass, field
from backend.models.portfolio import PersonaState, ExecutedTrade
from backend.engine.memory_system import AgentMemory


@dataclass
class ObserverReport:
    observer_id: str   # "physicist", "mathematician", "mystic"
    tick: int
    title: str
    content: str
    confidence: float  # physicist/mathematician: 0.7-1.0, mystic: 0.0-0.5


class ObserverEngine:
    def __init__(self):
        self._last_report_tick: dict[str, int] = {}
        self.reports: list[ObserverReport] = []

    def observe(
        self,
        observer_id: str,
        tick: int,
        prices: dict[str, float],
        changes: dict[str, float],
        personas: dict[str, PersonaState],
        memories: dict[str, AgentMemory],
        trades: list[ExecutedTrade],
        sentiment: float,
    ) -> ObserverReport | None:
        # Generate reports every 20 ticks per observer
        last = self._last_report_tick.get(observer_id, -100)
        if tick - last < 20:
            return None
        self._last_report_tick[observer_id] = tick

        if observer_id == "physicist":
            report = self._physicist_report(prices, changes, personas, trades, sentiment, tick)
        elif observer_id == "mathematician":
            report = self._mathematician_report(prices, personas, memories, trades, tick)
        elif observer_id == "mystic":
            report = self._mystic_report(prices, changes, personas, memories, sentiment, tick)
        else:
            return None

        self.reports.append(report)
        if len(self.reports) > 60:
            self.reports = self.reports[-60:]
        return report

    # ── Physicist ─────────────────────────────────────────────

    def _physicist_report(self, prices, changes, personas, trades, sentiment, tick):
        # Compute "order parameter" — how aligned agents' sentiment is
        moods = [
            p.portfolio_value(prices) / 10000.0 - 1.0
            for p in personas.values()
        ]
        avg_pnl = sum(moods) / max(len(moods), 1)
        variance = sum((m - avg_pnl) ** 2 for m in moods) / max(len(moods), 1)
        dispersion = math.sqrt(variance)

        # Detect "phase" based on alignment
        if dispersion < 0.01:
            if avg_pnl > 0:
                phase = "ordered — bullish consensus, high alignment. Susceptible to nucleation events."
            elif avg_pnl < -0.01:
                phase = "ordered — bearish consensus, the field is uniformly negative. A single fluctuation could trigger avalanche."
            else:
                phase = "critical point — the system sits exactly at the boundary. Maximum susceptibility."
        elif dispersion < 0.03:
            phase = "quasi-ordered — mild disagreement, correlation length decaying."
        else:
            phase = "disordered — high entropy, agents are decorrelated. Efficient market regime."

        # Energy analogy: sum of squared PnL changes
        recent_trade_count = len(trades)
        activity = "high" if recent_trade_count > 10 else "moderate" if recent_trade_count > 3 else "low"

        # Pick the most volatile symbol as "order parameter field"
        most_volatile = max(changes.items(), key=lambda x: abs(x[1])) if changes else ("?", 0)

        titles = [
            "A Note on Phase Transitions in Agent-Market Coupling",
            "Statistical Mechanics of a 16-Body Trading Ensemble",
            "On the Emergence of Collective Modes in Financial Microstructure",
            "Field Theory of Sentiment: A Mean-Field Approximation",
            "Correlation Functions and Critical Exponents in Agent Space",
        ]

        return ObserverReport(
            observer_id="physicist",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"Order parameter (mean PnL): {avg_pnl:.4f}. "
                f"Dispersion: {dispersion:.4f}. "
                f"Phase: {phase}. "
                f"Trading activity: {activity} ({recent_trade_count} events). "
                f"The {most_volatile[0]} field shows the strongest fluctuation "
                f"at |Δ| = {abs(most_volatile[1]):.3%}. "
                f"I expect the correlation length ξ ≈ {1.0/max(dispersion, 0.001):.0f} ticks."
            ),
            confidence=0.75 + random.uniform(-0.1, 0.1),
        )

    # ── Mathematician ─────────────────────────────────────────

    def _mathematician_report(self, prices, personas, memories, trades, tick):
        # Build a simple interaction graph: agents who traded the same symbol
        trade_symbols: dict[str, list[str]] = {}
        for t in trades:
            trade_symbols.setdefault(t.symbol, []).append(t.persona_id)

        # Find cliques (agents trading same symbol = connected component)
        components = []
        for sym, agents in trade_symbols.items():
            if len(set(agents)) >= 2:
                components.append((sym, len(set(agents))))

        num_components = len(components)
        max_clique_size = max((c[1] for c in components), default=0)

        # Agent diversity — how many unique strategies are active
        active_agents = len(set(
            t.persona_id for t in trades
        )) if trades else 0

        # Sentiment graph: count positive vs negative sentiment agents
        pos_count = sum(
            1 for m in memories.values()
            if m.get_sentiment() > 0.05
        )
        neg_count = sum(
            1 for m in memories.values()
            if m.get_sentiment() < -0.05
        )
        neutral_count = len(memories) - pos_count - neg_count

        # Optimization metric: trade diversity
        diversity = len(components) / max(len(trade_symbols), 1) if trade_symbols else 0

        titles = [
            "On the Connectivity of the Agent Interaction Graph",
            "A Combinatorial Analysis of Trading Coalition Formation",
            "Graph-Theoretic Measures of Market Fragmentation",
            "Optimal Transport Between Sentiment Clusters",
            "Spectral Properties of the Agent Correlation Matrix",
        ]

        return ObserverReport(
            observer_id="mathematician",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"Interaction graph: {num_components} connected components, "
                f"max clique size = {max_clique_size}. "
                f"Active agents: {active_agents}/16. "
                f"Sentiment distribution: ▮ {pos_count} bullish, ▮ {neg_count} bearish, "
                f"▬ {neutral_count} neutral. "
                f"Trade diversity index: {diversity:.2f}. "
                f"{'The graph is fragmenting — agents are forming isolated trading islands.' if diversity < 0.3 else 'The graph shows healthy cross-pollination between symbols.'}"
            ),
            confidence=0.80 + random.uniform(-0.1, 0.1),
        )

    # ── Mystic ────────────────────────────────────────────────

    def _mystic_report(self, prices, changes, personas, memories, sentiment, tick):
        # Find the "luckiest" and "unluckiest" agent
        pnls = [
            (pid, ps.pnl(10000, prices))
            for pid, ps in personas.items()
        ]
        pnls.sort(key=lambda x: x[1])
        unluckiest = pnls[0] if pnls else ("???", 0)
        luckiest = pnls[-1] if pnls else ("???", 0)

        # Find "resonance" — which symbol has the most chatter
        symbol_mentions: dict[str, int] = {}
        for mem in memories.values():
            for obs in mem.observations[-10:]:
                for sym in prices:
                    if sym in obs.content:
                        symbol_mentions[sym] = symbol_mentions.get(sym, 0) + 1
        most_mentioned = max(symbol_mentions, key=symbol_mentions.get) if symbol_mentions else "the void"

        # Cosmic signs
        signs = [
            "Mercury is in retrograde — communication breakdowns ahead.",
            "The stars align in a bullish pentagram.",
            "I ching hexagram ䷂ (Difficulty at the Beginning) appeared this morning.",
            "The crystal ball shows a red candle... no, green. Wait, it's flickering.",
            "The Fibonacci retracement of the cosmic energy field suggests 61.8%.",
            "I threw the coins six times. Three yarrow stalks point upward.",
            "The alignment of Jupiter and Saturn in the third house... hmm.",
            "Tea leaves form what looks like a double-top pattern. Very ominous.",
        ]

        titles = [
            "Cosmic Resonance Report",
            "Tea Leaves and Ticker Tape",
            "The I Ching of Intraday Volatility",
            "Astrological Forecasting of Agent Sentiment",
            "The Dao of Market Coupling",
            "Crystal Ball Calibration Log",
        ]

        return ObserverReport(
            observer_id="mystic",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"The cosmic energy field around {most_mentioned} is particularly strong. "
                f"{luckiest[0]} is blessed by the market spirits (+${luckiest[1]:.0f}), "
                f"while {unluckiest[0]} carries heavy karmic debt (${unluckiest[1]:.0f}). "
                f"Overall aura: {'radiant' if sentiment > 0 else 'turbulent' if sentiment < 0 else 'stagnant — the chi is blocked'}. "
                f"{random.choice(signs)} "
                f"My intuition says: {random.choice(['BUY the fear.', 'SELL the greed.', 'HOLD and meditate.', 'The answer lies in the space between candles.'])}"
            ),
            confidence=random.uniform(0.05, 0.45),
        )

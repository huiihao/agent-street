"""Observer agents: Physicist, Mathematician, Mystic.

They do not trade. They read the same market metrics the traders use, plus the
trust graph and agent memories, and publish periodic interpretations. The
physicist and mathematician now report real statistics rather than invented
ones; the mystic remains deliberately ungrounded.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from backend.config import INITIAL_CASH, OBSERVER_REPORT_EVERY_N_TICKS
from backend.engine.influence_network import InfluenceNetwork
from backend.engine.indicators import MarketMetrics
from backend.engine.market_data import MarketSnapshot
from backend.engine.memory_system import AgentMemory
from backend.models.portfolio import ExecutedTrade, PersonaState


@dataclass
class ObserverReport:
    observer_id: str
    tick: int
    title: str
    content: str
    confidence: float

    def to_payload(self) -> dict:
        return {
            "observerId": self.observer_id,
            "tick": self.tick,
            "title": self.title,
            "content": self.content,
            "confidence": round(self.confidence, 3),
        }


class ObserverEngine:
    def __init__(self):
        self._last_report_tick: dict[str, int] = {}
        self.reports: list[ObserverReport] = []

    def reset(self) -> None:
        self._last_report_tick.clear()
        self.reports.clear()

    def observe(
        self,
        observer_id: str,
        tick: int,
        snapshot: MarketSnapshot,
        metrics: MarketMetrics,
        personas: dict[str, PersonaState],
        memories: dict[str, AgentMemory],
        trades: list[ExecutedTrade],
        sentiment: float,
        influence: InfluenceNetwork | None = None,
        ecosystem: dict | None = None,
    ) -> ObserverReport | None:
        last = self._last_report_tick.get(observer_id, -10**9)
        if tick - last < OBSERVER_REPORT_EVERY_N_TICKS:
            return None
        self._last_report_tick[observer_id] = tick

        if observer_id == "physicist":
            report = self._physicist(tick, snapshot, metrics, trades, sentiment, ecosystem)
        elif observer_id == "mathematician":
            report = self._mathematician(
                tick, snapshot, metrics, personas, memories, trades, influence, ecosystem,
            )
        elif observer_id == "social_engineer":
            report = self._social_engineer(
                tick, metrics, personas, memories, trades, sentiment, influence, ecosystem,
            )
        elif observer_id == "mystic":
            report = self._mystic(tick, snapshot, personas, memories, sentiment)
        else:
            return None

        self.reports.append(report)
        if len(self.reports) > 60:
            self.reports = self.reports[-60:]
        return report

    # ── Physicist ─────────────────────────────────────────────

    def _physicist(
        self,
        tick: int,
        snapshot: MarketSnapshot,
        metrics: MarketMetrics,
        trades: list[ExecutedTrade],
        sentiment: float,
        ecosystem: dict | None = None,
    ) -> ObserverReport:
        alignment = abs(metrics.breadth)
        susceptibility = metrics.dispersion / max(metrics.avg_vol, 1e-6)
        correlation_length = 1.0 / max(metrics.dispersion, 1e-5)
        most_volatile = max(snapshot.changes.items(), key=lambda kv: abs(kv[1])) if snapshot.changes else ("?", 0.0)
        activity = len(trades)
        activity_word = "high" if activity > 10 else "moderate" if activity > 3 else "low"

        if alignment > 0.8:
            phase = "ordered — the cross-section is moving as one body"
        elif alignment > 0.4:
            phase = "quasi-ordered — a shared mode is emerging"
        elif metrics.dispersion > metrics.avg_vol * 2:
            phase = "disordered — idiosyncratic noise dominates"
        else:
            phase = "critical — no dominant mode; small shocks travel far"

        titles = [
            "A Note on Phase Transitions in Agent-Market Coupling",
            "Statistical Mechanics of a 16-Body Trading Ensemble",
            "On the Emergence of Collective Modes in Financial Microstructure",
            "Field Theory of Sentiment: A Mean-Field Approximation",
            "Correlation Functions and Critical Exponents in Agent Space",
        ]
        confidence = 0.70 + 0.15 * min(1.0, len(trades) / 8.0)

        return ObserverReport(
            observer_id="physicist",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"Order parameter |breadth| = {alignment:.2f} ({metrics.regime}). "
                f"Dispersion σ = {metrics.dispersion:.4f}, mean volatility = {metrics.avg_vol:.4f}; "
                f"susceptibility χ ≈ {susceptibility:.2f}. "
                f"Phase: {phase}. "
                f"Activity: {activity_word} ({activity} fills this tick). "
                f"{most_volatile[0]} carries the largest fluctuation at |Δ| = {abs(most_volatile[1]):.2%}. "
                f"Estimated correlation length ξ ≈ {correlation_length:.0f} bars. "
                f"Crowd field reads {sentiment:+.2f}. "
                f"Strategy diversity HHI = {float((ecosystem or {}).get('diversity', 0)):.2f}; "
                f"the population is at generation {int((ecosystem or {}).get('generation', 0))}."
            ),
            confidence=confidence,
        )

    # ── Mathematician ─────────────────────────────────────────

    def _mathematician(
        self,
        tick: int,
        snapshot: MarketSnapshot,
        metrics: MarketMetrics,
        personas: dict[str, PersonaState],
        memories: dict[str, AgentMemory],
        trades: list[ExecutedTrade],
        influence: InfluenceNetwork | None,
        ecosystem: dict | None = None,
    ) -> ObserverReport:
        components = self._components(personas.keys(), influence)
        degrees: dict[str, int] = {pid: 0 for pid in personas}
        if influence is not None:
            for edge in influence.top_edges(limit=200):
                degrees[edge["a"]] = degrees.get(edge["a"], 0) + 1
                degrees[edge["b"]] = degrees.get(edge["b"], 0) + 1
        hub = max(degrees.items(), key=lambda kv: kv[1]) if degrees else ("?", 0)

        traded_symbols = {t.symbol for t in trades}
        active_agents = {t.persona_id for t in trades}
        diversity = len(traded_symbols) / max(len(snapshot.bars), 1)

        sentiment_buckets = {"bullish": 0, "bearish": 0, "neutral": 0}
        for memory in memories.values():
            s = memory.get_sentiment()
            if s > 0.08:
                sentiment_buckets["bullish"] += 1
            elif s < -0.08:
                sentiment_buckets["bearish"] += 1
            else:
                sentiment_buckets["neutral"] += 1

        largest_component = max(components, default=1)
        titles = [
            "On the Connectivity of the Agent Interaction Graph",
            "A Combinatorial Analysis of Trading Coalition Formation",
            "Graph-Theoretic Measures of Market Fragmentation",
            "Optimal Transport Between Sentiment Clusters",
            "Spectral Properties of the Agent Correlation Matrix",
        ]
        confidence = 0.75 + 0.10 * min(1.0, len(trades) / 6.0)
        guilds = (ecosystem or {}).get("guilds", [])
        guild_text = ", ".join(
            f"{g['family']} {g['count']}" for g in guilds[:4]
        ) or "no settled guilds"
        dominant = (ecosystem or {}).get("dominant", "balanced")
        adaptations = int((ecosystem or {}).get("totalAdaptations", 0))

        return ObserverReport(
            observer_id="mathematician",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"Trust graph: {largest_component} connected component(s), "
                f"largest size {max(components, default=0)}/16; "
                f"highest degree node {hub[0]} (deg {hub[1]}). "
                f"Sentiment partition: {sentiment_buckets['bullish']} bullish · "
                f"{sentiment_buckets['bearish']} bearish · {sentiment_buckets['neutral']} neutral. "
                f"Active traders this tick: {len(active_agents)}/16. "
                f"Symbol diversity {diversity:.2f} across {len(traded_symbols)} venue(s). "
                f"Cross-sectional dispersion {metrics.dispersion:.4f}. "
                f"Strategy partition: {guild_text}; dominant playbook {dominant}, "
                f"{adaptations} adaptations recorded."
            ),
            confidence=confidence,
        )

    @staticmethod
    def _components(agent_ids, influence: InfluenceNetwork | None) -> list[int]:
        ids = list(agent_ids)
        parent = {pid: pid for pid in ids}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        if influence is not None:
            for edge in influence.top_edges(limit=500):
                if edge["a"] in parent and edge["b"] in parent and edge["weight"] >= 0.3:
                    union(edge["a"], edge["b"])

        sizes: dict[str, int] = {}
        for pid in ids:
            root = find(pid)
            sizes[root] = sizes.get(root, 0) + 1
        return sorted(sizes.values(), reverse=True)

    # ── Social Engineer ──────────────────────────────────────

    def _social_engineer(
        self,
        tick: int,
        metrics: MarketMetrics,
        personas: dict[str, PersonaState],
        memories: dict[str, AgentMemory],
        trades: list[ExecutedTrade],
        sentiment: float,
        influence: InfluenceNetwork | None,
        ecosystem: dict | None,
    ) -> ObserverReport:
        ids = list(personas.keys())
        n = max(len(ids), 1)
        edges = influence.top_edges(limit=500) if influence else []
        strong_edges = [e for e in edges if e["weight"] >= 0.3]
        possible = max(n * (n - 1) / 2, 1)
        density = len(strong_edges) / possible

        degree = {pid: 0 for pid in ids}
        adjacency = {pid: set() for pid in ids}
        for edge in strong_edges:
            a, b = edge["a"], edge["b"]
            if a in degree and b in degree:
                degree[a] += 1
                degree[b] += 1
                adjacency[a].add(b)
                adjacency[b].add(a)
        broker = max(degree.items(), key=lambda item: item[1]) if degree else ("?", 0)

        triangles = 0
        triples = 0
        for a in ids:
            neighbors = list(adjacency[a])
            for i, b in enumerate(neighbors):
                for c in neighbors[i + 1:]:
                    triples += 1
                    if c in adjacency[b]:
                        triangles += 1
        clustering = triangles / triples if triples else 0.0

        positive = sum(1 for memory in memories.values() if memory.get_sentiment() > 0.08)
        negative = sum(1 for memory in memories.values() if memory.get_sentiment() < -0.08)
        polarization = 2.0 * min(positive, negative) / max(len(memories), 1)

        guilds = (ecosystem or {}).get("guilds", [])
        dominant = (ecosystem or {}).get("dominant", "balanced")
        dominant_count = next((g["count"] for g in guilds if g["family"] == dominant), 0)
        dominant_share = dominant_count / n
        diversity = float((ecosystem or {}).get("diversity", 0.0))
        recent = (ecosystem or {}).get("adaptations", [])
        imitation_recent = sum(1 for item in recent if item.get("kind") == "imitate")
        guild_text = ", ".join(f"{g['family']} {g['count']}" for g in guilds[:5]) or "no settled guilds"

        if dominant_share > 0.55 and polarization > 0.30:
            cascade = "high — a dominant narrative is coupled to a split book"
            intervention = (
                "seed a dissenting, high-credibility signal at the Rumor Mill and "
                "reduce reliance on the current broker"
            )
        elif polarization > 0.42:
            cascade = "elevated — the town is arguing with itself"
            intervention = "host a cross-guild debate at the Guild Hall with paired opponents"
        elif density < 0.18:
            cascade = "low but fragile — the trust graph is sparse"
            intervention = "widen cross-location conversations before a cascade can organise"
        else:
            cascade = "contained — plural guilds with a connected trust graph"
            intervention = "keep the lab's imitation rate under observation"

        titles = [
            "Field Notes on Narrative Capture",
            "A Social Topology of the Trading Floor",
            "On Echo Chambers, Brokers and Cascade Risk",
            "The Social Engineering of Consensus",
            "Trust Density and the Coordination Problem",
        ]
        confidence = 0.66 + 0.14 * min(1.0, len(trades) / 6.0) + 0.08 * (1.0 - density)

        return ObserverReport(
            observer_id="social_engineer",
            tick=tick,
            title=random.choice(titles),
            content=(
                f"Trust density {density:.2f} over {n} agents; broker {broker[0]} "
                f"(degree {broker[1]}), clustering {clustering:.2f}. "
                f"Strategy guilds: {guild_text}; dominant {dominant} "
                f"({dominant_share:.0%}), diversity {diversity:.2f}. "
                f"Polarization index {polarization:.2f}; {imitation_recent} imitation event(s) "
                f"in the latest adaptation window. "
                f"Cross-sectional dispersion {metrics.dispersion:.4f}; crowd field {sentiment:+.2f}. "
                f"Cascade risk: {cascade}. Recommended intervention: {intervention}."
            ),
            confidence=confidence,
        )

    # ── Mystic ────────────────────────────────────────────────

    def _mystic(
        self,
        tick: int,
        snapshot: MarketSnapshot,
        personas: dict[str, PersonaState],
        memories: dict[str, AgentMemory],
        sentiment: float,
    ) -> ObserverReport:
        prices = {s: b.close for s, b in snapshot.bars.items()}
        ranked = sorted(
            ((pid, (ps.equity(prices) / INITIAL_CASH - 1.0) * 100.0) for pid, ps in personas.items()),
            key=lambda kv: kv[1],
        )
        unluckiest = ranked[0] if ranked else ("???", 0.0)
        luckiest = ranked[-1] if ranked else ("???", 0.0)

        mentions: dict[str, int] = {}
        for memory in memories.values():
            for obs in memory.observations[-8:]:
                for symbol in prices:
                    if symbol in obs.content:
                        mentions[symbol] = mentions.get(symbol, 0) + 1
        most_mentioned = max(mentions, key=mentions.get) if mentions else "the void"

        signs = [
            "Mercury is in retrograde — the tape is arguing with itself.",
            "The stars align in a bullish pentagram. Suspiciously convenient.",
            "Hexagram ䷂ (Difficulty at the Beginning) appeared this morning.",
            "The crystal ball shows a red candle... no, green. It's flickering.",
            "The cosmic retracement sits at 61.8%. The universe loves a ratio.",
            "I threw the coins six times. Three yarrow stalks point upward.",
            "Tea leaves form a double top. Very ominous. Or possibly breakfast.",
            "Jupiter and Saturn are squaring the circle in the third house.",
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
                f"The energy field around {most_mentioned} is unusually loud. "
                f"{luckiest[0]} is blessed by the market spirits ({luckiest[1]:+.1f}%), "
                f"while {unluckiest[0]} carries heavy karmic debt ({unluckiest[1]:+.1f}%). "
                f"Overall aura: {'radiant' if sentiment > 0.15 else 'turbulent' if sentiment < -0.15 else 'stagnant — the chi is blocked'}. "
                f"{random.choice(signs)} "
                f"My intuition says: {random.choice(['BUY the fear.', 'SELL the greed.', 'HOLD and meditate.', 'The answer lies between two candles.'])}"
            ),
            confidence=random.uniform(0.05, 0.45),
        )

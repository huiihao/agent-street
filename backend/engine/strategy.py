"""Experience-driven strategy evolution for the traders.

Every agent owns a small genome of signal weights and risk traits. The genome is
initialised from its MBTI profile, then evolves through three mechanisms:

1. **Reinforcement from experience** — when a position closes, the realised
   return is attributed to the signal components that were present at entry.
   Supportive weights grow after wins and shrink after losses.
2. **Imitation** — conversations between agents can transfer a blend of the
   better-performing agent's playbook. The trust graph gates how likely this is.
   The Quant Lab increases the learning rate; the Guild Hall encourages debate.
3. **Mutation** — small random variations keep the population diverse.

The result is a population of strategies that clusters into guilds and changes
over a replay session, rather than sixteen fixed probability tables.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field

SIGNAL_GENES = ("trend", "reversion", "rsi", "herding", "influence", "memory")
TRAIT_GENES = ("risk", "patience", "contrarian", "noise")
FAMILIES = ("momentum", "mean_reversion", "sentiment", "contrarian", "balanced")
EPS = 1e-9


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class StrategyGenome:
    trend: float = 0.22
    reversion: float = 0.20
    rsi: float = 0.12
    herding: float = 0.14
    influence: float = 0.12
    memory: float = 0.10
    risk: float = 0.50
    patience: float = 0.50
    contrarian: float = 0.50
    noise: float = 0.50
    generation: int = 0
    fitness: float = 0.0
    wins: int = 0
    losses: int = 0
    adaptations: int = 0
    family: str = "balanced"
    last_adaptation: str = "born with a balanced prior"

    def normalize(self) -> None:
        """Keep signal weights positive and summing to one."""
        values = {gene: max(0.008, getattr(self, gene)) for gene in SIGNAL_GENES}
        total = sum(values.values())
        for gene, value in values.items():
            setattr(self, gene, value / total)
        for gene in TRAIT_GENES:
            setattr(self, gene, _clip(getattr(self, gene), 0.05, 0.95))
        self.family = self.classify()

    def classify(self) -> str:
        if self.contrarian >= 0.64:
            return "contrarian"
        signal_top = max(SIGNAL_GENES, key=lambda gene: getattr(self, gene))
        social = self.herding + self.influence + self.memory
        if signal_top == "trend" and self.trend >= 0.26:
            return "momentum"
        if signal_top == "reversion" and self.reversion >= 0.26:
            return "mean_reversion"
        if social >= 0.43:
            return "sentiment"
        return "balanced"

    def set_signal(self, gene: str, value: float) -> None:
        if gene in SIGNAL_GENES:
            setattr(self, gene, max(0.008, value))

    def snapshot(self) -> dict:
        return {
            "family": self.family,
            "generation": self.generation,
            "fitness": round(self.fitness, 5),
            "wins": self.wins,
            "losses": self.losses,
            "adaptations": self.adaptations,
            "lastAdaptation": self.last_adaptation,
            "weights": {gene: round(getattr(self, gene), 4) for gene in SIGNAL_GENES},
            "traits": {gene: round(getattr(self, gene), 4) for gene in TRAIT_GENES},
        }


def genome_from_persona(traits, params) -> StrategyGenome:
    """Translate MBTI-derived trading parameters into a starting genome."""
    c = _clip(params.contrarianism)
    social = _clip(params.herding_weight)
    genome = StrategyGenome(
        trend=0.22 + 0.26 * (1.0 - c),
        reversion=0.15 + 0.30 * c,
        rsi=0.09 + 0.12 * c,
        herding=0.09 + 0.24 * social,
        influence=0.07 + 0.19 * social,
        memory=0.07 + 0.12 * (1.0 - _clip(traits.thinking)),
        risk=_clip(params.risk_tolerance),
        patience=_clip(params.holding_period_ticks / 15.0),
        contrarian=c,
        noise=_clip(0.25 + 0.55 * params.volatility_tolerance),
    )
    genome.normalize()
    genome.last_adaptation = f"born with a {genome.family} prior"
    return genome


class StrategyEngine:
    def __init__(self, initial_cash: float = 10_000.0):
        self.initial_cash = initial_cash
        self.genomes: dict[str, StrategyGenome] = {}
        self.adaptations: deque[dict] = deque(maxlen=48)
        self.total_adaptations = 0
        self.closed_trades = 0

    def reset(self) -> None:
        self.genomes.clear()
        self.adaptations.clear()
        self.total_adaptations = 0
        self.closed_trades = 0

    def register(self, persona_id: str, genome: StrategyGenome) -> None:
        self.genomes[persona_id] = genome

    def get(self, persona_id: str) -> StrategyGenome | None:
        return self.genomes.get(persona_id)

    def snapshot(self, persona_id: str) -> dict:
        genome = self.genomes.get(persona_id)
        return genome.snapshot() if genome else {}

    # ── experience ───────────────────────────────────────────

    def observe_closes(
        self,
        events: list,
        tick: int,
        locations: dict[str, str] | None = None,
        update_weights: bool = True,
    ) -> None:
        """Record closed-trade outcomes.

        ``update_weights=False`` still updates fitness, win/loss counts and the
        closed-trade counter, which is required for imitation-only ablations.
        """
        locations = locations or {}
        for event in events:
            genome = self.genomes.get(event.persona_id)
            if genome is None or not event.entry_context:
                continue
            entry_notional = max(event.entry_price * event.shares, 1.0)
            trade_return = event.realized_pnl / entry_notional
            reward = _clip(trade_return / 0.02, -1.0, 1.0)

            if update_weights:
                boosted = locations.get(event.persona_id) == "lab"
                lr = 0.10 * (1.7 if boosted else 1.0)

                # Reward-modulated Hebbian update: a signal that supported a
                # winning long is reinforced; a signal that supported a loser is
                # down-weighted.
                for gene in SIGNAL_GENES:
                    evidence = float(event.entry_context.get(gene, 0.0))
                    genome.set_signal(gene, getattr(genome, gene) + lr * reward * evidence)
                genome.risk = _clip(genome.risk + lr * reward * 0.55, 0.05, 0.95)
                genome.patience = _clip(genome.patience + lr * reward * 0.20, 0.05, 0.95)
                genome.normalize()
                genome.generation += 1
                genome.adaptations += 1

            genome.fitness = 0.85 * genome.fitness + 0.15 * trade_return
            if trade_return > 0:
                genome.wins += 1
            else:
                genome.losses += 1
            self.closed_trades += 1

            if update_weights:
                dominant = max(SIGNAL_GENES, key=lambda gene: getattr(genome, gene))
                if reward > 0.05:
                    action = "reinforced"
                elif reward < -0.05:
                    action = "down-weighted"
                else:
                    action = "fine-tuned"
                genome.last_adaptation = (
                    f"{action} {dominant} after {trade_return:+.2%} on {event.symbol}"
                )
                self._record(
                    tick, event.persona_id, genome, "learn",
                    f"{action} {dominant} after {trade_return:+.2%} on {event.symbol}",
                )

    # ── imitation ────────────────────────────────────────────

    def imitate(
        self,
        participants: list[str],
        trust_network,
        tick: int,
        location: str = "",
    ) -> None:
        if len(participants) < 2:
            return
        pairs = []
        for i, a in enumerate(participants):
            for b in participants[i + 1:]:
                pairs.append((a, b))
        for a, b in pairs:
            genome_a = self.genomes.get(a)
            genome_b = self.genomes.get(b)
            if genome_a is None or genome_b is None:
                continue
            if abs(genome_a.fitness - genome_b.fitness) < 0.0015:
                continue
            teacher, learner = (a, b) if genome_a.fitness >= genome_b.fitness else (b, a)
            teacher_g = self.genomes[teacher]
            learner_g = self.genomes[learner]
            trust = trust_network.get_trust(learner, teacher) if trust_network else 0.1
            probability = 0.14 + 0.22 * trust
            if location == "lab":
                probability += 0.18
            elif location == "hall":
                probability += 0.06
            if random.random() > min(0.62, probability):
                continue

            for gene in SIGNAL_GENES:
                blended = 0.76 * getattr(learner_g, gene) + 0.24 * getattr(teacher_g, gene)
                learner_g.set_signal(gene, blended + random.gauss(0.0, 0.010))
            for gene in ("risk", "patience", "contrarian"):
                blended = 0.80 * getattr(learner_g, gene) + 0.20 * getattr(teacher_g, gene)
                setattr(learner_g, gene, _clip(blended + random.gauss(0.0, 0.012), 0.05, 0.95))
            learner_g.normalize()
            learner_g.generation += 1
            learner_g.adaptations += 1
            learner_g.last_adaptation = (
                f"borrowed {teacher}'s {teacher_g.family} playbook at the "
                f"{location or 'street'}"
            )
            self._record(
                tick, learner, learner_g, "imitate",
                f"learned {teacher}'s {teacher_g.family} playbook",
            )

    # ── exploration ──────────────────────────────────────────

    def mutate(self, tick: int) -> None:
        for persona_id, genome in self.genomes.items():
            if random.random() > 0.10:
                continue
            if random.random() < 0.72:
                gene = random.choice(SIGNAL_GENES)
                genome.set_signal(gene, getattr(genome, gene) + random.gauss(0.0, 0.018))
                label = gene
            else:
                gene = random.choice(TRAIT_GENES)
                setattr(genome, gene, _clip(getattr(genome, gene) + random.gauss(0.0, 0.022), 0.05, 0.95))
                label = gene
            previous_family = genome.family
            genome.normalize()
            genome.generation += 1
            genome.adaptations += 1
            genome.last_adaptation = f"explored a new {label} variation"
            if genome.family != previous_family:
                self._record(
                    tick, persona_id, genome, "mutate",
                    f"drifted into the {genome.family} guild",
                )

    def _record(self, tick: int, persona_id: str, genome: StrategyGenome, kind: str, text: str) -> None:
        self.total_adaptations += 1
        self.adaptations.appendleft({
            "tick": tick,
            "agent": persona_id,
            "kind": kind,
            "family": genome.family,
            "text": text,
        })

    # ── ecosystem reporting ──────────────────────────────────

    def ecosystem(self, personas: dict, prices: dict[str, float]) -> dict:
        buckets: dict[str, dict] = {}
        total = 0
        for persona_id, genome in self.genomes.items():
            state = personas.get(persona_id)
            if state is None:
                continue
            equity = state.equity(prices)
            account_return = equity / self.initial_cash - 1.0
            bucket = buckets.setdefault(genome.family, {
                "family": genome.family,
                "count": 0,
                "fitnessSum": 0.0,
                "returnSum": 0.0,
                "equitySum": 0.0,
                "members": [],
            })
            bucket["count"] += 1
            bucket["fitnessSum"] += genome.fitness
            bucket["returnSum"] += account_return
            bucket["equitySum"] += equity
            bucket["members"].append(persona_id)
            total += 1

        guilds = []
        for bucket in buckets.values():
            count = bucket["count"]
            guilds.append({
                "family": bucket["family"],
                "count": count,
                "avgFitness": round(bucket["fitnessSum"] / count, 5),
                "avgReturn": round(bucket["returnSum"] / count, 5),
                "equity": round(bucket["equitySum"], 2),
                "members": bucket["members"],
            })
        guilds.sort(key=lambda item: (-item["count"], -item["avgFitness"]))
        diversity = 1.0 - sum((g["count"] / max(total, 1)) ** 2 for g in guilds)
        dominant = guilds[0]["family"] if guilds else "balanced"
        generations = [g.generation for g in self.genomes.values()]
        return {
            "guilds": guilds,
            "dominant": dominant,
            "diversity": round(diversity, 4),
            "generation": max(generations, default=0),
            "totalAdaptations": self.total_adaptations,
            "closedTrades": self.closed_trades,
            "adaptations": list(self.adaptations)[:8],
        }

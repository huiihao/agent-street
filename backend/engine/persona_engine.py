"""Personality-driven trading decisions.

Signals are dimensionless and computed once per tick by ``IndicatorEngine``:
  * trend:      5-bar momentum divided by its own realised volatility
  * reversion:  distance from the 20-bar mean in ATR units
  * rsi:        overbought/oversold pressure
  * social:     herding + trust-network influence + memory sentiment

The composite is blended with the agent's MBTI parameters, then passed through
risk controls: drawdown panic, stop loss, profit taking, holding period,
position cap and per-symbol cooldowns. Randomness is bounded and scaled by the
agent's volatility tolerance, so results are noisy without being arbitrary.
"""

from __future__ import annotations

import random

from backend.config import (
    BUY_THRESHOLD,
    MAX_POSITION_PCT,
    PANIC_COOLDOWN_TICKS,
    SELL_THRESHOLD,
)
from backend.engine.indicators import MarketMetrics, SymbolMetrics
from backend.engine.market_data import MarketSnapshot
from backend.engine.strategy import StrategyGenome
from backend.engine.memory_system import AgentMemory
from backend.mbti.types import TradingParams
from backend.models.portfolio import PersonaState, TradeIntent

EPS = 1e-9


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _tanh(value: float) -> float:
    try:
        return __import__("math").tanh(value)
    except (OverflowError, ValueError):
        return 0.0


class PersonaDecisionEngine:
    def __init__(self):
        self.memories: dict[str, AgentMemory] = {}
        self.strategies: dict[str, StrategyGenome] = {}
        self.influence = None  # InfluenceNetwork, injected by the simulation

    def register_memory(self, agent_id: str, memory: AgentMemory) -> None:
        self.memories[agent_id] = memory

    def register_strategy(self, agent_id: str, genome: StrategyGenome) -> None:
        self.strategies[agent_id] = genome

    # ── main entry point ─────────────────────────────────────

    def decide(
        self,
        persona: PersonaState,
        params: TradingParams,
        base_params: TradingParams | None,
        snapshot: MarketSnapshot,
        metrics: MarketMetrics,
        all_states: dict[str, PersonaState],
        tick: int,
    ) -> list[TradeIntent]:
        action_cooldown = max(1, int(round(1 + 6 * (1.0 - params.reaction_speed))))
        if tick - persona.last_decision_tick < action_cooldown:
            return []
        persona.last_decision_tick = tick

        prices = {s: b.close for s, b in snapshot.bars.items()}
        equity = persona.equity(prices)
        if equity <= 0:
            return []

        # Track peak equity for drawdown-based panic.
        persona.peak_equity = max(persona.peak_equity, equity)
        drawdown = equity / persona.peak_equity - 1.0 if persona.peak_equity > 0 else 0.0

        memory = self.memories.get(persona.persona_id)
        memory_sentiment = memory.get_sentiment() if memory else 0.0
        herding = self._compute_herding(all_states, persona.persona_id, tick)
        influence_signal = 0.0
        if self.influence is not None:
            influence_signal = self.influence.influence_signal(
                persona.persona_id, self.memories, prices,
            )

        # ── panic exit ───────────────────────────────────────
        effective_panic = params.panic_threshold * (1.0 + 0.25 * memory_sentiment)
        if (
            drawdown < effective_panic
            and tick - persona.last_panic_tick >= PANIC_COOLDOWN_TICKS
            and any(h.shares > 0 for h in persona.holdings.values())
        ):
            intents: list[TradeIntent] = []
            for holding in list(persona.holdings.values()):
                if holding.shares <= 0:
                    continue
                price = prices.get(holding.symbol, holding.avg_cost)
                intents.append(TradeIntent(
                    persona_id=persona.persona_id,
                    symbol=holding.symbol,
                    direction="SELL",
                    shares=holding.shares,
                    limit_price=price * 0.97,
                    reason="panic_sell",
                    timestamp=tick,
                ))
            persona.last_panic_tick = tick
            if memory:
                memory.observe(
                    f"Panic sold everything after a {drawdown:.1%} drawdown",
                    "reflection", 0.95, tick, sentiment=_clip(drawdown * 8),
                )
            return intents

        intents: list[TradeIntent] = []
        for symbol, bar in snapshot.bars.items():
            m = metrics.symbols.get(symbol)
            if m is None or bar.close <= 0:
                continue
            price = bar.close
            change = snapshot.changes.get(symbol, 0.0)
            holding = persona.holdings.get(symbol)
            held_shares = holding.shares if holding else 0

            # ── grounded memory observations (rate limited) ──
            if memory and abs(change) > 0.006:
                memory.observe(
                    f"{symbol} {'up' if change > 0 else 'down'} {abs(change):.2%} "
                    f"to ${price:.2f} (RSI {m.rsi_14:.0f}, trend {m.trend_score:+.2f})",
                    "price",
                    min(1.0, 0.3 + abs(change) * 25),
                    tick,
                    sentiment=_clip(change / 0.01),
                )

            # ── signal blend ─────────────────────────────────
            genome = self.strategies.get(persona.persona_id)
            contrarian = genome.contrarian if genome else params.contrarianism
            trend_adj = (1.0 - 2.0 * contrarian) * m.trend_score
            reversion_adj = (0.5 + contrarian) * m.reversion_score

            if genome:
                # The evolved genome replaces the fixed blend. Weights sum to
                # one across all six signal families, so the composite stays in
                # [-1, 1] before bounded exploration noise.
                tech = (
                    genome.trend * trend_adj
                    + genome.reversion * reversion_adj
                    + genome.rsi * m.rsi_score
                )
                social = (
                    genome.herding * herding
                    + genome.influence * influence_signal
                    + genome.memory * memory_sentiment
                )
                composite = _clip(tech + social)
                noise_scale = 0.03 + 0.10 * genome.noise
            else:
                tech = _clip(0.50 * trend_adj + 0.30 * reversion_adj + 0.20 * m.rsi_score)
                social = _clip(
                    0.45 * herding
                    + 0.35 * influence_signal
                    + 0.20 * memory_sentiment
                )
                composite = params.tech_weight * tech + (1.0 - params.tech_weight) * social
                noise_scale = 0.04 + 0.10 * (1.0 - params.volatility_tolerance)

            composite = _clip(composite + random.gauss(0.0, noise_scale))
            persona.signals[symbol] = round(composite, 4)
            signal_context = {
                "trend": round(trend_adj, 4),
                "reversion": round(reversion_adj, 4),
                "rsi": round(m.rsi_score, 4),
                "herding": round(herding, 4),
                "influence": round(influence_signal, 4),
                "memory": round(memory_sentiment, 4),
                "composite": round(composite, 4),
            }

            # ── cooldown after a recent action in this symbol ──
            if tick < persona.symbol_cooldowns.get(symbol, -1):
                continue

            # ── risk exits ───────────────────────────────────
            if holding and held_shares > 0:
                gain = (price - holding.avg_cost) / max(holding.avg_cost, EPS)
                held_ticks = tick - holding.opened_tick
                risk_appetite = genome.risk if genome else params.risk_tolerance
                stop_loss = 0.02 + 0.06 * (1.0 - risk_appetite)

                if gain < -stop_loss and held_ticks >= 1:
                    intents.append(self._sell(persona, symbol, held_shares, price, "stop_loss", tick))
                    persona.symbol_cooldowns[symbol] = tick + 3
                    if memory:
                        memory.observe(
                            f"Stopped out of {symbol} at {gain:.1%}",
                            "reflection", 0.8, tick, sentiment=-0.6,
                        )
                    break

                if gain > params.greed_threshold and held_ticks >= 1 and (
                    composite < 0.20 or m.rsi_14 > 70
                ):
                    qty = max(1, held_shares // 2)
                    if held_shares - qty == 1:
                        qty = held_shares
                    intents.append(self._sell(persona, symbol, qty, price, "profit_take", tick))
                    persona.symbol_cooldowns[symbol] = tick + 2
                    if memory:
                        memory.observe(
                            f"Took profit on {symbol} at {gain:.1%}",
                            "reflection", 0.7, tick, sentiment=0.5,
                        )
                    break

                # Require conviction to exit inside the minimum holding period.
                hold_base = params.holding_period_ticks * (
                    (0.6 + 0.8 * genome.patience) if genome else 1.0
                )
                min_hold = max(1, int(hold_base * 0.5))
                if held_ticks < min_hold and composite > SELL_THRESHOLD * 1.8:
                    continue

            # ── entries / exits ──────────────────────────────
            if composite > BUY_THRESHOLD:
                conviction = (composite - BUY_THRESHOLD) / max(1.0 - BUY_THRESHOLD, EPS)
                budget = self._position_budget(
                    persona, params, price, equity, conviction, held_shares, genome,
                )
                shares = int(budget / price) if price > 0 else 0
                if shares >= 1 and persona.cash >= shares * price:
                    intents.append(TradeIntent(
                        persona_id=persona.persona_id,
                        symbol=symbol,
                        direction="BUY",
                        shares=shares,
                        limit_price=price * 1.005,
                        reason="trend_follow" if m.trend_score > 0.1 else "contrarian_buy",
                        timestamp=tick,
                        context=signal_context,
                    ))
                    persona.symbol_cooldowns[symbol] = tick + 2 + int(4 * (1.0 - params.reaction_speed))
                    if memory:
                        memory.observe(
                            f"Bought {shares} {symbol} at ${price:.2f} "
                            f"(signal {composite:+.2f}, RSI {m.rsi_14:.0f})",
                            "reflection", 0.55 + 0.3 * conviction, tick,
                            sentiment=_clip(composite),
                        )
                    # One deliberate action per decision cycle keeps the tape
                    # readable and prevents firing five orders in one tick.
                    break

            elif composite < SELL_THRESHOLD and held_shares > 0:
                conviction = (SELL_THRESHOLD - composite) / max(1.0 + SELL_THRESHOLD, EPS)
                qty = max(1, int(held_shares * (0.30 + 0.70 * conviction)))
                qty = min(qty, held_shares)
                if held_shares - qty == 1:
                    qty = held_shares
                intents.append(self._sell(persona, symbol, qty, price, "contrarian_sell", tick))
                persona.symbol_cooldowns[symbol] = tick + 2 + int(3 * (1.0 - params.reaction_speed))
                if memory:
                    memory.observe(
                        f"Sold {qty} {symbol} at ${price:.2f} (signal {composite:+.2f})",
                        "reflection", 0.55, tick, sentiment=_clip(composite),
                    )
                break

        return intents

    # ── helpers ──────────────────────────────────────────────

    def _position_budget(
        self,
        persona: PersonaState,
        params: TradingParams,
        price: float,
        equity: float,
        conviction: float,
        held_shares: int,
        genome: StrategyGenome | None = None,
    ) -> float:
        risk = genome.risk if genome else params.risk_tolerance
        max_position_pct = MAX_POSITION_PCT * (0.55 + 0.9 * risk)
        max_position_value = equity * max_position_pct
        current_value = held_shares * price
        room = max(0.0, max_position_value - current_value)
        target = persona.cash * params.trade_size_pct * (0.55 + 0.75 * conviction)
        return max(0.0, min(persona.cash, room, target))

    @staticmethod
    def _sell(
        persona: PersonaState,
        symbol: str,
        shares: int,
        price: float,
        reason: str,
        tick: int,
    ) -> TradeIntent:
        return TradeIntent(
            persona_id=persona.persona_id,
            symbol=symbol,
            direction="SELL",
            shares=max(1, shares),
            limit_price=price * 0.995,
            reason=reason,
            timestamp=tick,
        )

    def _compute_herding(
        self,
        all_states: dict[str, PersonaState],
        exclude_id: str,
        tick: int,
    ) -> float:
        buy_weight = 0.0
        sell_weight = 0.0
        for pid, state in all_states.items():
            if pid == exclude_id or not state.trade_history:
                continue
            last = state.trade_history[-1]
            age = tick - last.timestamp
            if age > 20:
                continue
            weight = 1.0 - age / 20.0
            if last.direction == "BUY":
                buy_weight += weight
            else:
                sell_weight += weight
        total = buy_weight + sell_weight
        if total <= 0:
            return 0.0
        return (buy_weight - sell_weight) / total

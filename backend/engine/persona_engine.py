import random
from backend.models.portfolio import PersonaState, Holding, TradeIntent
from backend.mbti.types import TradingParams
from backend.engine.memory_system import AgentMemory
from backend.config import BUY_THRESHOLD, SELL_THRESHOLD, SYMBOLS


class PersonaDecisionEngine:
    def __init__(self):
        self._signal_memory: dict[str, dict[str, list[float]]] = {}
        # Track per-agent memories
        self.memories: dict[str, AgentMemory] = {}

    def register_memory(self, agent_id: str, memory: AgentMemory):
        self.memories[agent_id] = memory

    def decide(
        self,
        persona: PersonaState,
        params: TradingParams,
        prices: dict[str, float],
        changes: dict[str, float],
        all_states: dict[str, PersonaState],
        tick: int,
    ) -> list[TradeIntent]:
        if tick - persona.last_decision_tick < max(1, int(10 * (1 - params.reaction_speed))):
            return []

        persona.last_decision_tick = tick
        intents: list[TradeIntent] = []

        memory = self.memories.get(persona.persona_id)
        memory_sentiment = memory.get_sentiment() if memory else 0.0

        # Compute aggregate herding signal
        herding_signal = self._compute_herding(all_states, persona.persona_id)

        # Panic check — also considers memory sentiment
        portfolio_val = persona.portfolio_value(prices)
        pnl_pct = (portfolio_val - 10000) / 10000
        effective_panic = params.panic_threshold * (1 - 0.3 * memory_sentiment)  # Positive sentiment dulls panic
        if pnl_pct < effective_panic:
            for h in persona.holdings.values():
                if h.shares > 0:
                    intents.append(TradeIntent(
                        persona_id=persona.persona_id,
                        symbol=h.symbol,
                        direction="SELL",
                        shares=h.shares,
                        limit_price=prices.get(h.symbol, 0) * 0.95,
                        reason="panic_sell",
                        timestamp=tick,
                    ))
                    if memory:
                        memory.observe(
                            f"Panic sold {h.symbol} after {pnl_pct:.1%} drawdown",
                            "reflection", 0.9, tick,
                        )
            return intents

        # Process each symbol
        for symbol in SYMBOLS:
            price = prices.get(symbol, 0)
            change = changes.get(symbol, 0)
            if price <= 0:
                continue

            momentum = self._compute_momentum(symbol, price)
            volatility = self._compute_volatility(symbol, price)

            # Weighted composite score — now includes memory sentiment
            contrarian_adj = momentum * (1 - params.contrarianism) - momentum * params.contrarianism
            tech_signal = contrarian_adj * 0.6 + (1 - volatility / max(price * 0.1, 0.01)) * 0.4
            social_signal = (herding_signal + memory_sentiment) / 2 * params.herding_weight
            composite = params.tech_weight * tech_signal + (1 - params.tech_weight) * social_signal

            # Price change observation
            if memory and abs(change) > 0.005:
                direction = "up" if change > 0 else "down"
                memory.observe(
                    f"{symbol} went {direction} {abs(change):.1%} to ${price:.2f}",
                    "price", min(abs(change) * 20, 1.0), tick,
                )

            # Add randomness scaled by volatility tolerance
            noise = random.uniform(-0.15, 0.15) * (1 - params.volatility_tolerance)
            composite += noise

            # Greed check for existing holdings
            holding = persona.holdings.get(symbol)
            if holding and holding.shares > 0:
                gain_pct = (price - holding.avg_cost) / holding.avg_cost
                if gain_pct > params.greed_threshold:
                    sell_shares = max(1, int(holding.shares * 0.5))
                    intents.append(TradeIntent(
                        persona_id=persona.persona_id,
                        symbol=symbol,
                        direction="SELL",
                        shares=sell_shares,
                        limit_price=price * 0.98,
                        reason="profit_take",
                        timestamp=tick,
                    ))
                    if memory:
                        memory.observe(
                            f"Took profit on {symbol} at {gain_pct:.1%} gain",
                            "reflection", 0.7, tick,
                        )
                    continue

            # Buy / Sell decision
            trade_cash = persona.cash * params.trade_size_pct
            shares = max(1, int(trade_cash / price))

            if composite > BUY_THRESHOLD and persona.cash >= shares * price:
                reason = "trend_follow" if momentum > 0 else "contrarian_buy"
                intents.append(TradeIntent(
                    persona_id=persona.persona_id,
                    symbol=symbol,
                    direction="BUY",
                    shares=shares,
                    limit_price=price * 1.02,
                    reason=reason,
                    timestamp=tick,
                ))
                if memory:
                    memory.observe(
                        f"Bought {shares} {symbol} — {reason}",
                        "reflection", 0.6, tick,
                    )
            elif composite < SELL_THRESHOLD and holding and holding.shares > 0:
                sell_shares = max(1, int(holding.shares * abs(composite)))
                intents.append(TradeIntent(
                    persona_id=persona.persona_id,
                    symbol=symbol,
                    direction="SELL",
                    shares=min(sell_shares, holding.shares),
                    limit_price=price * 0.98,
                    reason="contrarian",
                    timestamp=tick,
                ))
                if memory:
                    memory.observe(
                        f"Sold {min(sell_shares, holding.shares)} {symbol} — contrarian signal",
                        "reflection", 0.6, tick,
                    )

        return intents

    def _compute_herding(self, all_states: dict[str, PersonaState], exclude_id: str) -> float:
        buy_count = 0
        sell_count = 0
        for pid, ps in all_states.items():
            if pid == exclude_id or not ps.trade_history:
                continue
            last_dir = ps.trade_history[-1].direction
            if last_dir == "BUY":
                buy_count += 1
            else:
                sell_count += 1
        total = buy_count + sell_count
        if total == 0:
            return 0.0
        return (buy_count - sell_count) / total

    def _compute_momentum(self, symbol: str, current_price: float) -> float:
        mem = self._signal_memory.setdefault(symbol, [])
        mem.append(current_price)
        if len(mem) > 10:
            mem.pop(0)
        if len(mem) < 3:
            return 0.0
        return (mem[-1] - mem[0]) / max(mem[0], 0.01)

    def _compute_volatility(self, symbol: str, current_price: float) -> float:
        mem = self._signal_memory.setdefault(symbol, [])
        if len(mem) < 5:
            return 0.01 * current_price
        mean = sum(mem) / len(mem)
        variance = sum((p - mean) ** 2 for p in mem) / len(mem)
        return variance ** 0.5

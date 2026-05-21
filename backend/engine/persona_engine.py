import random
from backend.models.portfolio import PersonaState, Holding, TradeIntent
from backend.mbti.types import TradingParams
from backend.config import BUY_THRESHOLD, SELL_THRESHOLD, SYMBOLS


class PersonaDecisionEngine:
    def __init__(self):
        self._signal_memory: dict[str, dict[str, list[float]]] = {}

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

        # Compute aggregate herding signal from other personas' trade direction bias
        herding_signal = self._compute_herding(all_states, persona.persona_id)

        # Panic check
        portfolio_val = persona.portfolio_value(prices)
        pnl_pct = (portfolio_val - 10000) / 10000
        if pnl_pct < params.panic_threshold:
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
            return intents

        # Process each symbol
        for symbol in SYMBOLS:
            price = prices.get(symbol, 0)
            if price <= 0:
                continue

            momentum = self._compute_momentum(symbol, price)
            volatility = self._compute_volatility(symbol, price)

            # Weighted composite score
            contrarian_adj = momentum * (1 - params.contrarianism) - momentum * params.contrarianism
            tech_signal = contrarian_adj * 0.6 + (1 - volatility / max(price * 0.1, 0.01)) * 0.4
            social_signal = herding_signal * params.herding_weight
            composite = params.tech_weight * tech_signal + (1 - params.tech_weight) * social_signal

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
                    continue

            # Buy / Sell decision
            trade_cash = persona.cash * params.trade_size_pct
            shares = max(1, int(trade_cash / price))

            if composite > BUY_THRESHOLD and persona.cash >= shares * price:
                intents.append(TradeIntent(
                    persona_id=persona.persona_id,
                    symbol=symbol,
                    direction="BUY" if composite > 0 else "SELL",
                    shares=shares,
                    limit_price=price * (1.02 if composite > 0 else 0.98),
                    reason="trend_follow" if composite > 0 else "contrarian",
                    timestamp=tick,
                ))
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

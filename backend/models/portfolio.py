from dataclasses import dataclass, field


@dataclass
class Holding:
    symbol: str
    shares: int
    avg_cost: float


@dataclass
class TradeIntent:
    persona_id: str
    symbol: str
    direction: str
    shares: int
    limit_price: float
    reason: str
    timestamp: float = 0.0


@dataclass
class ExecutedTrade:
    persona_id: str
    symbol: str
    direction: str
    shares: int
    price: float
    reason: str
    counterparty: str
    timestamp: float


@dataclass
class PersonaState:
    persona_id: str
    cash: float
    holdings: dict[str, Holding]
    trade_history: list[ExecutedTrade]
    last_decision_tick: int = -1

    def portfolio_value(self, prices: dict[str, float]) -> float:
        hv = sum(
            h.shares * prices.get(h.symbol, h.avg_cost)
            for h in self.holdings.values()
        )
        return self.cash + hv

    def pnl(self, initial_cash: float, prices: dict[str, float]) -> float:
        return self.portfolio_value(prices) - initial_cash

    def holding_count(self) -> int:
        return len([h for h in self.holdings.values() if h.shares > 0])

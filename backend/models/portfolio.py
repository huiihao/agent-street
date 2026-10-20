from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Holding:
    symbol: str
    shares: int
    avg_cost: float          # includes buy fees
    opened_tick: int = 0
    entry_context: dict = field(default_factory=dict)

    def market_value(self, price: float) -> float:
        return self.shares * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_cost) * self.shares


@dataclass
class TradeIntent:
    persona_id: str
    symbol: str
    direction: str           # "BUY" | "SELL"
    shares: int
    limit_price: float
    reason: str
    timestamp: float = 0.0
    context: dict = field(default_factory=dict)


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
    fee: float = 0.0
    realized_pnl: float = 0.0
    trade_id: str = ""
    liquidity: str = "house"  # "cross" | "house"


@dataclass
class PersonaState:
    persona_id: str
    cash: float
    holdings: dict[str, Holding]
    trade_history: list[ExecutedTrade]
    last_decision_tick: int = -1
    realized_pnl: float = 0.0
    peak_equity: float = 0.0
    last_panic_tick: int = -10**9
    symbol_cooldowns: dict[str, int] = field(default_factory=dict)
    signals: dict[str, float] = field(default_factory=dict)
    max_drawdown: float = 0.0
    winning_sells: int = 0
    total_sells: int = 0

    def portfolio_value(self, prices: dict[str, float]) -> float:
        return sum(
            h.shares * prices.get(h.symbol, h.avg_cost)
            for h in self.holdings.values()
            if h.shares > 0
        )

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.portfolio_value(prices)

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        return sum(
            h.unrealized_pnl(prices.get(h.symbol, h.avg_cost))
            for h in self.holdings.values()
            if h.shares > 0
        )

    def pnl(self, initial_cash: float, prices: dict[str, float]) -> float:
        return self.equity(prices) - initial_cash

    def return_pct(self, initial_cash: float, prices: dict[str, float]) -> float:
        return (self.equity(prices) / initial_cash - 1.0) if initial_cash else 0.0

    def holding_count(self) -> int:
        return len([h for h in self.holdings.values() if h.shares > 0])

    def holdings_detail(self, prices: dict[str, float]) -> list[dict]:
        rows = []
        for h in sorted(self.holdings.values(), key=lambda x: x.symbol):
            if h.shares <= 0:
                continue
            price = prices.get(h.symbol, h.avg_cost)
            rows.append({
                "symbol": h.symbol,
                "shares": h.shares,
                "avgCost": round(h.avg_cost, 4),
                "price": round(price, 4),
                "marketValue": round(h.shares * price, 2),
                "unrealizedPnl": round(h.unrealized_pnl(price), 2),
                "openedTick": h.opened_tick,
            })
        return rows

"""Order matching with an explicit market-maker ("House").

Semantics
---------
* Agent orders cross each other at a price inside both limit prices. A cross is
  only allowed when the best bid >= best offer; orders are price-then-time
  prioritised and may partially fill.
* Any residual order is absorbed by the House at the real market price adjusted
  by a configurable half-spread. The House balance sheet is tracked, so the
  simulation's total wealth is conserved (fees become a tracked treasury).
* Buys capitalise fees into average cost. Sells realise P&L against that cost.
  Zero-share positions are removed instead of lingering as ghosts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.config import FEE_BPS, MIN_FEE, SLIPPAGE_BPS
from backend.engine.market_data import MarketSnapshot
from backend.models.portfolio import ExecutedTrade, Holding, PersonaState, TradeIntent


@dataclass
class HouseState:
    cash: float = 0.0
    holdings: dict[str, int] = field(default_factory=dict)
    fees: float = 0.0

    def reset(self, symbols: list[str]) -> None:
        self.cash = 0.0
        self.holdings = {s: 0 for s in symbols}
        self.fees = 0.0


@dataclass
class CloseEvent:
    persona_id: str
    symbol: str
    shares: int
    entry_price: float
    exit_price: float
    realized_pnl: float
    fee: float
    entry_context: dict
    entry_tick: int
    exit_tick: int
    reason: str


@dataclass
class MatchOutcome:
    trades: list[ExecutedTrade]
    rejected: int = 0
    crossed_shares: int = 0
    house_shares: int = 0
    closed_events: list[CloseEvent] = field(default_factory=list)


class MatchingEngine:
    def __init__(
        self,
        fee_bps: float = FEE_BPS,
        slippage_bps: float = SLIPPAGE_BPS,
        min_fee: float = MIN_FEE,
    ):
        self.fee_bps = max(0.0, float(fee_bps))
        self.slippage_bps = max(0.0, float(slippage_bps))
        self.min_fee = max(0.0, float(min_fee))
        self._seq = 0

    def reset(self) -> None:
        self._seq = 0

    # ── public API ───────────────────────────────────────────

    def match(
        self,
        intents: list[TradeIntent],
        snapshot: MarketSnapshot,
        personas: dict[str, PersonaState],
        house: HouseState,
    ) -> MatchOutcome:
        trades: list[ExecutedTrade] = []
        closed_events: list[CloseEvent] = []
        rejected = 0
        crossed = 0
        house_shares = 0

        by_symbol: dict[str, dict[str, list[TradeIntent]]] = {}
        for intent in intents:
            if intent.shares <= 0 or intent.symbol not in snapshot.bars:
                continue
            if intent.direction not in ("BUY", "SELL"):
                continue
            if intent.persona_id not in personas:
                continue
            by_symbol.setdefault(intent.symbol, {"BUY": [], "SELL": []})[intent.direction].append(intent)

        for symbol, book in by_symbol.items():
            ref_price = snapshot.bars[symbol].close
            if ref_price <= 0:
                continue

            buys = sorted(book["BUY"], key=lambda x: (-x.limit_price, x.timestamp, x.persona_id))
            sells = sorted(book["SELL"], key=lambda x: (x.limit_price, x.timestamp, x.persona_id))

            # ── direct crosses ──────────────────────────────
            while buys and sells:
                buy = buys[0]
                sell = sells[0]
                if buy.limit_price + 1e-9 < sell.limit_price:
                    break

                buyer = personas.get(buy.persona_id)
                seller = personas.get(sell.persona_id)
                if not buyer or not seller:
                    if not buyer:
                        buys.pop(0)
                    if not seller:
                        sells.pop(0)
                    rejected += 1
                    continue

                price = min(buy.limit_price, max(sell.limit_price, (buy.limit_price + sell.limit_price) / 2.0))
                affordable = self._affordable_shares(buyer, price)
                available = self._available_shares(seller, symbol)
                qty = min(buy.shares, sell.shares, affordable, available)

                if qty <= 0:
                    if affordable <= 0 or buy.shares <= 0:
                        buys.pop(0)
                        rejected += 1
                    if available <= 0 or sell.shares <= 0:
                        sells.pop(0)
                        rejected += 1
                    continue

                trade_id = self._next_id()
                fee_buy = self._fee(qty * price)
                fee_sell = self._fee(qty * price)

                self._apply_buy(buyer, symbol, qty, price, fee_buy, buy.timestamp, buy.context)
                realized = self._apply_sell(
                    seller, symbol, qty, price, fee_sell, sell.timestamp,
                    sell.reason, closed_events,
                )
                house.fees += fee_buy + fee_sell

                trades.append(ExecutedTrade(
                    buy.persona_id, symbol, "BUY", qty, price, buy.reason,
                    sell.persona_id, buy.timestamp, fee_buy, 0.0, trade_id, "cross",
                ))
                trades.append(ExecutedTrade(
                    sell.persona_id, symbol, "SELL", qty, price, sell.reason,
                    buy.persona_id, sell.timestamp, fee_sell, realized, trade_id, "cross",
                ))

                buy.shares -= qty
                sell.shares -= qty
                crossed += qty
                if buy.shares <= 0:
                    buys.pop(0)
                if sell.shares <= 0:
                    sells.pop(0)

            # ── residual absorbed by the House ──────────────
            for intent in [i for i in buys + sells if i.shares > 0]:
                persona = personas.get(intent.persona_id)
                if not persona:
                    rejected += 1
                    continue

                if intent.direction == "BUY":
                    price = ref_price * (1.0 + self.slippage_bps / 10_000.0)
                    if intent.limit_price + 1e-9 < price:
                        rejected += 1
                        continue
                    qty = min(intent.shares, self._affordable_shares(persona, price))
                    if qty <= 0:
                        rejected += 1
                        continue
                    fee = self._fee(qty * price)
                    self._apply_buy(persona, symbol, qty, price, fee, intent.timestamp, intent.context)
                    house.cash += qty * price
                    house.holdings[symbol] = house.holdings.get(symbol, 0) - qty
                    house.fees += fee
                    trades.append(ExecutedTrade(
                        persona.persona_id, symbol, "BUY", qty, price, intent.reason,
                        "HOUSE", intent.timestamp, fee, 0.0, self._next_id(), "house",
                    ))
                else:
                    price = ref_price * (1.0 - self.slippage_bps / 10_000.0)
                    if intent.limit_price - 1e-9 > price:
                        rejected += 1
                        continue
                    qty = min(intent.shares, self._available_shares(persona, symbol))
                    if qty <= 0:
                        rejected += 1
                        continue
                    fee = self._fee(qty * price)
                    realized = self._apply_sell(
                        persona, symbol, qty, price, fee, intent.timestamp,
                        intent.reason, closed_events,
                    )
                    house.cash -= qty * price
                    house.holdings[symbol] = house.holdings.get(symbol, 0) + qty
                    house.fees += fee
                    trades.append(ExecutedTrade(
                        persona.persona_id, symbol, "SELL", qty, price, intent.reason,
                        "HOUSE", intent.timestamp, fee, realized, self._next_id(), "house",
                    ))
                house_shares += qty

        return MatchOutcome(
            trades=trades,
            rejected=rejected,
            crossed_shares=crossed,
            house_shares=house_shares,
            closed_events=closed_events,
        )

    # ── accounting ───────────────────────────────────────────

    def _affordable_shares(self, persona: PersonaState, price: float) -> int:
        if price <= 0 or persona.cash <= 0:
            return 0
        rate = self.fee_bps / 10_000.0
        budget = persona.cash
        shares = int(budget / (price * (1.0 + rate)))
        # Account for the minimum fee and float dust.
        while shares > 0 and shares * price * (1.0 + rate) + self.min_fee > budget + 1e-9:
            shares -= 1
        return max(0, shares)

    @staticmethod
    def _available_shares(persona: PersonaState, symbol: str) -> int:
        holding = persona.holdings.get(symbol)
        return max(0, holding.shares) if holding else 0

    def _fee(self, notional: float) -> float:
        return max(self.min_fee, round(notional * self.fee_bps / 10_000.0, 4))

    def _apply_buy(
        self,
        persona: PersonaState,
        symbol: str,
        qty: int,
        price: float,
        fee: float,
        tick: float,
        context: dict | None = None,
    ) -> None:
        notional = qty * price
        persona.cash -= notional + fee
        holding = persona.holdings.get(symbol)
        if holding is None or holding.shares <= 0:
            persona.holdings[symbol] = Holding(
                symbol=symbol,
                shares=qty,
                avg_cost=(notional + fee) / qty,
                opened_tick=int(tick),
                entry_context=dict(context or {}),
            )
        else:
            old_cost = holding.avg_cost * holding.shares
            holding.shares += qty
            holding.avg_cost = (old_cost + notional + fee) / holding.shares

    def _apply_sell(
        self,
        persona: PersonaState,
        symbol: str,
        qty: int,
        price: float,
        fee: float,
        tick: float,
        reason: str = "",
        closed_events: list[CloseEvent] | None = None,
    ) -> float:
        holding = persona.holdings.get(symbol)
        if holding is None or holding.shares <= 0:
            return 0.0
        qty = min(qty, holding.shares)
        notional = qty * price
        entry_price = holding.avg_cost
        entry_tick = holding.opened_tick
        entry_context = dict(holding.entry_context)
        realized = (price - entry_price) * qty - fee
        persona.realized_pnl += realized
        persona.total_sells += 1
        if realized > 0:
            persona.winning_sells += 1
        persona.cash += notional - fee
        holding.shares -= qty
        if holding.shares <= 0:
            persona.holdings.pop(symbol, None)
        if closed_events is not None:
            closed_events.append(CloseEvent(
                persona_id=persona.persona_id,
                symbol=symbol,
                shares=qty,
                entry_price=entry_price,
                exit_price=price,
                realized_pnl=realized,
                fee=fee,
                entry_context=entry_context,
                entry_tick=entry_tick,
                exit_tick=int(tick),
                reason=reason,
            ))
        return realized

    def _next_id(self) -> str:
        self._seq += 1
        return f"T{self._seq:07d}"

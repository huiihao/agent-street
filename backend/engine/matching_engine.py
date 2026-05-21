from backend.models.portfolio import TradeIntent, ExecutedTrade, PersonaState, Holding


class MatchingEngine:
    def __init__(self, strict: bool = False):
        self.strict = strict

    def match(
        self,
        intents: list[TradeIntent],
        prices: dict[str, float],
        personas: dict[str, PersonaState],
        house_cash: float,
        house_holdings: dict[str, int],
    ) -> tuple[list[ExecutedTrade], float, dict[str, int]]:
        trades: list[ExecutedTrade] = []

        # Group intents by symbol and direction
        by_symbol: dict[str, dict[str, list[TradeIntent]]] = {}
        for intent in intents:
            if intent.symbol not in by_symbol:
                by_symbol[intent.symbol] = {"BUY": [], "SELL": []}
            by_symbol[intent.symbol][intent.direction].append(intent)

        for symbol, dir_map in by_symbol.items():
            price = prices.get(symbol, 0)
            if price <= 0:
                continue

            buys = self._sort_buys(dir_map["BUY"])
            sells = self._sort_sells(dir_map["SELL"])

            # Direct crossing
            while buys and sells:
                buy = buys[0]
                sell = sells[0]
                if buy.limit_price >= sell.limit_price or not self.strict:
                    matched_shares = min(buy.shares, sell.shares)
                    if matched_shares <= 0:
                        if buy.shares <= 0:
                            buys.pop(0)
                        if sell.shares <= 0:
                            sells.pop(0)
                        continue

                    # Validate
                    buyer = personas.get(buy.persona_id)
                    seller = personas.get(sell.persona_id)
                    if not buyer or not seller:
                        if not buyer:
                            buys.pop(0)
                        if not seller:
                            sells.pop(0)
                        continue

                    cost = matched_shares * price
                    if buyer.cash < cost:
                        buys.pop(0)
                        continue
                    seller_holding = seller.holdings.get(symbol)
                    if not seller_holding or seller_holding.shares < matched_shares:
                        sells.pop(0)
                        continue

                    # Execute cross
                    buyer.cash -= cost
                    seller.cash += cost

                    if symbol not in buyer.holdings:
                        buyer.holdings[symbol] = Holding(symbol=symbol, shares=0, avg_cost=0)
                    bh = buyer.holdings[symbol]
                    total_cost_b = bh.shares * bh.avg_cost + cost
                    bh.shares += matched_shares
                    bh.avg_cost = total_cost_b / bh.shares if bh.shares > 0 else 0

                    seller.holdings[symbol].shares -= matched_shares

                    ts = buy.timestamp
                    trades.append(ExecutedTrade(buy.persona_id, symbol, "BUY", matched_shares, price, buy.reason, sell.persona_id, ts))
                    trades.append(ExecutedTrade(sell.persona_id, symbol, "SELL", matched_shares, price, sell.reason, buy.persona_id, ts))

                    buy.shares -= matched_shares
                    sell.shares -= matched_shares
                    if buy.shares <= 0:
                        buys.pop(0)
                    if sell.shares <= 0:
                        sells.pop(0)
                else:
                    break

            # House absorbs remaining intents
            remaining = buys + sells
            for intent in remaining:
                if intent.shares <= 0:
                    continue
                persona = personas.get(intent.persona_id)
                if not persona:
                    continue

                matched_shares = intent.shares
                cost = matched_shares * price

                if intent.direction == "BUY":
                    if persona.cash < cost:
                        continue
                    persona.cash -= cost
                    if symbol not in persona.holdings:
                        persona.holdings[symbol] = Holding(symbol=symbol, shares=0, avg_cost=0)
                    bh = persona.holdings[symbol]
                    total_cost = bh.shares * bh.avg_cost + cost
                    bh.shares += matched_shares
                    bh.avg_cost = total_cost / bh.shares if bh.shares > 0 else 0
                    house_holdings[symbol] = house_holdings.get(symbol, 0) - matched_shares
                    house_cash += cost
                else:
                    h = persona.holdings.get(symbol)
                    if not h or h.shares < matched_shares:
                        continue
                    h.shares -= matched_shares
                    persona.cash += cost
                    house_holdings[symbol] = house_holdings.get(symbol, 0) + matched_shares
                    house_cash -= cost

                trades.append(ExecutedTrade(
                    intent.persona_id, symbol, intent.direction,
                    matched_shares, price, intent.reason, "HOUSE", intent.timestamp
                ))

        return trades, house_cash, house_holdings

    def _sort_buys(self, buys: list[TradeIntent]) -> list[TradeIntent]:
        return sorted(buys, key=lambda x: x.limit_price, reverse=True)

    def _sort_sells(self, sells: list[TradeIntent]) -> list[TradeIntent]:
        return sorted(sells, key=lambda x: x.limit_price)

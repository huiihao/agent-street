import asyncio
import time
from backend.config import INITIAL_CASH, SYMBOLS, TICK_INTERVAL_SEC
from backend.models.portfolio import PersonaState, Holding, ExecutedTrade
from backend.models.market import (
    SimulationFrame, PersonaSnapshot, TradeRecord,
)
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.engine.market_data import MarketDataProvider
from backend.engine.persona_engine import PersonaDecisionEngine
from backend.engine.matching_engine import MatchingEngine


class SimulationLoop:
    def __init__(self):
        self.tick = 0
        self.running = False
        self.personas: dict[str, PersonaState] = {}
        self.house_cash = 0.0
        self.house_holdings: dict[str, int] = {}
        self.market = MarketDataProvider(SYMBOLS)
        self.decision_engine = PersonaDecisionEngine()
        self.matching_engine = MatchingEngine(strict=False)
        self._on_frame: callable | None = None

    def init_personas(self):
        for pid, defn in PERSONA_DEFINITIONS.items():
            self.personas[pid] = PersonaState(
                persona_id=pid,
                cash=INITIAL_CASH,
                holdings={},
                trade_history=[],
            )

    async def start(self):
        self.init_personas()
        self.house_cash = 0.0
        self.house_holdings = {s: 0 for s in SYMBOLS}
        self.tick = 0
        await self.market.fetch_init()
        self.running = True
        asyncio.create_task(self._loop())

    def stop(self):
        self.running = False

    async def _loop(self):
        while self.running:
            try:
                await self._do_tick()
            except Exception as e:
                print(f"Tick error: {e}")
            await asyncio.sleep(TICK_INTERVAL_SEC)

    async def _do_tick(self):
        prices, changes = await self.market.get_prices()

        all_intents = []
        for pid, persona in self.personas.items():
            defn = PERSONA_DEFINITIONS.get(pid)
            if not defn:
                continue
            intents = self.decision_engine.decide(
                persona, defn["params"], prices, changes,
                self.personas, self.tick,
            )
            all_intents.extend(intents)

        trades, self.house_cash, self.house_holdings = self.matching_engine.match(
            all_intents, prices, self.personas,
            self.house_cash, self.house_holdings,
        )

        for t in trades:
            persona = self.personas.get(t.persona_id)
            if persona:
                persona.trade_history.append(t)

        snapshots = self._build_snapshots(prices)
        trade_records = [
            TradeRecord.from_executed(t, PERSONA_DEFINITIONS.get(t.persona_id, {}).get("name", ""))
            for t in trades
        ]

        sentiment = self._compute_sentiment(prices)
        frame = SimulationFrame(
            tick=self.tick,
            prices=prices,
            changes=changes,
            personas=snapshots,
            trades=trade_records,
            sentiment=sentiment,
        )

        if self._on_frame:
            await self._on_frame(frame)

        self.tick += 1

    def _build_snapshots(self, prices: dict[str, float]) -> list[PersonaSnapshot]:
        snaps = []
        for pid, ps in self.personas.items():
            defn = PERSONA_DEFINITIONS.get(pid, {})
            pnl = ps.pnl(INITIAL_CASH, prices)
            pnl_pct = pnl / INITIAL_CASH
            if pnl_pct > 0.05:
                mood = "confident"
            elif pnl_pct > 0:
                mood = "calm"
            elif pnl_pct > -0.05:
                mood = "worried"
            elif pnl_pct > -0.10:
                mood = "panicked"
            else:
                mood = "panicked"
            snaps.append(PersonaSnapshot(
                persona_id=pid,
                name=defn.get("name", pid),
                cash=round(ps.cash, 2),
                pnl=round(pnl, 2),
                positions=ps.holding_count(),
                mood=mood,
            ))
        return snaps

    def _compute_sentiment(self, prices: dict[str, float]) -> float:
        pnls = [ps.pnl(INITIAL_CASH, prices) / INITIAL_CASH for ps in self.personas.values()]
        if not pnls:
            return 0.0
        avg = sum(pnls) / len(pnls)
        return max(-1.0, min(1.0, avg * 10))

    def on_frame(self, callback: callable):
        self._on_frame = callback

import asyncio
from backend.config import INITIAL_CASH, SYMBOLS, TICK_INTERVAL_SEC, REFLECTION_EVERY_N_TICKS
from backend.models.portfolio import PersonaState
from backend.models.market import (
    SimulationFrame, PersonaSnapshot, TradeRecord, ConversationRecord,
)
from backend.models.town import (
    LOCATIONS, HOME_ASSIGNMENTS, get_adjacent_agents,
)
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.mbti.types import TraitProfile
from backend.engine.market_data import HistoricalDataProvider
from backend.engine.persona_engine import PersonaDecisionEngine
from backend.engine.matching_engine import MatchingEngine
from backend.engine.memory_system import AgentMemory
from backend.engine.daily_routine import DailyRoutine
from backend.engine.conversation import ConversationSystem


class SimulationLoop:
    def __init__(self):
        self.tick = 0
        self.running = False
        self.personas: dict[str, PersonaState] = {}
        self.house_cash = 0.0
        self.house_holdings: dict[str, int] = {}
        self.market = HistoricalDataProvider(SYMBOLS)
        self.decision_engine = PersonaDecisionEngine()
        self.matching_engine = MatchingEngine(strict=False)
        # Generative Agents systems
        self.memories: dict[str, AgentMemory] = {}
        self.routines: dict[str, DailyRoutine] = {}
        self.conversation_system = ConversationSystem()
        self.agent_positions: dict[str, tuple[int, int]] = {}
        self._on_frame: callable | None = None

    def init_personas(self):
        self.personas.clear()
        self.memories.clear()
        self.routines.clear()
        for pid, defn in PERSONA_DEFINITIONS.items():
            self.personas[pid] = PersonaState(
                persona_id=pid,
                cash=INITIAL_CASH,
                holdings={},
                trade_history=[],
            )
            traits: TraitProfile = defn["traits"]
            memory = AgentMemory(pid, traits)
            self.memories[pid] = memory
            self.decision_engine.register_memory(pid, memory)

            routine = DailyRoutine(pid, traits)
            self.routines[pid] = routine
            self.agent_positions[pid] = routine.current_tile

    async def start(self):
        self.init_personas()
        self.house_cash = 0.0
        self.house_holdings = {s: 0 for s in SYMBOLS}
        self.tick = 0
        await self.market.fetch_init()
        prices, _ = await self.market.get_prices()
        # Seed initial observations
        for pid, memory in self.memories.items():
            for sym, price in prices.items():
                memory.observe(f"Market open — {sym} at ${price:.2f}", "price", 0.5, 0)
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

        # 1. Move agents around town
        location_changes: dict[str, str] = {}
        for pid, routine in self.routines.items():
            changed, new_loc = routine.tick(self.tick)
            self.agent_positions[pid] = routine.current_tile
            if routine.is_moving():
                routine.wander()
            if changed:
                location_changes[pid] = new_loc

        # 2. Generate reflections periodically
        if self.tick % REFLECTION_EVERY_N_TICKS == 0:
            for pid, memory in self.memories.items():
                new_refs = memory.reflect(self.tick, prices, changes)
                for ref in new_refs:
                    memory.observe(ref.content, "reflection", ref.confidence, self.tick)

        # 3. Conversations between nearby agents
        active_conversations = []
        for pid, traits_def in PERSONA_DEFINITIONS.items():
            if pid not in self.personas:
                continue
            # Get the location this agent is at
            routine = self.routines.get(pid)
            if not routine:
                continue
            loc_id = routine.current_location_id()
            loc = LOCATIONS.get(loc_id)
            if not loc:
                continue
            # Check if agent tile is within the location bounds
            tx, ty = self.agent_positions.get(pid, (0, 0))
            if not loc.contains(tx, ty):
                continue

            conv = self.conversation_system.try_converse(
                pid, traits_def["traits"],
                self.agent_positions, loc_id, self.tick,
                prices, changes,
                [],
            )
            if conv:
                active_conversations.append(conv)
                # Feed conversation to participants' memories
                for turn in conv.turns:
                    mem = self.memories.get(turn.speaker_id)
                    if mem:
                        mem.observe(
                            f"[{turn.speaker_id}]: \"{turn.content}\"",
                            "conversation", 0.4 + abs(turn.sentiment_effect),
                            self.tick,
                        )

        # 4. Agent trading decisions
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

        # 5. Matching engine
        trades, self.house_cash, self.house_holdings = self.matching_engine.match(
            all_intents, prices, self.personas,
            self.house_cash, self.house_holdings,
        )

        for t in trades:
            persona = self.personas.get(t.persona_id)
            if persona:
                persona.trade_history.append(t)

        # 6. Build frame with town data
        snapshots = self._build_snapshots(prices)
        trade_records = [
            TradeRecord.from_executed(t, PERSONA_DEFINITIONS.get(t.persona_id, {}).get("name", ""))
            for t in trades
        ]
        conv_records = [
            ConversationRecord(
                participants=c.participants,
                location=c.location,
                lines=[{"speaker": t.speaker_id, "content": t.content} for t in c.turns],
            )
            for c in active_conversations
        ]

        sentiment = self._compute_sentiment(prices)
        frame = SimulationFrame(
            tick=self.tick,
            prices=prices,
            changes=changes,
            personas=snapshots,
            trades=trade_records,
            sentiment=sentiment,
            conversations=conv_records,
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
            if pnl_pct > 0.10:
                mood = "excited"
            elif pnl_pct > 0.05:
                mood = "confident"
            elif pnl_pct > 0:
                mood = "calm"
            elif pnl_pct > -0.05:
                mood = "worried"
            elif pnl_pct > -0.10:
                mood = "panicked"
            else:
                mood = "panicked"

            routine = self.routines.get(pid)
            memory = self.memories.get(pid)
            tx, ty = self.agent_positions.get(pid, (0, 0))
            loc_id = routine.current_location_id() if routine else "home"
            loc_name = LOCATIONS[loc_id].name if loc_id in LOCATIONS else loc_id

            snaps.append(PersonaSnapshot(
                persona_id=pid,
                name=defn.get("name", pid),
                color=defn.get("color", "#888"),
                cash=round(ps.cash, 2),
                pnl=round(pnl, 2),
                positions=ps.holding_count(),
                mood=mood,
                tile_x=tx,
                tile_y=ty,
                location=loc_name,
                is_moving=routine.is_moving() if routine else False,
                recent_thoughts=memory.recent_thoughts(5) if memory else [],
                backstory=defn.get("backstory", ""),
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

"""Simulation orchestrator.

One tick:
  1. read the current, aligned market snapshot
  2. update shared indicators
  3. move agents, form reflections, hold conversations
  4. collect personality-driven intents and match them
  5. publish a fully-accounted frame

Reads never advance the replay. Only ``advance()`` at the end of a tick moves
the clock, which keeps REST snapshots idempotent.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import traceback
from datetime import datetime
from pathlib import Path

from backend.config import (
    INITIAL_CASH,
    LLM_REFLECTIONS_PER_BATCH,
    MAX_SPEED,
    REFLECTION_EVERY_N_TICKS,
    REFLECTION_MAX,
    SIM_SEED,
    SYMBOLS,
    TICK_INTERVAL_SEC,
)
from backend.engine.conversation import ConversationSystem
from backend.engine.daily_routine import DailyRoutine
from backend.engine.influence_network import InfluenceNetwork, apply_environment
from backend.engine.indicators import IndicatorEngine, MarketMetrics
from backend.engine.market_data import HistoricalDataProvider, MarketSnapshot
from backend.engine.matching_engine import HouseState, MatchingEngine
from backend.engine.memory_system import AgentMemory
from backend.engine.observer_engine import ObserverEngine
from backend.engine.persona_engine import PersonaDecisionEngine
from backend.engine.strategy import StrategyEngine, genome_from_persona
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.models.market import (
    ConversationRecord,
    PersonaSnapshot,
    SimulationFrame,
    TradeRecord,
)
from backend.models.portfolio import PersonaState
from backend.models.town import LOCATIONS, OBSERVER_HOMES

EPS = 1e-9

OBSERVER_DEFS = {
    "physicist": {
        "name": "Physicist",
        "color": "#7B9ECF",
        "backstory": (
            "Statistical physicist studying phase transitions in agent-market systems. "
            "Specialises in complex systems and critical phenomena."
        ),
    },
    "mathematician": {
        "name": "Mathematician",
        "color": "#9E7BCF",
        "backstory": "Graph theorist applying combinatorial optimisation to agent interaction networks.",
    },
    "social_engineer": {
        "name": "Social Engineer",
        "color": "#7FC8B0",
        "backstory": (
            "A social systems engineer who models narratives, trust, echo chambers and "
            "coordination failures. Sees the town as a network that can be steered."
        ),
    },
    "mystic": {
        "name": "Mystic",
        "color": "#CF7BAE",
        "backstory": "Reads tea leaves, casts I Ching hexagrams, and is right just often enough to be unsettling.",
    },
}


class SimulationLoop:
    def __init__(
        self,
        seed: int | None = None,
        enable_learning: bool = True,
        enable_imitation: bool = True,
        enable_mutation: bool = True,
        learning_scale: float = 1.0,
        imitation_scale: float = 1.0,
        mutation_scale: float = 1.0,
    ):
        self.seed = SIM_SEED if seed is None else int(seed)
        self.enable_learning = bool(enable_learning)
        self.enable_imitation = bool(enable_imitation)
        self.enable_mutation = bool(enable_mutation)
        self.learning_scale = max(0.0, float(learning_scale))
        self.imitation_scale = max(0.0, float(imitation_scale))
        self.mutation_scale = max(0.0, float(mutation_scale))
        self.tick = 0
        self.running = False
        self.personas: dict[str, PersonaState] = {}
        self.house = HouseState()
        self.market = HistoricalDataProvider(SYMBOLS)
        self.indicators = IndicatorEngine(SYMBOLS)
        self.decision_engine = PersonaDecisionEngine()
        self.strategy_engine = StrategyEngine(
            INITIAL_CASH,
            learning_scale=self.learning_scale,
            imitation_scale=self.imitation_scale,
            mutation_scale=self.mutation_scale,
        )
        self.observer_engine = ObserverEngine()
        self.influence_network = InfluenceNetwork()
        self.matching_engine = MatchingEngine()
        self.memories: dict[str, AgentMemory] = {}
        self.routines: dict[str, DailyRoutine] = {}
        self.conversation_system = ConversationSystem()
        self.agent_positions: dict[str, tuple[int, int]] = {}

        self._speed_multiplier = 1.0
        self._loop_task: asyncio.Task | None = None
        self._on_frame = None
        self._last_frame: SimulationFrame | None = None
        self._initialized = False
        self._activity: dict[str, str] = {}
        self._llm_tasks: set[asyncio.Task] = set()
        self._llm_cursor = 0
        self._invariant_failures = 0
        self._last_metrics: MarketMetrics | None = None
        self._trade_log = Path(__file__).resolve().parent.parent.parent / ".cache" / "trade_memory.jsonl"

    # ── lifecycle ────────────────────────────────────────────

    async def start(self) -> None:
        if self.running:
            return
        was_loaded = self.market.loaded
        await self.market.fetch_init()
        if not was_loaded:
            self.market.reset_index()

        if not was_loaded or not self._initialized:
            # Fresh data load can change the symbol universe; rebuild around it.
            self._init_all()
            self._initialized = True
        else:
            # Symbols may have been dropped during a late data load.
            self.house.holdings = {s: self.house.holdings.get(s, 0) for s in self.market.symbols}

        self.running = True
        self._loop_task = asyncio.create_task(self._loop(), name="simulation-loop")
        await self._broadcast_state()

    def stop(self) -> None:
        self.running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        self._cancel_llm_tasks()

    def reset(self) -> None:
        """Stop and rebuild every run-scoped structure (market replay rewinds)."""
        self.stop()
        if self.market.loaded:
            self.market.reset_index()
        if self.seed:
            random.seed(self.seed)
        self.tick = 0
        self._init_all()
        self._initialized = True
        self._last_frame = None
        self._invariant_failures = 0

    def _init_all(self) -> None:
        self.personas.clear()
        self.memories.clear()
        self.routines.clear()
        self.agent_positions.clear()
        self._activity.clear()
        self._last_metrics = None

        self.decision_engine.memories.clear()
        self.decision_engine.strategies.clear()
        self.strategy_engine.reset()
        self.influence_network.reset()
        self.decision_engine.influence = self.influence_network
        self._invariant_failures = 0
        self.observer_engine.reset()
        self.conversation_system.reset()
        self.matching_engine.reset()
        self.house.reset(self.market.symbols)
        self.indicators = IndicatorEngine(self.market.symbols)
        if self.market.loaded:
            self.indicators.warmup(self.market.warmup_history())

        if self.seed:
            random.seed(self.seed)

        for pid, defn in PERSONA_DEFINITIONS.items():
            self.personas[pid] = PersonaState(
                persona_id=pid,
                cash=INITIAL_CASH,
                holdings={},
                trade_history=[],
                peak_equity=INITIAL_CASH,
            )
            traits = defn["traits"]
            memory = AgentMemory(pid, traits)
            self.memories[pid] = memory
            self.decision_engine.register_memory(pid, memory)

            genome = genome_from_persona(traits, defn["params"])
            self.strategy_engine.register(pid, genome)
            self.decision_engine.register_strategy(pid, genome)

            routine = DailyRoutine(pid, traits)
            self.routines[pid] = routine
            self.agent_positions[pid] = routine.current_tile
            self._activity[pid] = "idle"

        snap = self.market.snapshot()
        if snap is not None:
            for pid, memory in self.memories.items():
                for symbol, bar in snap.bars.items():
                    memory.observe(
                        f"Market open — {symbol} at ${bar.close:.2f}",
                        "price", 0.45, self.tick, sentiment=0.0,
                    )

    async def run_headless(self, ticks: int):
        """Run ``ticks`` steps without real-time sleeps or a WebSocket.

        This is the experiment entry point: callers provide a loaded market
        provider (e.g. a frozen snapshot), seed the simulation, and collect
        frames through ``on_frame``. No background loop is created.
        """
        if not self.market.loaded:
            await self.market.fetch_init()
        if not self._initialized:
            self.market.reset_index()
            self._init_all()
            self._initialized = True
        for _ in range(max(0, int(ticks))):
            await self._do_tick()
        return self._last_frame

    def set_speed(self, multiplier: float) -> None:
        self._speed_multiplier = max(0.1, min(MAX_SPEED, float(multiplier)))

    @property
    def speed(self) -> float:
        return self._speed_multiplier

    # ── loop ─────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self.running:
            try:
                await self._do_tick()
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001 - keep the town alive
                print("[sim] tick failed:")
                traceback.print_exc()
            delay = max(0.02, TICK_INTERVAL_SEC / max(self._speed_multiplier, 0.1))
            await asyncio.sleep(delay)

    async def _do_tick(self) -> None:
        snap = self.market.snapshot()
        if snap is None:
            return
        prices = {s: b.close for s, b in snap.bars.items()}
        changes = dict(snap.changes)
        world_hour = snap.world_hour

        # Indicators: reset after a replay loop so the artificial price jump
        # never leaks into momentum or volatility.
        if snap.looped:
            # A replay loop starts a new session. Resetting the whole run keeps
            # the ledger coherent (no mark-to-market jump between day 5 and the
            # beginning of the next replay) and gives the strategy population a
            # clean generation 0, while the 3D world stays alive.
            self._cancel_llm_tasks()
            self.tick = 0
            self._init_all()
        metrics = self.indicators.update(snap.bars)
        self._last_metrics = metrics

        # 1. Movement
        location_changes: dict[str, str] = {}
        for pid, routine in self.routines.items():
            changed, new_loc = routine.tick(self.tick)
            self.agent_positions[pid] = routine.current_tile
            if changed:
                location_changes[pid] = new_loc

        # 2. Reflections (rule-based immediately; optional LLM enrichment)
        if self.tick % REFLECTION_EVERY_N_TICKS == 0:
            for pid, memory in self.memories.items():
                memory.reflect(self.tick, prices, changes)
            self._schedule_llm_reflections(prices, changes)

        # 3. Social graph decay + environment
        self.influence_network.decay(self.tick)
        self.decision_engine.influence = self.influence_network
        is_raining = snap.weather_rain

        # 4. Conversations
        active_conversations = []
        self.conversation_system.begin_tick(self.tick)
        for pid, defn in PERSONA_DEFINITIONS.items():
            routine = self.routines.get(pid)
            if not routine:
                continue
            loc_id = routine.current_location_id()
            loc = LOCATIONS.get(loc_id)
            if not loc:
                continue
            tx, ty = self.agent_positions.get(pid, (0, 0))
            if not loc.contains(tx, ty):
                continue
            conv = await self.conversation_system.try_converse(
                pid, defn["traits"], self.agent_positions, loc_id,
                self.tick, prices, changes,
            )
            if not conv:
                continue
            active_conversations.append(conv)
            for turn in conv.turns:
                memory = self.memories.get(turn.speaker_id)
                if memory:
                    memory.observe(
                        f"[{turn.speaker_id}]: \"{turn.content}\"",
                        "conversation",
                        0.35 + abs(turn.sentiment_effect),
                        self.tick,
                        sentiment=turn.sentiment_effect,
                    )
            self.influence_network.record_conversation(conv.participants, self.tick)
            if self.enable_imitation:
                self.strategy_engine.imitate(
                    conv.participants, self.influence_network, self.tick, loc_id,
                )

        # 5. Trading decisions
        all_intents = []
        for pid, persona in self.personas.items():
            defn = PERSONA_DEFINITIONS.get(pid)
            if not defn:
                continue
            routine = self.routines.get(pid)
            loc_id = routine.current_location_id() if routine else "home_nw"
            env_params = apply_environment(defn["params"], loc_id, world_hour, is_raining)
            all_intents.extend(self.decision_engine.decide(
                persona, env_params, defn["params"], snap, metrics,
                self.personas, self.tick,
            ))

        # 6. Matching
        outcome = self.matching_engine.match(all_intents, snap, self.personas, self.house)
        if outcome.closed_events and (self.enable_learning or self.enable_imitation):
            locations = {
                event.persona_id: self.routines[event.persona_id].current_location_id()
                for event in outcome.closed_events
                if event.persona_id in self.routines
            }
            self.strategy_engine.observe_closes(
                outcome.closed_events, self.tick, locations,
                update_weights=self.enable_learning,
            )
        if self.enable_mutation and self.tick % 20 == 0:
            self.strategy_engine.mutate(self.tick)
        trades = outcome.trades
        traded_agents: set[str] = set()
        panicked_agents: set[str] = set()
        for trade in trades:
            persona = self.personas.get(trade.persona_id)
            if persona:
                persona.trade_history.append(trade)
                if len(persona.trade_history) > 500:
                    persona.trade_history = persona.trade_history[-500:]
                traded_agents.add(trade.persona_id)
                if "panic" in trade.reason:
                    panicked_agents.add(trade.persona_id)
            self._log_trade(trade)

        chat_agents = {pid for conv in active_conversations for pid in conv.participants}
        for pid, routine in self.routines.items():
            if pid in panicked_agents:
                self._activity[pid] = "panicking"
            elif pid in traded_agents:
                self._activity[pid] = "trading"
            elif pid in chat_agents:
                self._activity[pid] = "chatting"
            elif routine.is_moving():
                self._activity[pid] = "moving"
            else:
                self._activity[pid] = "idle"

        # 7. Sentiment (market breadth + agent memories, not P&L)
        agent_sentiments = [m.get_sentiment() for m in self.memories.values()]
        agent_sentiment = sum(agent_sentiments) / max(len(agent_sentiments), 1)
        market_sentiment = math.tanh(metrics.avg_return / 0.0025)
        breadth = metrics.breadth
        sentiment = max(-1.0, min(1.0,
            0.45 * breadth + 0.25 * market_sentiment + 0.30 * agent_sentiment
        ))
        sentiment_parts = {
            "breadth": round(breadth, 4),
            "return": round(market_sentiment, 4),
            "agents": round(agent_sentiment, 4),
        }

        ecosystem = self.strategy_engine.ecosystem(self.personas, prices)

        # 8. Observer reports
        report_records = []
        for obs_id in ("physicist", "mathematician", "social_engineer", "mystic"):
            report = self.observer_engine.observe(
                obs_id, self.tick, snap, metrics, self.personas,
                self.memories, trades, sentiment, self.influence_network, ecosystem,
            )
            if report:
                report_records.append(report.to_payload())

        # 9. Frame
        snapshots = self._build_snapshots(prices, metrics)
        trade_records = [
            TradeRecord.from_executed(
                trade,
                PERSONA_DEFINITIONS.get(trade.persona_id, {}).get("name", trade.persona_id),
            )
            for trade in trades
        ]
        conv_records = [
            ConversationRecord(
                participants=conv.participants,
                location=conv.location,
                lines=[
                    {
                        "speaker": turn.speaker_id,
                        "content": turn.content,
                        "sentiment": round(turn.sentiment_effect, 2),
                    }
                    for turn in conv.turns
                ],
            )
            for conv in active_conversations
        ]

        total_equity = sum(p.equity(prices) for p in self.personas.values())
        expected_equity = INITIAL_CASH * len(self.personas)
        stats = {
            "totalEquity": round(total_equity, 2),
            "totalPnl": round(total_equity - expected_equity, 2),
            "totalReturnPct": round((total_equity / expected_equity - 1.0) if expected_equity else 0.0, 5),
            "fees": round(self.house.fees, 2),
            "activePositions": sum(p.holding_count() for p in self.personas.values()),
            "tradesThisTick": len(trades),
            "crossedShares": outcome.crossed_shares,
            "houseShares": outcome.house_shares,
            "rejectedIntents": outcome.rejected,
            "invariantFailures": self._invariant_failures,
        }

        if self.tick % 20 == 0:
            self._check_invariant(prices, expected_equity)

        frame = SimulationFrame(
            tick=self.tick,
            world_time=snap.world_time.strftime("%Y-%m-%d %H:%M"),
            prices=prices,
            changes=changes,
            personas=snapshots,
            trades=trade_records,
            sentiment=sentiment,
            conversations=conv_records,
            observer_reports=report_records,
            world_hour=round(world_hour, 3),
            ambient_hour=round(snap.ambient_hour, 3),
            weather_rain=snap.weather_rain,
            bar_index=snap.index,
            total_bars=snap.total_bars,
            looped=snap.looped,
            data_source=snap.source,
            source_info=self.market.source_info(),
            bars={symbol: bar.to_payload() for symbol, bar in snap.bars.items()},
            day_changes={k: round(v, 6) for k, v in snap.day_changes.items()},
            metrics={**metrics.to_dict(), "sentimentParts": sentiment_parts},
            sentiment_parts=sentiment_parts,
            stats=stats,
            ecosystem=ecosystem,
        )

        self._last_frame = frame
        if self._on_frame:
            try:
                await self._on_frame(frame)
            except Exception:  # noqa: BLE001
                traceback.print_exc()

        self.tick += 1
        self.market.advance()

    # ── snapshots & accounting ───────────────────────────────

    def _build_snapshots(self, prices: dict[str, float], metrics: MarketMetrics) -> list[PersonaSnapshot]:
        snaps: list[PersonaSnapshot] = []
        for pid, ps in self.personas.items():
            defn = PERSONA_DEFINITIONS.get(pid, {})
            equity = ps.equity(prices)
            pnl = equity - INITIAL_CASH
            return_pct = equity / INITIAL_CASH - 1.0 if INITIAL_CASH else 0.0
            peak = max(ps.peak_equity, equity)
            ps.peak_equity = peak
            drawdown = equity / peak - 1.0 if peak > 0 else 0.0
            if drawdown < ps.max_drawdown:
                ps.max_drawdown = drawdown
            win_rate = ps.winning_sells / ps.total_sells if ps.total_sells else 0.0

            mood = self._mood(return_pct, drawdown, self._activity.get(pid, "idle"))

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
                recent_thoughts=memory.recent_thoughts(6) if memory else [],
                backstory=defn.get("backstory", ""),
                equity=round(equity, 2),
                return_pct=round(return_pct, 5),
                realized_pnl=round(ps.realized_pnl, 2),
                unrealized_pnl=round(ps.unrealized_pnl(prices), 2),
                peak_equity=round(peak, 2),
                activity=self._activity.get(pid, "idle"),
                holdings=ps.holdings_detail(prices),
                signals=dict(ps.signals),
                max_drawdown=round(ps.max_drawdown, 5),
                win_rate=round(win_rate, 4),
                total_sells=ps.total_sells,
                strategy=self.strategy_engine.snapshot(pid),
            ))

        for obs_id, defn in OBSERVER_DEFS.items():
            home_id = OBSERVER_HOMES.get(obs_id)
            loc = LOCATIONS.get(home_id) if home_id else None
            snaps.append(PersonaSnapshot(
                persona_id=obs_id,
                name=defn["name"],
                color=defn["color"],
                cash=0, pnl=0, positions=0,
                mood="calm",
                tile_x=loc.tile_x if loc else 0,
                tile_y=loc.tile_y if loc else 0,
                location=loc.name if loc else "Observatory",
                is_moving=False,
                recent_thoughts=[],
                backstory=defn["backstory"],
                activity="idle",
                is_observer=True,
            ))
        return snaps

    @staticmethod
    def _mood(return_pct: float, drawdown: float, activity: str) -> str:
        if activity == "panicking" or drawdown <= -0.12:
            return "panicked"
        if return_pct > 0.08:
            return "excited"
        if return_pct > 0.03:
            return "confident"
        if return_pct > -0.02:
            return "calm"
        if return_pct > -0.06:
            return "worried"
        return "panicked"

    def _check_invariant(self, prices: dict[str, float], expected: float) -> None:
        """Total agent + house wealth + fees must be constant."""
        agent_wealth = sum(
            p.cash + sum(h.shares * prices.get(h.symbol, h.avg_cost) for h in p.holdings.values())
            for p in self.personas.values()
        )
        house_wealth = self.house.cash + sum(
            shares * prices.get(symbol, 0.0)
            for symbol, shares in self.house.holdings.items()
        )
        total = agent_wealth + house_wealth + self.house.fees
        if abs(total - expected) > 0.05:
            self._invariant_failures += 1
            print(
                f"[sim] wealth invariant broken at tick {self.tick}: "
                f"total={total:.4f} expected={expected:.4f} "
                f"delta={total - expected:+.4f}"
            )

    # ── async LLM enrichment ─────────────────────────────────

    def _schedule_llm_reflections(self, prices: dict[str, float], changes: dict[str, float]) -> None:
        try:
            from backend.engine.llm_client import llm_available
        except Exception:
            return
        if not llm_available():
            return
        if len(self._llm_tasks) >= 6:
            return

        ids = list(self.personas.keys())
        if not ids:
            return
        picks = []
        for _ in range(min(LLM_REFLECTIONS_PER_BATCH, len(ids))):
            picks.append(ids[self._llm_cursor % len(ids)])
            self._llm_cursor += 1

        for pid in picks:
            task = asyncio.create_task(
                self._run_llm_reflection(pid, prices, changes),
                name=f"llm-reflection-{pid}",
            )
            self._llm_tasks.add(task)
            task.add_done_callback(self._llm_tasks.discard)

    async def _run_llm_reflection(
        self,
        pid: str,
        prices: dict[str, float],
        changes: dict[str, float],
    ) -> None:
        from backend.engine.llm_client import generate_reflection, llm_available
        if not llm_available():
            return
        memory = self.memories.get(pid)
        defn = PERSONA_DEFINITIONS.get(pid)
        if not memory or not defn:
            return
        observations = [obs.content for obs in memory.observations[-8:]]
        try:
            content = await asyncio.wait_for(
                generate_reflection(
                    pid, defn.get("name", pid), defn.get("backstory", ""),
                    defn.get("motto", ""), observations, prices, self.tick,
                ),
                timeout=15.0,
            )
        except Exception:
            return
        if not content:
            return
        memory.add_reflection(
            content, self.tick, memory.get_sentiment(),
            source="llm", confidence=0.8,
        )

    def _cancel_llm_tasks(self) -> None:
        for task in list(self._llm_tasks):
            if not task.done():
                task.cancel()
        self._llm_tasks.clear()

    # ── persistence & status ─────────────────────────────────

    def _log_trade(self, trade) -> None:
        try:
            self._trade_log.parent.mkdir(exist_ok=True)
            entry = {
                "tick": self.tick,
                "agent": trade.persona_id,
                "direction": trade.direction,
                "symbol": trade.symbol,
                "shares": trade.shares,
                "price": round(trade.price, 4),
                "fee": round(trade.fee, 4),
                "realized_pnl": round(trade.realized_pnl, 4),
                "reason": trade.reason,
                "counterparty": trade.counterparty,
                "trade_id": trade.trade_id,
                "liquidity": trade.liquidity,
            }
            with open(self._trade_log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    async def _broadcast_state(self) -> None:
        if self._on_frame and self._last_frame is not None:
            await self._on_frame(self._last_frame)

    def status(self) -> dict:
        metrics = self._last_metrics
        snap = self.market.snapshot() if self.market.loaded else None
        return {
            "worldTime": snap.world_time.strftime("%Y-%m-%d %H:%M") if snap else None,
            "worldHour": round(snap.world_hour, 3) if snap else None,
            "ambientHour": round(snap.ambient_hour, 3) if snap else None,
            "running": self.running,
            "tick": self.tick,
            "speed": self._speed_multiplier,
            "personas": len(self.personas),
            "symbols": list(self.market.symbols),
            "progress": round(self.market.progress(), 4),
            "totalTicks": self.market.total_bars,
            "barIndex": self.market.index,
            "initialized": self._initialized,
            "data": self.market.source_info(),
            "metrics": metrics.to_dict() if metrics else None,
            "invariantFailures": self._invariant_failures,
        }

    def recent_observer_reports(self) -> list[dict]:
        latest: dict[str, dict] = {}
        for report in self.observer_engine.reports:
            latest[report.observer_id] = report.to_payload()
        return [
            latest[key]
            for key in ("physicist", "mathematician", "social_engineer", "mystic")
            if key in latest
        ]

    def recent_trades(self, limit: int = 40) -> list[dict]:
        from backend.ws_manager import trade_payload

        rows: list[dict] = []
        for pid, persona in self.personas.items():
            name = PERSONA_DEFINITIONS.get(pid, {}).get("name", pid)
            for trade in persona.trade_history[-limit:]:
                rows.append(trade_payload(trade, name))
        rows.sort(key=lambda row: row["tick"])
        return rows[-limit:]

    @property
    def last_frame(self) -> SimulationFrame | None:
        return self._last_frame

    def on_frame(self, callback) -> None:
        self._on_frame = callback

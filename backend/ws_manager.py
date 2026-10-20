"""WebSocket fan-out and frame serialisation."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from backend.models.market import SimulationFrame


def trade_payload(trade, persona_name: str = "") -> dict:
    return {
        "id": trade.trade_id,
        "tick": int(trade.timestamp),
        "persona": trade.persona_id,
        "personaName": persona_name or trade.persona_id,
        "symbol": trade.symbol,
        "direction": trade.direction,
        "shares": trade.shares,
        "price": trade.price,
        "reason": trade.reason,
        "counterparty": trade.counterparty,
        "fee": round(trade.fee, 4),
        "notional": round(trade.price * trade.shares, 2),
        "realizedPnl": round(trade.realized_pnl, 2),
        "liquidity": trade.liquidity,
    }


def frame_payload(frame: SimulationFrame) -> dict:
    return {
        "tick": frame.tick,
        "worldTime": frame.world_time,
        "worldHour": frame.world_hour,
        "ambientHour": frame.ambient_hour,
        "weather": {"rain": frame.weather_rain},
        "prices": frame.prices,
        "changes": frame.changes,
        "dayChanges": frame.day_changes,
        "bars": frame.bars,
        "personas": [
            {
                "id": p.persona_id,
                "name": p.name,
                "color": p.color,
                "cash": p.cash,
                "pnl": p.pnl,
                "positions": p.positions,
                "mood": p.mood,
                "tileX": p.tile_x,
                "tileY": p.tile_y,
                "location": p.location,
                "isMoving": p.is_moving,
                "thoughts": p.recent_thoughts,
                "backstory": p.backstory,
                "equity": p.equity,
                "returnPct": p.return_pct,
                "realizedPnl": p.realized_pnl,
                "unrealizedPnl": p.unrealized_pnl,
                "peakEquity": p.peak_equity,
                "activity": p.activity,
                "holdings": p.holdings,
                "signals": p.signals,
                "maxDrawdown": p.max_drawdown,
                "winRate": p.win_rate,
                "totalSells": p.total_sells,
                "strategy": p.strategy,
                "isObserver": p.is_observer,
            }
            for p in frame.personas
        ],
        "trades": [
            {
                "id": t.trade_id,
                "tick": frame.tick,
                "persona": t.persona_id,
                "personaName": t.persona_name,
                "symbol": t.symbol,
                "direction": t.direction,
                "shares": t.shares,
                "price": t.price,
                "reason": t.reason,
                "counterparty": t.counterparty,
                "counterpartyName": t.counterparty_name,
                "fee": t.fee,
                "notional": t.notional,
                "realizedPnl": t.realized_pnl,
                "liquidity": t.liquidity,
            }
            for t in frame.trades
        ],
        "conversations": [
            {
                "participants": c.participants,
                "location": c.location,
                "lines": c.lines,
            }
            for c in frame.conversations
        ],
        "observerReports": frame.observer_reports,
        "sentiment": frame.sentiment,
        "sentimentParts": frame.sentiment_parts,
        "barIndex": frame.bar_index,
        "totalBars": frame.total_bars,
        "looped": frame.looped,
        "dataSource": frame.data_source,
        "sourceInfo": frame.source_info,
        "metrics": frame.metrics,
        "stats": frame.stats,
        "ecosystem": frame.ecosystem,
    }


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def send(self, ws: WebSocket, data: dict) -> None:
        payload = json.dumps(data, default=str)
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=2.0)
        except Exception:
            await self.disconnect(ws)

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data, default=str)
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                # A stalled client must never hold the simulation loop hostage.
                await asyncio.wait_for(ws.send_text(payload), timeout=2.0)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    async def broadcast_frame(self, frame: SimulationFrame) -> None:
        await self.broadcast({"type": "tick", "data": frame_payload(frame)})

    async def broadcast_sim_state(self, sim) -> None:
        await self.broadcast({
            "type": "sim_state",
            "data": {
                "running": bool(sim and sim.running),
                "speed": sim.speed if sim else 1,
                "tick": sim.tick if sim else 0,
                "dataSource": sim.market.source if sim and sim.market.loaded else "loading",
            },
        })

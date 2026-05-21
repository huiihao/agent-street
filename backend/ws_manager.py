import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, data: dict):
        payload = json.dumps(data, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_frame(self, frame):
        data = {
            "type": "tick",
            "data": {
                "tick": frame.tick,
                "prices": frame.prices,
                "changes": frame.changes,
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
                    }
                    for p in frame.personas
                ],
                "trades": [
                    {
                        "persona": t.persona_id,
                        "personaName": t.persona_name,
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "shares": t.shares,
                        "price": t.price,
                        "reason": t.reason,
                        "counterparty": t.counterparty,
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
                "observerReports": [
                    {
                        "observerId": r["observer_id"],
                        "title": r["title"],
                        "content": r["content"],
                        "confidence": r["confidence"],
                        "tick": r["tick"],
                    }
                    for r in frame.observer_reports
                ],
                "sentiment": frame.sentiment,
            },
        }
        await self.broadcast(data)

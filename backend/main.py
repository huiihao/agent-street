from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.config import (
    FEE_BPS,
    HIST_INTERVAL,
    INITIAL_CASH,
    MAX_SPEED,
    SLIPPAGE_BPS,
    SYMBOLS,
    TICK_INTERVAL_SEC,
)
from backend.engine.simulation import OBSERVER_DEFS, SimulationLoop
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.models.town import HOME_ASSIGNMENTS, LOCATIONS, TILE_NAMES, TOWN_MAP
from backend.ws_manager import ConnectionManager, frame_payload

sim: SimulationLoop | None = None
ws_manager = ConnectionManager()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sim
    sim = SimulationLoop()
    sim.on_frame(ws_manager.broadcast_frame)
    yield
    if sim:
        sim.stop()


app = FastAPI(lifespan=lifespan, title="Agent Street", version="2.0")


# ── payload builders ─────────────────────────────────────────

def personas_payload() -> list[dict]:
    out = []
    for pid, d in PERSONA_DEFINITIONS.items():
        params = d["params"]
        traits = d["traits"]
        out.append({
            "id": pid,
            "name": d["name"],
            "color": d["color"],
            "motto": d["motto"],
            "backstory": d["backstory"],
            "traits": {
                "extraversion": traits.extraversion,
                "sensing": traits.sensing,
                "thinking": traits.thinking,
                "judging": traits.judging,
            },
            "params": {
                "risk_tolerance": params.risk_tolerance,
                "contrarianism": params.contrarianism,
                "reaction_speed": params.reaction_speed,
                "holding_period_ticks": params.holding_period_ticks,
                "tech_weight": params.tech_weight,
                "panic_threshold": params.panic_threshold,
                "greed_threshold": params.greed_threshold,
                "trade_size_pct": params.trade_size_pct,
                "herding_weight": params.herding_weight,
                "volatility_tolerance": params.volatility_tolerance,
            },
            "isObserver": False,
        })
    for obs_id, d in OBSERVER_DEFS.items():
        out.append({
            "id": obs_id,
            "name": d["name"],
            "color": d["color"],
            "motto": "",
            "backstory": d["backstory"],
            "traits": None,
            "params": None,
            "isObserver": True,
        })
    return out


def town_payload() -> dict:
    return {
        "map": TOWN_MAP,
        "tileNames": TILE_NAMES,
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "tileX": loc.tile_x,
                "tileY": loc.tile_y,
                "width": loc.width,
                "height": loc.height,
                "color": loc.color,
                "icon": loc.icon,
            }
            for loc in LOCATIONS.values()
        ],
        "homeAssignments": HOME_ASSIGNMENTS,
    }


def empty_history() -> dict:
    return {"times": [], "bars": {}, "index": 0, "totalBars": 0}


async def ensure_data_loaded() -> None:
    if sim and not sim.market.loaded:
        try:
            await sim.market.fetch_init()
        except Exception as exc:  # noqa: BLE001
            print(f"[api] data load failed: {exc}")


# ── REST ─────────────────────────────────────────────────────

@app.get("/api/bootstrap")
async def bootstrap():
    if sim is None:
        return {"error": "simulation not ready"}

    await ensure_data_loaded()
    history = sim.market.history(limit=180) if sim.market.loaded else empty_history()
    frame = frame_payload(sim.last_frame) if sim.last_frame else None
    return {
        "symbols": list(sim.market.symbols) if sim.market.loaded else list(SYMBOLS),
        "initialCash": INITIAL_CASH,
        "tickIntervalSec": TICK_INTERVAL_SEC,
        "maxSpeed": MAX_SPEED,
        "barInterval": HIST_INTERVAL,
        "history": history,
        "status": sim.status(),
        "frame": frame,
        "observerReports": sim.recent_observer_reports(),
        "recentTrades": sim.recent_trades(40),
        "personas": personas_payload(),
        "town": town_payload(),
        "config": {
            "feeBps": FEE_BPS,
            "slippageBps": SLIPPAGE_BPS,
        },
        "serverTime": datetime.now(tz=timezone.utc).isoformat(),
    }


@app.get("/api/personas")
async def get_personas():
    return personas_payload()


@app.get("/api/status")
async def get_status():
    if sim is None:
        return {"running": False, "tick": 0, "personas": 0, "symbols": SYMBOLS}
    return {
        **sim.status(),
        "connections": ws_manager.connection_count,
    }


@app.get("/api/health")
async def health():
    data = sim.market.source_info() if sim else {}
    healthy = (
        sim is not None
        and sim.market.loaded
        and not sim.market.stale
        and sim.market.source != "synthetic"
    )
    return {
        "ok": healthy,
        "source": data.get("source", "unloaded"),
        "stale": data.get("stale", True),
        "warnings": data.get("warnings", []),
        "running": bool(sim and sim.running),
    }


@app.get("/api/market")
async def get_market():
    """Read-only current bar. Never advances the replay."""
    if sim is None or not sim.market.loaded:
        return {"prices": {}, "changes": {}, "loaded": False}
    snap = sim.market.snapshot()
    if snap is None:
        return {"prices": {}, "changes": {}, "loaded": False}
    return {
        "loaded": True,
        "prices": {s: b.close for s, b in snap.bars.items()},
        "changes": snap.changes,
        "dayChanges": snap.day_changes,
        "bars": {s: b.to_payload() for s, b in snap.bars.items()},
        "barIndex": snap.index,
        "totalBars": snap.total_bars,
        "worldTime": snap.world_time.isoformat(),
        "source": sim.market.source_info(),
    }


@app.get("/api/market/history")
async def market_history(limit: int = Query(default=180, ge=10, le=2000)):
    if sim is None or not sim.market.loaded:
        return empty_history()
    return sim.market.history(limit=limit)


@app.get("/api/town")
async def get_town():
    return town_payload()


@app.post("/api/sim/start")
async def sim_start():
    if sim and not sim.running:
        await sim.start()
        await ws_manager.broadcast_sim_state(sim)
    return {"ok": True, "running": bool(sim and sim.running), "status": sim.status() if sim else None}


@app.post("/api/sim/stop")
async def sim_stop():
    if sim:
        sim.stop()
        await ws_manager.broadcast_sim_state(sim)
    return {"ok": True, "running": False}


@app.post("/api/sim/reset")
async def sim_reset():
    if sim:
        sim.reset()
        await ws_manager.broadcast_sim_state(sim)
        await ws_manager.broadcast({"type": "reset", "data": sim.status()})
    return {"ok": True, "status": sim.status() if sim else None}


# ── WebSocket ────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        await ws_manager.send(ws, {
            "type": "hello",
            "data": {
                "status": sim.status() if sim else None,
                "frame": frame_payload(sim.last_frame) if sim and sim.last_frame else None,
                "observerReports": sim.recent_observer_reports() if sim else [],
                "recentTrades": sim.recent_trades(40) if sim else [],
            },
        })
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = str(data.get("action", ""))

            try:
                if action == "ping":
                    await ws_manager.send(ws, {"type": "pong", "data": {"t": datetime.now(tz=timezone.utc).isoformat()}})
                elif action == "start" and sim:
                    if not sim.running:
                        await sim.start()
                    await ws_manager.broadcast_sim_state(sim)
                    if sim.last_frame:
                        await ws_manager.send(ws, {"type": "tick", "data": frame_payload(sim.last_frame)})
                elif action == "stop" and sim:
                    sim.stop()
                    await ws_manager.broadcast_sim_state(sim)
                elif action == "reset" and sim:
                    sim.reset()
                    await ws_manager.broadcast_sim_state(sim)
                    await ws_manager.broadcast({"type": "reset", "data": sim.status()})
                elif action.startswith("speed:") and sim:
                    try:
                        sim.set_speed(float(action.split(":", 1)[1]))
                    except ValueError:
                        pass
                    await ws_manager.broadcast_sim_state(sim)
            except Exception as exc:  # noqa: BLE001
                print(f"[ws] action '{action}' failed: {exc}")
                await ws_manager.send(ws, {"type": "error", "data": {"action": action, "message": str(exc)}})
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception:
        await ws_manager.disconnect(ws)


# ── static frontend ──────────────────────────────────────────

@app.get("/")
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
app.mount("/vendor", StaticFiles(directory=str(FRONTEND_DIR / "vendor")), name="vendor")
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

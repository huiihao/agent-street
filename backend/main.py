import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from backend.ws_manager import ConnectionManager
from backend.engine.simulation import SimulationLoop
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.config import SYMBOLS
from backend.models.town import TOWN_MAP, LOCATIONS, TILE_NAMES, HOME_ASSIGNMENTS

sim: SimulationLoop | None = None
ws_manager = ConnectionManager()

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sim
    sim = SimulationLoop()
    sim.on_frame(lambda f: ws_manager.broadcast_frame(f))
    yield
    if sim:
        sim.stop()


app = FastAPI(lifespan=lifespan, title="Mimic Stock Market")


@app.get("/api/personas")
async def get_personas():
    return [
        {
            "id": pid,
            "name": d["name"],
            "color": d["color"],
            "motto": d["motto"],
            "params": {
                "risk_tolerance": d["params"].risk_tolerance,
                "contrarianism": d["params"].contrarianism,
                "reaction_speed": d["params"].reaction_speed,
                "holding_period_ticks": d["params"].holding_period_ticks,
                "tech_weight": d["params"].tech_weight,
                "panic_threshold": d["params"].panic_threshold,
                "greed_threshold": d["params"].greed_threshold,
                "trade_size_pct": d["params"].trade_size_pct,
                "herding_weight": d["params"].herding_weight,
                "volatility_tolerance": d["params"].volatility_tolerance,
            },
        }
        for pid, d in PERSONA_DEFINITIONS.items()
    ]


@app.get("/api/status")
async def get_status():
    if sim is None:
        return {"running": False, "tick": 0, "personas": 0, "symbols": SYMBOLS}
    return {
        "running": sim.running,
        "tick": sim.tick,
        "speed": sim._speed_multiplier if sim else 1,
        "personas": len(sim.personas),
        "symbols": SYMBOLS,
        "progress": sim.market.progress() if sim.market else 0,
        "totalTicks": sim.market.estimate_total_ticks() if sim.market else 0,
    }


@app.post("/api/sim/start")
async def sim_start():
    if sim and not sim.running:
        await sim.start()
    return {"ok": True, "running": sim.running if sim else False}


@app.post("/api/sim/stop")
async def sim_stop():
    if sim:
        sim.stop()
    return {"ok": True, "running": False}


@app.post("/api/sim/reset")
async def sim_reset():
    if sim:
        sim.stop()
        sim.init_personas()
        sim.tick = 0
        sim.house_cash = 0.0
        sim.house_holdings = {s: 0 for s in SYMBOLS}
    return {"ok": True}


@app.get("/api/market")
async def get_market():
    if sim is None:
        return {"prices": {}, "changes": {}}
    prices, changes = await sim.market.get_prices()
    return {"prices": prices, "changes": changes}


@app.get("/api/town")
async def get_town():
    """Return town map, locations, and home assignments for frontend rendering."""
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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            action = data.get("action", "")
            if action == "start" and sim:
                if not sim.running:
                    await sim.start()
            elif action == "stop" and sim:
                sim.stop()
                sim._loop_task = None
            elif action and action.startswith("speed:"):
                if sim:
                    try:
                        sim.set_speed(float(action.split(":")[1]))
                    except ValueError:
                        pass
            elif action == "reset" and sim:
                sim.stop()
                sim.init_personas()
                sim.tick = 0
                sim.house_cash = 0.0
                sim.house_holdings = {s: 0 for s in SYMBOLS}
            await ws_manager.broadcast({"type": "sim_state", "data": {
                "running": sim.running if sim else False,
                "speed": sim._speed_multiplier if sim else 1,
            }})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


@app.get("/")
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


# Mount static files at /static to avoid conflicts with API routes
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

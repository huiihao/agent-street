from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.portfolio import ExecutedTrade


@dataclass
class PersonaSnapshot:
    persona_id: str
    name: str
    cash: float
    pnl: float
    positions: int
    mood: str
    tile_x: int = 0
    tile_y: int = 0
    location: str = "home"
    is_moving: bool = False
    color: str = "#888"
    recent_thoughts: list[str] = field(default_factory=list)
    backstory: str = ""
    # Enriched accounting / behaviour
    equity: float = 0.0
    return_pct: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float = 0.0
    activity: str = "idle"
    holdings: list[dict] = field(default_factory=list)
    signals: dict[str, float] = field(default_factory=dict)
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_sells: int = 0
    strategy: dict = field(default_factory=dict)
    is_observer: bool = False


@dataclass
class TradeRecord:
    persona_id: str
    persona_name: str
    symbol: str
    direction: str
    shares: int
    price: float
    reason: str
    counterparty: str
    counterparty_name: str = ""
    fee: float = 0.0
    notional: float = 0.0
    realized_pnl: float = 0.0
    trade_id: str = ""
    liquidity: str = "house"

    @staticmethod
    def from_executed(t: ExecutedTrade, persona_name: str = "") -> "TradeRecord":
        return TradeRecord(
            persona_id=t.persona_id,
            persona_name=persona_name or t.persona_id,
            symbol=t.symbol,
            direction=t.direction,
            shares=t.shares,
            price=t.price,
            reason=t.reason,
            counterparty=t.counterparty,
            fee=round(t.fee, 4),
            notional=round(t.price * t.shares, 2),
            realized_pnl=round(t.realized_pnl, 2),
            trade_id=t.trade_id,
            liquidity=t.liquidity,
        )


@dataclass
class ConversationRecord:
    participants: list[str]
    location: str
    lines: list[dict]


@dataclass
class SimulationFrame:
    tick: int
    world_time: str
    prices: dict[str, float]
    changes: dict[str, float]
    personas: list[PersonaSnapshot]
    trades: list[TradeRecord]
    sentiment: float
    conversations: list[ConversationRecord] = field(default_factory=list)
    observer_reports: list[dict] = field(default_factory=list)
    # Market context
    world_hour: float = 12.0
    ambient_hour: float = 12.0
    weather_rain: bool = False
    bar_index: int = 0
    total_bars: int = 0
    looped: bool = False
    data_source: str = ""
    source_info: dict = field(default_factory=dict)
    bars: dict[str, dict] = field(default_factory=dict)
    day_changes: dict[str, float] = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    sentiment_parts: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    ecosystem: dict = field(default_factory=dict)

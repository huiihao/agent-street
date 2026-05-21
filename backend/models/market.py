from dataclasses import dataclass, field
from backend.models.portfolio import ExecutedTrade


@dataclass
class PriceTick:
    symbol: str
    price: float
    change_pct: float
    volume: int
    timestamp: float


@dataclass
class PersonaSnapshot:
    persona_id: str
    name: str
    cash: float
    pnl: float
    positions: int
    mood: str  # "confident", "worried", "excited", "calm", "panicked"
    # New fields for Smallville integration
    tile_x: int = 0
    tile_y: int = 0
    location: str = "home"
    is_moving: bool = False
    color: str = "#888"
    recent_thoughts: list[str] = field(default_factory=list)
    backstory: str = ""


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
        )


@dataclass
class ConversationRecord:
    participants: list[str]
    location: str
    lines: list[dict]  # [{speaker: str, content: str}]


@dataclass
class SimulationFrame:
    tick: int
    prices: dict[str, float]
    changes: dict[str, float]  # symbol -> change_pct
    personas: list[PersonaSnapshot]
    trades: list[TradeRecord]
    sentiment: float
    conversations: list[ConversationRecord] = field(default_factory=list)

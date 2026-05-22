"""
Agent coupling network + environment effects.

Agents influence each other through:
  1. Conversations — direct sentiment transfer
  2. Co-location — shared space amplifies herding
  3. Trust graph — familiarity weights influence

Environment modifies trading parameters:
  - Building type (Cafe=social, Library=analytical, Park=contrarian, etc.)
  - Time of day (morning=energetic, night=cautious)
  - Weather proxy (rain=dampened mood)
"""

import math
from dataclasses import dataclass, field
from backend.mbti.types import TradingParams
from backend.models.town import LOCATIONS


# ── Environment modifiers per location ────────────────────────

LOCATION_MODIFIERS: dict[str, dict] = {
    "cafe": {
        "herding_weight": +0.20,
        "contrarianism": -0.10,
        "reaction_speed": +0.05,
        "desc": "social buzz amplifies groupthink",
    },
    "market": {
        "reaction_speed": +0.15,
        "tech_weight": +0.10,
        "risk_tolerance": +0.05,
        "desc": "trading floor adrenaline",
    },
    "library": {
        "tech_weight": +0.20,
        "herding_weight": -0.15,
        "holding_period_ticks": +4,
        "desc": "quiet analysis, deeper research",
    },
    "square": {
        "volatility_tolerance": +0.15,
        "herding_weight": +0.10,
        "contrarianism": -0.05,
        "desc": "crowd courage in open space",
    },
    "park": {
        "contrarianism": +0.15,
        "herding_weight": -0.10,
        "panic_threshold": +0.02,  # more tolerant (less negative)
        "desc": "solitude breeds independent thought",
    },
    "home_ne": {
        "panic_threshold": +0.03,
        "risk_tolerance": -0.05,
        "desc": "safe haven, conservative at home",
    },
    "home_nw": {
        "panic_threshold": +0.03,
        "risk_tolerance": -0.05,
        "desc": "safe haven",
    },
    "home_se": {
        "panic_threshold": +0.03,
        "risk_tolerance": -0.05,
        "desc": "safe haven",
    },
    "home_sw": {
        "panic_threshold": +0.03,
        "risk_tolerance": -0.05,
        "desc": "safe haven",
    },
}

# ── Time-of-day modifiers (hour 0-24) ─────────────────────────

def time_modifier(hour: float) -> dict:
    """Return param deltas based on world hour."""
    if 22 <= hour or hour < 5:
        return {"risk_tolerance": -0.10, "reaction_speed": -0.10}  # night: cautious
    elif 5 <= hour < 8:
        return {"reaction_speed": +0.05, "risk_tolerance": -0.02}  # dawn: waking up
    elif 8 <= hour < 11:
        return {"reaction_speed": +0.10, "risk_tolerance": +0.05}  # morning: energetic
    elif 11 <= hour < 14:
        return {"reaction_speed": +0.05, "trade_size_pct": +0.02}  # lunch: active
    elif 14 <= hour < 17:
        return {}                                                     # afternoon: neutral
    elif 17 <= hour < 20:
        return {"risk_tolerance": +0.05, "tech_weight": -0.05}       # evening: looser
    elif 20 <= hour < 22:
        return {"risk_tolerance": -0.05, "contrarianism": +0.05}     # late: reflective
    return {}

# ── Trust / familiarity graph ──────────────────────────────────

@dataclass
class TrustEdge:
    weight: float          # 0-1, how much A trusts B
    conversations: int     # count of past conversations
    last_tick: int


class InfluenceNetwork:
    """Tracks agent relationships and computes influence weights."""

    def __init__(self):
        self.edges: dict[str, dict[str, TrustEdge]] = {}  # a_id -> {b_id: edge}
        self._init_trust()

    def _init_trust(self):
        """Seed trust based on MBTI compatibility."""
        # Same home → baseline trust
        from backend.mbti.personas import PERSONA_DEFINITIONS
        from backend.models.town import HOME_ASSIGNMENTS

        for aid in PERSONA_DEFINITIONS:
            self.edges.setdefault(aid, {})
            for bid in PERSONA_DEFINITIONS:
                if aid == bid:
                    continue
                home_a = HOME_ASSIGNMENTS.get(aid, "")
                home_b = HOME_ASSIGNMENTS.get(bid, "")
                # Same home = higher baseline; similar E/I = easier trust
                traits_a = PERSONA_DEFINITIONS[aid]["traits"]
                traits_b = PERSONA_DEFINITIONS[bid]["traits"]
                e_sim = 1 - abs(traits_a.extraversion - traits_b.extraversion)
                t_sim = 1 - abs(traits_a.thinking - traits_b.thinking)
                base = 0.10
                if home_a == home_b:
                    base = 0.35  # housemates
                base += 0.10 * e_sim + 0.05 * t_sim
                self.edges[aid][bid] = TrustEdge(
                    weight=min(1.0, base),
                    conversations=0,
                    last_tick=-100,
                )

    def record_conversation(self, participants: list[str], tick: int):
        """Strengthen edges between all participants."""
        for i, a in enumerate(participants):
            for b in participants[i + 1:]:
                self._strengthen(a, b, tick)

    def _strengthen(self, a: str, b: str, tick: int):
        edge = self.edges.get(a, {}).get(b)
        if not edge:
            edge = TrustEdge(weight=0.1, conversations=0, last_tick=tick)
            self.edges.setdefault(a, {})[b] = edge
        edge.conversations += 1
        edge.last_tick = tick
        edge.weight = min(1.0, edge.weight + 0.03)
        # Symmetric
        rev = self.edges.get(b, {}).get(a)
        if rev:
            rev.conversations += 1
            rev.last_tick = tick
            rev.weight = min(1.0, rev.weight + 0.03)

    def decay(self, tick: int):
        """Decay trust edges that haven't been reinforced recently."""
        for aid, targets in self.edges.items():
            for bid, edge in targets.items():
                if tick - edge.last_tick > 30:
                    edge.weight = max(0.05, edge.weight - 0.01)

    def get_trust(self, a: str, b: str) -> float:
        edge = self.edges.get(a, {}).get(b)
        return edge.weight if edge else 0.1

    def get_trusted_opinions(self, agent_id: str, exclude_id: str | None = None) -> dict[str, float]:
        """Return {agent_id: trust_weight} for agents this agent trusts most."""
        edges = self.edges.get(agent_id, {})
        ranked = sorted(edges.items(), key=lambda x: x[1].weight, reverse=True)
        result = {}
        for bid, edge in ranked:
            if bid == exclude_id:
                continue
            if edge.weight > 0.2:
                result[bid] = edge.weight
            if len(result) >= 5:
                break
        return result

    def influence_signal(self, agent_id: str, memories: dict, prices: dict) -> float:
        """Weighted sentiment of trusted agents: -1 to +1."""
        trusted = self.get_trusted_opinions(agent_id)
        if not trusted:
            return 0.0
        total_weight = 0.0
        weighted_sent = 0.0
        for bid, weight in trusted.items():
            mem = memories.get(bid)
            if mem:
                s = mem.get_sentiment()
                weighted_sent += s * weight
                total_weight += weight
        return weighted_sent / max(total_weight, 0.01)

    def colocated_agents_at(self, location_id: str, positions: dict, self_id: str, radius: int = 3) -> list[str]:
        """Find agents near a location."""
        loc = LOCATIONS.get(location_id)
        if not loc:
            return []
        nearby = []
        for aid, (tx, ty) in positions.items():
            if aid == self_id:
                continue
            if loc.contains(tx, ty):
                nearby.append(aid)
        return nearby


# ── Modifier application ──────────────────────────────────────

def apply_environment(
    base: TradingParams,
    location_id: str,
    world_hour: float = 12,
    is_raining: bool = False,
) -> TradingParams:
    """Return a modified TradingParams reflecting current environment."""

    # Start with base values as dict
    p = {
        "risk_tolerance": base.risk_tolerance,
        "contrarianism": base.contrarianism,
        "reaction_speed": base.reaction_speed,
        "holding_period_ticks": base.holding_period_ticks,
        "tech_weight": base.tech_weight,
        "panic_threshold": base.panic_threshold,
        "greed_threshold": base.greed_threshold,
        "trade_size_pct": base.trade_size_pct,
        "herding_weight": base.herding_weight,
        "volatility_tolerance": base.volatility_tolerance,
    }

    # Apply location modifiers
    loc_mods = LOCATION_MODIFIERS.get(location_id, {})
    for key, delta in loc_mods.items():
        if key in p:
            p[key] += delta

    # Apply time-of-day
    time_mods = time_modifier(world_hour)
    for key, delta in time_mods.items():
        if key in p:
            p[key] += delta

    # Rain dampens mood
    if is_raining:
        p["risk_tolerance"] -= 0.05
        p["reaction_speed"] -= 0.03

    # Clamp all values to [0, 1] (except special ones)
    for key in p:
        if key in ("holding_period_ticks",):
            p[key] = max(1, min(60, int(p[key])))
        elif key in ("panic_threshold", "greed_threshold"):
            p[key] = max(-0.50, min(0.50, p[key]))
        else:
            p[key] = max(0.0, min(1.0, p[key]))

    return TradingParams(**p)

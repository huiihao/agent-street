"""Agent-to-agent conversations.

Rule-based lines are always available and produced synchronously inside the
generator. The templates, chance, cooldown, radius and per-location bias all
come from ``config/interaction_rules.json`` (with environment overrides). When
the optional LLM layer is enabled for the ``conversation`` capability, lines
are generated with a hard timeout; any failure falls back to the rule
templates. Agents have per-tick and per-agent cooldowns so the town does not
spend every frame talking over itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.engine.rules import (
    GREETINGS,
    RESPONSES_BEARISH,
    RESPONSES_BULLISH,
    RESPONSES_NEUTRAL,
    SENTIMENT_WORDS,
    get_rules,
)
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.mbti.types import TraitProfile
from backend.models.town import LOCATIONS, get_adjacent_agents


@dataclass
class ConversationTurn:
    speaker_id: str
    content: str
    sentiment_effect: float
    tick: int
    source: str = "rule"  # rule | llm


@dataclass
class Conversation:
    participants: list[str]
    location: str
    turns: list[ConversationTurn]
    tick: int

    def is_active(self, current_tick: int, duration: int = 3) -> bool:
        return current_tick - self.tick < duration


def _format(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


class ConversationSystem:
    def __init__(self, rules=None):
        self.rules = rules or get_rules()
        self.recent_conversations: list[Conversation] = []
        self._busy_until: dict[str, int] = {}
        self._last_tick = -1
        self._count_this_tick = 0

    def begin_tick(self, tick: int) -> None:
        if tick != self._last_tick:
            self._last_tick = tick
            self._count_this_tick = 0

    def reset(self) -> None:
        self.recent_conversations.clear()
        self._busy_until.clear()
        self._last_tick = -1
        self._count_this_tick = 0

    def _location_multiplier(self, location_id: str) -> float:
        multipliers = self.rules.get("conversation.location_multipliers", {}) or {}
        value = multipliers.get(location_id)
        if value is None and location_id.startswith("home_"):
            value = multipliers.get("home", 1.0)
        try:
            return max(0.0, min(5.0, float(value if value is not None else 1.0)))
        except (TypeError, ValueError):
            return 1.0

    async def try_converse(
        self,
        agent_id: str,
        traits: TraitProfile,
        agent_positions: dict[str, tuple[int, int]],
        location_id: str,
        tick: int,
        prices: dict[str, float],
        changes: dict[str, float],
        recent_trades: list[dict] | None = None,
    ) -> Conversation | None:
        self.begin_tick(tick)
        max_per_tick = int(self.rules.get("conversation.max_per_tick", 2))
        if self._count_this_tick >= max_per_tick:
            return None
        if tick < self._busy_until.get(agent_id, -1):
            return None

        radius = int(self.rules.get("conversation.radius", 4))
        nearby = get_adjacent_agents(
            agent_positions.get(agent_id, (0, 0)), agent_positions, agent_id, radius=radius,
        )
        nearby = [pid for pid in nearby if tick >= self._busy_until.get(pid, -1)]
        if not nearby:
            return None

        base_chance = float(self.rules.get("conversation.chance", 0.30))
        chance = float(self.rules.for_agent(
            agent_id, "conversation.chance", base_chance,
        ))
        chance = max(0.0, min(1.0, chance * self._location_multiplier(location_id)))
        if random.random() > chance:
            return None

        partners = random.sample(nearby, min(random.randint(1, 2), len(nearby)))
        participants = [agent_id] + partners
        symbols = list(prices.keys())
        if not symbols:
            return None
        symbol = random.choice(symbols)
        price = prices.get(symbol, 0.0)
        change_val = changes.get(symbol, 0.0)
        templates = self.rules.get("conversation.templates", {}) or {}
        sentiment_words = templates.get("sentiment_words") or SENTIMENT_WORDS
        sentiment_word = random.choice(sentiment_words)

        turns: list[ConversationTurn] = []
        llm_lines = await self._llm_lines(participants, symbol, price, change_val, location_id)
        if llm_lines:
            for speaker_id, line in llm_lines:
                turns.append(ConversationTurn(
                    speaker_id, line,
                    _line_sentiment(line), tick, source="llm",
                ))
        else:
            is_contrarian = (1.0 - traits.extraversion) > 0.5
            bias_change = -change_val if is_contrarian else change_val
            greeting = _format(
                random.choice(templates.get("greetings") or GREETINGS),
                symbol=symbol, sentiment_word=sentiment_word,
            )
            initiator_sentiment = 0.3 if bias_change > 0.001 else -0.3 if bias_change < -0.001 else 0.0
            turns.append(ConversationTurn(agent_id, greeting, initiator_sentiment, tick))

            for partner_id in partners:
                p_def = PERSONA_DEFINITIONS.get(partner_id, {})
                p_traits = p_def.get("traits")
                p_extravert = bool(p_traits and p_traits.extraversion > 0.5)
                if bias_change > 0.001:
                    resp = _format(
                        random.choice(templates.get("bullish") or RESPONSES_BULLISH),
                        symbol=symbol,
                    )
                    sent = 0.22
                elif bias_change < -0.001:
                    resp = _format(
                        random.choice(templates.get("bearish") or RESPONSES_BEARISH),
                        symbol=symbol,
                    )
                    sent = -0.22
                else:
                    resp = _format(
                        random.choice(templates.get("neutral") or RESPONSES_NEUTRAL),
                        symbol=symbol,
                    )
                    sent = 0.0
                if not p_extravert:
                    resp = resp.replace("I'm", "I'd rather say I'm")
                turns.append(ConversationTurn(partner_id, resp, sent, tick))

        # A bull/bear debate makes the reasoning visible; keep it occasional.
        debate_chance = float(self.rules.get("conversation.debate_chance", 0.12))
        if random.random() < debate_chance and len(participants) >= 2:
            bull_id, bear_id = random.sample(participants, 2)
            symbol2 = random.choice(symbols)
            debate = templates.get("debate") or [
                "{symbol} is mispriced — the numbers support the long.",
                "Or the market already priced the good news.",
                "Then the risk/reward wasn't in your favour to begin with.",
            ]
            if not isinstance(debate, list) or len(debate) < 2:
                debate = [
                    "{symbol} is mispriced — the numbers support the long.",
                    "Or the market already priced the good news.",
                    "Then the risk/reward wasn't in your favour to begin with.",
                ]
            third = (
                debate[2] if len(debate) > 2
                else "Then the risk/reward wasn't in your favour to begin with."
            )
            turns.extend([
                ConversationTurn(bull_id, _format(debate[0], symbol=symbol2), 0.25, tick),
                ConversationTurn(bear_id, debate[1], -0.20, tick),
                ConversationTurn(bull_id, third, 0.15, tick),
            ])

        conversation = Conversation(
            participants=participants,
            location=location_id,
            turns=turns,
            tick=tick,
        )
        self.recent_conversations.append(conversation)
        if len(self.recent_conversations) > 50:
            self.recent_conversations = self.recent_conversations[-50:]
        self._count_this_tick += 1
        cooldown = int(self.rules.for_agent(
            agent_id, "conversation.cooldown_ticks",
            self.rules.get("conversation.cooldown_ticks", 5),
        ))
        until = tick + max(0, cooldown)
        for pid in participants:
            self._busy_until[pid] = until
        return conversation

    async def _llm_lines(
        self,
        participants: list[str],
        symbol: str,
        price: float,
        change: float,
        location_id: str,
    ) -> list[tuple[str, str]] | None:
        try:
            from backend.engine.llm_client import generate_conversation_line, llm_available
        except Exception:
            return None
        if not llm_available("conversation"):
            return None

        import asyncio

        location = LOCATIONS.get(location_id)
        location_name = location.name if location else "a small town street"
        lines: list[tuple[str, str]] = []
        for speaker_id in participants:
            defn = PERSONA_DEFINITIONS.get(speaker_id, {})
            listener_id = next((p for p in participants if p != speaker_id), speaker_id)
            traits = defn.get("traits")
            traits_desc = (
                f"{'extravert' if traits and traits.extraversion > 0.5 else 'introvert'}, "
                f"{'analytical' if traits and traits.thinking > 0.5 else 'intuitive'}"
            )
            try:
                line = await asyncio.wait_for(
                    generate_conversation_line(
                        speaker_id, defn.get("name", speaker_id), traits_desc,
                        listener_id, symbol, price, change, [],
                        location_name=location_name,
                    ),
                    timeout=3.0,
                )
            except Exception:
                return None
            if not line:
                return None
            lines.append((speaker_id, line))
        return lines

    def get_active_at_location(self, location_id: str, tick: int) -> list[Conversation]:
        return [
            c for c in self.recent_conversations
            if c.location == location_id and c.is_active(tick)
        ]

    def get_agent_recent_turns(self, agent_id: str, n: int = 5) -> list[ConversationTurn]:
        turns: list[ConversationTurn] = []
        for conv in reversed(self.recent_conversations):
            for turn in conv.turns:
                if turn.speaker_id == agent_id:
                    turns.append(turn)
                    if len(turns) >= n:
                        return turns
        return turns


def _line_sentiment(line: str) -> float:
    lower = line.lower()
    positive = sum(word in lower for word in ("buy", "bull", "long", "add", "strong", "up", "room"))
    negative = sum(word in lower for word in ("sell", "bear", "short", "trim", "risk", "down", "heavy"))
    score = 0.18 * positive - 0.18 * negative
    return max(-0.45, min(0.45, score))

"""Agent-to-agent conversations.

Rule-based lines are always available and produced synchronously inside the
generator. When ``LLM_CONVERSATIONS`` is enabled, lines are generated through
the async LLM client with a hard timeout; any failure falls back to templates.
Agents have per-tick and per-agent cooldowns so the town does not spend every
frame talking over itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.config import (
    CONVERSATION_CHANCE,
    CONVERSATION_COOLDOWN_TICKS,
    MAX_CONVERSATIONS_PER_TICK,
    LLM_CONVERSATIONS,
)
from backend.mbti.personas import PERSONA_DEFINITIONS
from backend.mbti.types import TraitProfile
from backend.models.town import get_adjacent_agents


@dataclass
class ConversationTurn:
    speaker_id: str
    content: str
    sentiment_effect: float
    tick: int


@dataclass
class Conversation:
    participants: list[str]
    location: str
    turns: list[ConversationTurn]
    tick: int

    def is_active(self, current_tick: int, duration: int = 3) -> bool:
        return current_tick - self.tick < duration


GREETINGS = [
    "What's your read on {symbol} today?",
    "How's your book holding up?",
    "Did you see the {symbol} tape just now?",
    "Volatility is doing all the talking today.",
    "I keep staring at {symbol} and can't decide.",
    "You look like you've seen something in {symbol}.",
    "Market feels {sentiment_word}. Am I wrong?",
    "Quick sanity check: are you long or flat here?",
]

RESPONSES_BULLISH = [
    "I'm adding {symbol}. The bid keeps stepping up.",
    "{symbol} has room — the trend is doing the work.",
    "I bought more this morning. The data looks clean.",
    "Everyone's leaning in. I'd rather be early than late.",
    "The pullback was bought in seconds. That tells you something.",
]

RESPONSES_BEARISH = [
    "I'm trimming {symbol}. The risk isn't paying anymore.",
    "Something feels heavy in this tape.",
    "I sold {symbol} this morning. I'll take the win.",
    "The bounce is thin. I'm not chasing it.",
    "Cash is a position, and right now it's my favourite one.",
]

RESPONSES_NEUTRAL = [
    "I'm flat and watching. No edge here yet.",
    "Could go either way. I'll let the market tip its hand.",
    "Waiting for the next bar before I do anything.",
    "The signal is muddy. I'd rather miss it than force it.",
    "Let me check my numbers again before we talk size.",
]

SENTIMENT_WORDS = ["bullish", "bearish", "choppy", "quiet", "frantic", "sleepy", "heavy", "springy"]


class ConversationSystem:
    def __init__(self):
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
        if self._count_this_tick >= MAX_CONVERSATIONS_PER_TICK:
            return None
        if tick < self._busy_until.get(agent_id, -1):
            return None

        nearby = get_adjacent_agents(
            agent_positions.get(agent_id, (0, 0)), agent_positions, agent_id, radius=4,
        )
        nearby = [pid for pid in nearby if tick >= self._busy_until.get(pid, -1)]
        if not nearby:
            return None
        if random.random() > CONVERSATION_CHANCE:
            return None

        partners = random.sample(nearby, min(random.randint(1, 2), len(nearby)))
        participants = [agent_id] + partners
        symbols = list(prices.keys())
        if not symbols:
            return None
        symbol = random.choice(symbols)
        price = prices.get(symbol, 0.0)
        change_val = changes.get(symbol, 0.0)
        sentiment_word = random.choice(SENTIMENT_WORDS)

        turns: list[ConversationTurn] = []
        llm_lines = await self._llm_lines(participants, symbol, price, change_val) if LLM_CONVERSATIONS else None
        if llm_lines:
            for speaker_id, line in llm_lines:
                turns.append(ConversationTurn(
                    speaker_id, line,
                    _line_sentiment(line), tick,
                ))
        else:
            is_contrarian = (1.0 - traits.extraversion) > 0.5
            bias_change = -change_val if is_contrarian else change_val
            greeting = random.choice(GREETINGS).format(
                symbol=symbol, sentiment_word=sentiment_word,
            )
            initiator_sentiment = 0.3 if bias_change > 0.001 else -0.3 if bias_change < -0.001 else 0.0
            turns.append(ConversationTurn(agent_id, greeting, initiator_sentiment, tick))

            for partner_id in partners:
                p_def = PERSONA_DEFINITIONS.get(partner_id, {})
                p_traits = p_def.get("traits")
                p_extravert = bool(p_traits and p_traits.extraversion > 0.5)
                if bias_change > 0.001:
                    resp = random.choice(RESPONSES_BULLISH).format(symbol=symbol)
                    sent = 0.22
                elif bias_change < -0.001:
                    resp = random.choice(RESPONSES_BEARISH).format(symbol=symbol)
                    sent = -0.22
                else:
                    resp = random.choice(RESPONSES_NEUTRAL).format(symbol=symbol)
                    sent = 0.0
                if not p_extravert:
                    resp = resp.replace("I'm", "I'd rather say I'm")
                turns.append(ConversationTurn(partner_id, resp, sent, tick))

        # A bull/bear debate makes the reasoning visible; keep it occasional.
        if random.random() < 0.12 and len(participants) >= 2:
            bull_id, bear_id = random.sample(participants, 2)
            symbol2 = random.choice(symbols)
            turns.extend([
                ConversationTurn(bull_id, f"{symbol2} is mispriced — the numbers support the long.", 0.25, tick),
                ConversationTurn(bear_id, "Or the market already priced the good news.", -0.20, tick),
                ConversationTurn(bull_id, "Then the risk/reward wasn't in your favour to begin with.", 0.15, tick),
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
        until = tick + CONVERSATION_COOLDOWN_TICKS
        for pid in participants:
            self._busy_until[pid] = until
        return conversation

    async def _llm_lines(
        self,
        participants: list[str],
        symbol: str,
        price: float,
        change: float,
    ) -> list[tuple[str, str]] | None:
        try:
            from backend.engine.llm_client import generate_conversation_line, llm_available
        except Exception:
            return None
        if not llm_available():
            return None

        import asyncio

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

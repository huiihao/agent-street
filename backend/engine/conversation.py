import random
from dataclasses import dataclass, field
from backend.mbti.types import TraitProfile
from backend.models.town import get_adjacent_agents


@dataclass
class ConversationTurn:
    speaker_id: str
    content: str
    sentiment_effect: float  # -1.0 to +1.0, how it affects listeners
    tick: int


@dataclass
class Conversation:
    participants: list[str]
    location: str
    turns: list[ConversationTurn]
    tick: int

    def is_active(self, current_tick: int, duration: int = 3) -> bool:
        return current_tick - self.tick < duration


# Conversation templates keyed by personality and context
GREETINGS = [
    "Hey, what do you think of the market today?",
    "How's your portfolio holding up?",
    "Seen any good setups lately?",
    "The volatility is crazy, right?",
    "Mind if I pick your brain about {symbol}?",
    "Did you catch {symbol}'s move just now?",
    "I've got a feeling about {symbol}.",
    "Market's been {sentiment_word} all morning.",
]

RESPONSES_BULLISH = [
    "I'm loading up on {symbol}. This is just the beginning.",
    "The trend is your friend. I'm all in.",
    "Feeling bullish. The data looks solid.",
    "Everyone's piling in. Momentum is real.",
    "This rally has legs. Trust me.",
    "I just bought more {symbol}. Can't miss this.",
]

RESPONSES_BEARISH = [
    "I'm trimming positions. Too much risk right now.",
    "Something feels off about this market.",
    "I sold {symbol} this morning. Locking in profits.",
    "Bears are waking up. Stay cautious.",
    "The technicals look weak. I'd wait.",
    "Cash is a position too, you know.",
]

RESPONSES_NEUTRAL = [
    "I'm just watching for now. No clear signal.",
    "Hard to read. Could go either way.",
    "Waiting for more data before I decide.",
    "Let me check my notes. Give me a tick.",
    "The noise is too loud. I'll sit this one out.",
]

SENTIMENT_WORDS = ["bullish", "bearish", "choppy", "quiet", "frantic", "sleepy", "red-hot", "ice-cold"]


class ConversationSystem:
    def __init__(self):
        self.recent_conversations: list[Conversation] = []

    def try_converse(
        self,
        agent_id: str,
        traits: TraitProfile,
        agent_positions: dict[str, tuple[int, int]],
        location_id: str,
        tick: int,
        prices: dict[str, float],
        changes: dict[str, float],
        recent_trades: list[dict],
    ) -> Conversation | None:
        """Attempt to start or join a conversation. Returns None if no conversation happens."""
        nearby = get_adjacent_agents(agent_positions.get(agent_id, (0, 0)), agent_positions, agent_id, radius=4)
        if not nearby:
            return None

        # Don't talk every tick
        if random.random() > 0.25:
            return None

        # Pick 1-2 conversation partners
        partners = random.sample(nearby, min(random.randint(1, 2), len(nearby)))

        # Build conversation
        participants = [agent_id] + partners
        symbol = random.choice(list(prices.keys()))
        sentiment_word = random.choice(SENTIMENT_WORDS)

        is_extravert = traits.extraversion > 0.5
        is_thinking = traits.thinking > 0.5
        is_contrarian = (1 - traits.extraversion) > 0.5  # introverts tend contrarian

        # Speaker 1 (initiator)
        greeting = random.choice(GREETINGS).format(symbol=symbol, sentiment_word=sentiment_word)

        # Determine initiator's sentiment bias
        change_val = changes.get(symbol, 0)
        if is_contrarian:
            change_val = -change_val
        initiator_bias = "bullish" if change_val > 0 else "bearish" if change_val < -0.005 else "neutral"
        initiator_sentiment = 0.3 if initiator_bias == "bullish" else -0.3 if initiator_bias == "bearish" else 0.0

        turns = [ConversationTurn(agent_id, greeting, initiator_sentiment, tick)]

        # Partner responses
        for partner_id in partners:
            if initiator_bias == "bullish":
                resp = random.choice(RESPONSES_BULLISH).format(symbol=symbol)
                sent = 0.2
            elif initiator_bias == "bearish":
                resp = random.choice(RESPONSES_BEARISH).format(symbol=symbol)
                sent = -0.2
            else:
                resp = random.choice(RESPONSES_NEUTRAL).format(symbol=symbol)
                sent = 0.0
            turns.append(ConversationTurn(partner_id, resp, sent, tick))

        conv = Conversation(
            participants=participants,
            location=location_id,
            turns=turns,
            tick=tick,
        )
        self.recent_conversations.append(conv)
        if len(self.recent_conversations) > 50:
            self.recent_conversations = self.recent_conversations[-50:]

        return conv

    def get_active_at_location(self, location_id: str, tick: int) -> list[Conversation]:
        return [
            c for c in self.recent_conversations
            if c.location == location_id and c.is_active(tick)
        ]

    def get_agent_recent_turns(self, agent_id: str, n: int = 5) -> list[ConversationTurn]:
        turns: list[ConversationTurn] = []
        for conv in reversed(self.recent_conversations):
            for t in conv.turns:
                if t.speaker_id == agent_id:
                    turns.append(t)
                    if len(turns) >= n:
                        return turns
        return turns

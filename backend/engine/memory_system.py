"""Observation -> reflection -> sentiment memory.

Sentiment is no longer inferred by scanning text for words like "bull" or
"dark". Every observation carries an explicit signed sentiment supplied by the
caller (price change, conversation effect, reflection outcome), and decaying
recency weights turn those into a bounded score. This makes the sentiment an
actual function of the data the agent saw.

Reflections are rule-based and synchronous, so the tick loop never waits on a
network. When an LLM is configured, the simulation schedules an asynchronous
enrichment that appends a richer reflection without blocking the simulation.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from backend.config import OBSERVATION_MAX, REFLECTION_MAX
from backend.mbti.types import TraitProfile

EPS = 1e-9


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class Observation:
    content: str
    category: str          # price | news | conversation | reflection
    importance: float      # 0..1
    tick: int
    sentiment: float = 0.0  # -1..1, signed meaning for this agent
    timestamp: float = field(default_factory=time.time)
    seq: int = 0


@dataclass
class Reflection:
    content: str
    confidence: float
    source_observations: list[int]
    tick: int
    sentiment: float = 0.0
    source: str = "rule"   # rule | llm


class AgentMemory:
    def __init__(self, agent_id: str, traits: TraitProfile):
        self.agent_id = agent_id
        self.traits = traits
        self.observations: list[Observation] = []
        self.reflections: list[Reflection] = []
        self.current_tick = 0
        self._seq = 0
        self._last_reflected_seq = 0

    # ── perception ───────────────────────────────────────────

    def observe(
        self,
        content: str,
        category: str,
        importance: float,
        tick: int,
        sentiment: float = 0.0,
    ) -> Observation:
        self.current_tick = max(self.current_tick, tick)
        self._seq += 1
        obs = Observation(
            content=content,
            category=category,
            importance=_clip(importance, 0.0, 1.0),
            tick=tick,
            sentiment=_clip(sentiment),
            seq=self._seq,
        )
        self.observations.append(obs)
        if len(self.observations) > OBSERVATION_MAX:
            self.observations = self.observations[-OBSERVATION_MAX:]
        return obs

    # ── reflection ───────────────────────────────────────────

    def reflect(
        self,
        tick: int,
        prices: dict[str, float],
        changes: dict[str, float],
    ) -> list[Reflection]:
        self.current_tick = max(self.current_tick, tick)
        pending = [
            obs for obs in self.observations
            if obs.seq > self._last_reflected_seq and obs.importance >= 0.25
        ]
        if not pending:
            return []
        self._last_reflected_seq = self._seq

        grouped: dict[str, list[Observation]] = {}
        for obs in pending:
            grouped.setdefault(obs.category, []).append(obs)

        content, sentiment = self._rule_reflection(grouped, prices, changes, pending)
        confidence = _clip(
            0.35 + 0.25 * self.traits.thinking + 0.20 * min(1.0, len(pending) / 8.0),
            0.2, 0.9,
        )
        ref = Reflection(
            content=content,
            confidence=confidence,
            source_observations=[obs.seq for obs in pending],
            tick=tick,
            sentiment=sentiment,
            source="rule",
        )
        self._append_reflection(ref)
        return [ref]

    def add_reflection(
        self,
        content: str,
        tick: int,
        sentiment: float,
        source: str = "llm",
        confidence: float = 0.75,
    ) -> Reflection:
        ref = Reflection(
            content=content.strip(),
            confidence=_clip(confidence, 0.1, 1.0),
            source_observations=[],
            tick=tick,
            sentiment=_clip(sentiment),
            source=source,
        )
        self._append_reflection(ref)
        self.current_tick = max(self.current_tick, tick)
        return ref

    def _append_reflection(self, ref: Reflection) -> None:
        self.reflections.append(ref)
        if len(self.reflections) > REFLECTION_MAX:
            self.reflections = self.reflections[-REFLECTION_MAX:]

    def _rule_reflection(
        self,
        grouped: dict[str, list[Observation]],
        prices: dict[str, float],
        changes: dict[str, float],
        pending: list[Observation],
    ) -> tuple[str, float]:
        avg_sentiment = sum(o.sentiment * o.importance for o in pending) / max(
            sum(o.importance for o in pending), EPS
        )
        strongest_symbol, strongest_change = ("the market", 0.0)
        if changes:
            strongest_symbol, strongest_change = max(changes.items(), key=lambda kv: abs(kv[1]))

        price_obs = grouped.get("price", [])
        chat_obs = grouped.get("conversation", [])
        sentence = ""
        if price_obs and abs(strongest_change) > 1e-5:
            direction = "jumped" if strongest_change > 0 else "slid"
            sentence = (
                f"{strongest_symbol} {direction} {abs(strongest_change):.2%} "
                f"while I was watching"
            )
            if avg_sentiment > 0.25:
                sentence += "; buyers still look in control."
            elif avg_sentiment < -0.25:
                sentence += "; the tape feels heavy."
            else:
                sentence += "; conviction is thin on both sides."
        elif chat_obs:
            speakers = sorted({
                obs.content.split("]")[0].lstrip("[")
                for obs in chat_obs
                if obs.content.startswith("[")
            })
            who = ", ".join(speakers[:2]) if speakers else "the others"
            sentence = (
                f"{who} sounded {'positive' if avg_sentiment > 0 else 'cautious' if avg_sentiment < 0 else 'undecided'}"
                f" — I'm adjusting my read."
            )
        elif avg_sentiment > 0.15:
            sentence = "The order flow feels constructive. I want to stay involved."
        elif avg_sentiment < -0.15:
            sentence = "Something is off in the tape. I'd rather protect capital."
        else:
            sentence = "Quiet tape, mixed signals. Patience is a position too."

        if self.traits.thinking > 0.7 and price_obs:
            sentence += " Checking the signal against my own model."
        elif self.traits.extraversion > 0.7:
            sentence += " I should hear what the town thinks."

        return sentence, _clip(avg_sentiment)

    # ── retrieval ────────────────────────────────────────────

    def get_sentiment(self) -> float:
        """Decaying weighted sentiment from observations and reflections."""
        tick = self.current_tick
        total_weight = 0.0
        score = 0.0
        for obs in reversed(self.observations):
            age = max(0, tick - obs.tick)
            decay = 0.92 ** age
            weight = obs.importance * decay
            score += obs.sentiment * weight
            total_weight += weight
        for ref in reversed(self.reflections):
            age = max(0, tick - ref.tick)
            decay = 0.96 ** age
            weight = ref.confidence * decay * 1.4
            score += ref.sentiment * weight
            total_weight += weight
        if total_weight <= EPS:
            return 0.0
        return _clip(score / total_weight)

    def recent_thoughts(self, n: int = 8) -> list[str]:
        items: list[tuple[int, str]] = []
        for ref in self.reflections[-n:]:
            label = "[THINK]" if ref.source == "rule" else "[LLM]"
            items.append((ref.tick, f"{label} {ref.content}"))
        for obs in self.observations[-n:]:
            if obs.importance < 0.35:
                continue
            label = {
                "price": "[PRICE]", "news": "[NEWS]",
                "conversation": "[CHAT]", "reflection": "[THINK]",
            }.get(obs.category, "[*]")
            items.append((obs.tick, f"{label} {obs.content}"))
        items.sort(key=lambda item: item[0])
        return [text for _, text in items[-n:]]

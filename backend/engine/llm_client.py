"""Optional LLM integration for generative agent behavior.

Set LLM_ENABLED=True and provide LLM_API_KEY in config.py or env vars.
Supports any OpenAI-compatible API (OpenAI, Anthropic via proxy, Ollama, vLLM, etc.).
If disabled or key missing, agents fall back to rule-based templates.
"""

import asyncio
import json
import os
import requests
from backend.config import (
    LLM_ENABLED, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_MAX_TOKENS, LLM_TEMPERATURE,
)


def _get_config():
    """Read LLM config from env vars (preferred) or config.py (fallback)."""
    return {
        "enabled": os.getenv("LLM_ENABLED", str(LLM_ENABLED)).lower() in ("true", "1", "yes"),
        "api_key": os.getenv("LLM_API_KEY", LLM_API_KEY),
        "base_url": os.getenv("LLM_BASE_URL", LLM_BASE_URL),
        "model": os.getenv("LLM_MODEL", LLM_MODEL),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", str(LLM_MAX_TOKENS))),
        "temperature": float(os.getenv("LLM_TEMPERATURE", str(LLM_TEMPERATURE))),
    }


def _call_llm(system_prompt: str, user_prompt: str) -> str | None:
    """Synchronous LLM call. Returns response text or None on failure."""
    cfg = _get_config()
    if not cfg["enabled"] or not cfg["api_key"]:
        return None
    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": cfg["max_tokens"],
                "temperature": cfg["temperature"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        print(f"LLM error: {e}")
        return None


async def generate_reflection(
    agent_id: str,
    agent_name: str,
    backstory: str,
    motto: str,
    recent_observations: list[str],
    prices: dict[str, float],
    tick: int,
) -> str | None:
    """Generate a reflection/thought for an agent based on recent observations."""
    obs_text = "\n".join(recent_observations[-10:]) if recent_observations else "(no observations yet)"
    price_text = ", ".join(f"{s}=${p:.2f}" for s, p in list(prices.items())[:5])

    system = (
        f"You are {agent_name} ({agent_id}), a trader living in a small town called Agent Street. "
        f"Your backstory: {backstory} "
        f"Your motto: \"{motto}\" "
        f"You are looking at the market and forming a thought. "
        f"Respond in 1-2 short sentences, in first person. Be specific — mention a stock or a feeling. "
        f"Do not use hashtags or emoji. Keep it under 100 characters."
    )
    user = (
        f"Current prices: {price_text}\n"
        f"Recent things you noticed:\n{obs_text}\n\n"
        f"What are you thinking right now?"
    )
    return await asyncio.to_thread(_call_llm, system, user)


async def generate_conversation_line(
    speaker_id: str,
    speaker_name: str,
    speaker_traits: str,  # brief personality description
    listener_id: str,
    topic_symbol: str,
    topic_price: float,
    topic_change: float,
    recent_thoughts: list[str],
) -> str | None:
    """Generate what one agent says to another about the market."""
    direction = "up" if topic_change > 0 else "down"
    thought_context = " ".join(recent_thoughts[-3:]) if recent_thoughts else ""

    system = (
        f"You are {speaker_name} ({speaker_id}), a {speaker_traits} trader. "
        f"You're chatting with {listener_id} at a cafe in a small town. "
        f"Say ONE line (under 80 chars) about {topic_symbol} (${topic_price:.2f}, {direction} {abs(topic_change):.1%}). "
        f"Match your personality. Be casual and natural. No hashtags, no emoji."
    )
    user = (
        f"Recent thoughts: {thought_context}\n"
        f"What do you say to {listener_id} about {topic_symbol}?"
    )
    return await asyncio.to_thread(_call_llm, system, user)


async def generate_trade_rationale(
    agent_id: str,
    agent_name: str,
    symbol: str,
    direction: str,
    price: float,
    recent_thoughts: list[str],
    pnl: float,
) -> str | None:
    """Generate a rationale for why an agent made a trade."""
    thought_context = " ".join(recent_thoughts[-3:]) if recent_thoughts else "just following my instincts"

    system = (
        f"You are {agent_name} ({agent_id}), a trader. "
        f"You just {direction.lower()} {symbol} at ${price:.2f}. Your P&L is ${pnl:.0f}. "
        f"Explain your reasoning in ONE short sentence (under 80 chars). Be specific. No hashtags."
    )
    user = f"Recent thoughts: {thought_context}\nWhy did you {direction} {symbol}?"
    return await asyncio.to_thread(_call_llm, system, user)


def llm_available() -> bool:
    cfg = _get_config()
    return cfg["enabled"] and bool(cfg["api_key"])

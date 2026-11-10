"""Optional LLM narrative layer with a strict rule-based fallback.

The simulation is rule-first. Nothing in this module is imported on the hot
path unless the user explicitly enables LLM calls with ``LLM_ENABLED=true``
and supplies a key (Ollama does not need one). Every public generator returns
``None`` when the layer is disabled, over budget, or fails; callers then keep
the deterministic template.

The provider interface is intentionally small and OpenAI-compatible: DeepSeek,
OpenAI, Ollama, vLLM and most proxies can be selected with ``LLM_PROVIDER``.
A per-run call budget, an input-size cap, a bounded response cache and a
concurrency semaphore make accidental spend visible and bounded.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

import requests

from backend.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_CACHE_SIZE,
    LLM_CONVERSATIONS,
    LLM_ENABLED,
    LLM_MAX_CALLS_PER_RUN,
    LLM_MAX_CONCURRENCY,
    LLM_MAX_INPUT_CHARS,
    LLM_MAX_TOKENS,
    LLM_MODE,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SEC,
)

VALID_MODES = {"off", "reflection", "conversation", "all"}

PROVIDER_PRESETS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "requires_key": True,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "requires_key": True,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "requires_key": False,
    },
    "custom": {"base_url": "", "model": "", "requires_key": True},
}


def _env(name: str, fallback: str) -> str:
    value = os.getenv(name)
    return fallback if value is None else value


def _get_config() -> dict:
    """Resolve environment/config into one immutable-ish settings dictionary."""
    provider = _env("LLM_PROVIDER", LLM_PROVIDER).strip().lower() or "openai"
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
    base_url = (
        _env("LLM_BASE_URL", LLM_BASE_URL).strip()
        or preset["base_url"]
    ).rstrip("/")
    model = _env("LLM_MODEL", LLM_MODEL).strip() or preset["model"]
    enabled = _env("LLM_ENABLED", str(LLM_ENABLED)).lower() in ("1", "true", "yes")

    raw_mode = (_env("LLM_MODE", LLM_MODE) or "").strip().lower()
    conversations = _env(
        "LLM_CONVERSATIONS", str(LLM_CONVERSATIONS),
    ).lower() in ("1", "true", "yes")
    if raw_mode not in VALID_MODES:
        raw_mode = ""
    if not raw_mode:
        raw_mode = ("all" if conversations else "reflection") if enabled else "off"
    mode = raw_mode if enabled else "off"

    def _int(name: str, fallback: int, minimum: int = 0) -> int:
        try:
            return max(minimum, int(_env(name, str(fallback))))
        except (TypeError, ValueError):
            return fallback

    def _float(name: str, fallback: float, minimum: float = 0.0) -> float:
        try:
            return max(minimum, float(_env(name, str(fallback))))
        except (TypeError, ValueError):
            return fallback

    return {
        "enabled": enabled,
        "mode": mode,
        "provider": provider,
        "api_key": _env("LLM_API_KEY", LLM_API_KEY).strip(),
        "base_url": base_url,
        "model": model,
        "requires_key": bool(preset["requires_key"]),
        "max_tokens": _int("LLM_MAX_TOKENS", LLM_MAX_TOKENS, 16),
        "temperature": _float("LLM_TEMPERATURE", LLM_TEMPERATURE, 0.0),
        "timeout": _float("LLM_TIMEOUT_SEC", LLM_TIMEOUT_SEC, 0.5),
        "max_concurrency": _int("LLM_MAX_CONCURRENCY", LLM_MAX_CONCURRENCY, 1),
        "max_calls_per_run": _int("LLM_MAX_CALLS_PER_RUN", LLM_MAX_CALLS_PER_RUN, 0),
        "max_input_chars": _int("LLM_MAX_INPUT_CHARS", LLM_MAX_INPUT_CHARS, 500),
        "cache_size": _int("LLM_CACHE_SIZE", LLM_CACHE_SIZE, 0),
    }


@dataclass(frozen=True)
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMProvider(Protocol):
    """Minimal provider contract. Implementations must be thread-safe."""

    name: str

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> LLMResponse | None: ...


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible ``/chat/completions`` endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = "openai-compatible"

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> LLMResponse | None:
        if not self.base_url or not self.model:
            return None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": int(max_tokens),
                "temperature": float(temperature),
            },
            timeout=max(0.5, float(timeout)),
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            return None
        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        return LLMResponse(
            text=content.strip(),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )


class NullProvider:
    name = "null"

    def complete(self, *args, **kwargs) -> LLMResponse | None:
        return None


def build_provider(config: dict) -> LLMProvider:
    if not config.get("base_url") or not config.get("model"):
        return NullProvider()
    return OpenAICompatibleProvider(
        config["base_url"], config.get("api_key", ""), config["model"],
    )


class LLMClient:
    """Budgeted, cached facade around a provider.

    ``available(capability)`` is the single gate used by the simulation. It
    returns false unless the layer is enabled, the requested capability is in
    the selected mode, and credentials/endpoints are present.
    """

    def __init__(self, config: dict, provider: LLMProvider | None = None):
        self.config = dict(config)
        self.provider = provider or build_provider(self.config)
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._calls = 0
        self._cache_hits = 0
        self._failures = 0
        self._budget_exhausted = 0
        self._truncated = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        max_workers = max(1, int(self.config.get("max_concurrency", 1)))
        self._semaphore = threading.BoundedSemaphore(max_workers)

    # ── availability ─────────────────────────────────────────

    def available(self, capability: str | None = None) -> bool:
        cfg = self.config
        if not cfg.get("enabled") or cfg.get("mode") == "off":
            return False
        if cfg.get("requires_key") and not cfg.get("api_key"):
            return False
        if not cfg.get("base_url") or not cfg.get("model"):
            return False
        if capability and cfg.get("mode") not in (capability, "all"):
            return False
        return True

    # ── calls ────────────────────────────────────────────────

    def complete(
        self,
        system: str,
        user: str,
        capability: str = "reflection",
        cache_extra: str = "",
    ) -> str | None:
        if not self.available(capability):
            return None

        system = str(system)
        user = str(user)
        max_input = int(self.config.get("max_input_chars", 6000))
        if len(system) + len(user) > max_input:
            # Keep the system instruction; trim the context instead of failing.
            keep = max(200, max_input - len(system) - 32)
            user = user[:keep].rstrip() + "\n[truncated]"
            with self._lock:
                self._truncated += 1

        key = self._cache_key(system, user, cache_extra)
        with self._lock:
            if self.config.get("cache_size", 0) and key in self._cache:
                self._cache.move_to_end(key)
                self._cache_hits += 1
                return self._cache[key]
            max_calls = int(self.config.get("max_calls_per_run", 0))
            if max_calls and self._calls >= max_calls:
                self._budget_exhausted += 1
                return None
            self._calls += 1

        response: LLMResponse | None = None
        try:
            with self._semaphore:
                response = self.provider.complete(
                    system,
                    user,
                    max_tokens=int(self.config.get("max_tokens", 150)),
                    temperature=float(self.config.get("temperature", 0.9)),
                    timeout=float(self.config.get("timeout", 10.0)),
                )
        except Exception as exc:  # noqa: BLE001 - optional layer must never kill a tick
            with self._lock:
                self._failures += 1
            print(f"[llm] {self.config.get('provider', '?')} call failed: {exc}")
            return None

        if response is None or not response.text.strip():
            with self._lock:
                self._failures += 1
            return None

        text = response.text.strip()
        with self._lock:
            self._prompt_tokens += response.prompt_tokens
            self._completion_tokens += response.completion_tokens
            cache_size = int(self.config.get("cache_size", 0))
            if cache_size:
                self._cache[key] = text
                self._cache.move_to_end(key)
                while len(self._cache) > cache_size:
                    self._cache.popitem(last=False)
        return text

    def _cache_key(self, system: str, user: str, extra: str) -> str:
        raw = "\0".join([
            self.config.get("provider", ""),
            self.config.get("model", ""),
            str(self.config.get("temperature", "")),
            str(self.config.get("max_tokens", "")),
            extra,
            system,
            user,
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ── observability ────────────────────────────────────────

    def status(self) -> dict:
        with self._lock:
            max_calls = int(self.config.get("max_calls_per_run", 0))
            return {
                "enabled": bool(self.config.get("enabled")),
                "mode": self.config.get("mode", "off"),
                "provider": self.config.get("provider", ""),
                "model": self.config.get("model", ""),
                "baseUrl": self.config.get("base_url", ""),
                "apiKeyConfigured": bool(self.config.get("api_key")),
                "available": self.available(),
                "calls": self._calls,
                "cacheHits": self._cache_hits,
                "cacheEntries": len(self._cache),
                "failures": self._failures,
                "budgetExhausted": self._budget_exhausted,
                "truncated": self._truncated,
                "promptTokens": self._prompt_tokens,
                "completionTokens": self._completion_tokens,
                "maxCallsPerRun": max_calls,
                "remainingCalls": max(0, max_calls - self._calls) if max_calls else None,
                "maxInputChars": int(self.config.get("max_input_chars", 0)),
                "maxConcurrency": int(self.config.get("max_concurrency", 1)),
            }

    def reset_stats(self, clear_cache: bool = True) -> None:
        with self._lock:
            self._calls = 0
            self._cache_hits = 0
            self._failures = 0
            self._budget_exhausted = 0
            self._truncated = 0
            self._prompt_tokens = 0
            self._completion_tokens = 0
            if clear_cache:
                self._cache.clear()


_CLIENT: LLMClient | None = None
_CLIENT_LOCK = threading.Lock()


def get_client() -> LLMClient:
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = LLMClient(_get_config())
        return _CLIENT


def reload_client() -> LLMClient:
    """Rebuild after environment/config changes (used by tests and the API)."""
    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = LLMClient(_get_config())
        return _CLIENT


def reset_llm_stats(clear_cache: bool = True) -> None:
    get_client().reset_stats(clear_cache=clear_cache)


def llm_available(capability: str | None = None) -> bool:
    return get_client().available(capability)


def llm_status() -> dict:
    return get_client().status()


# ── prompt helpers ───────────────────────────────────────────

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
    return await asyncio.to_thread(
        get_client().complete, system, user, "reflection",
    )


async def generate_conversation_line(
    speaker_id: str,
    speaker_name: str,
    speaker_traits: str,
    listener_id: str,
    topic_symbol: str,
    topic_price: float,
    topic_change: float,
    recent_thoughts: list[str],
    location_name: str = "a small town street",
) -> str | None:
    """Generate what one agent says to another about the market."""
    direction = "up" if topic_change > 0 else "down"
    thought_context = " ".join(recent_thoughts[-3:]) if recent_thoughts else ""

    system = (
        f"You are {speaker_name} ({speaker_id}), a {speaker_traits} trader. "
        f"You're chatting with {listener_id} at {location_name} in a small town. "
        f"Say ONE line (under 80 chars) about {topic_symbol} (${topic_price:.2f}, {direction} {abs(topic_change):.1%}). "
        f"Match your personality. Be casual and natural. No hashtags, no emoji."
    )
    user = (
        f"Recent thoughts: {thought_context}\n"
        f"What do you say to {listener_id} about {topic_symbol}?"
    )
    return await asyncio.to_thread(
        get_client().complete, system, user, "conversation",
    )


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
    return await asyncio.to_thread(
        get_client().complete, system, user, "conversation",
    )

"""User-editable interaction rules.

The control loop is deliberately rule-first. A rule book is a plain JSON
document so a user can change how neighbours talk, how often agents wander,
and how aggressive entries are without touching Python. The LLM layer is
optional and lives above these rules; it is never required for a run.

Defaults are kept identical to the historical hard-coded values, which keeps
existing experiment results reproducible. Environment variables still win over
the JSON file for the values they expose, so CI and ablations keep working.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

from backend.config import (
    BUY_THRESHOLD,
    CONVERSATION_CHANCE,
    CONVERSATION_COOLDOWN_TICKS,
    CONVERSATION_RADIUS,
    LLM_REFLECTIONS_PER_BATCH,
    MAX_CONVERSATIONS_PER_TICK,
    MAX_POSITION_PCT,
    PANIC_COOLDOWN_TICKS,
    REFLECTION_EVERY_N_TICKS,
    SELL_THRESHOLD,
)


class RuleValidationError(ValueError):
    """Raised when an API update would make the rule book unusable."""


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

SENTIMENT_WORDS = [
    "bullish", "bearish", "choppy", "quiet", "frantic", "sleepy", "heavy", "springy",
]

LOCATION_MULTIPLIERS = {
    "home": 1.0,
    "cafe": 1.0,
    "market": 1.0,
    "library": 1.0,
    "square": 1.0,
    "park": 1.0,
    "rumor": 1.0,
    "lab": 1.0,
    "hall": 1.0,
    "observatory": 1.0,
    "math_tower": 1.0,
    "fortune_tent": 1.0,
}

DEFAULT_RULES = {
    "_readme": (
        "Edit this file to change the town's default behaviour. The simulation "
        "never calls an LLM unless LLM_ENABLED=true and an API key is present. "
        "Use the 'home' placeholder in routines; it resolves to each agent's house."
    ),
    "version": 1,
    "conversation": {
        "radius": CONVERSATION_RADIUS,
        "chance": CONVERSATION_CHANCE,
        "cooldown_ticks": CONVERSATION_COOLDOWN_TICKS,
        "max_per_tick": MAX_CONVERSATIONS_PER_TICK,
        "debate_chance": 0.12,
        "location_multipliers": dict(LOCATION_MULTIPLIERS),
        "templates": {
            "greetings": list(GREETINGS),
            "bullish": list(RESPONSES_BULLISH),
            "bearish": list(RESPONSES_BEARISH),
            "neutral": list(RESPONSES_NEUTRAL),
            "sentiment_words": list(SENTIMENT_WORDS),
            "debate": [
                "{symbol} is mispriced — the numbers support the long.",
                "Or the market already priced the good news.",
                "Then the risk/reward wasn't in your favour to begin with.",
            ],
        },
    },
    "reflection": {
        "every_n_ticks": REFLECTION_EVERY_N_TICKS,
        "importance_threshold": 0.25,
        "llm_per_batch": LLM_REFLECTIONS_PER_BATCH,
    },
    "routines": {
        "perceiving_duration_delta": -1,
        "wander_chance": 0.10,
        "extravert": [
            ["home", 3], ["cafe", 3], ["rumor", 3], ["market", 3],
            ["hall", 3], ["square", 3], ["home", 2],
        ],
        "thinking": [
            ["home", 2], ["library", 4], ["lab", 4], ["market", 3],
            ["cafe", 2], ["square", 2], ["library", 2], ["home", 2],
        ],
        "default": [
            ["home", 3], ["park", 4], ["cafe", 3], ["square", 2],
            ["rumor", 2], ["hall", 2], ["home", 2],
        ],
    },
    "trading": {
        "buy_threshold": BUY_THRESHOLD,
        "sell_threshold": SELL_THRESHOLD,
        "max_position_pct": MAX_POSITION_PCT,
        "panic_cooldown_ticks": PANIC_COOLDOWN_TICKS,
    },
    # Optional per-agent overrides, merged over the global sections above:
    # "INTJ": {"conversation": {"chance": 0.18}, "trading": {"buy_threshold": 0.16}}
    "agents": {},
}


def _deep_merge(base, override):
    """Return a copy of *base* with *override* merged recursively."""
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: copy.deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _num(section, key, lo, hi, default):
    try:
        return _clamp(float(section.get(key, default)), lo, hi)
    except (TypeError, ValueError):
        return default


def _int(section, key, lo, hi, default):
    try:
        return int(_clamp(int(section.get(key, default)), lo, hi))
    except (TypeError, ValueError):
        return default


def _text_list(value, fallback):
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or list(fallback)


def _schedule(value, fallback):
    if not isinstance(value, list):
        return copy.deepcopy(fallback)
    cleaned = []
    for item in value:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], str)
            and item[0].strip()
        ):
            try:
                ticks = int(item[1])
            except (TypeError, ValueError):
                continue
            cleaned.append([item[0].strip(), max(1, ticks)])
    return cleaned or copy.deepcopy(fallback)


def _normalize(data: dict) -> dict:
    """Repair a loaded document without discarding unrelated user edits."""
    data = copy.deepcopy(data)
    try:
        data["version"] = int(data.get("version", 1) or 1)
    except (TypeError, ValueError):
        data["version"] = 1
    conv = data.setdefault("conversation", {})
    if not isinstance(conv, dict):
        conv = data["conversation"] = {}
    conv["radius"] = _int(conv, "radius", 1, 20, DEFAULT_RULES["conversation"]["radius"])
    conv["chance"] = _num(conv, "chance", 0.0, 1.0, DEFAULT_RULES["conversation"]["chance"])
    conv["cooldown_ticks"] = _int(
        conv, "cooldown_ticks", 0, 1000, DEFAULT_RULES["conversation"]["cooldown_ticks"],
    )
    conv["max_per_tick"] = _int(
        conv, "max_per_tick", 0, 20, DEFAULT_RULES["conversation"]["max_per_tick"],
    )
    conv["debate_chance"] = _num(
        conv, "debate_chance", 0.0, 1.0, DEFAULT_RULES["conversation"]["debate_chance"],
    )
    multipliers = conv.get("location_multipliers")
    if not isinstance(multipliers, dict):
        multipliers = dict(LOCATION_MULTIPLIERS)
    conv["location_multipliers"] = {
        str(key): _clamp(float(value), 0.0, 5.0)
        for key, value in multipliers.items()
        if _is_number(value)
    } or dict(LOCATION_MULTIPLIERS)
    templates = conv.get("templates")
    if not isinstance(templates, dict):
        templates = {}
    defaults = DEFAULT_RULES["conversation"]["templates"]
    conv["templates"] = {
        "greetings": _text_list(templates.get("greetings"), defaults["greetings"]),
        "bullish": _text_list(templates.get("bullish"), defaults["bullish"]),
        "bearish": _text_list(templates.get("bearish"), defaults["bearish"]),
        "neutral": _text_list(templates.get("neutral"), defaults["neutral"]),
        "sentiment_words": _text_list(templates.get("sentiment_words"), defaults["sentiment_words"]),
        "debate": _text_list(templates.get("debate"), defaults["debate"]),
    }

    reflection = data.setdefault("reflection", {})
    if not isinstance(reflection, dict):
        reflection = data["reflection"] = {}
    reflection["every_n_ticks"] = _int(
        reflection, "every_n_ticks", 1, 1000, DEFAULT_RULES["reflection"]["every_n_ticks"],
    )
    reflection["importance_threshold"] = _num(
        reflection, "importance_threshold", 0.0, 1.0,
        DEFAULT_RULES["reflection"]["importance_threshold"],
    )
    reflection["llm_per_batch"] = _int(
        reflection, "llm_per_batch", 0, 20, DEFAULT_RULES["reflection"]["llm_per_batch"],
    )

    routines = data.setdefault("routines", {})
    if not isinstance(routines, dict):
        routines = data["routines"] = {}
    routines["perceiving_duration_delta"] = _int(
        routines, "perceiving_duration_delta", -5, 5,
        DEFAULT_RULES["routines"]["perceiving_duration_delta"],
    )
    routines["wander_chance"] = _num(
        routines, "wander_chance", 0.0, 1.0, DEFAULT_RULES["routines"]["wander_chance"],
    )
    for key in ("extravert", "thinking", "default"):
        routines[key] = _schedule(routines.get(key), DEFAULT_RULES["routines"][key])

    trading = data.setdefault("trading", {})
    if not isinstance(trading, dict):
        trading = data["trading"] = {}
    trading["buy_threshold"] = _num(
        trading, "buy_threshold", 0.0, 1.0, DEFAULT_RULES["trading"]["buy_threshold"],
    )
    trading["sell_threshold"] = _num(
        trading, "sell_threshold", -1.0, 0.0, DEFAULT_RULES["trading"]["sell_threshold"],
    )
    trading["max_position_pct"] = _num(
        trading, "max_position_pct", 0.01, 1.0, DEFAULT_RULES["trading"]["max_position_pct"],
    )
    trading["panic_cooldown_ticks"] = _int(
        trading, "panic_cooldown_ticks", 0, 1000,
        DEFAULT_RULES["trading"]["panic_cooldown_ticks"],
    )

    agents = data.setdefault("agents", {})
    if not isinstance(agents, dict):
        data["agents"] = {}
    else:
        cleaned_agents = {}
        for agent_id, override in agents.items():
            if isinstance(override, dict):
                cleaned_agents[str(agent_id)] = _normalize_agent_override(override)
        data["agents"] = cleaned_agents
    return data


def _normalize_agent_override(override: dict) -> dict:
    """Keep only the known per-agent sections and clamp their scalars."""
    cleaned = copy.deepcopy(override)
    conv = cleaned.get("conversation")
    if isinstance(conv, dict):
        if "chance" in conv:
            try:
                conv["chance"] = _clamp(float(conv["chance"]), 0.0, 1.0)
            except (TypeError, ValueError):
                conv.pop("chance", None)
        if "cooldown_ticks" in conv:
            try:
                conv["cooldown_ticks"] = max(0, min(1000, int(conv["cooldown_ticks"])))
            except (TypeError, ValueError):
                conv.pop("cooldown_ticks", None)
    trading = cleaned.get("trading")
    if isinstance(trading, dict):
        for key, lo, hi in (
            ("buy_threshold", 0.0, 1.0),
            ("sell_threshold", -1.0, 0.0),
            ("max_position_pct", 0.01, 1.0),
        ):
            if key in trading:
                try:
                    trading[key] = _clamp(float(trading[key]), lo, hi)
                except (TypeError, ValueError):
                    trading.pop(key, None)
    return cleaned


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _traverse(data: dict, dotted: str, default=None):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _set_path(data: dict, dotted: str, value) -> None:
    node = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _env_value(name: str, cast, fallback):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return None


def _apply_env(data: dict) -> None:
    """Apply only *explicit* environment overrides.

    Config constants always contain a default. Applying them unconditionally
    would silently overwrite every user edit in the JSON file, so only names
    actually present in the environment are applied here. Values are parsed
    from the environment rather than the import-time constants so a reloaded
    process or test can change them without a restart.
    """
    values = {
        ("conversation", "radius"): _env_value("CONVERSATION_RADIUS", int, CONVERSATION_RADIUS),
        ("conversation", "chance"): _env_value("CONVERSATION_CHANCE", float, CONVERSATION_CHANCE),
        ("conversation", "cooldown_ticks"): _env_value("CONVERSATION_COOLDOWN_TICKS", int, CONVERSATION_COOLDOWN_TICKS),
        ("conversation", "max_per_tick"): _env_value("MAX_CONVERSATIONS_PER_TICK", int, MAX_CONVERSATIONS_PER_TICK),
        ("reflection", "every_n_ticks"): _env_value("REFLECTION_EVERY_N_TICKS", int, REFLECTION_EVERY_N_TICKS),
        ("reflection", "llm_per_batch"): _env_value("LLM_REFLECTIONS_PER_BATCH", int, LLM_REFLECTIONS_PER_BATCH),
        ("trading", "buy_threshold"): _env_value("BUY_THRESHOLD", float, BUY_THRESHOLD),
        ("trading", "sell_threshold"): _env_value("SELL_THRESHOLD", float, SELL_THRESHOLD),
        ("trading", "max_position_pct"): _env_value("MAX_POSITION_PCT", float, MAX_POSITION_PCT),
        ("trading", "panic_cooldown_ticks"): _env_value("PANIC_COOLDOWN_TICKS", int, PANIC_COOLDOWN_TICKS),
    }
    for (section, key), value in values.items():
        if value is not None:
            _set_path(data, f"{section}.{key}", value)


class RuleBook:
    """A validated, reloadable view of the interaction rules."""

    def __init__(self, path: str | Path | None = None):
        root = Path(__file__).resolve().parents[2]
        configured = path or os.getenv(
            "INTERACTION_RULES_PATH", str(root / "config" / "interaction_rules.json")
        )
        self.path = Path(configured).expanduser()
        if not self.path.is_absolute():
            self.path = root / self.path
        self._lock = threading.RLock()
        self._data = copy.deepcopy(DEFAULT_RULES)
        self._file_data = copy.deepcopy(DEFAULT_RULES)
        self._mtime = None
        self.reload()

    # ── loading / persistence ────────────────────────────────

    def reload(self) -> dict:
        with self._lock:
            raw = {}
            mtime = None
            if self.path.exists():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    mtime = self.path.stat().st_mtime
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"[rules] cannot read {self.path}: {exc}")
                    raw = {}
            merged = _deep_merge(DEFAULT_RULES, raw if isinstance(raw, dict) else {})
            self._file_data = _normalize(merged)
            runtime = copy.deepcopy(self._file_data)
            _apply_env(runtime)
            self._data = _normalize(runtime)
            self._mtime = mtime
            return self._data

    def reload_if_changed(self) -> bool:
        with self._lock:
            try:
                mtime = self.path.stat().st_mtime if self.path.exists() else None
            except OSError:
                mtime = None
            if mtime != self._mtime:
                self.reload()
                return True
            return False

    def update(self, partial: dict) -> dict:
        """Merge a partial rule document, validate it, and persist atomically."""
        if not isinstance(partial, dict):
            raise RuleValidationError("rules must be a JSON object")
        with self._lock:
            candidate = _deep_merge(self._data, partial)
            # Validate user-editable scalar types before clamping anything.
            self._validate_strict(candidate)
            _apply_env(candidate)
            self._data = _normalize(candidate)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temp.replace(self.path)
            return self._data

    def reset(self) -> dict:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
            return self.reload()

    @staticmethod
    def _validate_strict(data: dict) -> None:
        conv = data.get("conversation", {})
        for key in ("chance", "debate_chance"):
            if key in conv and not _is_number(conv[key]):
                raise RuleValidationError(f"conversation.{key} must be numeric")
        for key in ("radius", "cooldown_ticks", "max_per_tick"):
            if key in conv:
                try:
                    int(conv[key])
                except (TypeError, ValueError):
                    raise RuleValidationError(f"conversation.{key} must be an integer")
        templates = conv.get("templates", {})
        if templates and not isinstance(templates, dict):
            raise RuleValidationError("conversation.templates must be an object")
        for key, value in (templates or {}).items():
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise RuleValidationError(f"conversation.templates.{key} must be a list of strings")
        routines = data.get("routines", {})
        for key in ("extravert", "thinking", "default"):
            if key in routines:
                value = routines[key]
                if not isinstance(value, list):
                    raise RuleValidationError(f"routines.{key} must be a list")
                for item in value:
                    if not (
                        isinstance(item, (list, tuple))
                        and len(item) == 2
                        and isinstance(item[0], str)
                    ):
                        raise RuleValidationError(
                            f"routines.{key} entries must be [location, ticks]"
                        )
        agents = data.get("agents", {})
        if not isinstance(agents, dict):
            raise RuleValidationError("agents must be an object")

    # ── access ───────────────────────────────────────────────

    def get(self, dotted: str, default=None):
        with self._lock:
            return _traverse(self._data, dotted, default)

    def for_agent(self, agent_id: str, dotted: str, default=None):
        with self._lock:
            override = self._data.get("agents", {}).get(agent_id, {})
            value = _traverse(override, dotted, None)
            if value is not None:
                return value
            return _traverse(self._data, dotted, default)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    @property
    def source(self) -> str:
        return str(self.path)


_RULES: RuleBook | None = None
_RULES_LOCK = threading.Lock()


def get_rules() -> RuleBook:
    global _RULES
    with _RULES_LOCK:
        if _RULES is None:
            _RULES = RuleBook()
        return _RULES


def reload_rules() -> RuleBook:
    global _RULES
    with _RULES_LOCK:
        _RULES = RuleBook()
        return _RULES

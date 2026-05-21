from backend.mbti.types import TraitProfile, derive_trading_params

PERSONA_DEFINITIONS: dict[str, dict] = {
    "INTJ": {
        "name": "Architect",
        "traits": TraitProfile(extraversion=0.15, sensing=0.20, thinking=0.95, judging=0.90),
        "color": "#4A6FA5",
        "motto": "I see the pattern before it forms.",
    },
    "INTP": {
        "name": "Logician",
        "traits": TraitProfile(extraversion=0.10, sensing=0.15, thinking=0.90, judging=0.20),
        "color": "#6B7DB3",
        "motto": "The data tells the truth, eventually.",
    },
    "ENTJ": {
        "name": "Commander",
        "traits": TraitProfile(extraversion=0.90, sensing=0.25, thinking=0.90, judging=0.85),
        "color": "#C4543E",
        "motto": "Control the capital, control the world.",
    },
    "ENTP": {
        "name": "Debater",
        "traits": TraitProfile(extraversion=0.85, sensing=0.20, thinking=0.80, judging=0.15),
        "color": "#D4853A",
        "motto": "What if we're all wrong about this?",
    },
    "INFJ": {
        "name": "Advocate",
        "traits": TraitProfile(extraversion=0.30, sensing=0.15, thinking=0.10, judging=0.85),
        "color": "#5B9E6F",
        "motto": "I feel the market's heartbeat.",
    },
    "INFP": {
        "name": "Mediator",
        "traits": TraitProfile(extraversion=0.20, sensing=0.10, thinking=0.05, judging=0.15),
        "color": "#7DB37D",
        "motto": "Every trend has a soul.",
    },
    "ENFJ": {
        "name": "Protagonist",
        "traits": TraitProfile(extraversion=0.90, sensing=0.20, thinking=0.15, judging=0.80),
        "color": "#D4A843",
        "motto": "Together, we move the market!",
    },
    "ENFP": {
        "name": "Campaigner",
        "traits": TraitProfile(extraversion=0.95, sensing=0.15, thinking=0.10, judging=0.10),
        "color": "#E8B84B",
        "motto": "This stock is gonna moon, I can feel it!",
    },
    "ISTJ": {
        "name": "Logistician",
        "traits": TraitProfile(extraversion=0.15, sensing=0.90, thinking=0.85, judging=0.90),
        "color": "#5A7A9A",
        "motto": "Trust the numbers, nothing else.",
    },
    "ISFJ": {
        "name": "Defender",
        "traits": TraitProfile(extraversion=0.10, sensing=0.85, thinking=0.15, judging=0.85),
        "color": "#6B9E8A",
        "motto": "Safety first. Always.",
    },
    "ESTJ": {
        "name": "Executive",
        "traits": TraitProfile(extraversion=0.85, sensing=0.90, thinking=0.85, judging=0.90),
        "color": "#B84D3E",
        "motto": "Discipline beats genius.",
    },
    "ESFJ": {
        "name": "Consul",
        "traits": TraitProfile(extraversion=0.85, sensing=0.85, thinking=0.15, judging=0.85),
        "color": "#C46D5E",
        "motto": "What's everyone else doing?",
    },
    "ISTP": {
        "name": "Virtuoso",
        "traits": TraitProfile(extraversion=0.10, sensing=0.90, thinking=0.80, judging=0.15),
        "color": "#4A7A9A",
        "motto": "I'll trade when the moment is right.",
    },
    "ISFP": {
        "name": "Adventurer",
        "traits": TraitProfile(extraversion=0.15, sensing=0.85, thinking=0.10, judging=0.15),
        "color": "#5B9E7A",
        "motto": "The chart is a canvas.",
    },
    "ESTP": {
        "name": "Entrepreneur",
        "traits": TraitProfile(extraversion=0.90, sensing=0.90, thinking=0.75, judging=0.10),
        "color": "#C46D3E",
        "motto": "Scalp first, ask questions later.",
    },
    "ESFP": {
        "name": "Entertainer",
        "traits": TraitProfile(extraversion=0.95, sensing=0.85, thinking=0.10, judging=0.10),
        "color": "#D48D5E",
        "motto": "If it goes up, I'm in!",
    },
}

for pid, defn in PERSONA_DEFINITIONS.items():
    defn["params"] = derive_trading_params(defn["traits"])
    defn["id"] = pid

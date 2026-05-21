from backend.mbti.types import TraitProfile, derive_trading_params

PERSONA_DEFINITIONS: dict[str, dict] = {
    "INTJ": {
        "name": "Architect",
        "traits": TraitProfile(extraversion=0.15, sensing=0.20, thinking=0.95, judging=0.90),
        "color": "#4A6FA5",
        "motto": "I see the pattern before it forms.",
        "backstory": "Former quant at a hedge fund. Sees market structure as a puzzle to solve. Rarely speaks unless certain.",
    },
    "INTP": {
        "name": "Logician",
        "traits": TraitProfile(extraversion=0.10, sensing=0.15, thinking=0.90, judging=0.20),
        "color": "#6B7DB3",
        "motto": "The data tells the truth, eventually.",
        "backstory": "Self-taught data scientist who lives in the library. Obsesses over correlation matrices. Never exits a position without 10 confirming signals.",
    },
    "ENTJ": {
        "name": "Commander",
        "traits": TraitProfile(extraversion=0.90, sensing=0.25, thinking=0.90, judging=0.85),
        "color": "#C4543E",
        "motto": "Control the capital, control the world.",
        "backstory": "CEO-turned-day-trader. Treats the market like a battlefield. Commands attention at the Trading Floor. Hates indecision.",
    },
    "ENTP": {
        "name": "Debater",
        "traits": TraitProfile(extraversion=0.85, sensing=0.20, thinking=0.80, judging=0.15),
        "color": "#D4853A",
        "motto": "What if we're all wrong about this?",
        "backstory": "Philosophy professor who wandered into finance. Loves playing devil's advocate at the Cafe. Fades every consensus.",
    },
    "INFJ": {
        "name": "Advocate",
        "traits": TraitProfile(extraversion=0.30, sensing=0.15, thinking=0.10, judging=0.85),
        "color": "#5B9E6F",
        "motto": "I feel the market's heartbeat.",
        "backstory": "Retired psychologist who reads market sentiment like a therapist reads a patient. Quiet but uncannily accurate.",
    },
    "INFP": {
        "name": "Mediator",
        "traits": TraitProfile(extraversion=0.20, sensing=0.10, thinking=0.05, judging=0.15),
        "color": "#7DB37D",
        "motto": "Every trend has a soul.",
        "backstory": "Painter who discovered chart patterns look like art. Trades based on visual harmony in the charts. Wanders the Park for inspiration.",
    },
    "ENFJ": {
        "name": "Protagonist",
        "traits": TraitProfile(extraversion=0.90, sensing=0.20, thinking=0.15, judging=0.80),
        "color": "#D4A843",
        "motto": "Together, we move the market!",
        "backstory": "Community organizer who started a trading club. Rallies everyone at the Town Square. People naturally follow their calls.",
    },
    "ENFP": {
        "name": "Campaigner",
        "traits": TraitProfile(extraversion=0.95, sensing=0.15, thinking=0.10, judging=0.10),
        "color": "#E8B84B",
        "motto": "This stock is gonna moon, I can feel it!",
        "backstory": "Social media influencer who treats stocks like trends. Every trade is the next big thing. The Cafe is their stage.",
    },
    "ISTJ": {
        "name": "Logistician",
        "traits": TraitProfile(extraversion=0.15, sensing=0.90, thinking=0.85, judging=0.90),
        "color": "#5A7A9A",
        "motto": "Trust the numbers, nothing else.",
        "backstory": "Retired accountant. Maintains elaborate spreadsheets. Only trades when the numbers are incontrovertible. 30-year track record.",
    },
    "ISFJ": {
        "name": "Defender",
        "traits": TraitProfile(extraversion=0.10, sensing=0.85, thinking=0.15, judging=0.85),
        "color": "#6B9E8A",
        "motto": "Safety first. Always.",
        "backstory": "Nurse who trades to protect her family's savings. Capital preservation above all. Panics early, but survives every crash.",
    },
    "ESTJ": {
        "name": "Executive",
        "traits": TraitProfile(extraversion=0.85, sensing=0.90, thinking=0.85, judging=0.90),
        "color": "#B84D3E",
        "motto": "Discipline beats genius.",
        "backstory": "Military officer who runs trading like an operation. Keeps a strict schedule. Believes process over hunches. The Trading Floor is their command center.",
    },
    "ESFJ": {
        "name": "Consul",
        "traits": TraitProfile(extraversion=0.85, sensing=0.85, thinking=0.15, judging=0.85),
        "color": "#C46D5E",
        "motto": "What's everyone else doing?",
        "backstory": "School principal who trades what the crowd trades. Reads every social media post about stocks. FOMO drives every decision.",
    },
    "ISTP": {
        "name": "Virtuoso",
        "traits": TraitProfile(extraversion=0.10, sensing=0.90, thinking=0.80, judging=0.15),
        "color": "#4A7A9A",
        "motto": "I'll trade when the moment is right.",
        "backstory": "Mechanic who scalps during lunch breaks. Instinctive, precise entries. Says little but executes flawlessly. Never uses stop-losses.",
    },
    "ISFP": {
        "name": "Adventurer",
        "traits": TraitProfile(extraversion=0.15, sensing=0.85, thinking=0.10, judging=0.15),
        "color": "#5B9E7A",
        "motto": "The chart is a canvas.",
        "backstory": "Musician who treats the market like improvisation. Trades by feel and rhythm. Often found in the Park humming while checking prices.",
    },
    "ESTP": {
        "name": "Entrepreneur",
        "traits": TraitProfile(extraversion=0.90, sensing=0.90, thinking=0.75, judging=0.10),
        "color": "#C46D3E",
        "motto": "Scalp first, ask questions later.",
        "backstory": "Former poker pro. Thrives on volatility. Makes 20 trades a day. Tells the best war stories at the Cafe. Risk is breakfast.",
    },
    "ESFP": {
        "name": "Entertainer",
        "traits": TraitProfile(extraversion=0.95, sensing=0.85, thinking=0.10, judging=0.10),
        "color": "#D48D5E",
        "motto": "If it goes up, I'm in!",
        "backstory": "Actor who trades on momentum and vibes. Every trade is a performance. The Town Square is their stage. Loses big, wins bigger.",
    },
}

for pid, defn in PERSONA_DEFINITIONS.items():
    defn["params"] = derive_trading_params(defn["traits"])
    defn["id"] = pid

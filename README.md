<div align="center">

<img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python" alt="Python">
<img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
<img src="https://img.shields.io/badge/status-active-brightgreen?style=flat-square" alt="Status">
<img src="https://img.shields.io/badge/agents-19-ff69b4?style=flat-square" alt="Agents">
<img src="https://img.shields.io/badge/LLM-optional-orange?style=flat-square" alt="LLM">

</div>

<h1 align="center">
  🏘️ Agent Street
</h1>

<p align="center">
  <i>A pixel-art simulation town where AI traders live, chat, and fight the market.</i>
  <br>
  <i>16 MBTI traders + 3 observer agents. Real stock data. Fragile equilibria. LLM-powered souls.</i>
</p>

<p align="center">
  <sub><a href="README_CN.md">📖 中文文档</a></sub>
</p>

---

## 💡 Concept

```
Real stock bars  ──forced projection──→  🏪 Town Market
                                              │
     ┌────────────────────────────────────────┼────────────────────────┐
     ▼                        ▼               ▼                        ▼
  🧠 Observe·Reflect·Memory  💬 Chat·Spread   📈 Personality-driven    🔭📐🔮 Observer
                              Sentiment        Trading                 Reports
     │                        │               │                        │
     └────────────────────────┼───────────────┘                        │
                              ▼                                        │
                    ⚖️ Hedging Engine (House MM)                       │
                    Absorbs net imbalance → Price ≡ Real Price          │
                              │                                        │
                              ▼                                        │
              🔄 Fragile equilibrium → Break → New equilibrium → Break │
```

> Historical K-lines advance tick by tick. Agents observe price changes, form reflections, hold conversations, and place orders. All net imbalance is absorbed by a House market-maker, guaranteeing the town's stock price equals the real-world price. The tension between agent sentiment and real market movement forms a **fragile equilibrium that keeps breaking**.

---

## 🖥️ Screenshot

> _Add a screenshot here after running the simulation:_
> 1. `python run.py` → http://localhost:8765 → click START
> 2. Wait 30 seconds for the map to fill with activity
> 3. Screenshot: `Win+Shift+S` (Windows) or `Cmd+Shift+4` (macOS)
> 4. Save as `docs/screenshot.png` and update the path below

![Agent Street Screenshot](docs/screenshot.png)

## 🗺️ Town Map

```
Actual 20x14 tile map generated from backend/models/town.py:

Legend:  . grass  = road  | road_v  # building  * tree  ~ water  : sidewalk

***..............***
*..................*
..###...###...###...
..###...###...###...
::::::::::::::::::::
....................
..##....###....##...
..##....###....##...
::::::::::::::::::::
...*....~~....*....
...*....~~....*....
::::::::::::::::::::
........###.........
.**..*..###..*..**..

Locations:
  Blue Roof House (2,2)    Red Roof House (9,2)   Green Roof House (14,2)
  Yellow Roof House (2,6)  Morning Brew Cafe (9,6) Data Library (15,6)
  Trading Floor (2,9)      Willow Park (9,9)       Town Square (9,12)
  Observatory (17,10)       Math Tower (18,2)       Fortune Tent (1,11)
```

## 🖥️ Interface

<table>
<tr>
<td width="65%">

```
        🏘️  Agent Street (20×14 tile town map)

         ┌──────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
         │ 🏠 Blue  │  │ 🏠 Red   │  │ 🏠 Green │    │ 📐 Math  │
         │  Roof    │  │  Roof    │  │  Roof    │    │  Tower   │
         │INTJ INTP │  │INFJ INFP │  │ISTJ ISFJ │    │(observer)│
         │ENTJ ENTP │  │ENFJ ENFP │  │ESTJ ESFJ │    └──────────┘
         └──────────┘  └──────────┘  └──────────┘
         ═══════════════════════════════════════════════  ← Main Road
         ┌─────┐    ┌──────────┐              ┌──────────┐
         │ ☕   │    │ 🏠 Yellow│              │ 📚 Data  │
         │Cafe │    │  Roof    │              │ Library  │
         └─────┘    │ISTP ISFP │              └──────────┘
                    │ESTP ESFP │
         ═══════════┴──────────╩════════════════════════
    ┌──────────┐  ┌──────────┐  ┌────┐
 🔮 │ Fortune  │  │📊Trading │  │🌿  │          ┌──────────┐
    │  Tent    │  │  Floor   │  │Park│          │ 🔭 Obser-│
    └──────────┘  └──────────┘  └────┘          │  vatory  │
         ═══════════════════════════════════     └──────────┘
              ┌────────────┐
              │ 🌳 Town    │
              │   Square   │
              └────────────┘
```

</td>
<td width="35%">

**Every tick pushes live:**
- 📍 19 agents moving on the map
- 💬 Chat bubbles with actual dialog
- 😊 Mood expressions (calm/panic/excited)
- 📈 5-line stock chart (% change)
- 🏆 Real-time P&L leaderboard
- 📝 Trade feed with rationale
- 🔭📐🔮 Observer reports

**Click an agent** → View memory
- Recent reflections
- Conversations heard
- Personal backstory

</td>
</tr>
</table>

---

## 🚀 Quick Start

```bash
git clone https://github.com/huiihao/agent-street.git
cd agent-street
pip install -r requirements.txt
python run.py
```

Open **http://localhost:8765**, click **START**.

✅ Works out of the box — no API key needed.

---

## 🤖 LLM Integration (optional, recommended)

Set environment variables to let LLMs power agent reflections and conversations:

```bash
# Windows PowerShell
$env:LLM_ENABLED="true"
$env:LLM_API_KEY="sk-xxxxxxxxxxxxx"
$env:LLM_MODEL="gpt-4o-mini"

# Linux / macOS
export LLM_ENABLED=true
export LLM_API_KEY="sk-xxxxxxxxxxxxx"
```

Compatible with any OpenAI-format API:

| Backend | `LLM_BASE_URL` |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Anthropic (via proxy) | `https://api.anthropic.com/v1` |
| Ollama (local) | `http://localhost:11434/v1` |
| vLLM / LM Studio | `http://localhost:8000/v1` |

Without an API key, rule-based templates take over automatically.

---

## 👥 Agents

### 16 MBTI Traders

Each personality maps to 10 trading parameters via a continuous function of E/I, S/N, T/F, J/P dimensions.

| 🎨 | ID | Name | Style | Haunt |
|---|---|---|---|---|
| `#4A6FA5` | **INTJ** | Architect | Quant analyst, sees patterns before they form | 📚 |
| `#6B7DB3` | **INTP** | Logician | Data obsessive, needs 10 signals to act | 📚 |
| `#C4543E` | **ENTJ** | Commander | Treats the market like a battlefield | 📊 |
| `#D4853A` | **ENTP** | Debater | Contrarian, fades every consensus | ☕ |
| `#5B9E6F` | **INFJ** | Advocate | Reads market sentiment like a therapist | 🌿 |
| `#7DB37D` | **INFP** | Mediator | Trades by visual harmony in the charts | 🌿 |
| `#D4A843` | **ENFJ** | Protagonist | Community leader, people follow their calls | 🌳 |
| `#E8B84B` | **ENFP** | Campaigner | Every trade is the next big thing | ☕ |
| `#5A7A9A` | **ISTJ** | Logistician | Retired accountant, 30-year track record | 📊 |
| `#6B9E8A` | **ISFJ** | Defender | Capital preservation above all | 🏠 |
| `#B84D3E` | **ESTJ** | Executive | Military discipline, process > hunches | 📊 |
| `#C46D5E` | **ESFJ** | Consul | FOMO-driven, buys what others buy | 🌳 |
| `#4A7A9A` | **ISTP** | Virtuoso | Mechanic, precise entries during lunch break | ☕ |
| `#5B9E7A` | **ISFP** | Adventurer | Musician, trades by rhythm and feel | 🌿 |
| `#C46D3E` | **ESTP** | Entrepreneur | Ex-poker pro, thrives on volatility | ☕ |
| `#D48D5E` | **ESFP** | Entertainer | Every trade is a performance | 🌳 |

### 🔭📐🔮 3 Observers

Three non-trading agents who analyze the system from the outside:

| 🎨 | ID | Name | Location | Approach | Confidence |
|---|---|---|---|---|---|
| `#7B9ECF` | **physicist** | Physicist | 🔭 Observatory | Statistical physics, phase transitions, order parameters, correlation lengths | 70–85% |
| `#9E7BCF` | **mathematician** | Mathematician | 📐 Math Tower | Graph theory, combinatorial optimization, sentiment topology, clique detection | 75–90% |
| `#CF7BAE` | **mystic** | Mystic | 🔮 Fortune Tent | I Ching, tea leaves, cosmic energy, astrology, vibes | 5–45% ⭐ |

Each generates a report every ~20 ticks in their own domain language.

---

## ⚖️ Hedging Engine

```
Agent trade intents
    │
    ├─ ✅ Matchable  ──→  Agent A buys ←→ Agent B sells (direct cross)
    │
    └─ ❌ Unmatched  ──→  🏛️ House market-maker absorbs
                           │
                           ├─ Net buying  → House sells (goes short)
                           ├─ Net selling → House buys (goes long)
                           │
                           └─ Net effect: Town price ≡ Real price
```

---

## 🔧 Configuration

Edit `backend/config.py`:

```python
# 📡 Historical data replay
HIST_DAYS_BACK = 5        # Days of history to load
HIST_INTERVAL = "5m"      # Bar interval: 1m / 5m / 15m / 30m / 1h
HIST_LOOP = True          # Loop when data runs out

# ⏱️ Simulation speed
TICK_INTERVAL_SEC = 1.5   # Seconds per tick

# 📈 Symbols
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

# 💵 Agent parameters
INITIAL_CASH = 10_000.0   # Starting cash per agent
BUY_THRESHOLD = 0.08      # Buy signal threshold
SELL_THRESHOLD = -0.05    # Sell signal threshold
```

---

## 🧱 Project Structure

```
agent-street/
├── backend/
│   ├── main.py              # FastAPI entry | REST + WebSocket
│   ├── config.py            # All tunable parameters
│   ├── ws_manager.py        # WebSocket broadcast manager
│   ├── models/
│   │   ├── portfolio.py     # Holdings, trade intents, agent state
│   │   ├── market.py        # Simulation frame, snapshots
│   │   └── town.py          # 20×14 town map, 12 locations, BFS pathfinding
│   ├── engine/
│   │   ├── simulation.py    # 🎯 Main loop: orchestrates all subsystems
│   │   ├── market_data.py   # 📡 yfinance historical bar replay
│   │   ├── persona_engine.py# 🧠 MBTI → trading decisions
│   │   ├── matching_engine.py# ⚖️ Hedging engine + House market-maker
│   │   ├── memory_system.py # 🗄️ 3-layer memory (observe→reflect→long-term)
│   │   ├── daily_routine.py # 🚶 MBTI schedules + town movement
│   │   ├── conversation.py  # 💬 Agent-to-agent conversation
│   │   ├── observer_engine.py# 🔭📐🔮 Observer report generation
│   │   └── llm_client.py    # 🤖 LLM API client (optional)
│   └── mbti/
│       ├── types.py         # Personality dimensions, parameter derivation
│       └── personas.py      # 16 agent definitions
├── frontend/
│   ├── index.html           # Single-page app
│   ├── css/style.css        # Pixel-art dark theme
│   └── js/
│       ├── app.js           # Bootstrap + event wiring
│       ├── ws_client.js     # WebSocket client (auto-reconnect)
│       ├── rendering/
│       │   └── pixel_art.js # 8×8 procedural pixel sprites
│       └── canvas/
│           ├── town_map.js       # 🗺️ Town map renderer
│           ├── stock_chart.js    # 📈 5-line %-change chart
│           ├── leaderboard.js    # 🏆 P&L ranking
│           ├── trade_feed.js     # 📝 Scrolling trade log
│           ├── agent_detail.js   # 👤 Agent detail panel
│           └── observer_reports.js# 🔭📐🔮 Observer report panel
├── requirements.txt
├── run.py
├── README.md
└── README_CN.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| 🐍 Backend | Python 3.10+ · FastAPI |
| 📡 Data | yfinance (Yahoo Finance) |
| 🤖 AI | OpenAI-compatible API (optional) |
| 🎨 Frontend | Vanilla JS · HTML5 Canvas |
| 🔤 Font | Press Start 2P (Google Fonts) |

---

## 🙏 Acknowledgments

This project draws inspiration from:

- 🏘️ [**Generative Agents** (Park et al., 2023)](https://github.com/joonspk-research/generative_agents) — Stanford Smallville, LLM-powered generative agent town
- 🧠 **MBTI personality theory** — applied to quantitative trading behavior modeling
- 🎮 **Pixel art tradition** — the aesthetic legacy of 16-bit games

---

<div align="center">
  <sub>Made with ❤️ · MIT License · <a href="https://github.com/huiihao/agent-street">github.com/huiihao/agent-street</a></sub>
</div>

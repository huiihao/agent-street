# Agent Street

> 在小镇里住着 16 个性格各异的 AI 交易员，外部真实的股票走势会投射到小镇的股市里。Agent 会聊天、反思、交易——人格驱动决策，LLM 赋予灵魂。

A pixel-art simulation town where 16 generative AI agents live, trade stocks, and influence each other. Real market data is projected onto the town's stock market. Agents with MBTI personalities make decisions, form memories, hold conversations, and collectively discover fragile equilibria — only to break them again.

https://github.com/user-attachments/assets/demo-screenshot-placeholder

---

## 概念 / Concept

真实世界的股票数据和虚拟小镇的 Agent 之间形成了一个双向映射：

1. **外部数据投射** — 历史 K 线（5 分钟级）逐根推进小镇股市
2. **Agent 决策** — 每根 K 线触发 16 个 MBTI Agent 的观察、反思、对话、交易
3. **对冲平衡** — 总买卖差额由 House 吸收，确保小镇股价 ≡ 真实股价
4. **脆弱均衡** — Agent 群体情绪和真实走势之间反复博弈：均衡 → 打破 → 新均衡 → 再打破

Real stock data is forced onto the town's market. Agents trade against it. The net imbalance is absorbed by a House market-maker, guaranteeing price fidelity. The tension between agent sentiment and real price movement creates a cycle of fragile equilibria.

---

## 架构 / Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Street                          │
│                                                         │
│  yfinance 历史K线 ──→ 逐根回放 ──→ 小镇股市              │
│                              │                          │
│      ┌───────────────────────┼──────────────────────┐   │
│      ▼                       ▼                      ▼   │
│  16 MBTI Agent         对冲引擎 (House)        前端 UI   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐   │
│  │ 观察 → 反思  │    │ 匹配买卖双方  │    │ 像素小镇  │   │
│  │ 对话 → 决策  │    │ House 吸差额 │    │ 股票图表  │   │
│  │ 记忆 → 情绪  │    │ 价格强制对齐  │    │ 排行榜    │   │
│  └──────────────┘    └──────────────┘    │ 对话气泡  │   │
│       │                                  │ Agent面板 │   │
│       └──── LLM (可选) ←─────────────────┴──────────┘   │
│           OpenAI / Anthropic / Ollama                    │
└─────────────────────────────────────────────────────────┘
```

---

## 快速开始 / Quick Start

```bash
# 1. 克隆
git clone https://github.com/huiihao/agent-street.git
cd agent-street

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python run.py
```

浏览器打开 **http://localhost:8765**，点击 **START**。

无需任何 API key 即可运行（Agent 使用内置规则引擎）。

---

## 接入 LLM（可选）/ LLM Integration

配置环境变量后，Agent 会使用 LLM 生成反思和对话，行为更加丰富：

```bash
# Windows PowerShell
$env:LLM_ENABLED="true"
$env:LLM_API_KEY="sk-xxxxxxxxxxxxx"
$env:LLM_MODEL="gpt-4o-mini"          # 可选，默认 gpt-4o-mini
$env:LLM_BASE_URL="https://api.openai.com/v1"  # 可选

# 然后用本地模型：
# $env:LLM_BASE_URL="http://localhost:11434/v1"
# $env:LLM_MODEL="llama3"

python run.py
```

```bash
# Linux / macOS
export LLM_ENABLED=true
export LLM_API_KEY="sk-xxxxxxxxxxxxx"
python run.py
```

支持的 API 格式：OpenAI Chat Completions（兼容 Anthropic、DeepSeek、Ollama、vLLM、LM Studio 等）。

不上 LLM 也完全可用——规则模板会自动接管。

---

## 小镇地图 / Town Map

```
   🌲🌲🌲                    🌲🌲🌲
         🏠Blue Roof    🏠Red Roof    🏠Green Roof
         (INTJ,INTP,    (INFJ,INFP,   (ISTJ,ISFJ,
          ENTJ,ENTP)     ENFJ,ENFP)    ESTJ,ESFJ)
         ────────────────────────────────  ← Main Road
              ☕ Cafe        📚 Library
         ────────────────────────────────
    📊 Trading Floor    🌿 Park    🏠Yellow Roof
                                  (ISTP,ISFP,
         ───────────────────────── ESTP,ESFP)
              🌳 Town Square
```

| 地点 / Location | 功能 / Purpose |
|---|---|
| Blue/Red/Green/Yellow Roof | 4 栋住宅，每栋 4 人 |
| Morning Brew Cafe | 上午聚集，闲聊股票 |
| Trading Floor | 交易大厅，分析数据 |
| Data Library | 安静研究 |
| Town Square | 下午聚会，传播情绪 |
| Willow Park | 傍晚散步，独自反思 |

---

## 16 个 MBTI Agent

每种人格有独特的交易参数和日常行程：

| Agent | 人格 | 风格 | 活跃地点 |
|---|---|---|---|
| INTJ | Architect | 量化分析型，看穿模式 | Library |
| INTP | Logician | 数据偏执型，等 10 个信号才动手 | Library |
| ENTJ | Commander | 战场指挥官，厌恶犹豫 | Trading Floor |
| ENTP | Debater | 逆向思维，专门和共识对着干 | Cafe |
| INFJ | Advocate | 读市场情绪如读人心 | Park |
| INFP | Mediator | 把 K 线当画看，凭美感交易 | Park |
| ENFJ | Protagonist | 社区领袖，一呼百应 | Town Square |
| ENFP | Campaigner | 社交媒体体质，每笔交易都是 next big thing | Cafe |
| ISTJ | Logistician | 退休会计师，30 年不败记录 | Trading Floor |
| ISFJ | Defender | 资本保全至上，恐慌得早但每次都活下来 | Home |
| ESTJ | Executive | 军人作风，纪律 > 直觉 | Trading Floor |
| ESFJ | Consul | FOMO 驱动，看别人买什么就买什么 | Town Square |
| ISTP | Virtuoso | 机械师，午休时精准狙击 | Cafe |
| ISFP | Adventurer | 音乐家，凭节奏交易 | Park |
| ESTP | Entrepreneur | 前扑克选手，波动越大越兴奋 | Cafe |
| ESFP | Entertainer | 演员，每笔交易都是一场表演 | Town Square |

---

## 对冲机制 / Hedging Engine

```
Agent 买卖意图
    │
    ├─ 可以直接撮合的 → Agent A vs Agent B 对敲
    │
    └─ 无法撮合的 → House 做市商吸收
                     │
                     ├─ 买入多 → House 卖出（做空）
                     ├─ 卖出多 → House 买入（做多）
                     │
                     └─ 净效果：股价 = 真实股价（不变）
```

---

## 配置 / Configuration

编辑 `backend/config.py`：

```python
# 数据回放
HIST_DAYS_BACK = 5       # 加载几天
HIST_INTERVAL = "5m"     # K线级别: 1m, 5m, 15m, 30m, 1h
HIST_LOOP = True         # 播完循环

# 模拟速度
TICK_INTERVAL_SEC = 1.5  # 每 tick 间隔

# 股票
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

# Agent 参数
INITIAL_CASH = 10_000.0  # 每人初始资金
BUY_THRESHOLD = 0.08     # 买入信号阈值
SELL_THRESHOLD = -0.05   # 卖出信号阈值
```

---

## 项目结构 / Project Structure

```
agent-street/
├── backend/
│   ├── main.py              # FastAPI 入口，路由，WebSocket
│   ├── config.py            # 所有可调参数
│   ├── ws_manager.py        # WebSocket 连接管理
│   ├── models/
│   │   ├── portfolio.py     # Holding, TradeIntent, PersonaState
│   │   ├── market.py        # SimulationFrame, 快照数据结构
│   │   └── town.py          # 小镇地图，地点，寻路
│   ├── engine/
│   │   ├── simulation.py    # 主循环编排
│   │   ├── market_data.py   # 历史K线回放 (yfinance)
│   │   ├── persona_engine.py # MBTI 交易决策引擎
│   │   ├── matching_engine.py# 对冲撮合引擎
│   │   ├── memory_system.py # 三层记忆（观察/反思/长期）
│   │   ├── daily_routine.py # MBTI 日程系统
│   │   ├── conversation.py  # Agent 对话系统
│   │   └── llm_client.py    # LLM API 客户端（可选）
│   └── mbti/
│       ├── types.py         # TraitProfile, TradingParams
│       └── personas.py      # 16 个人格定义
├── frontend/
│   ├── index.html           # 单页应用
│   ├── css/style.css        # 像素风主题
│   └── js/
│       ├── app.js           # 启动脚本
│       ├── ws_client.js     # WebSocket 客户端
│       ├── rendering/
│       │   └── pixel_art.js # 像素精灵生成
│       └── canvas/
│           ├── town_map.js      # 小镇地图渲染
│           ├── stock_chart.js   # 股票走势图
│           ├── leaderboard.js   # 盈亏排行榜
│           ├── trade_feed.js    # 交易流水
│           └── agent_detail.js  # Agent 详情面板
├── requirements.txt
├── run.py
└── README.md
```

---

## 技术栈 / Tech Stack

| 层 | 技术 |
|---|---|
| 后端 | Python, FastAPI, WebSocket |
| 数据 | yfinance (Yahoo Finance) |
| AI | OpenAI-compatible API (可选) |
| 前端 | Vanilla JS, HTML5 Canvas, 像素精灵 |
| 字体 | Press Start 2P (Google Fonts) |

---

## 致谢 / Acknowledgments

本项目概念受以下工作启发：
- [Generative Agents (Park et al., 2023)](https://github.com/joonspk-research/generative_agents) — 斯坦福 Smallville 小镇
- MBTI 人格理论在量化交易行为建模中的应用

---

## License

MIT

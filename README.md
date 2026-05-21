<div align="center">

<img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python" alt="Python">
<img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
<img src="https://img.shields.io/badge/status-active-brightgreen?style=flat-square" alt="Status">
<img src="https://img.shields.io/badge/agents-16-ff69b4?style=flat-square" alt="Agents">
<img src="https://img.shields.io/badge/LLM-optional-orange?style=flat-square" alt="LLM">

</div>

<h1 align="center">
  🏘️ Agent Street
</h1>

<p align="center">
  <i>A pixel-art simulation town where 16 AI traders live, chat, and fight the market.</i>
  <br>
  <i>16 个性格各异的 AI 交易员住在一个像素小镇里。他们观察行情、彼此交谈、做出决策——</i>
  <br>
  <i>真实股价被强制投射进来，Agent 群体在脆弱均衡与瞬间崩溃之间反复摇摆。</i>
</p>

<br>

<p align="center">
  <b>🏠 Home</b> &nbsp;·&nbsp;
  <b>☕ Cafe</b> &nbsp;·&nbsp;
  <b>📊 Trading Floor</b> &nbsp;·&nbsp;
  <b>📚 Library</b> &nbsp;·&nbsp;
  <b>🌳 Town Square</b> &nbsp;·&nbsp;
  <b>🌿 Park</b>
</p>

---

## 💡 核心概念

```
外部真实股价 ──强制投射──→ 🏪 小镇股市
                              │
     ┌────────────────────────┼────────────────────────┐
     ▼                        ▼                        ▼
  🧠 观察·反思·记忆      💬 Agent 交谈·传播情绪      📈 人格驱动交易
     │                        │                        │
     └────────────────────────┼────────────────────────┘
                              ▼
                    ⚖️ 对冲引擎 (House 做市商)
                    吸收净差额 → 股价 ≡ 真实股价
                              │
                              ▼
              🔄 脆弱均衡 → 打破 → 新均衡 → 再打破
```

> **外部 K 线**逐根推进。Agent 观察涨跌、生成反思、彼此交谈、下单买卖。所有买卖净额由 House 做市商吸收，确保小镇的股价始终等于真实世界的股价。Agent 的情绪和真实走势之间的张力，形成了一种**不断被打破的脆弱平衡**。

---

## 🖥️ 界面

<table>
<tr>
<td width="65%">

```
🏘️  AGENT STREET 小镇地图 (20×14 tiles)

🌲🌲🌲                    🌲🌲🌲
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ 🏠 Blue  │  │ 🏠 Red   │  │ 🏠 Green │
      │  Roof    │  │  Roof    │  │  Roof    │
      │ INTJ INTP│  │ INFJ INFP│  │ ISTJ ISFJ│
      │ ENTJ ENTP│  │ ENFJ ENFP│  │ ESTJ ESFJ│
      └──────────┘  └──────────┘  └──────────┘
      ════════════════════════════════════════  ← Main Road
      ┌─────┐                         ┌──────────┐
      │ ☕   │                         │ 📚 Data  │
      │Cafe │                         │ Library  │
      └─────┘                         └──────────┘
      ════════════════════════════════════════
 ┌──────────┐   ┌────┐             ┌──────────┐
 │📊Trading │   │🌿  │             │ 🏠 Yellow│
 │  Floor   │   │Park│             │  Roof    │
 └──────────┘   └────┘             │ISTP ISFP │
      ════════════════════════════ │ESTP ESFP │
            ┌────────────┐         └──────────┘
            │ 🌳 Town    │
            │   Square   │
            └────────────┘
```
</td>
<td width="35%">

**每个 tick 实时推送：**
- 📍 Agent 在地图上的位置
- 💬 对话气泡（谁在跟谁聊天）
- 😊 Agent 表情（淡定/恐慌/兴奋）
- 📈 5 条股票走势线
- 🏆 实时盈亏排行榜
- 📝 交易流水 + 决策理由

**点击 Agent** → 查看记忆
- 最近的反思
- 听到的对话
- 个人背景故事

</td>
</tr>
</table>

---

## 🚀 快速开始

```bash
git clone https://github.com/huiihao/agent-street.git
cd agent-street
pip install -r requirements.txt
python run.py
```

浏览器打开 **http://localhost:8765**，点击 **START**。

✅ 无需 API key，开箱即用（Agent 使用内置规则引擎）。

---

## 🤖 接入 LLM（可选，但推荐）

配置环境变量后，Agent 的反思和对话会由 LLM 生成——每个 Agent 的人格真正活起来：

```bash
# Windows PowerShell
$env:LLM_ENABLED="true"
$env:LLM_API_KEY="sk-xxxxxxxxxxxxx"
$env:LLM_MODEL="gpt-4o-mini"

# Linux / macOS
export LLM_ENABLED=true
export LLM_API_KEY="sk-xxxxxxxxxxxxx"
```

兼容任意 OpenAI 格式 API：

| 后端 | `LLM_BASE_URL` |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Anthropic (proxy) | `https://api.anthropic.com/v1` |
| Ollama (本地) | `http://localhost:11434/v1` |
| vLLM / LM Studio | `http://localhost:8000/v1` |

没有配置 API key？没关系——规则模板自动接管，Agent 依然能跑。

---

## 👥 16 个 Agent

每个人格都有专属的交易参数、日常行程和颜色：

| 🎨 | ID | 名称 | 风格 | 常去 |
|---|---|---|---|---|
| `#4A6FA5` | **INTJ** | Architect | 量化分析，看穿模式 | 📚 |
| `#6B7DB3` | **INTP** | Logician | 数据偏执，等十个信号才动手 | 📚 |
| `#C4543E` | **ENTJ** | Commander | 战场指挥官，厌恶犹豫 | 📊 |
| `#D4853A` | **ENTP** | Debater | 逆向思维，专和共识对着干 | ☕ |
| `#5B9E6F` | **INFJ** | Advocate | 读市场情绪如读人心 | 🌿 |
| `#7DB37D` | **INFP** | Mediator | 把 K 线当画看，凭美感交易 | 🌿 |
| `#D4A843` | **ENFJ** | Protagonist | 一呼百应，社区领袖 | 🌳 |
| `#E8B84B` | **ENFP** | Campaigner | 每笔交易都是 next big thing | ☕ |
| `#5A7A9A` | **ISTJ** | Logistician | 退休会计师，三十年不败 | 📊 |
| `#6B9E8A` | **ISFJ** | Defender | 保守至上，恐慌得早但活得久 | 🏠 |
| `#B84D3E` | **ESTJ** | Executive | 军人作风，纪律 > 直觉 | 📊 |
| `#C46D5E` | **ESFJ** | Consul | FOMO 驱动，别人买啥我买啥 | 🌳 |
| `#4A7A9A` | **ISTP** | Virtuoso | 机械师，午休精准狙击 | ☕ |
| `#5B9E7A` | **ISFP** | Adventurer | 音乐家，凭节奏交易 | 🌿 |
| `#C46D3E` | **ESTP** | Entrepreneur | 前扑克选手，波动越大越兴奋 | ☕ |
| `#D48D5E` | **ESFP** | Entertainer | 演员，每笔交易都是表演 | 🌳 |

### 人格 → 交易参数

每个 MBTI 四维度（E/I, S/N, T/F, J/P）通过数学映射推导出 **10 个交易参数**：

| 参数 | 含义 | 受什么影响 |
|---|---|---|
| 💰 `risk_tolerance` | 每笔交易承担的风险 | 高 T + 高 E → 激进 |
| 🔄 `contrarianism` | 逆向倾向（专跟趋势对着干） | 高 I → 逆向 |
| ⚡ `reaction_speed` | 多少 tick 行动一次 | 高 J → 快速 |
| ⏳ `holding_period_ticks` | 平均持仓时长 | 高 N + 高 P → 长线 |
| 📊 `tech_weight` | 技术分析 vs 直觉 | 高 T → 技术派 |
| 😱 `panic_threshold` | 跌多少就恐慌抛售 | 低 T → 易恐慌 |
| 🤑 `greed_threshold` | 涨多少就落袋为安 | 高 T → 更贪婪 |
| 📦 `trade_size_pct` | 每次下注比例 | 高 J + 高 E → 重仓 |
| 🐑 `herding_weight` | 从众程度 | 高 E + 低 T → 羊群 |
| 🎢 `volatility_tolerance` | 对波动的承受力 | 高 T + 高 N → 抗波动 |

---

## ⚖️ 对冲机制

```
Agent 产生买卖意图
    │
    ├─ ✅ 可以直接撮合 ──→ Agent A 买 ←→ Agent B 卖（直接对敲）
    │
    └─ ❌ 无法撮合 ──→ 🏛️ House 做市商吸收
                         │
                         ├─ 净买入 → House 卖出（做空）
                         ├─ 净卖出 → House 买入（做多）
                         │
                         └─ 净效果：小镇股价 ≡ 真实股价
```

---

## 🔧 配置

编辑 `backend/config.py`：

```python
# 📡 数据回放
HIST_DAYS_BACK = 5        # 加载几天的历史数据
HIST_INTERVAL = "5m"      # K 线级别: 1m / 5m / 15m / 30m / 1h
HIST_LOOP = True          # 播完后是否循环

# ⏱️ 模拟速度
TICK_INTERVAL_SEC = 1.5   # 每 tick 秒数

# 📈 股票标的
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

# 💵 Agent 参数
INITIAL_CASH = 10_000.0   # 初始资金
BUY_THRESHOLD = 0.08      # 买入信号触发阈值
SELL_THRESHOLD = -0.05    # 卖出信号触发阈值
```

---

## 🧱 项目结构

```
agent-street/
├── backend/
│   ├── main.py              # FastAPI 入口 | REST + WebSocket
│   ├── config.py            # 所有可调参数集中管理
│   ├── ws_manager.py        # WebSocket 广播管理器
│   ├── models/
│   │   ├── portfolio.py     # 持仓 | 交易意图 | Agent 状态
│   │   ├── market.py        # 仿真帧 | 快照 | 对话记录
│   │   └── town.py          # 20×14 小镇地图 | 9 个地点 | BFS 寻路
│   ├── engine/
│   │   ├── simulation.py    # 🎯 主循环：编排所有子系统
│   │   ├── market_data.py   # 📡 yfinance 历史 K 线逐根回放
│   │   ├── persona_engine.py# 🧠 MBTI → 交易决策
│   │   ├── matching_engine.py# ⚖️ 对冲撮合 + House 做市
│   │   ├── memory_system.py # 🗄️ 三层记忆（观察→反思→长期）
│   │   ├── daily_routine.py # 🚶 MBTI 日程 + 小镇移动
│   │   ├── conversation.py  # 💬 Agent 对话生成
│   │   └── llm_client.py    # 🤖 LLM API 客户端（可选）
│   └── mbti/
│       ├── types.py         # 人格维度 | 交易参数推导
│       └── personas.py      # 16 个 Agent 完整定义
├── frontend/
│   ├── index.html           # 单页应用入口
│   ├── css/style.css        # 像素风暗色主题
│   └── js/
│       ├── app.js           # 启动 + 事件绑定
│       ├── ws_client.js     # WebSocket 客户端（自动重连）
│       ├── rendering/
│       │   └── pixel_art.js # 8×8 像素精灵程序化生成
│       └── canvas/
│           ├── town_map.js      # 🗺️ 小镇地图 Canvas 渲染
│           ├── stock_chart.js   # 📈 五线百分比走势图
│           ├── leaderboard.js   # 🏆 盈亏排行榜
│           ├── trade_feed.js    # 📝 交易实时滚动
│           └── agent_detail.js  # 👤 Agent 详情面板
├── requirements.txt
├── run.py
└── README.md
```

---

## 🛠️ 技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| 🐍 后端 | Python 3.10+ · FastAPI | REST API + WebSocket 实时推送 |
| 📡 数据 | yfinance | Yahoo Finance 历史 K 线下载 |
| 🤖 AI | OpenAI-compatible API | Agent 反思与对话（可选） |
| 🎨 前端 | Vanilla JS · HTML5 Canvas | 像素风渲染，零框架依赖 |
| 🔤 字体 | Press Start 2P | 8-bit 复古像素字体 |

---

## 🙏 致谢

本项目核心概念受以下工作启发：

- 🏘️ [**Generative Agents** (Park et al., 2023)](https://github.com/joonspk-research/generative_agents) — 斯坦福 Smallville，LLM 驱动的生成式 Agent 小镇
- 🧠 **MBTI 人格理论** — 在量化交易行为建模中的应用
- 🎮 像素艺术传统 — 16-bit 游戏的美学遗产

---

<div align="center">
  <sub>Made with ❤️ · MIT License · <a href="https://github.com/huiihao/agent-street">github.com/huiihao/agent-street</a></sub>
</div>

<div align="center">

<img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python" alt="Python">
<img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
<img src="https://img.shields.io/badge/status-active-brightgreen?style=flat-square" alt="Status">
<img src="https://img.shields.io/badge/agents-19-ff69b4?style=flat-square" alt="Agents">
<img src="https://img.shields.io/badge/LLM-optional-orange?style=flat-square" alt="LLM">

</div>

<h1 align="center">
  🏘️ Agent Street · 小人镇
</h1>

<p align="center">
  <i>像素风模拟小镇：19 个 AI Agent 在这里生活、聊天、炒股。</i>
  <br>
  <i>16 个 MBTI 交易员 + 3 个观察者。真实股票数据。脆弱均衡被反复打破。</i>
</p>

<p align="center">
  <sub><a href="README.md">📖 English Docs</a></sub>
</p>

---

## 💡 核心概念

```
外部真实K线  ──强制投射──→  🏪 小镇股市
                                │
     ┌──────────────────────────┼──────────────────────────┐
     ▼              ▼           ▼              ▼           ▼
  🧠 观察·反思  💬 交谈·传播  📈 人格驱动  🔭📐🔮 观察者
     记忆         情绪         交易           分析报告
     │              │           │              │
     └──────────────┼───────────┘              │
                    ▼                          │
          ⚖️ 对冲引擎 (House 做市商)            │
          吸收净差额 → 股价 ≡ 真实股价           │
                    │                          │
                    ▼                          │
    🔄 脆弱均衡 → 打破 → 新均衡 → 再打破 ← 观察者记录
```

> 历史 K 线逐根推进。Agent 观察涨跌、生成反思、彼此交谈、下单买卖。所有净买卖额由 House 做市商吸收，保证小镇股价始终等于真实股价。Agent 情绪与真实走势之间的张力，形成**不断被打破的脆弱平衡**——物理学家称之为"临界现象"，数学家画成"交互图"，玄学高手称之为"道的流转"。

---

## 🚀 快速开始

```bash
git clone https://github.com/huiihao/agent-street.git
cd agent-street
pip install -r requirements.txt
python run.py
```

浏览器打开 **http://localhost:8765**，点击 **START**。

✅ 无需 API key，开箱即用。

---

## 🤖 接入 LLM（可选，推荐）

配置环境变量后，Agent 的反思和对话由 LLM 生成：

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
| Anthropic (代理) | `https://api.anthropic.com/v1` |
| Ollama (本地) | `http://localhost:11434/v1` |
| vLLM / LM Studio | `http://localhost:8000/v1` |

没有 API key？规则模板自动接管。

---

## 🏘️ 小镇地图（12 个地点）

```
         ┌──────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
         │ 🏠 蓝屋顶 │  │ 🏠 红屋顶 │  │ 🏠 绿屋顶 │    │ 📐 数学塔 │
         │INTJ INTP │  │INFJ INFP │  │ISTJ ISFJ │    │(观察者)  │
         │ENTJ ENTP │  │ENFJ ENFP │  │ESTJ ESFJ │    └──────────┘
         └──────────┘  └──────────┘  └──────────┘
         ═══════════════════════════════════════════════  ← 主路
         ┌─────┐    ┌──────────┐              ┌──────────┐
         │ ☕   │    │ 🏠 黄屋顶 │              │ 📚 图书馆 │
         │咖啡馆│    │ISTP ISFP │              └──────────┘
         └─────┘    │ESTP ESFP │
         ═══════════┴──────────╩════════════════════════
    ┌──────────┐  ┌──────────┐  ┌────┐         ┌──────────┐
 🔮 │ 占卜帐篷 │  │📊交易大厅│  │🌿  │         │ 🔭 天文台 │
    └──────────┘  └──────────┘  │公园│         └──────────┘
         ═══════════════════════╡    │
              ┌────────────┐
              │ 🌳 中心广场 │
              └────────────┘
```

---

## 👥 Agent 介绍

### 16 个 MBTI 交易员

每个人格通过数学映射推导出 10 个交易参数：

| 🎨 | ID | 名称 | 风格 | 常去 |
|---|---|---|---|---|
| `#4A6FA5` | **INTJ** | 建筑师 | 量化分析，看穿规律 | 📚 |
| `#6B7DB3` | **INTP** | 逻辑学家 | 数据偏执，等十个信号才动手 | 📚 |
| `#C4543E` | **ENTJ** | 指挥官 | 市场即战场，厌恶犹豫 | 📊 |
| `#D4853A` | **ENTP** | 辩论家 | 逆向思维，专和共识对着干 | ☕ |
| `#5B9E6F` | **INFJ** | 提倡者 | 读市场情绪如读人心 | 🌿 |
| `#7DB37D` | **INFP** | 调停者 | 把K线当画看，凭美感交易 | 🌿 |
| `#D4A843` | **ENFJ** | 主人公 | 社区领袖，一呼百应 | 🌳 |
| `#E8B84B` | **ENFP** | 竞选者 | 每笔交易都是 next big thing | ☕ |
| `#5A7A9A` | **ISTJ** | 物流师 | 退休会计师，三十年不败 | 📊 |
| `#6B9E8A` | **ISFJ** | 守卫者 | 资本保全至上，恐慌得早但活得久 | 🏠 |
| `#B84D3E` | **ESTJ** | 总经理 | 军人纪律，直觉让步于流程 | 📊 |
| `#C46D5E` | **ESFJ** | 执政官 | FOMO驱动，别人买啥我买啥 | 🌳 |
| `#4A7A9A` | **ISTP** | 鉴赏家 | 机械师，午休精准狙击 | ☕ |
| `#5B9E7A` | **ISFP** | 探险家 | 音乐家，凭节奏交易 | 🌿 |
| `#C46D3E` | **ESTP** | 企业家 | 前扑克选手，波动越大越兴奋 | ☕ |
| `#D48D5E` | **ESFP** | 表演者 | 每笔交易都是一场表演 | 🌳 |

### 🔭📐🔮 3 位观察者

不参与交易，站在系统之外观察 Agent 与市场的耦合规律：

| 🎨 | ID | 名称 | 地点 | 方法论 | 置信度 |
|---|---|---|---|---|---|
| `#7B9ECF` | **physicist** | 物理学家 | 🔭 天文台 | 统计物理、相变理论、序参量、关联长度 | 70–85% |
| `#9E7BCF` | **mathematician** | 数学家 | 📐 数学塔 | 图论、组合优化、交互图连通分量、团检测 | 75–90% |
| `#CF7BAE` | **mystic** | 玄学高手 | 🔮 占卜帐篷 | 易经、茶叶、水星逆行、宇宙能量场 | 5–45% ⭐ |

每 ~20 tick 各发一份分析报告，语言风格各具特色。

---

## ⚖️ 对冲机制

```
Agent 买卖意图
    │
    ├─ ✅ 可撮合 ──→ Agent A 买 ←→ Agent B 卖（直接对敲）
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
# 📡 历史数据回放
HIST_DAYS_BACK = 5        # 加载几天的数据
HIST_INTERVAL = "5m"      # K线级别: 1m / 5m / 15m / 30m / 1h
HIST_LOOP = True          # 播完是否循环

# ⏱️ 模拟速度
TICK_INTERVAL_SEC = 1.5   # 每 tick 秒数

# 📈 股票标的
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

# 💵 Agent 参数
INITIAL_CASH = 10_000.0   # 初始资金
BUY_THRESHOLD = 0.08      # 买入信号阈值
SELL_THRESHOLD = -0.05    # 卖出信号阈值
```

---

## 🧱 项目结构

```
agent-street/
├── backend/
│   ├── main.py              # FastAPI 入口 | REST + WebSocket
│   ├── config.py            # 所有可调参数
│   ├── ws_manager.py        # WebSocket 广播
│   ├── models/
│   │   ├── portfolio.py     # 持仓 | 交易意图 | Agent 状态
│   │   ├── market.py        # 仿真帧 | 快照
│   │   └── town.py          # 20×14 小镇地图 | 12 个地点 | BFS 寻路
│   ├── engine/
│   │   ├── simulation.py    # 🎯 主循环
│   │   ├── market_data.py   # 📡 yfinance 历史K线回放
│   │   ├── persona_engine.py# 🧠 MBTI → 交易决策
│   │   ├── matching_engine.py# ⚖️ 对冲撮合
│   │   ├── memory_system.py # 🗄️ 三层记忆
│   │   ├── daily_routine.py # 🚶 日程+移动
│   │   ├── conversation.py  # 💬 Agent 对话
│   │   ├── observer_engine.py# 🔭📐🔮 观察者引擎
│   │   └── llm_client.py    # 🤖 LLM 客户端（可选）
│   └── mbti/
│       ├── types.py         # 人格维度 | 参数推导
│       └── personas.py      # 16 个 Agent 定义
├── frontend/
│   ├── index.html           # 单页应用
│   ├── css/style.css        # 像素风主题
│   └── js/
│       ├── app.js
│       ├── ws_client.js
│       ├── rendering/
│       │   └── pixel_art.js # 8×8 像素精灵
│       └── canvas/
│           ├── town_map.js       # 🗺️ 小镇地图
│           ├── stock_chart.js    # 📈 走势图
│           ├── leaderboard.js    # 🏆 排行榜
│           ├── trade_feed.js     # 📝 交易流水
│           ├── agent_detail.js   # 👤 Agent 面板
│           └── observer_reports.js# 🔭📐🔮 观察报告
├── requirements.txt
├── run.py
├── README.md
└── README_CN.md
```

---

## 🙏 致谢

- 🏘️ [**Generative Agents** (Park et al., 2023)](https://github.com/joonspk-research/generative_agents) — 斯坦福 Smallville
- 🧠 MBTI 人格理论
- 🎮 像素艺术传统

---

<div align="center">
  <sub>MIT License · <a href="https://github.com/huiihao/agent-street">github.com/huiihao/agent-street</a></sub>
</div>

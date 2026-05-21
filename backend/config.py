INITIAL_CASH = 10_000.0
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
TICK_INTERVAL_SEC = 1.5
MAX_PRICE_HISTORY = 300
STRICT_MATCHING = False
BUY_THRESHOLD = 0.08
SELL_THRESHOLD = -0.05

# Historical data replay
HIST_DAYS_BACK = 5       # days of history to load
HIST_INTERVAL = "5m"     # bar interval: 1m, 5m, 15m, 30m, 1h
HIST_LOOP = True          # loop back to start when data runs out

# LLM integration (optional)
LLM_ENABLED = False       # set True to enable LLM-powered agents
LLM_API_KEY = ""          # your API key
LLM_BASE_URL = "https://api.openai.com/v1"  # OpenAI-compatible endpoint
LLM_MODEL = "gpt-4o-mini" # model name
LLM_MAX_TOKENS = 150
LLM_TEMPERATURE = 0.9

# Town simulation
CONVERSATION_RADIUS = 4
REFLECTION_EVERY_N_TICKS = 5
OBSERVATION_MAX = 60
REFLECTION_MAX = 30

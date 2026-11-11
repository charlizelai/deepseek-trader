"""
Central configuration. All hard risk limits live here as CODE constants --
they are not part of any LLM prompt and the model can never change them.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---- DeepSeek API ----
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/beta")  # beta endpoint required for strict mode
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ---- Trading symbol ----
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")

# ==== HARD RISK LIMITS (code layer, model-invisible) ====
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.10"))     # single position <= 10% of equity
MAX_ORDER_USD = float(os.getenv("MAX_ORDER_USD", "500"))            # single order <= $500
MAX_DAILY_DRAWDOWN = float(os.getenv("MAX_DAILY_DRAWDOWN", "0.05")) # 5% intraday drawdown -> no new entries
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))  # 3 losses in a row -> pause
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.02"))           # 2% stop loss attached at entry
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.06"))       # 6% take profit (1:3 RR)

# ---- Paper ledger ----
INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10000"))

# ---- Loop ----
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", "60"))  # seconds

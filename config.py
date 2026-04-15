import os
from dotenv import load_dotenv

load_dotenv()

# ========== Dhan API ==========
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# ========== Telegram ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========== Strategy Parameters ==========
ORB_START = "09:15"
ORB_END = "09:29"                    # 🔥 FIXED: exclude 9:30 candle
MORNING_SESSION_START = "09:30"
MORNING_SESSION_END = "10:30"
AFTERNOON_SESSION_START = "14:30"
AFTERNOON_SESSION_END = "15:00"
SQUARE_OFF_TIME = "15:15"

# RSI
RSI_PERIOD = 14
RSI_LONG_THRESHOLD = 55
RSI_SHORT_THRESHOLD = 45

# Volume
VOLUME_PERIOD = 20
VOLUME_MULTIPLIER = 1.5
VOLUME_INCREASE_REQUIRED = True      # 🔥 ADDED: volume must be > previous candle

# Retest tolerance (0.2%)
RETEST_TOLERANCE = 0.002

# Relative Strength
RELATIVE_STRENGTH_DELTA = 0.002

# Risk Management
RISK_PER_TRADE = 0.01                # 1% of capital
MAX_TRADES_PER_DAY = 3
DAILY_LOSS_LIMIT = 0.02              # 2% of capital
MAX_CONSECUTIVE_LOSSES = 2

# Profit Targets
TARGET_1_R = 1.5
TARGET_2_R = 2.5

# Slippage
SLIPPAGE = 0.0005                    # 🔥 ADDED: 0.05% slippage

# Paper Trading
INITIAL_CAPITAL = 5_00_000
TRADE_LOG_FILE = "trade_log.csv"

# Logging
LOG_FILE = "algo_trader.log"

# Nifty Symbol (Dhan correct ticker)
NIFTY_SYMBOL = "NIFTY"               # 🔥 FIXED: Dhan uses "NIFTY"
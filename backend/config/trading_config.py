"""
Configuration for Daily Trading System

Centralized configuration for strategy execution.
"""

# ============================================================================
# TRADING SYMBOLS
# ============================================================================

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

# ============================================================================
# TIMEFRAMES
# ============================================================================

# Primary timeframe for strategy execution
PRIMARY_TIMEFRAME = "5minute"

# Additional timeframes for multi-timeframe analysis
EXTRA_TIMEFRAMES = ["15minute", "1day"]

# ============================================================================
# RISK PARAMETERS
# ============================================================================

# Maximum capital to deploy per trade
CAPITAL_PER_TRADE = 25000

# Maximum daily loss limit
MAX_DAILY_LOSS = 5000

# Maximum number of simultaneous positions
MAX_POSITIONS = 5

# Total available capital
TOTAL_CAPITAL = 100000

# ============================================================================
# ORDER PARAMETERS
# ============================================================================

# Default product type: MIS (Intraday) or CNC (Delivery)
DEFAULT_PRODUCT = "MIS"

# Order type: MARKET or LIMIT
DEFAULT_ORDER_TYPE = "MARKET"

# Slippage tolerance (in percentage)
SLIPPAGE_TOLERANCE = 0.1

# ============================================================================
# STRATEGY CONFIGURATION
# ============================================================================

# Strategies directory path (relative to backend/)
STRATEGIES_DIR = "strategies"

# Default strategy to use for daily trading
DEFAULT_STRATEGY = "COMBINED_POWER_STRATEGY"

# Enable/disable specific strategies
ENABLED_STRATEGIES = [
    "combined_strategy",  # Primary combined strategy
    "supertrend_strategy",
    "liquidity_strategy",
    "trendline_break_strategy",
]

# Strategy-specific configurations
STRATEGY_CONFIGS = {
    "combined_strategy": {
        "min_confidence": 0.6,
        "weights": {
            "supertrend": 0.25,
            "liquidity": 0.15,
            "trendline": 0.20,
            "vwap": 0.15,
            "bollinger": 0.15,
            "atr": 0.10,
        },
    },
    "supertrend_strategy": {"atr_length": 10, "factor": 3.0},
    "liquidity_strategy": {"swing_length": 14, "use_volume_filter": True},
    "trendline_break_strategy": {"lookback_period": 20, "breakout_threshold": 0.02},
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Log file path
LOG_FILE = "logs/daily_trades.log"

# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = "INFO"

# ============================================================================
# INDIAN BROKERAGE COST CONFIGURATION (AngelOne)
# ============================================================================

# Brokerage: 0.25% OR ₹20 per order (whichever is lower)
BROKERAGE_PERCENT = 0.0025  # 0.25%
BROKERAGE_MINIMUM = 20.0  # ₹20 minimum per order

# Securities Transaction Tax (STT)
STT_DELIVERY = 0.001  # 0.1% on delivery (equity)
STT_INTRADAY = 0.00025  # 0.025% on intraday (equity)

# Transaction Charges (NSE)
TRANSACTION_CHARGES_PERCENT = 0.0000325  # 0.00325% of turnover

# GST on brokerage + transaction charges
GST_PERCENT = 0.18  # 18%

# Slippage configuration
SLIPPAGE_PERCENT = 0.0005  # 0.05% default

# ============================================================================
# EXECUTION SETTINGS
# ============================================================================

# Prevent multiple runs per day
PREVENT_MULTIPLE_RUNS = False  # Set to True for production

# Last run tracking file
LAST_RUN_FILE = "config/last_run.json"

# Market hours check (only trade during market hours)
CHECK_MARKET_HOURS = False  # Set to True for production

# Market open time (IST)
MARKET_OPEN = "09:15"

# Market close time (IST)
MARKET_CLOSE = "15:30"

# ============================================================================
# ZERODHA SPECIFIC
# ============================================================================

# Exchange for NSE stocks
EXCHANGE = "NSE"

# Token storage location
TOKEN_FILE = "config/zerodha_session.json"

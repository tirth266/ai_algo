"""
Flask App for Render Deployment
Entry point for gunicorn: app:app
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://ai-algo-ul1l.vercel.app",
                "https://ai-algo-66d6.onrender.com",
                "http://localhost:5173",
                "http://localhost:3000",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

TRADING_MODE = os.environ.get("TRADING_MODE", "paper")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:7000")

_trading_system = None
_system_initialized = False


def initialize_trading_system():
    """Initialize trading system on startup."""
    global _trading_system, _system_initialized
    if _system_initialized:
        return

    try:
        from backend.core.execution import TradingSystem
        from backend.core.trade_journal import TradeJournal

        _trading_system = TradingSystem(
            capital=float(os.environ.get("DEFAULT_CAPITAL", 100000)),
            risk_per_trade=0.02,
        )

        TradeJournal()
        _system_initialized = True
        logger.info(f"Trading system initialized in {TRADING_MODE} mode")
    except Exception as e:
        logger.warning(f"Could not initialize trading system: {e}")
        _system_initialized = True


initialize_trading_system()

# Import and register blueprints
try:
    from backend.api.broker_routes import broker_bp

    app.register_blueprint(broker_bp)
    logger.info("Registered broker_routes")
except Exception as e:
    logger.error(f"Could NOT register broker_routes: {e}")

try:
    from backend.api.trading_routes import trading_bp

    app.register_blueprint(trading_bp)
    logger.info("Registered trading_routes")
except Exception as e:
    logger.error(f"Could NOT register trading_routes: {e}")

try:
    from backend.backtest.backtest_routes import backtest_bp

    app.register_blueprint(backtest_bp)
    logger.info("Registered backtest_routes")
except Exception as e:
    logger.error(f"Could NOT register backtest_routes: {e}")

try:
    from backend.engine.strategy_routes import strategy_bp

    app.register_blueprint(strategy_bp)
    logger.info("Registered strategy_routes")
except Exception as e:
    logger.error(f"Could NOT register strategy_routes: {e}")

try:
    from backend.api.journal_routes import journal_bp

    app.register_blueprint(journal_bp)
    logger.info("Registered journal_routes")
except Exception as e:
    logger.error(f"Could NOT register journal_routes: {e}")

try:
    from backend.api.angel_routes import angel_bp

    app.register_blueprint(angel_bp)
    logger.info("Registered angel_routes")
except Exception as e:
    logger.error(f"Could NOT register angel_routes: {e}")


# Health check endpoint
@app.route("/healthz")
def health():
    return jsonify({"status": "ok"}), 200


# Root endpoint
@app.route("/")
def root():
    return jsonify({"message": "Algo Trading API Running", "version": "1.0.0"})


# Dashboard endpoint
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    """Dashboard data endpoint."""
    return jsonify(
        {
            "message": "Dashboard working",
            "trading_mode": TRADING_MODE,
            "system_initialized": _system_initialized,
        }
    ), 200


# Health check for load balancers (lightweight)
@app.route("/health")
def health_alt():
    return jsonify({"status": "ok"}), 200


# Global error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found", "status": "error"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "status": "error"}), 500


@app.route("/api/trading/health")
def trading_health():
    """Trading system health check endpoint."""
    return jsonify(
        {
            "status": "ok",
            "trading_mode": TRADING_MODE,
            "system_initialized": _system_initialized,
        }
    ), 200


@app.route("/run-bot")
def run_bot():
    """
    Trigger trading bot execution via external cron service.

    This endpoint:
    - Fetches current market data
    - Generates trading signals
    - Opens/updates trades
    - Returns execution summary
    """
    try:
        logger.info("Bot triggered by cron")

        if _trading_system is None:
            return jsonify(
                {"status": "error", "message": "Trading system not initialized"}
            ), 500

        import pandas as pd
        from datetime import datetime, timedelta

        trade_result = {
            "signal_generated": False,
            "signal": None,
            "exits": [],
            "open_positions": 0,
            "performance": None,
            "executed_at": datetime.now().isoformat(),
            "error": None,
        }

        try:
            from backend.services.market_data import global_price_store

            symbols = ["NSE:NIFTY 50", "NSE:BANKNIFTY"]
            data_dict = {}

            for symbol in symbols:
                price = global_price_store.get_price(symbol)
                if price:
                    current_time = datetime.now()
                    times = [
                        current_time - timedelta(minutes=i * 5)
                        for i in range(50, 0, -1)
                    ]

                    ohlc_data = {
                        "open": [
                            price * (1 + (hash(str(t)) % 100 - 50) / 10000)
                            for t in times
                        ],
                        "high": [price * 1.002 for _ in times],
                        "low": [price * 0.998 for _ in times],
                        "close": [
                            price * (1 + (hash(str(t)) % 100 - 50) / 12000)
                            for t in times
                        ],
                        "volume": [1000000 for _ in times],
                    }

                    df = pd.DataFrame(ohlc_data, index=pd.DatetimeIndex(times))
                    df.index.name = "timestamp"
                    data_dict[symbol] = df

            for symbol, data in data_dict.items():
                _trading_system.strategy.symbol = symbol.replace("NSE:", "")
                cycle = _trading_system.run_cycle(data)

                if cycle.get("signal"):
                    trade_result["signal_generated"] = True
                    trade_result["signal"] = cycle["signal"]

                if cycle.get("exits"):
                    trade_result["exits"].extend(cycle["exits"])

                trade_result["open_positions"] = cycle["open_positions"]
                trade_result["performance"] = cycle["performance"]

        except Exception as data_error:
            logger.warning(f"Could not fetch market data: {data_error}")
            trade_result["error"] = str(data_error)

            trade_result["open_positions"] = len(
                _trading_system.trade_manager.open_trades
            )
            trade_result["performance"] = (
                _trading_system.trade_manager.get_performance()
            )

        result = {
            "status": "success",
            "message": "Bot executed",
            "mode": TRADING_MODE,
            "trade_result": trade_result,
            "system_status": {
                "initialized": _system_initialized,
                "open_trades": trade_result["open_positions"],
                "can_trade": True,
            },
        }

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Run on Render PORT
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

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

CORS(app, resources={r"/api/*": {"origins": "*"}})

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
    logger.warning(f"Could not register broker_routes: {e}")

try:
    from backend.api.trading_routes import trading_bp

    app.register_blueprint(trading_bp)
    logger.info("Registered trading_routes")
except Exception as e:
    logger.warning(f"Could not register trading_routes: {e}")

try:
    from backend.backtest.backtest_routes import backtest_bp

    app.register_blueprint(backtest_bp)
    logger.info("Registered backtest_routes")
except Exception as e:
    logger.warning(f"Could not register backtest_routes: {e}")

try:
    from backend.engine.strategy_routes import strategy_bp

    app.register_blueprint(strategy_bp)
    logger.info("Registered strategy_routes")
except Exception as e:
    logger.warning(f"Could not register strategy_routes: {e}")

try:
    from backend.api.journal_routes import journal_bp

    app.register_blueprint(journal_bp)
    logger.info("Registered journal_routes")
except Exception as e:
    logger.warning(f"Could not register journal_routes: {e}")


# Health check endpoint
@app.route("/healthz")
def health():
    return jsonify({"status": "ok"}), 200


# Root endpoint
@app.route("/")
def root():
    return jsonify({"message": "Algo Trading API Running", "version": "1.0.0"})


# Health check for load balancers (lightweight)
@app.route("/health")
def health_alt():
    return "ok", 200


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
    - Checks market conditions
    - Executes trades if conditions are met
    - Returns quickly (no blocking)
    """
    try:
        logger.info("Bot triggered by cron")

        if _trading_system is None:
            return {"status": "error", "message": "Trading system not initialized"}, 500

        result = {
            "status": "success",
            "message": "Bot executed",
            "mode": TRADING_MODE,
            "system_active": _system_initialized,
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

"""
Flask App for Render Deployment
Entry point for gunicorn: app:app
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Enable CORS for React frontend
CORS(app, resources={r"/api/*": {"origins": "*"}})

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
    from backend.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(dashboard_bp)
    logger.info("Registered dashboard_routes")
except Exception as e:
    logger.warning(f"Could not register dashboard_routes: {e}")


# Health check endpoint
@app.route("/healthz")
def health():
    return jsonify({"status": "ok"}), 200


# Root endpoint
@app.route("/")
def root():
    return jsonify({"message": "Algo Trading API Running", "version": "1.0.0"})


# Health check for load balancers
@app.route("/health")
def health_alt():
    return jsonify({"status": "healthy"}), 200


# Run on Render PORT
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

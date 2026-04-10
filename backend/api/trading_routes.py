"""Trading control API routes implemented with Flask Blueprints."""

import logging
import threading
from datetime import datetime

from flask import Blueprint, jsonify

from backend.flask_compat import ApiError

logger = logging.getLogger(__name__)

trading_bp = Blueprint("trading", __name__, url_prefix="/api/trading")

trading_state = {
    "running": False,
    "thread": None,
    "start_time": None,
    "active_strategies": 0,
    "broker_connected": False,
    "symbols_monitored": [],
    "signals_generated": 0,
    "orders_placed": 0,
}


@trading_bp.route("/start", methods=["POST"])
def start_trading():
    try:
        logger.info("Web UI requested to start trading...")

        if trading_state["running"]:
            return jsonify(
                {
                    "success": False,
                    "message": "Trading engine already running",
                    "status": _build_trading_status_payload(),
                }
            )

        try:
            from backend.trading.web_trading_controller import WebTradingController

            controller = WebTradingController()
        except ImportError as exc:
            raise ApiError(500, f"Trading controller not found: {str(exc)}")

        def run_trading():
            try:
                trading_state["running"] = True
                trading_state["start_time"] = datetime.now().isoformat()
                controller.run_trading_loop()
            except Exception as exc:
                logger.error(f"Trading loop error: {str(exc)}")
                trading_state["running"] = False
                raise

        trading_state["thread"] = threading.Thread(target=run_trading, daemon=True)
        trading_state["thread"].start()

        return jsonify(
            {
                "success": True,
                "message": "Trading engine started successfully",
                "status": _build_trading_status_payload(),
            }
        )
    except ApiError:
        raise
    except Exception as exc:
        logger.error(f"Failed to start trading: {str(exc)}")
        trading_state["running"] = False
        raise ApiError(500, f"Failed to start trading: {str(exc)}")


@trading_bp.route("/stop", methods=["POST"])
def stop_trading():
    try:
        if not trading_state["running"]:
            return jsonify(
                {
                    "success": False,
                    "message": "Trading engine not running",
                    "status": _build_trading_status_payload(),
                }
            )

        trading_state["running"] = False
        if trading_state["thread"]:
            trading_state["thread"].join(timeout=5.0)

        return jsonify(
            {
                "success": True,
                "message": "Trading engine stopped successfully",
                "status": _build_trading_status_payload(),
            }
        )
    except Exception as exc:
        logger.error(f"Failed to stop trading: {str(exc)}")
        raise ApiError(500, f"Failed to stop trading: {str(exc)}")


def _build_trading_status_payload():
    return {
        "running": trading_state["running"],
        "active_strategies": trading_state["active_strategies"],
        "broker_connected": trading_state["broker_connected"],
        "symbols_monitored": trading_state["symbols_monitored"],
        "signals_generated": trading_state["signals_generated"],
        "orders_placed": trading_state["orders_placed"],
        "start_time": trading_state["start_time"],
        "uptime": calculate_uptime(trading_state["start_time"])
        if trading_state["start_time"]
        else None,
    }


@trading_bp.route("/status", methods=["GET"])
def get_trading_status():
    try:
        return jsonify({"success": True, "status": _build_trading_status_payload()})
    except Exception as exc:
        logger.error(f"Failed to get trading status: {str(exc)}")
        raise ApiError(500, f"Failed to get status: {str(exc)}")


def calculate_uptime(start_time_str: str) -> str:
    try:
        start_time = datetime.fromisoformat(start_time_str)
        now = datetime.now()
        delta = now - start_time

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except:
        return "Unknown"


def update_trading_stats(
    active_strategies: int,
    broker_connected: bool,
    symbols: list,
    signals: int,
    orders: int,
):
    trading_state["active_strategies"] = active_strategies
    trading_state["broker_connected"] = broker_connected
    trading_state["symbols_monitored"] = symbols
    trading_state["signals_generated"] = signals
    trading_state["orders_placed"] = orders

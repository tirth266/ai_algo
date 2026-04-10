import sys
import os
from pathlib import Path
from typing import Optional, List
import logging
import uuid
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from backend.flask_compat import ApiError

# Add the backend directory to sys.path to allow imports like 'from api...import...'
# regardless of whether the app is run from the root or within the backend folder.
backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from utils.logger import setup_logging

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

from utils.symbol_manager import SymbolManager
from services.angelone_service import (
    login as angel_login,
    get_angel_one_service,
)
from services.market_data import global_price_store, start_data_manager
from database.models import SessionLocal, Trade, init_db
from core.nse_order_validator import validate_nse_order

# Trading system imports
from core.execution import TradingSystem, Backtester
from core.trade_manager import TradeManager

app = Flask(__name__)
symbol_manager = SymbolManager()

from backend.api.angel_routes import angel_bp
from backend.api.broker_routes import broker_bp
from backend.api.journal_routes import journal_bp
from backend.api.trading_routes import trading_bp
from backend.routes.dashboard_routes import dashboard_bp
from backend.routes.reconciliation_routes import reconciliation_bp
from backend.routes.auth import auth_bp

app.register_blueprint(angel_bp)
app.register_blueprint(broker_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(trading_bp)
app.register_blueprint(reconciliation_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(auth_bp)

load_dotenv()
setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@app.after_request
def apply_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "https://ai-algo-ul1l.vercel.app"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.errorhandler(ApiError)
def handle_api_error(error):
    return jsonify({"status": "error", "detail": error.detail}), error.status_code


@app.errorhandler(Exception)
def handle_exception(error):
    logger.exception("Unhandled exception")
    status_code = getattr(error, "code", 500)
    return jsonify({"status": "error", "detail": str(error)}), status_code


startup_complete = False

@app.before_request
def before_request():
    global startup_complete
    if startup_complete:
        return

    init_db()
    try:
        if start_data_manager():
            logger.info("✓ Live market data streaming started")
        else:
            logger.warning("⚠ Could not start live market data streaming")
    except Exception as e:
        logger.warning(f"Could not start market data manager: {e}")

    startup_complete = True


class OrderRequest(BaseModel):
    symbol: str  # e.g., 'SBIN-EQ'
    quantity: int
    price: float = 0.0  # Required > 0 for LIMIT
    transaction_type: str  # 'BUY' or 'SELL'
    exchange: str = "NSE"
    order_type: str = "LIMIT"  # Defualt to LIMIT per 2026 rules
    product_type: str = "INTRADAY"


class ConnectRequest(BaseModel):
    auth_token: str = None


@app.route("/api/auth/connect", methods=["POST"])
def connect_angel_one():
    try:
        data = request.get_json(silent=True) or {}
        req = ConnectRequest(**data) if data else ConnectRequest()

        if req and req.auth_token:
            service = get_angel_one_service()
            service.token_manager._store_tokens(req.auth_token, None, None)
            service.is_authenticated = True
        else:
            angel_login()

        return {"status": "Success", "message": "Angel One session active."}
    except ValidationError as exc:
        raise ApiError(400, str(exc))
    except Exception as exc:
        raise ApiError(401, str(exc))


@app.route("/api/auth/status", methods=["GET"])
def check_auth_status():
    service = get_angel_one_service()
    return {
        "status": "Success",
        "is_authenticated": service.is_valid_session(),
    }


@app.route("/api/prices", methods=["GET"])
def get_prices():
    return global_price_store.get_all_prices()


@app.route("/api/place-order", methods=["POST"])
def place_order_endpoint():
    try:
        payload = request.get_json(silent=True) or {}
        order = OrderRequest(**payload)
    except ValidationError as exc:
        raise ApiError(400, str(exc))

    logger.info(f"Received order request: {order}")
    db = SessionLocal()

    # Resolve symbol to token
    token, lot_size = symbol_manager.get_token(order.symbol, order.exchange)

    if not token:
        db.close()
        logger.error(f"Failed to find token for symbol: {order.symbol}")
        raise ApiError(
            400,
            f"Invalid symbol or token not found for {order.symbol}",
        )

    logger.info(f"Resolved {order.symbol} to token: {token}")

    # Enforce 2026 Limits
    if order.order_type.upper() == "MARKET":
        logger.warning(
            "Intercepted MARKET order. Enforcing LIMIT due to 2026 NSE Algo restrictions."
        )
        order.order_type = "LIMIT"

    if order.order_type.upper() == "LIMIT" and order.price <= 0:
        db.close()
        raise ApiError(400, "LIMIT orders require a specified price > 0.")

    # Get current LTP for validation
    ltp = global_price_store.get_price(token)
    if not ltp or ltp <= 0:
        logger.warning(f"LTP not available for {order.symbol}")
        ltp = order.price  # Fallback to order price if LTP unavailable

    # NSE Compliance Validation
    nse_validation = validate_nse_order(
        symbol=order.symbol,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        ltp=ltp,
        lot_size=lot_size,
        max_slippage_pct=2.0,
    )

    if not nse_validation["valid"]:
        db.close()
        logger.error(
            f"NSE validation failed for {order.symbol}: {nse_validation['reason']}"
        )
        raise ApiError(
            400,
            f"NSE Order Validation Failed: {nse_validation['reason']}",
        )

    logger.info(f"NSE validation passed: {order.symbol} {order.quantity}@{order.price}")

    # Legacy slippage check (kept for compatibility)
    if ltp is not None and order.price > 0:
        difference = abs(order.price - ltp) / ltp
        if difference > 0.05:
            db.close()
            logger.warning(
                f"Price validation failed: Order price {order.price} is >5% away from LTP {ltp}"
            )
            raise ApiError(
                400,
                f"Safety Check Failed: Order price {order.price} is more than 5% away from LTP {ltp} ({difference * 100:.2f}% disparity).",
            )

    try:
        # Example Simulated Order Execution
        order_id = str(uuid.uuid4())
        response = {
            "status": True,
            "message": "Order placed successfully (Simulated)",
            "data": {"orderid": order_id, "token": token},
        }

        if response.get("status"):
            # Save the successful trade to SQLite
            new_trade = Trade(
                order_id=order_id,
                symbol=order.symbol,
                qty=order.quantity,
                price=order.price if order.price > 0 else (ltp or 0.0),
                status="COMPLETED",
            )
            db.add(new_trade)
            db.commit()

            return {
                "status": "success",
                "order_id": order_id,
                "token_used": token,
                "ltp_reference": ltp,
            }
        else:
            raise ApiError(
                400,
                response.get("message", "Order placement failed"),
            )

    except Exception as e:
        logger.error(f"Order error: {e}")
        # Common Angel One error handling e.g., Token Expired
        if "Token Expired" in str(e) or "AB1004" in str(e):
            raise ApiError(
                401, "Session expired. Please relogin to Angel One."
            )
        raise ApiError(500, f"Internal Server Error: {str(e)}")
    finally:
        db.close()


@app.route("/", methods=["GET"])
def read_root():
    return {"message": "Angel One Algo Trading Support API Running"}


# ==============================================================================
# TRADING SYSTEM ENDPOINTS
# ==============================================================================

# Trading system state
_trading_system: Optional[TradingSystem] = None
_is_running = False


def get_trading_system() -> TradingSystem:
    """Get or initialize trading system."""
    global _trading_system
    if _trading_system is None:
        _trading_system = TradingSystem(capital=100000, risk_per_trade=0.02)
    return _trading_system


class TradingStartRequest(BaseModel):
    capital: float = 100000.0
    risk_per_trade: float = 0.02
    max_positions: int = 2
    enable_trailing: bool = True
    mode: str = "paper"


class TradingOrderRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    quantity: int
    reason: str = ""
    confidence: str = "medium"


@app.route("/api/trading/start", methods=["POST"])
def start_trading():
    """Start the trading system."""
    global _is_running, _trading_system

    try:
        payload = request.get_json(silent=True) or {}
        request_data = TradingStartRequest(**payload) if payload else TradingStartRequest()
    except ValidationError as exc:
        raise ApiError(400, str(exc))

    if _is_running:
        return {
            "status": "already_running",
            "message": "Trading system is already running",
        }

    _trading_system = TradingSystem(
        capital=request_data.capital,
        risk_per_trade=request_data.risk_per_trade,
        max_open_positions=request_data.max_positions,
        enable_trailing=request_data.enable_trailing,
    )

    _is_running = True

    logger.info(f"Trading system started: mode={request_data.mode}")

    return {
        "status": "success",
        "message": f"Trading system started in {request_data.mode} mode",
        "capital": request_data.capital,
        "mode": request_data.mode,
    }


@app.route("/api/trading/stop", methods=["POST"])
def stop_trading():
    """Stop the trading system."""
    global _is_running

    if not _is_running:
        return {"status": "not_running", "message": "Trading system is not running"}

    _is_running = False
    logger.info("Trading system stopped")

    return {"status": "success", "message": "Trading system stopped"}


@app.route("/api/trading/status", methods=["GET"])
def get_trading_status():
    """Get trading system status."""
    global _trading_system, _is_running

    if _trading_system is None:
        _trading_system = get_trading_system()

    return {
        "is_running": _is_running,
        "capital": _trading_system.trade_manager.capital,
        "open_trades": len(_trading_system.trade_manager.open_trades),
        "performance": _trading_system.trade_manager.get_performance(),
    }


@app.route("/api/trading/signals", methods=["GET"])
def get_signals():
    """Get recent trading signals."""
    return []  # Populated when signals generated


@app.route("/api/trading/trades", methods=["GET"])
def get_trades():
    """Get active trades."""
    global _trading_system

    if _trading_system is None:
        return []

    return _trading_system.trade_manager.get_open_trades()


@app.route("/api/trading/performance", methods=["GET"])
def get_performance():
    """Get trading performance metrics."""
    global _trading_system

    if _trading_system is None:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0,
        }

    return _trading_system.trade_manager.get_performance()


@app.route("/api/trading/execute", methods=["POST"])
def execute_order():
    """Execute an order."""
    global _trading_system

    try:
        payload = request.get_json(silent=True) or {}
        request_data = TradingOrderRequest(**payload)
    except ValidationError as exc:
        raise ApiError(400, str(exc))

    if _trading_system is None:
        _trading_system = get_trading_system()

    try:
        trade = _trading_system.trade_manager.open_trade(
            symbol=request_data.symbol,
            direction=request_data.direction,
            entry_price=request_data.entry_price,
            stop_loss=request_data.stop_loss,
            take_profit_1=request_data.take_profit_1,
            take_profit_2=request_data.take_profit_2,
            quantity=request_data.quantity,
            confidence=request_data.confidence,
            reason=request_data.reason,
        )

        return {
            "status": "success",
            "trade_id": trade.id,
            "message": f"Order executed: {request_data.direction} {request_data.quantity} {request_data.symbol} @ {request_data.entry_price}",
        }

    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        raise ApiError(500, str(e))


@app.route("/api/trading/backtest", methods=["POST"])
def run_backtest():
    """Run backtest on historical data."""
    payload = request.get_json(silent=True)

    if isinstance(payload, list):
        data = payload
        initial_capital = float(request.args.get("initial_capital", 100000))
        risk_per_trade = float(request.args.get("risk_per_trade", 0.02))
    else:
        payload = payload or {}
        data = payload.get("data", [])
        initial_capital = payload.get("initial_capital", 100000)
        risk_per_trade = payload.get("risk_per_trade", 0.02)

    import pandas as pd

    df = pd.DataFrame(data)

    backtester = Backtester(
        initial_capital=initial_capital, risk_per_trade=risk_per_trade
    )

    results = backtester.run(df)

    return results


@app.route("/api/health", methods=["GET"])
def health_check():
    """Real system health check endpoint."""
    from services.angelone_service import get_angel_one_service
    from services.market_data import get_data_manager
    from core.risk_engine import RiskEngine

    health_details = {
        "broker": "unknown",
        "websocket": "unknown",
        "db": "unknown",
        "risk": "unknown",
    }

    # 1. Check Broker connection
    try:
        angel_service = get_angel_one_service()
        if angel_service.is_valid_session():
            health_details["broker"] = "ok"
        else:
            health_details["broker"] = "invalid_token"
    except Exception:
        health_details["broker"] = "error"

    # 2. Check WebSocket (receiving ticks)
    try:
        data_manager = get_data_manager()
        ws_health = data_manager.health_status()
        if ws_health["is_connected"] and not ws_health["is_stale"]:
            health_details["websocket"] = "ok"
        elif ws_health["is_connected"] and ws_health["is_stale"]:
            health_details["websocket"] = "stale"
        else:
            health_details["websocket"] = "disconnected"
    except Exception:
        health_details["websocket"] = "error"

    # 3. Check RiskEngine (not blocked)
    try:
        # Create a temporary risk engine to check status
        risk_engine = RiskEngine()
        risk_status = risk_engine.get_risk_status()
        if risk_status["trading_allowed"]:
            health_details["risk"] = "ok"
        else:
            health_details["risk"] = "blocked"
    except Exception:
        health_details["risk"] = "error"

    # 4. Check Database connection
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_details["db"] = "ok"
    except SQLAlchemyError:
        health_details["db"] = "error"
    except Exception:
        health_details["db"] = "error"

    # Determine overall status
    broker_ok = health_details["broker"] == "ok"
    websocket_ok = health_details["websocket"] == "ok"
    db_ok = health_details["db"] == "ok"
    risk_ok = health_details["risk"] == "ok"

    # Critical failures (broker or db) -> down
    if not broker_ok or not db_ok:
        status = "down"
    # Partial failures -> degraded
    elif not websocket_ok or not risk_ok:
        status = "degraded"
    # All good -> healthy
    else:
        status = "healthy"

    return {"status": status, "details": health_details}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)

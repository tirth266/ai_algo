"""
Trading Control API Routes
"""

from fastapi import APIRouter, Request, HTTPException
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/api/trading")

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


@trading_router.post("/start")
async def start_trading(request: Request):
    try:
        logger.info("Web UI requested to start trading...")

        if trading_state["running"]:
            return {
                "success": False,
                "message": "Trading engine already running",
                "status": await get_trading_status(request),
            }

        try:
            from trading.web_trading_controller import WebTradingController

            controller = WebTradingController()
        except ImportError as e:
            raise HTTPException(
                status_code=500, detail=f"Trading controller not found: {str(e)}"
            )

        def run_trading():
            try:
                trading_state["running"] = True
                trading_state["start_time"] = datetime.now().isoformat()
                controller.run_trading_loop()
            except Exception as e:
                logger.error(f"Trading loop error: {str(e)}")
                trading_state["running"] = False
                raise

        trading_state["thread"] = threading.Thread(target=run_trading, daemon=True)
        trading_state["thread"].start()

        status_result = await get_trading_status(request)
        return {
            "success": True,
            "message": "Trading engine started successfully",
            "status": status_result.get("status"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start trading: {str(e)}")
        trading_state["running"] = False
        raise HTTPException(
            status_code=500, detail=f"Failed to start trading: {str(e)}"
        )


@trading_router.post("/stop")
async def stop_trading(request: Request):
    try:
        if not trading_state["running"]:
            return {
                "success": False,
                "message": "Trading engine not running",
                "status": await get_trading_status(request),
            }

        trading_state["running"] = False
        if trading_state["thread"]:
            trading_state["thread"].join(timeout=5.0)

        status_result = await get_trading_status(request)
        return {
            "success": True,
            "message": "Trading engine stopped successfully",
            "status": status_result.get("status"),
        }

    except Exception as e:
        logger.error(f"Failed to stop trading: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop trading: {str(e)}")


@trading_router.get("/status")
async def get_trading_status(request: Request):
    try:
        status = {
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
        return {"success": True, "status": status}
    except Exception as e:
        logger.error(f"Failed to get trading status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


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

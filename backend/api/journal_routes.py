"""
Trade Journal API Routes

Endpoints for logs, analytics, and equity curve data.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

journal_router = APIRouter(prefix="/api/trading")


def get_journal():
    """Get TradeJournal singleton instance."""
    from backend.core.trade_journal import TradeJournal

    return TradeJournal()


@journal_router.get("/logs")
async def get_trade_logs(request: Request):
    """
    Get trade logs with optional filters.

    Query params:
        - limit: Max trades to return (default 100)
        - symbol: Filter by symbol
        - start_date: Filter start date (ISO format)
        - end_date: Filter end date (ISO format)

    Returns:
        JSON with trades array
    """
    try:
        limit = int(request.query_params.get("limit", 100))
        symbol = request.query_params.get("symbol", None)
        start_date = request.query_params.get("start_date", None)
        end_date = request.query_params.get("end_date", None)

        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        journal = get_journal()
        trades = journal.get_trades(
            limit=limit, symbol=symbol, start_date=start, end_date=end
        )

        return {"success": True, "trades": trades, "count": len(trades)}

    except Exception as e:
        logger.error(f"Failed to get trade logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/signals")
async def get_signal_logs(request: Request):
    """
    Get signal logs with optional filters.

    Query params:
        - limit: Max signals to return (default 100)
        - symbol: Filter by symbol
        - executed: Only executed signals (true/false)
        - strategy: Filter by strategy

    Returns:
        JSON with signals array
    """
    try:
        limit = int(request.query_params.get("limit", 100))
        symbol = request.query_params.get("symbol", None)
        executed_only = request.query_params.get("executed", "false").lower() == "true"
        strategy = request.query_params.get("strategy", None)

        journal = get_journal()
        signals = journal.get_signals(
            limit=limit, symbol=symbol, executed_only=executed_only, strategy=strategy
        )

        return {"success": True, "signals": signals, "count": len(signals)}

    except Exception as e:
        logger.error(f"Failed to get signal logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/analytics")
async def get_analytics(request: Request):
    """
    Get performance analytics.

    Returns:
        JSON with performance metrics
    """
    try:
        journal = get_journal()
        analytics = journal.get_full_analytics()

        return {"success": True, "analytics": analytics}

    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/equity-curve")
async def get_equity_curve(request: Request):
    try:
        limit = int(request.query_params.get("limit", 1000))

        journal = get_journal()
        equity_data = journal.get_equity_curve()

        if len(equity_data) > limit:
            equity_data = equity_data[-limit:]

        return {"success": True, "equity_curve": equity_data, "count": len(equity_data)}

    except Exception as e:
        logger.error(f"Failed to get equity curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/strategy-performance")
async def get_strategy_performance(request: Request):
    """
    Get strategy-wise performance breakdown.

    Returns:
        JSON with strategy performance
    """
    try:
        journal = get_journal()
        breakdown = journal.get_strategy_breakdown()

        return {"success": True, "strategies": breakdown}

    except Exception as e:
        logger.error(f"Failed to get strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/daily-summary")
async def get_daily_summary(request: Request):
    try:
        date_str = request.query_params.get("date", None)
        date = datetime.fromisoformat(date_str) if date_str else datetime.now()

        journal = get_journal()
        summary = journal.get_daily_summary(date)

        return {"success": True, "summary": summary}

    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.get("/signal-stats")
async def get_signal_stats(request: Request):
    try:
        journal = get_journal()
        stats = journal.get_signal_statistics()

        return {"success": True, "stats": stats}

    except Exception as e:
        logger.error(f"Failed to get signal stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@journal_router.post("/clear-logs")
async def clear_logs(request: Request):
    try:
        data = await request.json()
        confirm = data.get("confirm", "false").lower()

        if confirm != "true":
            raise HTTPException(status_code=400, detail="Must provide confirm=true to clear logs")

        journal = get_journal()
        journal.trade_logger.clear_logs()
        journal.signal_logger.clear_logs()

        return {"success": True, "message": "All logs cleared"}

    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

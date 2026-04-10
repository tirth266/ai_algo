"""Trade journal API routes implemented with Flask Blueprints."""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.flask_compat import ApiError

logger = logging.getLogger(__name__)

journal_bp = Blueprint("journal", __name__, url_prefix="/api/trading")


def get_journal():
    """Get TradeJournal singleton instance."""
    from backend.core.trade_journal import TradeJournal

    return TradeJournal()


@journal_bp.route("/logs", methods=["GET"])
def get_trade_logs():
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
        limit = int(request.args.get("limit", 100))
        symbol = request.args.get("symbol")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        journal = get_journal()
        trades = journal.get_trades(
            limit=limit, symbol=symbol, start_date=start, end_date=end
        )

        return jsonify({"success": True, "trades": trades, "count": len(trades)})
    except Exception as exc:
        logger.error(f"Failed to get trade logs: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/signals", methods=["GET"])
def get_signal_logs():
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
        limit = int(request.args.get("limit", 100))
        symbol = request.args.get("symbol")
        executed_only = request.args.get("executed", "false").lower() == "true"
        strategy = request.args.get("strategy")

        journal = get_journal()
        signals = journal.get_signals(
            limit=limit, symbol=symbol, executed_only=executed_only, strategy=strategy
        )

        return jsonify({"success": True, "signals": signals, "count": len(signals)})
    except Exception as exc:
        logger.error(f"Failed to get signal logs: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/analytics", methods=["GET"])
def get_analytics():
    """
    Get performance analytics.

    Returns:
        JSON with performance metrics
    """
    try:
        journal = get_journal()
        analytics = journal.get_full_analytics()

        return jsonify({"success": True, "analytics": analytics})
    except Exception as exc:
        logger.error(f"Failed to get analytics: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/equity-curve", methods=["GET"])
def get_equity_curve():
    try:
        limit = int(request.args.get("limit", 1000))

        journal = get_journal()
        equity_data = journal.get_equity_curve()

        if len(equity_data) > limit:
            equity_data = equity_data[-limit:]

        return jsonify(
            {"success": True, "equity_curve": equity_data, "count": len(equity_data)}
        )
    except Exception as exc:
        logger.error(f"Failed to get equity curve: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/strategy-performance", methods=["GET"])
def get_strategy_performance():
    """
    Get strategy-wise performance breakdown.

    Returns:
        JSON with strategy performance
    """
    try:
        journal = get_journal()
        breakdown = journal.get_strategy_breakdown()

        return jsonify({"success": True, "strategies": breakdown})
    except Exception as exc:
        logger.error(f"Failed to get strategy performance: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/daily-summary", methods=["GET"])
def get_daily_summary():
    try:
        date_str = request.args.get("date")
        date = datetime.fromisoformat(date_str) if date_str else datetime.now()

        journal = get_journal()
        summary = journal.get_daily_summary(date)

        return jsonify({"success": True, "summary": summary})
    except Exception as exc:
        logger.error(f"Failed to get daily summary: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/signal-stats", methods=["GET"])
def get_signal_stats():
    try:
        journal = get_journal()
        stats = journal.get_signal_statistics()

        return jsonify({"success": True, "stats": stats})
    except Exception as exc:
        logger.error(f"Failed to get signal stats: {exc}")
        raise ApiError(500, str(exc))


@journal_bp.route("/clear-logs", methods=["POST"])
def clear_logs():
    try:
        data = request.get_json(silent=True) or {}
        confirm = str(data.get("confirm", "false")).lower()

        if confirm != "true":
            raise ApiError(400, "Must provide confirm=true to clear logs")

        journal = get_journal()
        journal.trade_logger.clear_logs()
        journal.signal_logger.clear_logs()

        return jsonify({"success": True, "message": "All logs cleared"})
    except ApiError:
        raise
    except Exception as exc:
        logger.error(f"Failed to clear logs: {exc}")
        raise ApiError(500, str(exc))

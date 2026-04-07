"""
Trade Journal API Routes

Endpoints for logs, analytics, and equity curve data.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

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
        limit = request.args.get("limit", 100, type=int)
        symbol = request.args.get("symbol", None)
        start_date = request.args.get("start_date", None)
        end_date = request.args.get("end_date", None)

        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        journal = get_journal()
        trades = journal.get_trades(
            limit=limit, symbol=symbol, start_date=start, end_date=end
        )

        return jsonify({"success": True, "trades": trades, "count": len(trades)}), 200

    except Exception as e:
        logger.error(f"Failed to get trade logs: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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
        limit = request.args.get("limit", 100, type=int)
        symbol = request.args.get("symbol", None)
        executed_only = request.args.get("executed", "false").lower() == "true"
        strategy = request.args.get("strategy", None)

        journal = get_journal()
        signals = journal.get_signals(
            limit=limit, symbol=symbol, executed_only=executed_only, strategy=strategy
        )

        return jsonify(
            {"success": True, "signals": signals, "count": len(signals)}
        ), 200

    except Exception as e:
        logger.error(f"Failed to get signal logs: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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

        return jsonify({"success": True, "analytics": analytics}), 200

    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@journal_bp.route("/equity-curve", methods=["GET"])
def get_equity_curve():
    """
    Get equity curve data for charting.

    Query params:
        - limit: Max points to return

    Returns:
        JSON with equity curve array
    """
    try:
        limit = request.args.get("limit", 1000, type=int)

        journal = get_journal()
        equity_data = journal.get_equity_curve()

        if len(equity_data) > limit:
            equity_data = equity_data[-limit:]

        return jsonify(
            {"success": True, "equity_curve": equity_data, "count": len(equity_data)}
        ), 200

    except Exception as e:
        logger.error(f"Failed to get equity curve: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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

        return jsonify({"success": True, "strategies": breakdown}), 200

    except Exception as e:
        logger.error(f"Failed to get strategy performance: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@journal_bp.route("/daily-summary", methods=["GET"])
def get_daily_summary():
    """
    Get daily trading summary.

    Query params:
        - date: Date for summary (ISO format, default today)

    Returns:
        JSON with daily summary
    """
    try:
        date_str = request.args.get("date", None)
        date = datetime.fromisoformat(date_str) if date_str else datetime.now()

        journal = get_journal()
        summary = journal.get_daily_summary(date)

        return jsonify({"success": True, "summary": summary}), 200

    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@journal_bp.route("/signal-stats", methods=["GET"])
def get_signal_stats():
    """
    Get signal execution statistics.

    Returns:
        JSON with signal stats
    """
    try:
        journal = get_journal()
        stats = journal.get_signal_statistics()

        return jsonify({"success": True, "stats": stats}), 200

    except Exception as e:
        logger.error(f"Failed to get signal stats: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@journal_bp.route("/clear-logs", methods=["POST"])
def clear_logs():
    """
    Clear all logs (requires confirmation).

    Body:
        - confirm: Must be 'true'

    Returns:
        JSON with result
    """
    try:
        confirm = request.json.get("confirm", "false").lower()

        if confirm != "true":
            return jsonify(
                {"success": False, "message": "Must provide confirm=true to clear logs"}
            ), 400

        journal = get_journal()
        journal.trade_logger.clear_logs()
        journal.signal_logger.clear_logs()

        return jsonify({"success": True, "message": "All logs cleared"}), 200

    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

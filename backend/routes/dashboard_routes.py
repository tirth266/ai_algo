"""
Dashboard Routes - Real-time Zerodha Account Data

Provides live account information, positions, orders, and P&L from Zerodha Kite Connect.
Converted from Flask Blueprint to FastAPI APIRouter.
"""

from fastapi import APIRouter, Request
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

dashboard_bp = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# In-memory cache (2 seconds)
_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 2,  # Cache TTL in seconds
}


def get_zerodha_dashboard_data() -> Optional[Dict[str, Any]]:
    """
    Fetch live data from Zerodha Kite Connect API.

    Returns:
        Dictionary with account data or None if not connected
    """
    try:
        logger.info("Starting dashboard data fetch...")

        from trading.zerodha_auth_web import get_zerodha_auth_web

        auth = get_zerodha_auth_web()

        session_data = auth.session_data
        if not session_data:
            logger.warning("No session data available")
            return None

        logger.info(f"Session found for user: {session_data.get('user_id')}")

        try:
            from kiteconnect import KiteConnect

            kite = KiteConnect(api_key=auth.api_key)
            kite.set_access_token(session_data["access_token"])
            logger.info("Kite instance created successfully")
        except Exception as e:
            logger.error(f"Failed to create Kite instance: {e}")
            return None

        try:
            profile = kite.profile()
            logger.info(f"Profile retrieved: {profile.get('user_id')}")
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            return None

        margins = kite.margins(product="equity")
        available_margin = margins.get("available", {}).get("net_debit", 0)
        total_margin = margins.get("net", 0)
        used_margin = total_margin - available_margin

        positions = kite.positions()
        net_positions = positions.get("net", [])
        open_positions = len([p for p in net_positions if abs(p.get("qty", 0)) > 0])
        today_pnl = sum(p.get("pnl", 0) for p in net_positions)

        orders = kite.orders()
        today_orders = [
            o
            for o in orders
            if o.get("order_timestamp", "")[:10] == datetime.now().strftime("%Y-%m-%d")
        ]
        total_orders = len(today_orders)

        holdings = kite.holdings()
        holdings_count = len(holdings) if holdings else 0

        user_id = profile.get("user_id", "")
        user_name = profile.get("user_name", "")

        dashboard_data = {
            "account_balance": total_margin,
            "available_margin": available_margin,
            "used_margin": used_margin,
            "today_pnl": round(today_pnl, 2),
            "total_orders": total_orders,
            "open_positions": open_positions,
            "holdings_count": holdings_count,
            "broker_status": "connected",
            "user_id": user_id,
            "user_name": user_name,
            "fetched_at": datetime.now().isoformat(),
        }

        logger.info(
            f"Dashboard data fetched successfully: Balance={total_margin}, PnL={today_pnl}"
        )
        return dashboard_data

    except ImportError as e:
        logger.error(f"Auth module import failed: {e}")
        return None

    except Exception as e:
        logger.error(f"Failed to fetch dashboard data: {str(e)}")
        return None


def get_cached_dashboard_data() -> Dict[str, Any]:
    """
    Get dashboard data with 2-second caching.
    """
    now = datetime.now()

    if _cache["data"] and _cache["timestamp"]:
        age = (now - _cache["timestamp"]).total_seconds()
        if age < _cache["ttl"]:
            logger.debug(f"Returning cached dashboard data (age: {age:.1f}s)")
            return _cache["data"]

    logger.info("Cache expired, fetching fresh data from Zerodha")
    fresh_data = get_zerodha_dashboard_data()

    if fresh_data:
        _cache["data"] = fresh_data
        _cache["timestamp"] = now
        return fresh_data
    else:
        return {
            "account_balance": 0,
            "available_margin": 0,
            "used_margin": 0,
            "today_pnl": 0,
            "total_orders": 0,
            "open_positions": 0,
            "holdings_count": 0,
            "broker_status": "disconnected",
            "user_id": "",
            "user_name": "",
            "fetched_at": now.isoformat(),
            "error": "Failed to fetch data from Zerodha",
        }


@dashboard_bp.get("")
async def get_dashboard(request: Request):
    """
    Get real-time dashboard data.

    Returns:
        JSON with account balance, margin, positions, orders, and P&L
    """
    try:
        logger.info("Dashboard API called")
        dashboard_data = get_cached_dashboard_data()
        return {"success": True, "data": dashboard_data}

    except Exception as e:
        logger.error(f"Dashboard endpoint error: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch dashboard data: {str(e)}",
            "data": {"broker_status": "disconnected", "error": str(e)},
        }

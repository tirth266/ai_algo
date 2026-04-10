from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
from typing import Dict, Any

from config import settings

logger = logging.getLogger(__name__)

broker_router = APIRouter(prefix="/api/broker", tags=["broker"])

@broker_router.get("/status")
async def broker_status():
    """
    Check current broker status with safeguards.
    No 500 should ever be raised from here.
    """
    try:
        # Check if Angel One is configured
        if not settings.ANGEL_ONE_API_KEY or not settings.ANGEL_ONE_CLIENT_ID:
            return {
                "success": True,
                "connected": False,
                "broker": "not_configured",
                "message": "Angel One credentials missing in environment"
            }

        try:
            from services.angelone_service import get_angel_one_service
            service = get_angel_one_service()
            status = service.get_status()
            
            return {
                "success": True,
                "connected": status.get("authenticated", False),
                "broker": "AngelOne",
                "details": {
                    "authenticated": status.get("authenticated", False),
                    "client_id": status.get("client_id"),
                    "user_name": status.get("user_profile", {}).get("name") if status.get("user_profile") else None
                }
            }
        except Exception as inner_exc:
            logger.error(f"Error communicating with Angel One service: {inner_exc}")
            return {
                "success": False,
                "connected": False,
                "broker": "error",
                "message": "Broker service internal error",
                "details": str(inner_exc)
            }

    except Exception as exc:
        logger.error(f"Critical error in /status endpoint: {exc}")
        return JSONResponse(
            status_code=200, # Still return 200 to satisfy safeguard requirement
            content={
                "success": False,
                "status": "error",
                "message": "Safeguard triggered",
                "details": str(exc)
            }
        )

@broker_router.get("/profile")
async def broker_profile():
    """Returns 401 if not authenticated, as expected."""
    try:
        from services.angelone_service import get_angel_one_service
        service = get_angel_one_service()
        
        if not service.token_manager.is_authenticated():
            return JSONResponse(status_code=401, content={"status": "error", "message": "Session expired, please re-login."})

        profile = service.get_profile()
        if profile.get("success"):
            return {
                "status": "success",
                "data": profile["data"]
            }
        
        return JSONResponse(status_code=400, content={"status": "error", "message": profile.get("message", "Profile fetch failed")})

    except Exception as exc:
        logger.error(f"Profile error: {exc}")
        return JSONResponse(status_code=401, content={"status": "error", "message": "Session authentication failed"})

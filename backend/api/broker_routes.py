"""
Broker Authentication API Routes
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import logging

logger = logging.getLogger(__name__)

broker_router = APIRouter(prefix="/api/broker")

@broker_router.get("/login")
async def broker_login(request: Request):
    try:
        from backend.trading.zerodha_auth_web import get_zerodha_auth_web
        auth = get_zerodha_auth_web()
        login_url = auth.generate_login_url()
        return RedirectResponse(login_url)
    except Exception as e:
        logger.error(f"Failed to generate login URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@broker_router.get("/callback")
async def broker_callback(request: Request):
    try:
        request_token = request.query_params.get("request_token")
        status = request.query_params.get("status", "success")

        if status == "error" or not request_token:
            return RedirectResponse("http://localhost:3000/broker?status=error&message=Authentication_failed")

        from backend.trading.zerodha_auth_web import get_zerodha_auth_web
        auth = get_zerodha_auth_web()
        result = auth.handle_callback(request_token)

        return RedirectResponse(
            f"http://localhost:3000/broker?status=success&user_id={result['user_id']}&user_name={result['user_name']}"
        )
    except Exception as e:
        logger.error(f"Callback handling failed: {str(e)}")
        return RedirectResponse(f"http://localhost:3000/broker?status=error&message={str(e)}")

@broker_router.get("/status")
async def broker_status(request: Request):
    try:
        from backend.trading.zerodha_auth_web import get_zerodha_auth_web
        auth = get_zerodha_auth_web()
        connected = auth.is_connected()

        if connected:
            session_info = auth.get_session_info()
            return {
                "success": True,
                "connected": True,
                "broker": "Zerodha",
                "user_id": session_info.get("user_id"),
                "user_name": session_info.get("user_name"),
                "email": session_info.get("email"),
                "login_time": session_info.get("login_time"),
                "expiry_date": session_info.get("expiry_date")
            }
        else:
            return {
                "success": True,
                "connected": False,
                "broker": None,
                "message": "Not connected to any broker"
            }
    except Exception as e:
        logger.error(f"Failed to check broker status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@broker_router.post("/logout")
async def broker_logout(request: Request):
    try:
        from backend.trading.zerodha_auth_web import get_zerodha_auth_web
        auth = get_zerodha_auth_web()
        auth.logout()
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@broker_router.get("/info")
async def broker_info(request: Request):
    try:
        from backend.trading.zerodha_auth_web import get_zerodha_auth_web
        auth = get_zerodha_auth_web()
        session_info = auth.get_session_info()

        if session_info:
            return {
                "success": True,
                "connected": True,
                "broker": "Zerodha",
                "session": session_info
            }
        else:
            return {
                "success": True,
                "connected": False,
                "broker": None,
                "session": None
            }
    except Exception as e:
        logger.error(f"Failed to get broker info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@broker_router.get("/profile")
async def broker_profile(request: Request):
    try:
        kite = None
        try:
            from backend.trading.zerodha_auth_web import get_zerodha_auth_web
            auth = get_zerodha_auth_web()
            if auth.is_connected():
                kite = auth.get_kite_client()
        except:
            pass

        if kite is None:
            try:
                from backend.trading.zerodha_auth_manager import get_kite_client
                kite = get_kite_client(auto_renew=False)
            except:
                pass

        if kite is None:
            raise HTTPException(status_code=401, detail="Session expired, please re-login.")

        margins = kite.margins()
        profile = kite.profile()
        equity = margins.get("equity", {})
        commodity = margins.get("commodity", {})

        from datetime import datetime
        return {
            "status": "success",
            "data": {
                "user_id": profile.get("user_id"),
                "user_name": profile.get("user_name"),
                "email": profile.get("email", ""),
                "broker": profile.get("broker", "ZERODHA"),
                "equity": {
                    "available_cash": equity.get("available", {}).get("cash", 0),
                    "available_margin": equity.get("available", {}).get("live_balance", 0),
                    "used_margin": equity.get("utilised", {}).get("debits", 0),
                    "net": equity.get("net", 0),
                },
                "commodity": {
                    "available_cash": commodity.get("available", {}).get("cash", 0),
                    "available_margin": commodity.get("available", {}).get("live_balance", 0),
                    "used_margin": commodity.get("utilised", {}).get("debits", 0),
                    "net": commodity.get("net", 0),
                },
                "timestamp": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Broker profile fetch failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Session expired, please re-login.")

"""
Angel One API Routes
"""
from fastapi import APIRouter, Request, HTTPException
import logging
import os
from backend.services.angelone_service import get_angel_one_service

logger = logging.getLogger(__name__)

angel_router = APIRouter(prefix="/api/angel")

def get_service():
    return get_angel_one_service()

@angel_router.post("/login")
async def angel_login(request: Request):
    try:
        data = await request.json()
        totp = data.get("totp")
        if not totp:
            raise HTTPException(status_code=400, detail="Missing required field: totp")

        service = get_service()
        client_code = os.getenv("ANGEL_ONE_CLIENT_ID")
        password = os.getenv("ANGEL_ONE_PASSWORD")

        if not client_code or not password:
            raise HTTPException(status_code=500, detail="Server configuration missing. Contact admin.")

        result = service.login(client_code, password, totp)
        if result.get("success"):
            return {
                "status": "success",
                "message": "Login successful",
                "data": {"connected": True},
            }
        else:
            raise HTTPException(status_code=401, detail=result.get("message", "Login failed"))

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@angel_router.post("/auto-login")
async def angel_auto_login(request: Request):
    try:
        service = get_service()
        result = service.auto_login()

        if result.get("success"):
            return {
                "status": "success",
                "message": "Auto-login successful",
                "data": {
                    "jwt_token": result["data"].get("jwt_token"),
                    "feed_token": result["data"].get("feed_token"),
                },
            }
        else:
            raise HTTPException(status_code=401, detail=result.get("message", "Auto-login failed"))

    except Exception as e:
        logger.error(f"Auto-login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@angel_router.get("/profile")
async def angel_profile(request: Request):
    try:
        service = get_service()
        if not service.is_authenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")

        result = service.get_profile()
        if result.get("success"):
            return {
                "status": "success",
                "message": "Profile retrieved",
                "data": result["data"],
            }
        else:
             raise HTTPException(status_code=400, detail=result.get("message", "Failed to get profile"))

    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@angel_router.get("/status")
async def angel_status(request: Request):
    try:
        service = get_service()
        status = service.get_status()

        return {
            "status": "success",
            "data": {
                "authenticated": status.get("authenticated", False),
                "api_key_set": status.get("api_key_set", False),
                "client_id": status.get("client_id"),
                "user_name": status.get("user_profile", {}).get("name") if status.get("user_profile") else None,
            },
        }
    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@angel_router.post("/logout")
async def angel_logout(request: Request):
    try:
        service = get_service()
        service.logout()
        return {"status": "success", "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

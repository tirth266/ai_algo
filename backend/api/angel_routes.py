from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
import logging
import os
from typing import Optional

from services.angelone_service import get_angel_one_service

logger = logging.getLogger(__name__)

angel_router = APIRouter(prefix="/api/angel", tags=["angel"])

@angel_router.post("/login")
async def angel_login(totp: str = Body(..., embed=True)):
    try:
        service = get_angel_one_service()
        # MPIN/Password should come from settings/env for auto-login or manual
        client_code = os.getenv("ANGEL_ONE_CLIENT_ID")
        password = os.getenv("ANGEL_ONE_MPIN") or os.getenv("ANGEL_ONE_PASSWORD")

        if not client_code or not password:
            return JSONResponse(status_code=500, content={"status": "error", "message": "Server configuration missing."})

        result = service.login(client_code, password, totp)
        if result.get("success"):
            return {
                "status": "success",
                "message": "Login successful",
                "data": {"connected": True, "tokens": result.get("data")}
            }

        return JSONResponse(status_code=401, content={"status": "error", "message": result.get("message", "Login failed")})

    except Exception as exc:
        logger.error(f"Angel login error: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

@angel_router.post("/auto-login")
async def angel_auto_login():
    try:
        service = get_angel_one_service()
        result = service.auto_login()

        if result.get("success"):
            return {
                "status": "success",
                "message": "Auto-login successful",
                "data": result.get("data")
            }

        return JSONResponse(status_code=401, content={"status": "error", "message": result.get("message", "Auto-login failed")})
    except Exception as exc:
        logger.error(f"Auto-login error: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

@angel_router.get("/status")
async def angel_status():
    try:
        service = get_angel_one_service()
        status = service.get_status()
        return {
            "status": "success",
            "data": {
                "authenticated": status.get("authenticated", False),
                "api_key_set": status.get("api_key_set", False),
                "client_id": status.get("client_id"),
                "user_name": status.get("user_profile", {}).get("name") if status.get("user_profile") else None
            }
        }
    except Exception as exc:
        logger.error(f"Angel status error: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})

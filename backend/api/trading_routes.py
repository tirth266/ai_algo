from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

trading_router = APIRouter(prefix="/api/trading", tags=["trading"])

@trading_router.get("/status")
async def get_trading_status():
    return {"status": "success", "is_running": True}

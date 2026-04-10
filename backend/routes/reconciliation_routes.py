from fastapi import APIRouter, HTTPException
import logging
from typing import Dict, Any

from core.execution import TradingSystem

logger = logging.getLogger(__name__)

reconciliation_router = APIRouter(prefix="/api/reconcile", tags=["reconciliation"])

@reconciliation_router.post("")
async def trigger_reconciliation():
    try:
        # Get global trading system and trigger reconciliation
        # Note: In real app, you'd use a dependency or manager
        system = TradingSystem()
        report = system.reconcile_with_broker()
        return report
    except Exception as exc:
        logger.error(f"Reconciliation trigger failed: {exc}")
        return {"status": "error", "message": str(exc)}

@reconciliation_router.get("/status")
async def get_reconciliation_status():
    try:
        system = TradingSystem()
        return system.reconciliation_status
    except Exception as exc:
        logger.error(f"Status check failed: {exc}")
        return {"status": "error", "message": str(exc)}

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

journal_router = APIRouter(prefix="/api/journal", tags=["journal"])

@journal_router.get("")
async def get_journal():
    return {"status": "success", "data": []}

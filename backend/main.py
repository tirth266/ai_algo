import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add the backend directory to sys.path
backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from flask_cors import CORS

# Load env before config is imported
load_dotenv()

from config import settings
from utils.logger import setup_logging

setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title="Angel One Algo Trading (FastAPI)")

# Apply Flask-CORS fallback as requested, with wildcard fallback
try:
    CORS(app, origins="*")
except Exception as e:
    # If Flask-CORS cannot wrap this app, fallback to FastAPI CORS middleware
    logging.warning(f"Flask-CORS not applied: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-algo-ul1l.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Robust Exception Handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error at {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal Server Error",
            "details": str(exc)
        }
    )

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting FastAPI Trading System...")
    logger.info("✓ Database initialization skipped for zero-external-services mode")

    # Lazy data manager start if configured
    try:
        from services.market_data import start_data_manager
        if start_data_manager():
            logger.info("✓ Market data streaming started")
    except Exception as e:
        logger.warning(f"⚠️ Market data manager could not start (likely missing credentials): {e}")

# Health Endpoint
@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "database": "disabled",
        "redis": "disabled",
        "env": "loaded"
    }

# Import and include routers
from api.broker_routes import broker_router
from api.angel_routes import angel_router
from api.journal_routes import journal_router
from api.trading_routes import trading_router
from routes.reconciliation_routes import reconciliation_router

app.include_router(broker_router)
app.include_router(angel_router)
app.include_router(journal_router)
app.include_router(trading_router)
app.include_router(reconciliation_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

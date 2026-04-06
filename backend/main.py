from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import logging
import uuid
from sqlalchemy.orm import Session

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

from backend.utils.symbol_manager import SymbolManager
from backend.auth_manager import global_smart_session
from backend.services.market_data import global_price_store
from backend.database.models import SessionLocal, Trade, init_db

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="Angel One Algo Trading API")
symbol_manager = SymbolManager()

# Init DB on startup
@app.on_event("startup")
def on_startup():
    init_db()

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class OrderRequest(BaseModel):
    symbol: str  # e.g., 'SBIN-EQ'
    quantity: int
    price: float = 0.0  # Required > 0 for LIMIT
    transaction_type: str  # 'BUY' or 'SELL'
    exchange: str = 'NSE'
    order_type: str = 'LIMIT'  # Defualt to LIMIT per 2026 rules
    product_type: str = 'INTRADAY'

class ConnectRequest(BaseModel):
    auth_token: str = None

@app.post("/api/auth/connect")
def connect_angel_one(req: ConnectRequest = None):
    if req and req.auth_token:
        success = global_smart_session.finalize_from_callback(req.auth_token)
    else:
        success = global_smart_session.login()
        
    if success:
        return {"status": "Success", "message": "Angel One session active."}
    else:
        raise HTTPException(status_code=401, detail="Angel One authentication failed.")

@app.get("/api/auth/status")
def check_auth_status():
    return {"status": "Success", "is_authenticated": global_smart_session.is_valid_session()}

@app.get("/api/prices")
def get_prices():
    return global_price_store.get_all_prices()

@app.post("/place-order")
async def place_order_endpoint(order: OrderRequest, db: Session = Depends(get_db)):
    logger.info(f"Received order request: {order}")
    
    # Resolve symbol to token
    token, lot_size = symbol_manager.get_token(order.symbol, order.exchange)
    
    if not token:
        logger.error(f"Failed to find token for symbol: {order.symbol}")
        raise HTTPException(status_code=400, detail=f"Invalid symbol or token not found for {order.symbol}")
        
    logger.info(f"Resolved {order.symbol} to token: {token}")

    # Enforce 2026 Limits
    if order.order_type.upper() == "MARKET":
        logger.warning("Intercepted MARKET order. Enforcing LIMIT due to 2026 NSE Algo restrictions.")
        order.order_type = "LIMIT"

    if order.order_type.upper() == "LIMIT" and order.price <= 0:
        raise HTTPException(status_code=400, detail="LIMIT orders require a specified price > 0.")

    # Price Validation against LTP
    ltp = global_price_store.get_price(token)
    if ltp is not None and order.price > 0:
        difference = abs(order.price - ltp) / ltp
        if difference > 0.05:
            # Drop the order if price is more than 5% away
            logger.warning(f"Price validation failed: Order price {order.price} is >5% away from LTP {ltp}")
            raise HTTPException(
                status_code=400, 
                detail=f"Safety Check Failed: Order price {order.price} is more than 5% away from LTP {ltp} ({difference*100:.2f}% disparity)."
            )

    try:
        # Example Simulated Order Execution
        order_id = str(uuid.uuid4())
        response = {
            "status": True, 
            "message": "Order placed successfully (Simulated)", 
            "data": {"orderid": order_id, "token": token}
        }
        
        if response.get('status'):
            # Save the successful trade to SQLite
            new_trade = Trade(
                order_id=order_id,
                symbol=order.symbol,
                qty=order.quantity,
                price=order.price if order.price > 0 else (ltp or 0.0),
                status="COMPLETED"
            )
            db.add(new_trade)
            db.commit()

            return {"status": "success", "order_id": order_id, "token_used": token, "ltp_reference": ltp}
        else:
            raise HTTPException(status_code=400, detail=response.get('message', 'Order placement failed'))
            
    except Exception as e:
        logger.error(f"Order error: {e}")
        # Common Angel One error handling e.g., Token Expired
        if "Token Expired" in str(e) or "AB1004" in str(e):
            raise HTTPException(status_code=401, detail="Session expired. Please relogin to Angel One.")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Angel One Algo Trading Support API Running"}

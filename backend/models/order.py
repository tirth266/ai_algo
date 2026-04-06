"""
Order Database Model

Represents a trading order in the database.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from models.base import Base


class OrderStatus(enum.Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(enum.Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_MARKET = "stop_loss_market"


class Order(Base):
    """
    Order model for storing trading orders.
    
    Table: orders
    
    Fields:
        id: Primary key
        symbol: Stock symbol (e.g., 'RELIANCE')
        side: Buy or Sell
        quantity: Number of shares
        price: Order price
        status: Order status (pending, filled, cancelled, etc.)
        order_type: Type of order (market, limit, etc.)
        broker_order_id: Order ID from broker (Zerodha)
        strategy_name: Name of strategy that generated the order
        created_at: Timestamp when order was created
        updated_at: Timestamp when order was last updated
    """
    
    __tablename__ = 'orders'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Order details
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # 'BUY' or 'SELL'
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    
    # Order status and type
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    order_type = Column(Enum(OrderType), default=OrderType.MARKET, nullable=False)
    
    # Broker information
    broker_order_id = Column(String(100), unique=True, index=True)
    exchange = Column(String(20), default='NSE')
    
    # Strategy information
    strategy_name = Column(String(100), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert order to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'status': self.status.value,
            'order_type': self.order_type.value,
            'broker_order_id': self.broker_order_id,
            'exchange': self.exchange,
            'strategy_name': self.strategy_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<Order(id={self.id}, symbol='{self.symbol}', side='{self.side}', quantity={self.quantity}, status='{self.status.value}')>"

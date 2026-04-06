"""
Trade Database Model

Represents an executed trade in the database.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from models.base import Base


class Trade(Base):
    """
    Trade model for storing executed trades.
    
    Table: trades
    
    Fields:
        id: Primary key
        order_id: Foreign key to orders table
        symbol: Stock symbol
        side: Buy or Sell
        quantity: Number of shares traded
        entry_price: Average entry price
        exit_price: Average exit price (if closed)
        pnl: Profit/Loss (if closed)
        pnl_percentage: PnL as percentage
        status: Trade status (open, closed)
        exit_reason: Reason for exiting trade
        created_at: Entry timestamp
        exited_at: Exit timestamp
    """
    
    __tablename__ = 'trades'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to orders
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, index=True)
    
    # Trade details
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # 'BUY' or 'SELL'
    quantity = Column(Integer, nullable=False)
    
    # Prices
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    
    # Profit/Loss
    pnl = Column(Float, default=0.0)
    pnl_percentage = Column(Float, default=0.0)
    
    # Trade status
    status = Column(String(20), default='open', nullable=False, index=True)  # 'open' or 'closed'
    exit_reason = Column(String(200), nullable=True)
    
    # Strategy information
    strategy_name = Column(String(100), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    exited_at = Column(DateTime, nullable=True)
    
    # Relationships
    order = relationship("Order", back_populates="trades")
    
    def to_dict(self):
        """Convert trade to dictionary."""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'pnl_percentage': self.pnl_percentage,
            'status': self.status,
            'exit_reason': self.exit_reason,
            'strategy_name': self.strategy_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'exited_at': self.exited_at.isoformat() if self.exited_at else None
        }
    
    def calculate_pnl(self, current_price: float):
        """
        Calculate unrealized PnL based on current price.
        
        Args:
            current_price: Current market price
        """
        if self.side == 'BUY':
            self.pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - current_price) * self.quantity
        
        self.pnl_percentage = (self.pnl / self.entry_price) * 100 if self.entry_price > 0 else 0
    
    def close(self, exit_price: float, reason: str = None):
        """
        Close the trade.
        
        Args:
            exit_price: Exit price
            reason: Reason for closing
        """
        self.exit_price = exit_price
        self.status = 'closed'
        self.exit_reason = reason
        self.exited_at = datetime.utcnow()
        
        # Calculate final PnL
        if self.side == 'BUY':
            self.pnl = (exit_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
        
        self.pnl_percentage = (self.pnl / self.entry_price) * 100 if self.entry_price > 0 else 0
    
    def __repr__(self):
        return f"<Trade(id={self.id}, symbol='{self.symbol}', side='{self.side}', quantity={self.quantity}, pnl={self.pnl:.2f})>"

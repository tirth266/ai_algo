"""
Position Database Model

Represents an open trading position in the database.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

from models.base import Base


class Position(Base):
    """
    Position model for storing open positions.
    
    Table: positions
    
    Fields:
        id: Primary key
        symbol: Stock symbol
        side: Long or Short
        quantity: Number of shares held
        average_price: Average entry price
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss from partial exits
        created_at: Position opened timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = 'positions'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Position details
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # 'LONG' or 'SHORT'
    quantity = Column(Integer, nullable=False, default=0)
    
    # Prices
    average_price = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=True)
    
    # Profit/Loss
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percentage = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    
    # Risk management
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    
    # Strategy information
    strategy_name = Column(String(100), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert position to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'average_price': self.average_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_percentage': self.unrealized_pnl_percentage,
            'realized_pnl': self.realized_pnl,
            'stop_loss': self.stop_loss,
            'target': self.target,
            'strategy_name': self.strategy_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_pnl(self, current_price: float):
        """
        Update unrealized PnL based on current price.
        
        Args:
            current_price: Current market price
        """
        self.current_price = current_price
        
        if self.quantity > 0:
            if self.side == 'LONG':
                self.unrealized_pnl = (current_price - self.average_price) * self.quantity
            else:
                self.unrealized_pnl = (self.average_price - current_price) * self.quantity
            
            self.unrealized_pnl_percentage = (
                (self.unrealized_pnl / self.average_price) * 100 
                if self.average_price > 0 else 0
            )
    
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.quantity > 0
    
    def close(self):
        """Close the position."""
        self.quantity = 0
        self.unrealized_pnl = 0
        self.unrealized_pnl_percentage = 0
    
    def __repr__(self):
        return f"<Position(id={self.id}, symbol='{self.symbol}', side='{self.side}', quantity={self.quantity}, pnl={self.unrealized_pnl:.2f})>"

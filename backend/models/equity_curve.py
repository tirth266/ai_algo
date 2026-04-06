"""
Equity Curve Database Model

Tracks portfolio equity over time.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

from models.base import Base


class EquityCurve(Base):
    """
    Equity curve model for tracking portfolio performance.
    
    Table: equity_curve
    
    Fields:
        id: Primary key
        date: Date/time of equity snapshot
        equity: Total portfolio equity
        cash: Available cash
        invested: Amount invested in positions
        drawdown: Absolute drawdown from peak
        drawdown_percentage: Drawdown as percentage
        daily_pnl: PnL for the day
        cumulative_pnl: Cumulative PnL
        created_at: Creation timestamp
    """
    
    __tablename__ = 'equity_curve'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Date
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Portfolio values
    equity = Column(Float, nullable=False, default=0.0)
    cash = Column(Float, default=0.0)
    invested = Column(Float, default=0.0)
    
    # Drawdown tracking
    peak_equity = Column(Float, default=0.0)
    drawdown = Column(Float, default=0.0)
    drawdown_percentage = Column(Float, default=0.0)
    
    # PnL tracking
    daily_pnl = Column(Float, default=0.0)
    cumulative_pnl = Column(Float, default=0.0)
    
    # Returns
    daily_return = Column(Float, default=0.0)
    cumulative_return = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert equity curve point to dictionary."""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'equity': self.equity,
            'cash': self.cash,
            'invested': self.invested,
            'drawdown': self.drawdown,
            'drawdown_percentage': self.drawdown_percentage,
            'daily_pnl': self.daily_pnl,
            'cumulative_pnl': self.cumulative_pnl,
            'daily_return': self.daily_return,
            'cumulative_return': self.cumulative_return,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def update_drawdown(self):
        """Update drawdown based on current equity and peak."""
        if self.peak_equity > 0:
            self.drawdown = self.peak_equity - self.equity
            self.drawdown_percentage = (self.drawdown / self.peak_equity) * 100
        else:
            self.peak_equity = self.equity
            self.drawdown = 0
            self.drawdown_percentage = 0
        
        # Update peak if current equity is higher
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            self.drawdown = 0
            self.drawdown_percentage = 0
    
    def calculate_returns(self, initial_capital: float):
        """
        Calculate returns based on initial capital.
        
        Args:
            initial_capital: Initial portfolio capital
        """
        if initial_capital > 0:
            self.cumulative_return = ((self.equity - initial_capital) / initial_capital) * 100
    
    def __repr__(self):
        return f"<EquityCurve(id={self.id}, date={self.date}, equity={self.equity:.2f}, drawdown={self.drawdown_percentage:.2f}%)>"

"""
Strategy Run Database Model

Logs strategy execution runs and results.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime

from models.base import Base


class StrategyRun(Base):
    """
    Strategy run model for logging strategy executions.
    
    Table: strategy_runs
    
    Fields:
        id: Primary key
        strategy_name: Name of the strategy
        run_date: Date of execution
        status: Run status (running, completed, failed)
        total_trades: Total trades executed
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        total_pnl: Total profit/loss
        win_rate: Win percentage
        max_drawdown: Maximum drawdown during run
        parameters: Strategy parameters used (JSON string)
        notes: Additional notes/comments
        created_at: Creation timestamp
        completed_at: Completion timestamp
    """
    
    __tablename__ = 'strategy_runs'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Strategy information
    strategy_name = Column(String(100), nullable=False, index=True)
    run_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Status
    status = Column(String(20), default='running', nullable=False, index=True)
    
    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    
    # Risk metrics
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_percentage = Column(Float, default=0.0)
    
    # Parameters and notes
    parameters = Column(Text, nullable=True)  # JSON string of parameters
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert strategy run to dictionary."""
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'run_date': self.run_date.isoformat() if self.run_date else None,
            'status': self.status,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl,
            'win_rate': self.win_rate,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_percentage': self.max_drawdown_percentage,
            'parameters': self.parameters,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def calculate_win_rate(self):
        """Calculate win rate from trade counts."""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
        else:
            self.win_rate = 0.0
    
    def complete(self):
        """Mark strategy run as completed."""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.calculate_win_rate()
    
    def fail(self, error_message: str = None):
        """Mark strategy run as failed."""
        self.status = 'failed'
        self.completed_at = datetime.utcnow()
        if error_message:
            self.notes = f"Error: {error_message}"
    
    def __repr__(self):
        return f"<StrategyRun(id={self.id}, strategy='{self.strategy_name}', status='{self.status}', pnl={self.total_pnl:.2f})>"

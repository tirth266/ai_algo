"""
Strategy Repository

Database operations for StrategyRun model.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.strategy_run import StrategyRun


class StrategyRepository:
    """
    Repository for strategy run database operations.
    
    Provides CRUD operations and queries for strategy runs.
    """
    
    def __init__(self, session: Session):
        """
        Initialize strategy repository.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def log_strategy_run(
        self,
        strategy_name: str,
        parameters: str = None,
        notes: str = None
    ) -> StrategyRun:
        """
        Log a new strategy run.
        
        Args:
            strategy_name: Name of strategy
            parameters: Strategy parameters (JSON string)
            notes: Additional notes
        
        Returns:
            Created StrategyRun instance
        """
        strategy_run = StrategyRun(
            strategy_name=strategy_name,
            run_date=datetime.utcnow(),
            status='running',
            parameters=parameters,
            notes=notes
        )
        
        self.session.add(strategy_run)
        self.session.commit()
        self.session.refresh(strategy_run)
        
        return strategy_run
    
    def get_strategy_run(self, run_id: int) -> Optional[StrategyRun]:
        """
        Get strategy run by ID.
        
        Args:
            run_id: Strategy run ID
        
        Returns:
            StrategyRun instance or None
        """
        return self.session.query(StrategyRun).filter(
            StrategyRun.id == run_id
        ).first()
    
    def get_strategy_runs(
        self,
        strategy_name: str = None,
        status: str = None,
        limit: int = 50
    ) -> List[StrategyRun]:
        """
        Get strategy runs with optional filters.
        
        Args:
            strategy_name: Filter by strategy name
            status: Filter by status
            limit: Maximum number of runs to return
        
        Returns:
            List of StrategyRun instances
        """
        query = self.session.query(StrategyRun)
        
        if strategy_name:
            query = query.filter(StrategyRun.strategy_name == strategy_name)
        
        if status:
            query = query.filter(StrategyRun.status == status)
        
        query = query.order_by(desc(StrategyRun.run_date)).limit(limit)
        
        return query.all()
    
    def complete_strategy_run(
        self,
        run_id: int,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        total_pnl: float,
        max_drawdown: float = 0.0
    ) -> Optional[StrategyRun]:
        """
        Mark strategy run as completed with performance metrics.
        
        Args:
            run_id: Strategy run ID
            total_trades: Total trades executed
            winning_trades: Number of winning trades
            losing_trades: Number of losing trades
            total_pnl: Total profit/loss
            max_drawdown: Maximum drawdown
        
        Returns:
            Updated StrategyRun instance or None
        """
        strategy_run = self.get_strategy_run(run_id)
        
        if strategy_run:
            strategy_run.total_trades = total_trades
            strategy_run.winning_trades = winning_trades
            strategy_run.losing_trades = losing_trades
            strategy_run.total_pnl = total_pnl
            strategy_run.max_drawdown = max_drawdown
            strategy_run.complete()
            
            self.session.commit()
            self.session.refresh(strategy_run)
        
        return strategy_run
    
    def fail_strategy_run(
        self,
        run_id: int,
        error_message: str = None
    ) -> Optional[StrategyRun]:
        """
        Mark strategy run as failed.
        
        Args:
            run_id: Strategy run ID
            error_message: Error message
        
        Returns:
            Updated StrategyRun instance or None
        """
        strategy_run = self.get_strategy_run(run_id)
        
        if strategy_run:
            strategy_run.fail(error_message)
            self.session.commit()
            self.session.refresh(strategy_run)
        
        return strategy_run
    
    def update_strategy_run_metrics(
        self,
        run_id: int,
        total_trades: int = None,
        winning_trades: int = None,
        losing_trades: int = None,
        total_pnl: float = None,
        max_drawdown: float = None
    ) -> Optional[StrategyRun]:
        """
        Update strategy run metrics.
        
        Args:
            run_id: Strategy run ID
            total_trades: Total trades
            winning_trades: Winning trades
            losing_trades: Losing trades
            total_pnl: Total PnL
            max_drawdown: Maximum drawdown
        
        Returns:
            Updated StrategyRun instance or None
        """
        strategy_run = self.get_strategy_run(run_id)
        
        if strategy_run:
            if total_trades is not None:
                strategy_run.total_trades = total_trades
            
            if winning_trades is not None:
                strategy_run.winning_trades = winning_trades
            
            if losing_trades is not None:
                strategy_run.losing_trades = losing_trades
            
            if total_pnl is not None:
                strategy_run.total_pnl = total_pnl
            
            if max_drawdown is not None:
                strategy_run.max_drawdown = max_drawdown
            
            strategy_run.calculate_win_rate()
            
            self.session.commit()
            self.session.refresh(strategy_run)
        
        return strategy_run

"""
Trade Repository

Database operations for Trade model.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from models.trade import Trade


class TradeRepository:
    """
    Repository for trade database operations.
    
    Provides CRUD operations and queries for trades.
    """
    
    def __init__(self, session: Session):
        """
        Initialize trade repository.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def create_trade(
        self,
        order_id: int,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        strategy_name: str = None
    ) -> Trade:
        """
        Create a new trade.
        
        Args:
            order_id: Related order ID
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares
            entry_price: Entry price
            strategy_name: Name of strategy
        
        Returns:
            Created Trade instance
        """
        trade = Trade(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            status='open',
            strategy_name=strategy_name
        )
        
        self.session.add(trade)
        self.session.commit()
        self.session.refresh(trade)
        
        return trade
    
    def get_trade_by_id(self, trade_id: int) -> Optional[Trade]:
        """
        Get trade by ID.
        
        Args:
            trade_id: Trade ID
        
        Returns:
            Trade instance or None
        """
        return self.session.query(Trade).filter(Trade.id == trade_id).first()
    
    def get_trades(
        self,
        symbol: str = None,
        status: str = None,
        strategy_name: str = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        Get trades with optional filters.
        
        Args:
            symbol: Filter by symbol
            status: Filter by status (open/closed)
            strategy_name: Filter by strategy name
            limit: Maximum number of trades to return
        
        Returns:
            List of Trade instances
        """
        query = self.session.query(Trade)
        
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        
        if status:
            query = query.filter(Trade.status == status)
        
        if strategy_name:
            query = query.filter(Trade.strategy_name == strategy_name)
        
        query = query.order_by(desc(Trade.created_at)).limit(limit)
        
        return query.all()
    
    def get_open_trades(self, symbol: str = None) -> List[Trade]:
        """
        Get open trades.
        
        Args:
            symbol: Filter by symbol (optional)
        
        Returns:
            List of open Trade instances
        """
        query = self.session.query(Trade).filter(Trade.status == 'open')
        
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        
        return query.all()
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        reason: str = None
    ) -> Optional[Trade]:
        """
        Close a trade.
        
        Args:
            trade_id: Trade ID
            exit_price: Exit price
            reason: Reason for closing
        
        Returns:
            Updated Trade instance or None
        """
        trade = self.get_trade_by_id(trade_id)
        
        if trade and trade.status == 'open':
            trade.close(exit_price, reason)
            self.session.commit()
            self.session.refresh(trade)
        
        return trade
    
    def update_trade_pnl(
        self,
        trade_id: int,
        current_price: float
    ) -> Optional[Trade]:
        """
        Update trade PnL based on current price.
        
        Args:
            trade_id: Trade ID
            current_price: Current market price
        
        Returns:
            Updated Trade instance or None
        """
        trade = self.get_trade_by_id(trade_id)
        
        if trade and trade.status == 'open':
            trade.calculate_pnl(current_price)
            self.session.commit()
            self.session.refresh(trade)
        
        return trade
    
    def get_total_pnl(self, symbol: str = None) -> float:
        """
        Get total PnL from all closed trades.
        
        Args:
            symbol: Filter by symbol (optional)
        
        Returns:
            Total PnL
        """
        query = self.session.query(
            func.sum(Trade.pnl)
        ).filter(Trade.status == 'closed')
        
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        
        result = query.scalar()
        return result or 0.0
    
    def count_trades(
        self,
        symbol: str = None,
        status: str = None
    ) -> int:
        """
        Count trades with optional filters.
        
        Args:
            symbol: Filter by symbol
            status: Filter by status
        
        Returns:
            Number of trades
        """
        query = self.session.query(Trade)
        
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        
        if status:
            query = query.filter(Trade.status == status)
        
        return query.count()

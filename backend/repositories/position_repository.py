"""
Position Repository

Database operations for Position model.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from models.position import Position


class PositionRepository:
    """
    Repository for position database operations.
    
    Provides CRUD operations and queries for positions.
    """
    
    def __init__(self, session: Session):
        """
        Initialize position repository.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position by symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Position instance or None
        """
        return self.session.query(Position).filter(
            Position.symbol == symbol,
            Position.quantity > 0
        ).first()
    
    def get_all_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position instances
        """
        return self.session.query(Position).filter(
            Position.quantity > 0
        ).all()
    
    def create_position(
        self,
        symbol: str,
        side: str,
        quantity: int,
        average_price: float,
        strategy_name: str = None,
        stop_loss: float = None,
        target: float = None
    ) -> Position:
        """
        Create a new position.
        
        Args:
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'
            quantity: Number of shares
            average_price: Average entry price
            strategy_name: Name of strategy
            stop_loss: Stop loss price
            target: Target price
        
        Returns:
            Created Position instance
        """
        position = Position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            average_price=average_price,
            current_price=average_price,
            strategy_name=strategy_name,
            stop_loss=stop_loss,
            target=target
        )
        
        self.session.add(position)
        self.session.commit()
        self.session.refresh(position)
        
        return position
    
    def update_position(
        self,
        symbol: str,
        quantity: int = None,
        average_price: float = None,
        current_price: float = None
    ) -> Optional[Position]:
        """
        Update an existing position.
        
        Args:
            symbol: Stock symbol
            quantity: New quantity (optional)
            average_price: New average price (optional)
            current_price: Current market price (optional)
        
        Returns:
            Updated Position instance or None
        """
        position = self.get_position(symbol)
        
        if position:
            if quantity is not None:
                position.quantity = quantity
            
            if average_price is not None:
                position.average_price = average_price
            
            if current_price is not None:
                position.current_price = current_price
                position.update_pnl(current_price)
            
            self.session.commit()
            self.session.refresh(position)
        
        return position
    
    def update_position_pnl(self, symbol: str, current_price: float) -> Optional[Position]:
        """
        Update position PnL based on current price.
        
        Args:
            symbol: Stock symbol
            current_price: Current market price
        
        Returns:
            Updated Position instance or None
        """
        position = self.get_position(symbol)
        
        if position:
            position.update_pnl(current_price)
            self.session.commit()
            self.session.refresh(position)
        
        return position
    
    def close_position(self, symbol: str) -> bool:
        """
        Close a position.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            True if closed, False otherwise
        """
        position = self.get_position(symbol)
        
        if position:
            position.close()
            self.session.commit()
            return True
        
        return False
    
    def get_total_unrealized_pnl(self) -> float:
        """
        Get total unrealized PnL from all positions.
        
        Returns:
            Total unrealized PnL
        """
        positions = self.get_all_positions()
        return sum(pos.unrealized_pnl for pos in positions)
    
    def count_positions(self) -> int:
        """
        Count number of open positions.
        
        Returns:
            Number of open positions
        """
        return self.session.query(Position).filter(
            Position.quantity > 0
        ).count()

"""
Position & Trade Persistence Layer

Handles database persistence for positions and trades with transaction safety.
Manages saving and loading state on startup to prevent data loss on restart.

Features:
- Transaction-based writes to prevent partial commits
- Duplicate prevention on restart
- Atomic operations for data consistency
- Support for both in-memory to DB and DB to memory sync

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.trade import Trade as TradeModel
from models.position import Position as PositionModel
from database.models import SessionLocal

logger = logging.getLogger(__name__)


class PositionPersistence:
    """
    Handles all database persistence operations for positions and trades.
    
    Ensures:
    - No data loss on restart
    - Transaction safety with rollback on failure
    - Duplicate prevention
    - Atomic operations
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize persistence layer.
        
        Args:
            session: SQLAlchemy session (creates new if not provided)
        """
        self.session = session or SessionLocal()
        self._closed = False

    @contextmanager
    def transaction(self):
        """
        Context manager for transaction safety.
        
        Yields:
            SQLAlchemy session
            
        Raises:
            SQLAlchemyError: On database error (auto-rollback)
        """
        try:
            yield self.session
            self.session.commit()
            logger.debug("Transaction committed successfully")
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Transaction failed, rollback executed: {str(e)}")
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(f"Unexpected error in transaction: {str(e)}")
            raise

    # ============================================================================
    # SAVE OPERATIONS (In-Memory → Database)
    # ============================================================================

    def save_position(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit_1: Optional[float] = None,
        take_profit_2: Optional[float] = None,
        strategy_name: Optional[str] = None,
        current_price: Optional[float] = None,
    ) -> PositionModel:
        """
        Save or update an open position in database.
        
        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            quantity: Position size
            entry_price: Entry price
            stop_loss: Stop loss level
            take_profit_1: First target
            take_profit_2: Second target
            strategy_name: Strategy that opened position
            current_price: Current market price
            
        Returns:
            Saved Position model instance
            
        Raises:
            SQLAlchemyError: On database error
        """
        with self.transaction() as session:
            # Check for existing position with same symbol
            existing_position = session.query(PositionModel).filter(
                and_(
                    PositionModel.symbol == symbol,
                    PositionModel.quantity > 0  # Only open positions
                )
            ).first()

            if existing_position:
                # Update existing position
                logger.info(f"Updating existing position: {symbol}")
                existing_position.quantity = quantity
                existing_position.average_price = entry_price
                existing_position.stop_loss = stop_loss
                existing_position.target = take_profit_2 or take_profit_1
                existing_position.current_price = current_price or entry_price
                existing_position.updated_at = datetime.utcnow()
                session.flush()
                return existing_position
            else:
                # Create new position
                logger.info(f"Creating new position: {symbol} qty={quantity} @ {entry_price}")
                position = PositionModel(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    average_price=entry_price,
                    current_price=current_price or entry_price,
                    stop_loss=stop_loss,
                    target=take_profit_2 or take_profit_1,
                    strategy_name=strategy_name,
                    created_at=datetime.utcnow(),
                )
                session.add(position)
                session.flush()
                return position

    def save_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        exit_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        status: str = "open",
        exit_reason: Optional[str] = None,
        strategy_name: Optional[str] = None,
        entry_time: Optional[datetime] = None,
        exit_time: Optional[datetime] = None,
        pnl: Optional[float] = None,
    ) -> TradeModel:
        """
        Save or update a trade in database.
        
        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            quantity: Trade quantity
            entry_price: Entry price
            exit_price: Exit price (if closed)
            stop_loss: Stop loss level
            take_profit: Take profit level
            status: 'open' or 'closed'
            exit_reason: Reason for exit
            strategy_name: Strategy name
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            pnl: Realized PnL (if closed)
            
        Returns:
            Saved Trade model instance
            
        Raises:
            SQLAlchemyError: On database error
        """
        with self.transaction() as session:
            # Calculate PnL if not provided
            calculated_pnl = 0.0
            if exit_price and status == 'closed':
                if side.upper() == 'BUY':
                    calculated_pnl = (exit_price - entry_price) * quantity
                else:  # SELL
                    calculated_pnl = (entry_price - exit_price) * quantity
                pnl = pnl or calculated_pnl

            calculated_pnl_pct = 0.0
            if entry_price > 0:
                calculated_pnl_pct = ((pnl or 0.0) / (entry_price * quantity)) * 100

            # Create trade record
            logger.info(
                f"Saving trade: {symbol} {side} qty={quantity} "
                f"entry={entry_price} exit={exit_price} status={status}"
            )
            trade = TradeModel(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=stop_loss,
                target=take_profit,
                status=status,
                exit_reason=exit_reason,
                strategy_name=strategy_name,
                created_at=entry_time or datetime.utcnow(),
                exited_at=exit_time,
                pnl=pnl or 0.0,
                pnl_percentage=calculated_pnl_pct,
            )
            session.add(trade)
            session.flush()
            return trade

    def update_position(
        self,
        symbol: str,
        quantity: Optional[int] = None,
        entry_price: Optional[float] = None,
        current_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        realized_pnl: Optional[float] = None,
    ) -> Optional[PositionModel]:
        """
        Update an existing position.
        
        Args:
            symbol: Stock symbol
            quantity: Updated quantity
            entry_price: Updated entry price
            current_price: Current price
            stop_loss: Updated stop loss
            realized_pnl: Add to realized PnL
            
        Returns:
            Updated Position or None if not found
            
        Raises:
            SQLAlchemyError: On database error
        """
        with self.transaction() as session:
            position = session.query(PositionModel).filter(
                PositionModel.symbol == symbol
            ).first()

            if not position:
                logger.warning(f"Position not found for update: {symbol}")
                return None

            if quantity is not None:
                position.quantity = quantity
            if entry_price is not None:
                position.average_price = entry_price
            if current_price is not None:
                position.current_price = current_price
            if stop_loss is not None:
                position.stop_loss = stop_loss
            if realized_pnl is not None:
                position.realized_pnl = (position.realized_pnl or 0.0) + realized_pnl

            position.updated_at = datetime.utcnow()
            session.flush()
            return position

    def close_position(self, symbol: str, realized_pnl: float = 0.0) -> Optional[PositionModel]:
        """
        Close a position (set quantity to 0).
        
        Args:
            symbol: Stock symbol
            realized_pnl: PnL from closing
            
        Returns:
            Closed Position or None if not found
            
        Raises:
            SQLAlchemyError: On database error
        """
        with self.transaction() as session:
            position = session.query(PositionModel).filter(
                PositionModel.symbol == symbol
            ).first()

            if not position:
                logger.warning(f"Position not found for closing: {symbol}")
                return None

            logger.info(f"Closing position: {symbol} qty={position.quantity}")
            position.quantity = 0
            position.realized_pnl = (position.realized_pnl or 0.0) + realized_pnl
            position.updated_at = datetime.utcnow()
            session.flush()
            return position

    # ============================================================================
    # LOAD OPERATIONS (Database → In-Memory)
    # ============================================================================

    def load_open_positions(self) -> List[Dict]:
        """
        Load all open positions from database.
        
        Returns:
            List of position dictionaries with structure matching Trade dataclass
            
        Example:
            [
                {
                    'symbol': 'AAPL',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 150.0,
                    'stop_loss': 145.0,
                    'take_profit_1': 155.0,
                    'take_profit_2': 160.0,
                    'timestamp': datetime.utcnow()
                },
                ...
            ]
        """
        try:
            positions = self.session.query(PositionModel).filter(
                PositionModel.quantity > 0  # Only open positions
            ).all()

            loaded = []
            for pos in positions:
                position_dict = {
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'quantity': pos.quantity,
                    'entry_price': pos.average_price,
                    'stop_loss': pos.stop_loss or pos.average_price * 0.95,
                    'take_profit_1': pos.target or pos.average_price * 1.02 if pos.target else None,
                    'take_profit_2': pos.target or pos.average_price * 1.04 if pos.target else None,
                    'timestamp': pos.created_at,
                }
                loaded.append(position_dict)
                logger.info(f"Loaded position: {pos.symbol} qty={pos.quantity}")

            logger.info(f"Loaded {len(loaded)} open positions from database")
            return loaded

        except Exception as e:
            logger.error(f"Error loading positions from database: {str(e)}")
            return []

    def load_open_trades(self) -> List[Dict]:
        """
        Load all open trades from database.
        
        Returns:
            List of trade dictionaries matching Trade dataclass format
            
        Example:
            [
                {
                    'id': 'AAPL_1712577600',
                    'symbol': 'AAPL',
                    'direction': 'BUY',
                    'entry_price': 150.0,
                    'quantity': 100,
                    'stop_loss': 145.0,
                    'take_profit_1': 155.0,
                    'take_profit_2': 160.0,
                    'entry_time': datetime.utcnow(),
                    'status': 'OPEN'
                },
                ...
            ]
        """
        try:
            trades = self.session.query(TradeModel).filter(
                TradeModel.status.in_(['open', 'OPEN', 'partial', 'PARTIAL'])
            ).all()

            loaded = []
            for trade in trades:
                trade_dict = {
                    'id': f"{trade.symbol}_{int(trade.created_at.timestamp())}",
                    'symbol': trade.symbol,
                    'direction': trade.side.upper(),
                    'entry_price': trade.entry_price,
                    'quantity': trade.quantity,
                    'stop_loss': trade.stop_loss or trade.entry_price * 0.95,
                    'take_profit_1': trade.target or trade.entry_price * 1.02 if trade.target else None,
                    'take_profit_2': trade.target or trade.entry_price * 1.04 if trade.target else None,
                    'entry_time': trade.created_at,
                    'status': 'OPEN',
                }
                loaded.append(trade_dict)
                logger.info(f"Loaded trade: {trade.symbol} {trade.side} qty={trade.quantity}")

            logger.info(f"Loaded {len(loaded)} open trades from database")
            return loaded

        except Exception as e:
            logger.error(f"Error loading trades from database: {str(e)}")
            return []

    def load_closed_trades(self, limit: int = 100) -> List[Dict]:
        """
        Load closed trades (for reporting/analysis).
        
        Args:
            limit: Maximum number of trades to load
            
        Returns:
            List of closed trade dictionaries
        """
        try:
            trades = self.session.query(TradeModel).filter(
                TradeModel.status.in_(['closed', 'CLOSED'])
            ).order_by(TradeModel.exited_at.desc()).limit(limit).all()

            logger.info(f"Loaded {len(trades)} closed trades from database")
            return [trade.to_dict() for trade in trades]

        except Exception as e:
            logger.error(f"Error loading closed trades: {str(e)}")
            return []

    # ============================================================================
    # UTILITY OPERATIONS
    # ============================================================================

    def get_position_by_symbol(self, symbol: str) -> Optional[PositionModel]:
        """
        Get position by symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position model or None
        """
        return self.session.query(PositionModel).filter(
            PositionModel.symbol == symbol
        ).first()

    # ============================================================================
    # DUPLICATE PREVENTION (Source of Truth: Database)
    # ============================================================================

    def has_open_position(self, symbol: str) -> bool:
        """
        Check if an open position already exists for symbol.
        
        Queries database directly (source of truth) to prevent duplicates.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if open position exists, False otherwise
        """
        try:
            count = self.session.query(PositionModel).filter(
                and_(
                    PositionModel.symbol == symbol,
                    PositionModel.quantity > 0  # Only open positions
                )
            ).count()
            
            if count > 0:
                logger.warning(
                    f"DUPLICATE PREVENTION: Open position already exists for {symbol} "
                    f"(qty > 0 in DB)"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for duplicate position: {str(e)}")
            # Fail safe: assume duplicate exists if DB check fails
            return True

    def has_open_trade(self, symbol: str) -> bool:
        """
        Check if an open trade already exists for symbol.
        
        Queries database directly (source of truth).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if open trade exists, False otherwise
        """
        try:
            count = self.session.query(TradeModel).filter(
                and_(
                    TradeModel.symbol == symbol,
                    TradeModel.status.in_(['open', 'OPEN', 'partial', 'PARTIAL'])
                )
            ).count()
            
            if count > 0:
                logger.warning(
                    f"DUPLICATE PREVENTION: Open trade already exists for {symbol}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for duplicate trade: {str(e)}")
            # Fail safe: assume duplicate exists if DB check fails
            return True

    def check_for_duplicates(self, symbol: str) -> Tuple[bool, str]:
        """
        Comprehensive duplicate check before trade entry.
        
        Queries database (source of truth) to detect:
        - Open positions in DB
        - Open trades in DB
        - Recent closed trades (unusual pattern)
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Tuple of (is_duplicate: bool, reason: str)
            
        Examples:
            (True, "Open position exists for AAPL (qty=100)")
            (False, "No duplicates detected")
        """
        try:
            # Check 1: Open position in positions table
            open_position = self.session.query(PositionModel).filter(
                and_(
                    PositionModel.symbol == symbol,
                    PositionModel.quantity > 0
                )
            ).first()
            
            if open_position:
                reason = (
                    f"Open position exists for {symbol} "
                    f"(qty={open_position.quantity} @ {open_position.average_price})"
                )
                logger.warning(f"DUPLICATE PREVENTED: {reason}")
                return True, reason
            
            # Check 2: Open trade in trades table
            open_trade = self.session.query(TradeModel).filter(
                and_(
                    TradeModel.symbol == symbol,
                    TradeModel.status.in_(['open', 'OPEN', 'partial', 'PARTIAL'])
                )
            ).first()
            
            if open_trade:
                reason = (
                    f"Open trade exists for {symbol} "
                    f"(id={open_trade.id}, qty={open_trade.quantity})"
                )
                logger.warning(f"DUPLICATE PREVENTED: {reason}")
                return True, reason
            
            # Check 3: Recently closed trade (within last hour) - unusual pattern
            from datetime import timedelta
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            recent_close = self.session.query(TradeModel).filter(
                and_(
                    TradeModel.symbol == symbol,
                    TradeModel.status.in_(['closed', 'CLOSED']),
                    TradeModel.exited_at >= one_hour_ago
                )
            ).first()
            
            if recent_close:
                # Not a hard block, but log as anomaly
                logger.warning(
                    f"DUPLICATE ANOMALY: {symbol} was just closed at "
                    f"{recent_close.exited_at} - unusual to re-enter immediately"
                )
            
            return False, f"No duplicates detected for {symbol}"
            
        except Exception as e:
            logger.error(f"Error performing duplicate check: {str(e)}")
            # Fail safe: assume duplicate if DB check fails
            return True, f"DB check failed: {str(e)} - blocking trade for safety"

    def clear_all_positions(self) -> int:
        """
        Clear all open positions (for testing/reset).
        
        Returns:
            Number of positions cleared
        """
        with self.transaction() as session:
            count = session.query(PositionModel).filter(
                PositionModel.quantity > 0
            ).update({'quantity': 0})
            logger.warning(f"Cleared {count} open positions")
            return count

    def get_total_open_positions(self) -> int:
        """
        Get count of open positions.
        
        Returns:
            Number of open positions
        """
        return self.session.query(PositionModel).filter(
            PositionModel.quantity > 0
        ).count()

    def get_total_realized_pnl(self) -> float:
        """
        Get total realized PnL from all closed positions.
        
        Returns:
            Total realized PnL
        """
        result = self.session.query(PositionModel).filter(
            PositionModel.quantity == 0
        ).all()
        return sum(pos.realized_pnl or 0.0 for pos in result)

    def close(self):
        """Close database session."""
        if not self._closed and self.session:
            self.session.close()
            self._closed = True
            logger.info("Position persistence session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.close()
        except Exception as e:
            logger.warning(f"Error during persistence cleanup: {str(e)}")

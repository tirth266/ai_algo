"""
Order Model Module

Trade and order data structures for backtesting.

Features:
- Trade tracking
- Order management
- PnL calculation
- Trade statistics

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(Enum):
    """Trade status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"


@dataclass
class Trade:
    """
    Represents a single trade.
    
    Attributes:
        symbol: Trading symbol
        direction: LONG or SHORT
        entry_price: Entry price
        stop_loss: Stop loss price
        position_size: Number of shares/contracts
        entry_time: Entry timestamp
        exit_time: Exit timestamp (if closed)
        exit_price: Exit price (if closed)
        pnl: Profit/Loss (if closed)
        pnl_percent: PnL as percentage (if closed)
        status: Trade status
        reason: Entry reason
        exit_reason: Exit reason
    
    Example:
        >>> trade = Trade(
        ...     symbol='RELIANCE',
        ...     direction='LONG',
        ...     entry_price=100.0,
        ...     stop_loss=95.0,
        ...     position_size=100
        ... )
    """
    
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    position_size: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN
    reason: Optional[str] = None
    exit_reason: Optional[str] = None
    
    def close(
        self,
        exit_price: float,
        exit_time: datetime,
        reason: str = None
    ):
        """
        Close the trade.
        
        Args:
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Exit reason
        
        Example:
            >>> trade.close(exit_price=105.0, time=datetime.now(), reason='target')
        """
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.reason = reason
        self.status = TradeStatus.CLOSED
        
        # Calculate PnL
        if self.direction == TradeDirection.LONG:
            self.pnl = (exit_price - self.entry_price) * self.position_size
        else:  # SHORT
            self.pnl = (self.entry_price - exit_price) * self.position_size
        
        # Calculate PnL percent
        if self.direction == TradeDirection.LONG:
            self.pnl_percent = (exit_price / self.entry_price - 1) * 100
        else:  # SHORT
            self.pnl_percent = (1 - exit_price / self.entry_price) * 100
        
        logger.info(
            f"Trade closed: {self.symbol} {self.direction.value} "
            f"PnL: {self.pnl:.2f} ({self.pnl_percent:.2f}%)"
        )
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        Check if stop loss is hit.
        
        Args:
            current_price: Current market price
        
        Returns:
            True if stop loss triggered
        
        Example:
            >>> if trade.check_stop_loss(current_price):
            ...     trade.close(current_price, datetime.now(), 'stop_loss')
        """
        if self.status != TradeStatus.OPEN:
            return False
        
        if self.direction == TradeDirection.LONG:
            if current_price <= self.stop_loss:
                self.close(
                    current_price,
                    datetime.now(),
                    'stop_loss'
                )
                return True
        else:  # SHORT
            if current_price >= self.stop_loss:
                self.close(
                    current_price,
                    datetime.now(),
                    'stop_loss'
                )
                return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            'symbol': self.symbol,
            'direction': self.direction.value,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'position_size': self.position_size,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'status': self.status.value,
            'reason': self.reason,
            'exit_reason': self.exit_reason
        }
    
    @classmethod
    def from_signal(cls, signal: Dict[str, Any], entry_time: datetime):
        """
        Create trade from signal dictionary.
        
        Args:
            signal: Signal from strategy
            entry_time: Entry timestamp
        
        Returns:
            Trade instance
        
        Example:
            >>> trade = Trade.from_signal(signal, datetime.now())
        """
        direction = TradeDirection.LONG if signal['type'] == 'BUY' else TradeDirection.SHORT
        
        return cls(
            symbol=signal.get('symbol', 'UNKNOWN'),
            direction=direction,
            entry_price=signal.get('entry_price', signal.get('price')),
            stop_loss=signal.get('stop_loss'),
            position_size=signal.get('quantity', signal.get('position_size', 100)),
            entry_time=entry_time,
            reason=', '.join(signal.get('reason', []))
        )


@dataclass
class Order:
    """
    Represents a trading order.
    
    Attributes:
        symbol: Trading symbol
        order_type: MARKET, LIMIT, STOP
        side: BUY or SELL
        quantity: Order quantity
        price: Limit/stop price (optional)
        status: Order status
        filled_price: Actual fill price
        filled_time: Fill timestamp
    
    Example:
        >>> order = Order(
        ...     symbol='RELIANCE',
        ...     order_type='MARKET',
        ...     side='BUY',
        ...     quantity=100
        ... )
    """
    
    symbol: str
    order_type: str  # MARKET, LIMIT, STOP
    side: str  # BUY or SELL
    quantity: int
    price: Optional[float] = None
    status: str = 'PENDING'  # PENDING, FILLED, CANCELLED
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None
    
    def fill(self, fill_price: float, fill_time: datetime = None):
        """
        Fill the order.
        
        Args:
            fill_price: Execution price
            fill_time: Execution time
        
        Example:
            >>> order.fill(fill_price=100.5)
        """
        self.filled_price = fill_price
        self.filled_time = fill_time or datetime.now()
        self.status = 'FILLED'
        
        logger.debug(
            f"Order filled: {self.symbol} {self.side} "
            f"{self.quantity} @ {fill_price:.2f}"
        )
    
    def cancel(self):
        """Cancel the order."""
        self.status = 'CANCELLED'
        logger.debug(f"Order cancelled: {self.symbol} {self.side}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            'symbol': self.symbol,
            'order_type': self.order_type,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'status': self.status,
            'filled_price': self.filled_price,
            'filled_time': self.filled_time.isoformat() if self.filled_time else None
        }


class TradeManager:
    """
    Manage collection of trades.
    
    Features:
    - Track open trades
    - Track closed trades
    - Trade statistics
    - PnL aggregation
    
    Usage:
        >>> manager = TradeManager()
        >>> manager.add_trade(trade)
        >>> manager.close_trade(trade_id, exit_price, exit_time)
    """
    
    def __init__(self):
        """Initialize trade manager."""
        self._trades: List[Trade] = []
        self._trade_counter = 0
        
        logger.info("TradeManager initialized")
    
    def add_trade(self, trade: Trade) -> int:
        """
        Add a new trade.
        
        Args:
            trade: Trade instance
        
        Returns:
            Trade ID
        
        Example:
            >>> trade_id = manager.add_trade(trade)
        """
        self._trade_counter += 1
        trade.trade_id = self._trade_counter
        self._trades.append(trade)
        
        logger.info(
            f"Trade #{self._trade_counter} opened: "
            f"{trade.symbol} {trade.direction.value} "
            f"@ {trade.entry_price:.2f}"
        )
        
        return self._trade_counter
    
    def get_open_trades(self) -> List[Trade]:
        """Get all open trades."""
        return [t for t in self._trades if t.status == TradeStatus.OPEN]
    
    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades."""
        return [t for t in self._trades if t.status != TradeStatus.OPEN]
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_time: datetime,
        reason: str = None
    ):
        """
        Close a specific trade.
        
        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Exit reason
        """
        trade = self.get_trade_by_id(trade_id)
        
        if trade:
            trade.close(exit_price, exit_time, reason)
        else:
            logger.error(f"Trade #{trade_id} not found")
    
    def get_trade_by_id(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID."""
        for trade in self._trades:
            if getattr(trade, 'trade_id', None) == trade_id:
                return trade
        return None
    
    def check_all_stop_losses(self, prices: Dict[str, float]):
        """
        Check stop losses for all open trades.
        
        Args:
            prices: Dictionary of symbol → current_price
        
        Example:
            >>> manager.check_all_stop_losses({'RELIANCE': 95.5})
        """
        for trade in self.get_open_trades():
            current_price = prices.get(trade.symbol)
            
            if current_price:
                trade.check_stop_loss(current_price)
    
    def get_total_pnl(self) -> float:
        """
        Get total PnL from all closed trades.
        
        Returns:
            Total PnL
        
        Example:
            >>> total = manager.get_total_pnl()
            >>> print(f"Total PnL: {total:.2f}")
        """
        closed = self.get_closed_trades()
        return sum(t.pnl for t in closed if t.pnl is not None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trade statistics."""
        closed = self.get_closed_trades()
        
        if not closed:
            return {'total_trades': 0}
        
        winning_trades = [t for t in closed if t.pnl and t.pnl > 0]
        losing_trades = [t for t in closed if t.pnl and t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in closed if t.pnl is not None)
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        return {
            'total_trades': len(closed),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(closed) * 100 if closed else 0,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': abs(avg_loss),
            'profit_factor': abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades and sum(t.pnl for t in losing_trades) != 0 else float('inf')
        }

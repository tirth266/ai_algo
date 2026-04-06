"""
Trade Simulator Module

Simulates realistic trade execution with:
- Entry/exit price calculation
- Slippage modeling
- Brokerage cost calculation
- Position tracking

Key Features:
- Realistic fill simulation
- Configurable slippage and brokerage
- Long and short position support
- P&L calculation
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade."""
    
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    slippage: float
    brokerage: float
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'slippage': self.slippage,
            'brokerage': self.brokerage,
            'pnl': self.pnl,
            'exit_reason': self.exit_reason
        }


@dataclass
class Position:
    """Represents an open position."""
    
    symbol: str
    action: str  # 'BUY' (long) or 'SELL' (short)
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    
    def update_price(self, price: float):
        """Update current market price."""
        self.current_price = price
    
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.action == 'BUY':
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - self.current_price) * self.quantity


class TradeSimulator:
    """
    Simulates realistic trade execution.
    
    Features:
    - Slippage modeling (percentage or fixed)
    - Brokerage calculation
    - Position management
    - Trade history tracking
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        slippage_percent: float = 0.0005,  # 0.05% default
        brokerage_per_trade: float = 20.0,  # Fixed per trade
        brokerage_percent: float = 0.0003,  # 0.03% default
    ):
        """
        Initialize trade simulator.
        
        Args:
            initial_capital: Starting capital
            slippage_percent: Slippage as percentage of price
            brokerage_per_trade: Fixed brokerage per trade
            brokerage_percent: Brokerage as percentage of trade value
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_percent = slippage_percent
        self.brokerage_per_trade = brokerage_per_trade
        self.brokerage_percent = brokerage_percent
        
        # Position tracking
        self.position: Optional[Position] = None
        
        # Trade history
        self.trades: List[Trade] = []
        
        # Running costs
        self.total_brokerage = 0.0
        self.total_slippage_cost = 0.0
        
        logger.info(f"TradeSimulator initialized with capital: {initial_capital}")
    
    def simulate_entry(
        self,
        signal: Dict[str, Any],
        current_price: float,
        timestamp: datetime,
        symbol: str = 'SYMBOL'
    ) -> Optional[Trade]:
        """
        Simulate entering a trade based on signal.
        
        Args:
            signal: Trading signal from strategy
            current_price: Current market price
            timestamp: Trade entry time
            symbol: Trading symbol
        
        Returns:
            Trade object if entry successful, None otherwise
        """
        action = signal.get('action', 'BUY')
        quantity = signal.get('quantity', 100)
        
        # Validate capital
        required_capital = current_price * quantity
        if required_capital > self.capital:
            logger.warning(f"Insufficient capital for entry: need {required_capital}, have {self.capital}")
            return None
        
        # Calculate slippage
        if action == 'BUY':
            # Buy at slightly higher price
            slippage = current_price * self.slippage_percent
            entry_price = current_price + slippage
        else:  # SELL
            # Sell at slightly lower price
            slippage = current_price * self.slippage_percent
            entry_price = current_price - slippage
        
        # Calculate brokerage
        brokerage = max(
            self.brokerage_per_trade,
            entry_price * quantity * self.brokerage_percent
        )
        
        # Create position
        self.position = Position(
            symbol=symbol,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=timestamp,
            current_price=current_price
        )
        
        # Deduct capital and costs
        self.capital -= (entry_price * quantity + brokerage)
        self.total_brokerage += brokerage
        self.total_slippage_cost += slippage * quantity
        
        logger.info(f"Entry: {action} {quantity} @ {entry_price:.2f} (slippage: {slippage:.2f})")
        
        return None  # Trade will be recorded on exit
    
    def simulate_exit(
        self,
        current_price: float,
        timestamp: datetime,
        reason: str = 'Exit signal'
    ) -> Optional[Trade]:
        """
        Simulate exiting current position.
        
        Args:
            current_price: Current market price
            timestamp: Exit time
            reason: Reason for exit
        
        Returns:
            Trade object if exit successful, None if no position
        """
        if not self.position:
            logger.warning("No open position to exit")
            return None
        
        pos = self.position
        
        # Calculate slippage on exit
        if pos.action == 'BUY':
            # Sell at slightly lower price
            slippage = current_price * self.slippage_percent
            exit_price = current_price - slippage
        else:  # SHORT
            # Buy back at slightly higher price
            slippage = current_price * self.slippage_percent
            exit_price = current_price + slippage
        
        # Calculate brokerage
        brokerage = max(
            self.brokerage_per_trade,
            exit_price * pos.quantity * self.brokerage_percent
        )
        
        # Calculate P&L
        if pos.action == 'BUY':
            gross_pnl = (exit_price - pos.entry_price) * pos.quantity
        else:  # SHORT
            gross_pnl = (pos.entry_price - exit_price) * pos.quantity
        
        # Net P&L after costs
        net_pnl = gross_pnl - brokerage - (slippage * pos.quantity)
        
        # Update capital
        self.capital += (exit_price * pos.quantity + net_pnl)
        self.total_brokerage += brokerage
        self.total_slippage_cost += slippage * pos.quantity
        
        # Create trade record
        trade = Trade(
            entry_time=pos.entry_time,
            exit_time=timestamp,
            symbol=pos.symbol,
            action=pos.action,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            slippage=slippage,
            brokerage=brokerage,
            pnl=net_pnl,
            exit_reason=reason
        )
        
        self.trades.append(trade)
        
        # Clear position
        self.position = None
        
        logger.info(f"Exit: {pos.action} {pos.quantity} @ {exit_price:.2f}, P&L: {net_pnl:.2f}")
        
        return trade
    
    def get_current_position(self) -> Optional[Position]:
        """Get current open position."""
        return self.position
    
    def has_position(self) -> bool:
        """Check if there's an open position."""
        return self.position is not None
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get list of all completed trades."""
        return [trade.to_dict() for trade in self.trades]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        avg_profit = 0.0
        if winning_trades > 0:
            avg_profit = sum(t.pnl for t in self.trades if t.pnl > 0) / winning_trades
        
        avg_loss = 0.0
        if losing_trades > 0:
            avg_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0)) / losing_trades
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'total_brokerage': self.total_brokerage,
            'total_slippage_cost': self.total_slippage_cost,
            'current_capital': self.capital,
            'total_pnl': self.capital - self.initial_capital
        }
    
    def reset(self):
        """Reset simulator to initial state."""
        self.capital = self.initial_capital
        self.position = None
        self.trades = []
        self.total_brokerage = 0.0
        self.total_slippage_cost = 0.0
        logger.info("TradeSimulator reset")

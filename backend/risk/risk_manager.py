"""
Risk Manager Module

Controls risk parameters for trading strategies.
Ensures safe position sizing and loss limits.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk management controller for trading strategies.
    
    Features:
    - Maximum capital per trade
    - Maximum daily loss limit
    - Maximum open positions
    - Position sizing based on capital
    
    Usage:
        >>> risk = RiskManager(capital_per_trade=25000, max_daily_loss=5000)
        >>> if risk.check_order(signal):
        ...     # Order is within risk limits
        ...     pass
    """
    
    def __init__(
        self,
        capital_per_trade: float = 25000,
        max_daily_loss: float = 5000,
        max_positions: int = 5,
        total_capital: float = 100000
    ):
        """
        Initialize risk manager.
        
        Args:
            capital_per_trade: Maximum capital to deploy per trade
            max_daily_loss: Maximum allowable loss per day
            max_positions: Maximum number of simultaneous positions
            total_capital: Total available capital
        """
        self.capital_per_trade = capital_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_positions = max_positions
        self.total_capital = total_capital
        
        # Runtime tracking
        self.daily_pnl = 0.0
        self.open_positions = 0
        self.trades_today = 0
        
        logger.info(f"RiskManager initialized: Capital/Trade={capital_per_trade}, "
                   f"MaxDailyLoss={max_daily_loss}, MaxPositions={max_positions}")
    
    def check_order(self, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Check if an order passes risk checks.
        
        Args:
            signal: Trading signal with action, quantity, price
            current_price: Current market price
        
        Returns:
            Dict with 'approved' (bool) and 'reason' (str)
        """
        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            return {
                'approved': False,
                'reason': f'Daily loss limit reached: {self.daily_pnl:.2f}'
            }
        
        # Check maximum positions
        if self.open_positions >= self.max_positions:
            return {
                'approved': False,
                'reason': f'Maximum positions reached: {self.open_positions}'
            }
        
        # Calculate required capital
        action = signal.get('action', '')
        quantity = signal.get('quantity', 0)
        
        if action == 'BUY':
            required_capital = quantity * current_price
            
            if required_capital > self.capital_per_trade:
                return {
                    'approved': False,
                    'reason': f'Required capital {required_capital:.2f} exceeds limit {self.capital_per_trade:.2f}'
                }
        
        # All checks passed
        return {
            'approved': True,
            'reason': 'All risk checks passed'
        }
    
    def calculate_position_size(self, signal: Dict[str, Any], current_price: float) -> int:
        """
        Calculate optimal position size based on risk parameters.
        
        Args:
            signal: Trading signal
            current_price: Current market price
        
        Returns:
            Optimal quantity to trade
        """
        # Maximum quantity based on capital per trade
        max_quantity = int(self.capital_per_trade / current_price)
        
        # Use signal quantity if provided, otherwise use max
        signal_quantity = signal.get('quantity', max_quantity)
        
        # Return minimum of signal quantity and max quantity
        quantity = min(signal_quantity, max_quantity)
        
        logger.debug(f"Position size calculated: {quantity} (signal: {signal_quantity}, max: {max_quantity})")
        
        return quantity
    
    def update_position(self, pnl: float, position_change: int):
        """
        Update risk manager after order execution.
        
        Args:
            pnl: Profit/Loss from the trade
            position_change: Change in position count (+1 for open, -1 for close)
        """
        self.daily_pnl += pnl
        self.open_positions += position_change
        self.trades_today += 1
        
        logger.info(f"RiskManager updated: DailyPnL={self.daily_pnl:.2f}, "
                   f"OpenPositions={self.open_positions}, TradesToday={self.trades_today}")
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at start of each trading day)."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        
        logger.info("RiskManager daily stats reset")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk status summary."""
        return {
            'daily_pnl': self.daily_pnl,
            'open_positions': self.open_positions,
            'trades_today': self.trades_today,
            'remaining_daily_loss': self.max_daily_loss + self.daily_pnl,
            'available_position_slots': self.max_positions - self.open_positions
        }

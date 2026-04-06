"""
Trade Executor Module

Execute and manage simulated trades in backtesting.

Features:
- Trade entry simulation
- Stop loss monitoring
- Position sizing
- Trade lifecycle management

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from .order_model import Trade, TradeDirection, TradeStatus, TradeManager

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Execute and manage trades during backtesting.
    
    Simulates trade execution based on signals.
    Monitors stop losses and manages trade lifecycle.
    
    Usage:
        >>> executor = TradeExecutor()
        >>> if signal:
        ...     executor.open_trade(signal, current_candle)
        >>> executor.check_stop_losses(current_prices)
    """
    
    def __init__(self):
        """Initialize trade executor."""
        self.trade_manager = TradeManager()
        
        # Configuration
        self._slippage_percent = 0.0  # Slippage percentage
        self._commission_per_trade = 0.0  # Fixed commission
        
        logger.info("TradeExecutor initialized")
    
    def open_trade(
        self,
        signal: Dict[str, Any],
        candle: Dict[str, Any],
        use_atr_sizing: bool = True
    ) -> Optional[int]:
        """
        Open a new trade from signal.
        
        Args:
            signal: Signal from strategy
            candle: Current candle data
            use_atr_sizing: Use ATR-based position sizing
        
        Returns:
            Trade ID or None if failed
        
        Example:
            >>> signal = strategy.generate_signal(candles)
            >>> trade_id = executor.open_trade(signal, current_candle)
        """
        try:
            # Validate signal
            if not signal or signal.get('type') not in ['BUY', 'SELL']:
                logger.warning("Invalid signal received")
                return None
            
            # Determine direction
            direction = TradeDirection.LONG if signal['type'] == 'BUY' else TradeDirection.SHORT
            
            # Get entry price (use candle close or signal price)
            entry_price = signal.get('entry_price', candle.get('close'))
            
            # Apply slippage
            entry_price = self._apply_slippage(entry_price, direction)
            
            # Get stop loss
            stop_loss = signal.get('stop_loss')
            
            if not stop_loss:
                logger.warning("No stop loss in signal, skipping trade")
                return None
            
            # Get position size
            position_size = signal.get('position_size', signal.get('quantity'))
            
            if not position_size:
                # Calculate default position size if not provided
                account_value = 100000  # Default
                risk_amount = account_value * 0.01  # 1% risk
                stop_distance = abs(entry_price - stop_loss)
                
                if stop_distance > 0:
                    position_size = int(risk_amount / stop_distance)
                else:
                    position_size = 100  # Default
                
                logger.info(f"Calculated position size: {position_size}")
            
            # Create trade
            trade = Trade.from_signal(signal, candle.get('time', datetime.now()))
            trade.entry_price = entry_price
            
            # Adjust stop loss for slippage
            if direction == TradeDirection.LONG:
                trade.stop_loss = stop_loss * (1 - self._slippage_percent / 100)
            else:
                trade.stop_loss = stop_loss * (1 + self._slippage_percent / 100)
            
            trade.position_size = position_size
            
            # Add to manager
            trade_id = self.trade_manager.add_trade(trade)
            
            logger.info(
                f"Trade opened: #{trade_id} {direction.value} "
                f"{trade.symbol} @ {entry_price:.2f}, "
                f"size={position_size}, stop={stop_loss:.2f}"
            )
            
            return trade_id
            
        except Exception as e:
            logger.error(f"Error opening trade: {str(e)}", exc_info=True)
            return None
    
    def _apply_slippage(self, price: float, direction: TradeDirection) -> float:
        """
        Apply slippage to entry price.
        
        Args:
            price: Original price
            direction: Trade direction
        
        Returns:
            Adjusted price
        """
        if self._slippage_percent <= 0:
            return price
        
        slippage_factor = self._slippage_percent / 100
        
        if direction == TradeDirection.LONG:
            return price * (1 + slippage_factor)
        else:
            return price * (1 - slippage_factor)
    
    def check_stop_losses(self, prices: Dict[str, float]) -> List[int]:
        """
        Check stop losses for all open trades.
        
        Args:
            prices: Dictionary of symbol → current_price
        
        Returns:
            List of closed trade IDs
        
        Example:
            >>> closed = executor.check_stop_losses({'RELIANCE': 95.5})
            >>> if closed:
            ...     print(f"Stopped out: {closed}")
        """
        closed_trades = []
        
        for trade in self.trade_manager.get_open_trades():
            current_price = prices.get(trade.symbol)
            
            if current_price and trade.check_stop_loss(current_price):
                closed_trades.append(getattr(trade, 'trade_id', None))
                
                logger.info(
                    f"Stop loss hit: #{getattr(trade, 'trade_id')} "
                    f"{trade.symbol} @ {current_price:.2f}"
                )
        
        return closed_trades
    
    def close_all_trades(
        self,
        prices: Dict[str, float],
        exit_time: datetime = None,
        reason: str = "market_close"
    ):
        """
        Close all open trades (e.g., end of backtest).
        
        Args:
            prices: Current prices for all symbols
            exit_time: Exit timestamp
            reason: Exit reason
        
        Example:
            >>> executor.close_all_trades(prices, reason='end_of_backtest')
        """
        exit_time = exit_time or datetime.now()
        
        for trade in self.trade_manager.get_open_trades():
            exit_price = prices.get(trade.symbol, trade.entry_price)
            
            trade.close(exit_price, exit_time, reason)
            
            logger.info(
                f"Trade closed: #{getattr(trade, 'trade_id')} "
                f"{trade.symbol} @ {exit_price:.2f}, "
                f"PnL: {trade.pnl:.2f}"
            )
    
    def get_open_trades(self) -> List[Trade]:
        """Get all currently open trades."""
        return self.trade_manager.get_open_trades()
    
    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades."""
        return self.trade_manager.get_closed_trades()
    
    def get_total_pnl(self) -> float:
        """Get total PnL from all closed trades."""
        return self.trade_manager.get_total_pnl()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trade statistics."""
        return self.trade_manager.get_stats()
    
    def configure(
        self,
        slippage_percent: float = 0.0,
        commission_per_trade: float = 0.0
    ):
        """
        Configure execution parameters.
        
        Args:
            slippage_percent: Slippage percentage (e.g., 0.1 for 0.1%)
            commission_per_trade: Fixed commission per trade
        """
        self._slippage_percent = slippage_percent
        self._commission_per_trade = commission_per_trade
        
        logger.info(
            f"TradeExecutor configured: "
            f"slippage={slippage_percent}%, commission={commission_per_trade}"
        )

"""
Portfolio Manager Module

Track account balance, positions, and equity curve.

Features:
- Account balance tracking
- Position management
- Equity curve calculation
- Drawdown monitoring
- Portfolio valuation

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..execution.order_model import Trade, TradeStatus

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Manage portfolio state during backtesting.
    
    Tracks:
    - Cash balance
    - Open positions
    - Equity curve
    - Drawdown
    
    Usage:
        >>> portfolio = PortfolioManager(initial_capital=100000)
        >>> portfolio.update_equity(closed_trades)
        >>> print(f"Current equity: {portfolio.get_portfolio_value()}")
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        Initialize portfolio manager.
        
        Args:
            initial_capital: Starting capital
        
        Example:
            >>> portfolio = PortfolioManager(initial_capital=500000)
        """
        self.initial_capital = initial_capital
        
        # Current state
        self.cash = initial_capital
        self._open_positions: Dict[str, Trade] = {}
        
        # Equity tracking
        self.equity_curve: List[Dict[str, Any]] = []
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0
        self._current_drawdown = 0.0
        
        # Statistics
        self._total_deposits = 0.0
        self._total_withdrawals = 0.0
        
        logger.info(
            f"PortfolioManager initialized with capital: {initial_capital:.2f}"
        )
    
    def update_equity(
        self,
        closed_trades: List[Trade],
        timestamp: datetime = None
    ):
        """
        Update equity from closed trades.
        
        Args:
            closed_trades: List of recently closed trades
            timestamp: Update timestamp
        
        Example:
            >>> portfolio.update_equity(closed_trades, datetime.now())
        """
        timestamp = timestamp or datetime.now()
        
        # Calculate PnL from closed trades
        total_pnl = sum(
            trade.pnl for trade in closed_trades
            if trade.pnl is not None
        )
        
        # Update cash
        self.cash += total_pnl
        
        # Record in equity curve
        current_equity = self.get_portfolio_value()
        
        # Update peak and drawdown
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        
        self._current_drawdown = (
            (self._peak_equity - current_equity) / self._peak_equity * 100
            if self._peak_equity > 0 else 0
        )
        
        if self._current_drawdown > self._max_drawdown:
            self._max_drawdown = self._current_drawdown
        
        # Add to equity curve
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': current_equity,
            'cash': self.cash,
            'drawdown': self._current_drawdown,
            'peak_equity': self._peak_equity
        })
        
        logger.debug(
            f"Portfolio updated: Equity={current_equity:.2f}, "
            f"Cash={self.cash:.2f}, PnL={total_pnl:.2f}, DD={self._current_drawdown:.2f}%"
        )
    
    def add_position(self, trade: Trade):
        """
        Add an open position.
        
        Args:
            trade: Open trade
        
        Example:
            >>> portfolio.add_position(trade)
        """
        self._open_positions[trade.symbol] = trade
        
        logger.debug(
            f"Position added: {trade.symbol} "
            f"{trade.direction.value} {trade.position_size} shares"
        )
    
    def remove_position(self, symbol: str):
        """
        Remove a closed position.
        
        Args:
            symbol: Symbol to remove
        
        Example:
            >>> portfolio.remove_position('RELIANCE')
        """
        if symbol in self._open_positions:
            del self._open_positions[symbol]
            logger.debug(f"Position removed: {symbol}")
    
    def get_portfolio_value(self) -> float:
        """
        Get total portfolio value (cash + unrealized PnL).
        
        Returns:
            Total portfolio value
        
        Example:
            >>> value = portfolio.get_portfolio_value()
            >>> print(f"Portfolio: {value:.2f}")
        """
        # Start with cash
        total = self.cash
        
        # Add unrealized PnL from open positions
        # Note: In backtesting, we typically use close price
        # This is simplified - would need current prices for accuracy
        
        logger.debug(f"Portfolio value calculated: {total:.2f}")
        return total
    
    def get_equity_curve(self) -> pd.DataFrame:
        """
        Get equity curve as DataFrame.
        
        Returns:
            DataFrame with equity history
        
        Example:
            >>> df = portfolio.get_equity_curve()
            >>> print(df.tail())
        """
        if not self.equity_curve:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.equity_curve)
        
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def get_max_drawdown(self) -> float:
        """
        Get maximum drawdown percentage.
        
        Returns:
            Maximum drawdown as percentage
        
        Example:
            >>> mdd = portfolio.get_max_drawdown()
            >>> print(f"Max DD: {mdd:.2f}%")
        """
        return self._max_drawdown
    
    def get_current_drawdown(self) -> float:
        """
        Get current drawdown percentage.
        
        Returns:
            Current drawdown as percentage
        """
        return self._current_drawdown
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get portfolio statistics.
        
        Returns:
            Stats dictionary
        
        Example:
            >>> stats = portfolio.get_stats()
        """
        current_equity = self.get_portfolio_value()
        total_return = ((current_equity - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'initial_capital': self.initial_capital,
            'current_equity': current_equity,
            'cash': self.cash,
            'total_return': total_return,
            'total_return_abs': current_equity - self.initial_capital,
            'peak_equity': self._peak_equity,
            'max_drawdown': self._max_drawdown,
            'current_drawdown': self._current_drawdown,
            'open_positions': len(self._open_positions),
            'equity_points': len(self.equity_curve)
        }
    
    def deposit(self, amount: float):
        """
        Add capital to portfolio.
        
        Args:
            amount: Amount to deposit
        
        Example:
            >>> portfolio.deposit(50000)
        """
        self.cash += amount
        self._total_deposits += amount
        
        logger.info(f"Deposited {amount:.2f}, new cash: {self.cash:.2f}")
    
    def withdraw(self, amount: float):
        """
        Withdraw capital from portfolio.
        
        Args:
            amount: Amount to withdraw
        
        Example:
            >>> portfolio.withdraw(10000)
        """
        if amount > self.cash:
            logger.warning(f"Insufficient cash for withdrawal: {amount} > {self.cash}")
            return
        
        self.cash -= amount
        self._total_withdrawals += amount
        
        logger.info(f"Withdrew {amount:.2f}, remaining cash: {self.cash:.2f}")
    
    def get_open_positions(self) -> Dict[str, Trade]:
        """Get all open positions."""
        return dict(self._open_positions)
    
    def get_total_exposure(self) -> float:
        """
        Get total capital deployed in open positions.
        
        Returns:
            Total exposure
        
        Example:
            >>> exposure = portfolio.get_total_exposure()
        """
        total = 0.0
        
        for trade in self._open_positions.values():
            total += trade.entry_price * trade.position_size
        
        return total
    
    def get_cash_utilization(self) -> float:
        """
        Get percentage of cash deployed.
        
        Returns:
            Utilization percentage
        
        Example:
            >>> util = portfolio.get_cash_utilization()
            >>> print(f"Cash utilization: {util:.1f}%")
        """
        total_deployed = self.get_total_exposure()
        total_capital = self.get_portfolio_value()
        
        if total_capital > 0:
            return (total_deployed / total_capital) * 100
        
        return 0.0
    
    def export_equity_curve(self, filepath: str):
        """
        Export equity curve to CSV.
        
        Args:
            filepath: Output CSV path
        
        Example:
            >>> portfolio.export_equity_curve('equity_curve.csv')
        """
        df = self.get_equity_curve()
        
        if len(df) > 0:
            df.to_csv(filepath)
            logger.info(f"Equity curve exported to {filepath}")
        else:
            logger.warning("No equity curve data to export")

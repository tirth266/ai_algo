"""
Performance Metrics Module

Calculates comprehensive trading performance statistics.

Metrics Include:
- Total Return
- Win Rate
- Profit Factor
- Sharpe Ratio
- Maximum Drawdown
- Average Win/Loss
- Expectancy
- Risk-adjusted returns
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Calculate professional trading performance metrics.
    
    Inputs:
    - Trade history from backtest
    - Equity curve data
    
    Outputs:
    - Comprehensive statistics dictionary
    - Risk metrics
    - Performance ratios
    """
    
    def __init__(self):
        """Initialize metrics calculator."""
        logger.info("PerformanceMetrics initialized")
    
    def calculate_all(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: pd.DataFrame,
        initial_capital: float,
        risk_free_rate: float = 0.06  # 6% annual default
    ) -> Dict[str, Any]:
        """
        Calculate all performance metrics.
        
        Args:
            trades: List of completed trades
            equity_curve: DataFrame with equity time series
            initial_capital: Starting capital
            risk_free_rate: Annual risk-free rate (default: 6%)
        
        Returns:
            Dictionary with all calculated metrics
        """
        logger.info(f"Calculating metrics for {len(trades)} trades")
        
        if not trades:
            return self._empty_metrics()
        
        # Extract trade P&L values
        pnls = [trade['pnl'] for trade in trades if trade['pnl'] is not None]
        
        if not pnls:
            return self._empty_metrics()
        
        # Calculate basic metrics
        total_return = sum(pnls)
        total_return_pct = (total_return / initial_capital) * 100
        
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)
        total_trades = len(pnls)
        
        win_rate = num_wins / total_trades if total_trades > 0 else 0.0
        
        avg_profit = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0.0
        
        profit_factor = (sum(winning_trades) / abs(sum(losing_trades))) if losing_trades and sum(losing_trades) != 0 else float('inf')
        
        # Calculate expectancy
        expectancy = (win_rate * avg_profit) - ((1 - win_rate) * avg_loss)
        
        # Calculate max drawdown from equity curve
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve, risk_free_rate)
        
        # Calculate Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(equity_curve, risk_free_rate)
        
        # Calculate Calmar ratio
        calmar_ratio = self._calculate_calmar_ratio(total_return_pct, max_drawdown)
        
        # Calculate largest win and loss
        largest_win = max(pnls) if pnls else 0.0
        largest_loss = min(pnls) if pnls else 0.0
        
        # Calculate average holding period
        avg_holding_period = self._calculate_avg_holding_period(trades)
        
        # Calculate profit per trade
        profit_per_trade = total_return / total_trades if total_trades > 0 else 0.0
        
        # Build results dictionary
        metrics = {
            # Return metrics
            'total_return': round(total_return, 2),
            'total_return_pct': round(total_return_pct, 2),
            'profit_per_trade': round(profit_per_trade, 2),
            
            # Win/Loss metrics
            'total_trades': total_trades,
            'winning_trades': num_wins,
            'losing_trades': num_losses,
            'win_rate': round(win_rate, 4),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
            'expectancy': round(expectancy, 2),
            
            # Extreme values
            'largest_win': round(largest_win, 2),
            'largest_loss': round(largest_loss, 2),
            
            # Risk metrics
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(abs(max_drawdown), 2),
            
            # Risk-adjusted returns
            'sharpe_ratio': round(sharpe_ratio, 2),
            'sortino_ratio': round(sortino_ratio, 2),
            'calmar_ratio': round(calmar_ratio, 2),
            
            # Time metrics
            'avg_holding_period_minutes': round(avg_holding_period, 2),
            
            # Final capital
            'final_capital': round(initial_capital + total_return, 2)
        }
        
        logger.info(f"Metrics calculated: Return={total_return_pct:.2f}%, Win Rate={win_rate*100:.1f}%")
        
        return metrics
    
    def _calculate_max_drawdown(self, equity_df: pd.DataFrame) -> float:
        """
        Calculate maximum drawdown from equity curve.
        
        Args:
            equity_df: DataFrame with equity values
        
        Returns:
            Maximum drawdown as percentage
        """
        if equity_df.empty or 'equity' not in equity_df.columns:
            return 0.0
        
        equity = equity_df['equity']
        
        # Calculate running maximum
        running_max = equity.expanding().max()
        
        # Calculate drawdowns
        drawdowns = (equity - running_max) / running_max * 100
        
        # Return maximum drawdown
        max_dd = drawdowns.min()
        
        logger.debug(f"Max drawdown calculated: {max_dd:.2f}%")
        
        return abs(max_dd)
    
    def _calculate_sharpe_ratio(
        self, 
        equity_df: pd.DataFrame, 
        risk_free_rate: float
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Sharpe Ratio = (Portfolio Return - Risk Free Rate) / Portfolio Std Dev
        
        Args:
            equity_df: DataFrame with equity values
            risk_free_rate: Annual risk-free rate
        
        Returns:
            Sharpe ratio (annualized)
        """
        if equity_df.empty or 'equity' not in equity_df.columns or len(equity_df) < 2:
            return 0.0
        
        # Calculate returns
        returns = equity_df['equity'].pct_change().dropna()
        
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        
        # Annualize parameters
        # Assuming 5-minute data: 78 bars/day * 252 days/year = 19656 bars/year
        periods_per_year = 19656
        
        excess_return = returns.mean() * periods_per_year - risk_free_rate
        volatility = returns.std() * np.sqrt(periods_per_year)
        
        sharpe = excess_return / volatility if volatility > 0 else 0.0
        
        logger.debug(f"Sharpe ratio calculated: {sharpe:.2f}")
        
        return sharpe
    
    def _calculate_sortino_ratio(
        self, 
        equity_df: pd.DataFrame, 
        risk_free_rate: float
    ) -> float:
        """
        Calculate Sortino ratio (uses downside deviation).
        
        Args:
            equity_df: DataFrame with equity values
            risk_free_rate: Annual risk-free rate
        
        Returns:
            Sortino ratio
        """
        if equity_df.empty or 'equity' not in equity_df.columns or len(equity_df) < 2:
            return 0.0
        
        returns = equity_df['equity'].pct_change().dropna()
        
        if len(returns) < 2:
            return 0.0
        
        # Downside returns (negative returns only)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')  # No losing periods
        
        # Annualize
        periods_per_year = 19656
        
        excess_return = returns.mean() * periods_per_year - risk_free_rate
        
        # Downside deviation
        downside_deviation = downside_returns.std() * np.sqrt(periods_per_year)
        
        sortino = excess_return / downside_deviation if downside_deviation > 0 else float('inf')
        
        logger.debug(f"Sortino ratio calculated: {sortino:.2f}")
        
        return sortino
    
    def _calculate_calmar_ratio(self, total_return: float, max_drawdown: float) -> float:
        """
        Calculate Calmar ratio (Return / Max Drawdown).
        
        Args:
            total_return: Total return percentage
            max_drawdown: Maximum drawdown percentage
        
        Returns:
            Calmar ratio
        """
        if max_drawdown == 0 or max_drawdown == 0.0:
            return 0.0
        
        calmar = total_return / abs(max_drawdown)
        
        logger.debug(f"Calmar ratio calculated: {calmar:.2f}")
        
        return calmar
    
    def _calculate_avg_holding_period(self, trades: List[Dict[str, Any]]) -> float:
        """
        Calculate average holding period in minutes.
        
        Args:
            trades: List of completed trades
        
        Returns:
            Average holding period in minutes
        """
        holding_periods = []
        
        for trade in trades:
            if trade.get('entry_time') and trade.get('exit_time'):
                try:
                    entry = pd.to_datetime(trade['entry_time'])
                    exit = pd.to_datetime(trade['exit_time'])
                    period = (exit - entry).total_seconds() / 60.0  # Convert to minutes
                    holding_periods.append(period)
                except Exception:
                    pass
        
        if holding_periods:
            avg_period = np.mean(holding_periods)
            logger.debug(f"Average holding period: {avg_period:.1f} minutes")
            return avg_period
        
        return 0.0
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics dictionary when no trades."""
        return {
            'total_return': 0.0,
            'total_return_pct': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_trades': 0,
            'final_capital': 0.0
        }

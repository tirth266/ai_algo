"""
Performance Metrics Module

Calculate comprehensive trading statistics and performance metrics.

Features:
- Return calculations
- Risk metrics
- Drawdown analysis
- Win/loss statistics
- Risk-adjusted returns

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Calculate trading performance metrics.
    
    Metrics include:
    - Total return
    - Win rate
    - Average win/loss
    - Sharpe ratio
    - Maximum drawdown
    - Profit factor
    
    Usage:
        >>> metrics = PerformanceMetrics()
        >>> results = metrics.calculate_all(equity_curve, trades)
    """
    
    def __init__(self, risk_free_rate: float = 0.06):
        """
        Initialize performance metrics calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 6%)
        
        Example:
            >>> calc = PerformanceMetrics(risk_free_rate=0.05)
        """
        self.risk_free_rate = risk_free_rate
        
        logger.info(
            f"PerformanceMetrics initialized "
            f"(risk-free rate: {risk_free_rate*100:.1f}%)"
        )
    
    def calculate_total_return(
        self,
        initial_capital: float,
        final_capital: float
    ) -> float:
        """
        Calculate total return percentage.
        
        Args:
            initial_capital: Starting capital
            final_capital: Ending capital
        
        Returns:
            Total return as percentage
        
        Example:
            >>> return_pct = calc.calculate_total_return(100000, 138400)
            >>> print(f"Total return: {return_pct:.2f}%")
            38.40%
        """
        if initial_capital <= 0:
            logger.warning("Invalid initial capital")
            return 0.0
        
        return ((final_capital - initial_capital) / initial_capital) * 100
    
    def calculate_win_rate(self, trades: List[Any]) -> float:
        """
        Calculate win rate percentage.
        
        Args:
            trades: List of closed trades
        
        Returns:
            Win rate as percentage
        
        Example:
            >>> win_rate = calc.calculate_win_rate(trades)
            >>> print(f"Win rate: {win_rate:.1f}%")
        """
        if not trades:
            return 0.0
        
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        
        return (len(winning_trades) / len(trades)) * 100
    
    def calculate_average_win(self, trades: List[Any]) -> float:
        """
        Calculate average profit on winning trades.
        
        Args:
            trades: List of closed trades
        
        Returns:
            Average winning amount
        
        Example:
            >>> avg_win = calc.calculate_average_win(trades)
        """
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        
        if not winning_trades:
            return 0.0
        
        return sum(t.pnl for t in winning_trades) / len(winning_trades)
    
    def calculate_average_loss(self, trades: List[Any]) -> float:
        """
        Calculate average loss on losing trades.
        
        Args:
            trades: List of closed trades
        
        Returns:
            Average losing amount (as positive number)
        """
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
        if not losing_trades:
            return 0.0
        
        return abs(sum(t.pnl for t in losing_trades) / len(losing_trades))
    
    def calculate_risk_reward_ratio(
        self,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate risk-reward ratio.
        
        Args:
            avg_win: Average win amount
            avg_loss: Average loss amount
        
        Returns:
            Risk-reward ratio (win/loss)
        
        Example:
            >>> rr = calc.calculate_risk_reward_ratio(1500, 750)
            >>> print(f"Risk-Reward: {rr:.2f}")
            2.00
        """
        if avg_loss == 0:
            return float('inf') if avg_win > 0 else 0.0
        
        return avg_win / avg_loss
    
    def calculate_profit_factor(self, trades: List[Any]) -> float:
        """
        Calculate profit factor (gross profit / gross loss).
        
        Args:
            trades: List of closed trades
        
        Returns:
            Profit factor
        
        Example:
            >>> pf = calc.calculate_profit_factor(trades)
            >>> print(f"Profit factor: {pf:.2f}")
            1.85
        """
        gross_profit = sum(t.pnl for t in trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl and t.pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown percentage.
        
        Args:
            equity_curve: Series of equity values
        
        Returns:
            Maximum drawdown as percentage
        
        Example:
            >>> mdd = calc.calculate_max_drawdown(equity)
            >>> print(f"Max DD: {mdd:.2f}%")
        """
        if len(equity_curve) == 0:
            return 0.0
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown at each point
        drawdown = (equity_curve - running_max) / running_max * 100
        
        # Return maximum drawdown (most negative value)
        max_dd = drawdown.min()
        
        return abs(max_dd)
    
    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sharpe ratio (risk-adjusted return).
        
        Args:
            returns: Series of period returns
            periods_per_year: Number of periods per year
                             (252 for daily, 12 for monthly)
        
        Returns:
            Annualized Sharpe ratio
        
        Example:
            >>> sharpe = calc.calculate_sharpe_ratio(daily_returns)
            >>> print(f"Sharpe: {sharpe:.2f}")
        """
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        
        # Calculate excess returns (over risk-free rate)
        daily_rf = self.risk_free_rate / periods_per_year
        excess_returns = returns - daily_rf
        
        # Calculate Sharpe ratio
        sharpe = excess_returns.mean() / excess_returns.std()
        
        # Annualize
        annualized_sharpe = sharpe * np.sqrt(periods_per_year)
        
        return annualized_sharpe
    
    def calculate_sortino_ratio(
        self,
        returns: pd.Series,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino ratio (downside risk-adjusted return).
        
        Args:
            returns: Series of period returns
            periods_per_year: Periods per year
        
        Returns:
            Annualized Sortino ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Separate downside returns (negative returns)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')  # No downside volatility
        
        # Calculate downside deviation
        daily_rf = self.risk_free_rate / periods_per_year
        excess_downside = downside_returns - daily_rf
        
        downside_deviation = np.sqrt((excess_downside ** 2).mean())
        
        if downside_deviation == 0:
            return float('inf')
        
        # Calculate Sortino ratio
        mean_return = returns.mean() - daily_rf
        sortino = mean_return / downside_deviation
        
        # Annualize
        annualized_sortino = sortino * np.sqrt(periods_per_year)
        
        return annualized_sortino
    
    def calculate_calmar_ratio(
        self,
        total_return: float,
        max_drawdown: float,
        years: float
    ) -> float:
        """
        Calculate Calmar ratio (return / max drawdown).
        
        Args:
            total_return: Total return percentage
            max_drawdown: Maximum drawdown percentage
            years: Time period in years
        
        Returns:
            Calmar ratio
        """
        if max_drawdown == 0 or years == 0:
            return 0.0
        
        # Annualized return
        annualized_return = total_return / years
        
        return annualized_return / max_drawdown
    
    def calculate_expectancy(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate trade expectancy (expected profit per trade).
        
        Args:
            win_rate: Win rate percentage
            avg_win: Average win amount
            avg_loss: Average loss amount
        
        Returns:
            Expectancy per trade
        
        Example:
            >>> exp = calc.calculate_expectancy(57, 1500, 750)
            >>> print(f"Expectancy: {exp:.2f} per trade")
        """
        win_prob = win_rate / 100
        loss_prob = 1 - win_prob
        
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)
        
        return expectancy
    
    def calculate_consecutive_losses(self, trades: List[Any]) -> int:
        """
        Calculate maximum consecutive losses.
        
        Args:
            trades: List of closed trades
        
        Returns:
            Maximum consecutive losses
        """
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.pnl and trade.pnl < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def calculate_all(
        self,
        initial_capital: float,
        final_capital: float,
        trades: List[Any],
        equity_curve: pd.Series = None,
        returns: pd.Series = None,
        years: float = 1.0
    ) -> Dict[str, Any]:
        """
        Calculate all performance metrics.
        
        Args:
            initial_capital: Starting capital
            final_capital: Ending capital
            trades: List of closed trades
            equity_curve: Series of equity values (optional)
            returns: Series of returns (optional)
            years: Time period in years
        
        Returns:
            Dictionary with all metrics
        
        Example:
            >>> results = calc.calculate_all(100000, 138400, trades)
            >>> for metric, value in results.items():
            ...     print(f"{metric}: {value}")
        """
        # Basic returns
        total_return = self.calculate_total_return(initial_capital, final_capital)
        
        # Trade statistics
        win_rate = self.calculate_win_rate(trades)
        avg_win = self.calculate_average_win(trades)
        avg_loss = self.calculate_average_loss(trades)
        risk_reward = self.calculate_risk_reward_ratio(avg_win, avg_loss)
        profit_factor = self.calculate_profit_factor(trades)
        
        # Advanced metrics
        max_drawdown = 0.0
        if equity_curve is not None:
            max_drawdown = self.calculate_max_drawdown(equity_curve)
        
        sharpe_ratio = 0.0
        if returns is not None:
            sharpe_ratio = self.calculate_sharpe_ratio(returns)
        
        sortino_ratio = 0.0
        if returns is not None:
            sortino_ratio = self.calculate_sortino_ratio(returns)
        
        calmar_ratio = self.calculate_calmar_ratio(
            total_return, max_drawdown, years
        )
        
        expectancy = self.calculate_expectancy(win_rate, avg_win, avg_loss)
        consecutive_losses = self.calculate_consecutive_losses(trades)
        
        # Compile results
        metrics = {
            'total_return': round(total_return, 2),
            'total_return_abs': round(final_capital - initial_capital, 2),
            'win_rate': round(win_rate, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'risk_reward_ratio': round(risk_reward, 2),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'sortino_ratio': round(sortino_ratio, 2),
            'calmar_ratio': round(calmar_ratio, 2),
            'expectancy': round(expectancy, 2),
            'consecutive_losses': consecutive_losses,
            'total_trades': len(trades)
        }
        
        logger.info(
            f"Performance metrics calculated: "
            f"Return={total_return:.2f}%, "
            f"WinRate={win_rate:.1f}%, "
            f"Sharpe={sharpe_ratio:.2f}"
        )
        
        return metrics

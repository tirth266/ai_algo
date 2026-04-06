"""
Portfolio Simulator Module

Simulate portfolio performance using optimized weights.

Features:
- Multi-asset equity curve
- Portfolio drawdown
- Portfolio Sharpe ratio
- Rebalancing logic (monthly, quarterly, yearly)

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PortfolioSimulator:
    """
    Simulate portfolio performance over time.
    
    Tracks equity curve, calculates drawdowns, and handles
    periodic rebalancing.
    
    Usage:
        >>> simulator = PortfolioSimulator(initial_capital=100000)
        >>> results = simulator.simulate(returns, weights, rebalance='monthly')
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        transaction_cost: float = 0.001,
        annualization_factor: int = 252
    ):
        """
        Initialize portfolio simulator.
        
        Args:
            initial_capital: Starting capital
            transaction_cost: Transaction cost as percentage (default: 0.1%)
            annualization_factor: Trading days per year
        
        Example:
            >>> sim = PortfolioSimulator(
            ...     initial_capital=500000,
            ...     transaction_cost=0.0005
            ... )
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.annualization_factor = annualization_factor
        
        logger.info(
            f"PortfolioSimulator initialized: "
            f"capital={initial_capital}, tx_cost={transaction_cost:.3%}"
        )
    
    def simulate(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
        rebalance: str = 'monthly',
        target_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Simulate portfolio performance with rebalancing.
        
        Args:
            returns: DataFrame with asset returns
            weights: Initial asset weights
            rebalance: Rebalancing frequency ('daily', 'monthly', 'quarterly', 'yearly')
            target_weights: Target weights for rebalancing (defaults to initial weights)
        
        Returns:
            Dictionary with simulation results
        
        Example:
            >>> results = simulator.simulate(returns, weights, rebalance='monthly')
            >>> print(f"Final capital: {results['final_capital']:.2f}")
        """
        if target_weights is None:
            target_weights = weights
        
        # Initialize tracking arrays
        n_periods = len(returns)
        equity_curve = np.zeros(n_periods)
        drawdowns = np.zeros(n_periods)
        
        # Current weights (will drift without rebalancing)
        current_weights = weights.copy()
        
        # Track capital
        capital = self.initial_capital
        
        # Rebalancing dates
        rebalance_dates = self._get_rebalance_dates(returns.index, rebalance)
        
        # Simulate period by period
        for i in range(n_periods):
            date = returns.index[i]
            
            # Calculate portfolio return for the period
            port_return = sum(current_weights[col] * returns.iloc[i][col] 
                            for col in returns.columns if col in current_weights)
            
            # Update capital
            capital *= (1 + port_return)
            
            # Record equity
            equity_curve[i] = capital
            
            # Calculate drawdown
            if i == 0:
                running_max = capital
            else:
                running_max = max(running_max, capital)
            
            drawdowns[i] = (capital - running_max) / running_max
            
            # Rebalance if needed
            if date in rebalance_dates and i < n_periods - 1:
                current_weights = self._rebalance(
                    current_weights,
                    target_weights,
                    returns.iloc[i],
                    capital
                )
        
        # Create results DataFrame
        results_df = pd.DataFrame({
            'equity': equity_curve,
            'drawdown': drawdowns,
            'capital': capital
        }, index=returns.index)
        
        # Calculate metrics
        metrics = self._calculate_metrics(results_df, returns)
        
        logger.info(f"Simulation completed: {n_periods} periods, final capital: {capital:.2f}")
        
        return {
            'equity_curve': results_df,
            'final_capital': capital,
            'metrics': metrics,
            'rebalance_dates': rebalance_dates
        }
    
    def _get_rebalance_dates(
        self,
        dates: pd.DatetimeIndex,
        frequency: str
    ) -> List[pd.Timestamp]:
        """Get list of rebalancing dates."""
        rebalance_dates = []
        
        if frequency == 'daily':
            return dates.tolist()
        
        elif frequency == 'monthly':
            # First trading day of each month
            current_month = None
            for date in dates:
                if date.month != current_month:
                    rebalance_dates.append(date)
                    current_month = date.month
        
        elif frequency == 'quarterly':
            # First trading day of each quarter
            current_quarter = None
            for date in dates:
                quarter = (date.month - 1) // 3
                if quarter != current_quarter:
                    rebalance_dates.append(date)
                    current_quarter = quarter
        
        elif frequency == 'yearly':
            # First trading day of each year
            current_year = None
            for date in dates:
                if date.year != current_year:
                    rebalance_dates.append(date)
                    current_year = date.year
        
        else:
            raise ValueError(f"Unknown rebalancing frequency: {frequency}")
        
        return rebalance_dates
    
    def _rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        current_returns: pd.Series,
        current_capital: float
    ) -> Dict[str, float]:
        """Rebalance portfolio to target weights."""
        # Update weights based on returns
        new_weights = {}
        total_value = 0
        
        for asset in current_weights:
            if asset in current_returns.index:
                old_value = current_weights[asset] * current_capital
                new_value = old_value * (1 + current_returns[asset])
                new_weights[asset] = new_value
                total_value += new_value
        
        # Normalize to sum to 1
        if total_value > 0:
            new_weights = {k: v / total_value for k, v in new_weights.items()}
        
        # Reset to target weights (simplified - assumes costless rebalancing)
        return target_weights.copy()
    
    def _calculate_metrics(
        self,
        results_df: pd.DataFrame,
        returns: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate portfolio performance metrics."""
        # Calculate daily returns from equity curve
        equity = results_df['equity']
        daily_returns = equity.pct_change().dropna()
        
        # Total return
        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        
        # Annualized return
        n_years = len(returns) / self.annualization_factor
        annualized_return = (equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1
        
        # Annualized volatility
        annualized_vol = daily_returns.std() * np.sqrt(self.annualization_factor)
        
        # Sharpe ratio (assuming risk-free rate embedded in returns)
        sharpe_ratio = annualized_return / annualized_vol if annualized_vol > 0 else 0
        
        # Maximum drawdown
        max_drawdown = abs(results_df['drawdown'].min())
        
        # Calmar ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'final_capital': results_df['capital'].iloc[-1],
            'n_periods': len(returns),
            'n_years': n_years
        }


def simulate_portfolio_performance(
    returns: pd.DataFrame,
    weights: Dict[str, float],
    initial_capital: float = 100000.0,
    rebalance: str = 'monthly'
) -> Dict[str, Any]:
    """
    Convenience function for portfolio simulation.
    
    Args:
        returns: DataFrame with asset returns
        weights: Asset weights dictionary
        initial_capital: Starting capital
        rebalance: Rebalancing frequency
    
    Returns:
        Simulation results dictionary
    
    Example:
        >>> results = simulate_portfolio_performance(returns, weights)
    """
    simulator = PortfolioSimulator(initial_capital=initial_capital)
    
    return simulator.simulate(returns, weights, rebalance=rebalance)

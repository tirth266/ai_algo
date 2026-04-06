"""
Monte Carlo Simulation Module for Strategy Robustness Testing

Performs Monte Carlo simulations on trade results to evaluate strategy robustness.

Features:
- Random trade order shuffling
- Bootstrap sampling
- Alternative equity curve simulation
- Return distribution analysis
- Worst-case drawdown estimation

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for trading strategy robustness testing.
    
    Simulates thousands of alternative equity curves by randomly
    shuffling and resampling historical trades.
    
    Usage:
        >>> simulator = MonteCarloSimulator(n_simulations=1000)
        >>> results = simulator.run_simulation(trades, initial_capital=100000)
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        confidence_levels: List[float] = None,
        random_seed: int = None
    ):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            n_simulations: Number of simulations to run (default: 1000)
            confidence_levels: Confidence levels for statistics (default: [0.90, 0.95, 0.99])
            random_seed: Random seed for reproducibility (optional)
        
        Example:
            >>> sim = MonteCarloSimulator(
            ...     n_simulations=5000,
            ...     confidence_levels=[0.90, 0.95, 0.99]
            ... )
        """
        self.n_simulations = n_simulations
        self.confidence_levels = confidence_levels or [0.90, 0.95, 0.99]
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        logger.info(
            f"MonteCarloSimulator initialized with {n_simulations} simulations"
        )
    
    def run_simulation(
        self,
        trades: List[Any],
        initial_capital: float = 100000.0,
        sampling_method: str = 'bootstrap'
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on trade sequence.
        
        Args:
            trades: List of trade objects with pnl attribute
            initial_capital: Starting capital (default: 100,000)
            sampling_method: Sampling method ('bootstrap', 'random_shuffle', 'block')
        
        Returns:
            Dictionary with simulation results:
            - simulated_equity_curves: Array of equity curves
            - return_distribution: Array of final returns
            - drawdown_distribution: Array of max drawdowns
            - probability_of_loss: Probability of losing money
            - median_return: Median return across simulations
            - worst_case_return: Worst case return (lowest percentile)
            - confidence_intervals: Dict of confidence intervals
        
        Example:
            >>> results = simulator.run_simulation(trades, initial_capital=100000)
            >>> print(f"Probability of loss: {results['probability_of_loss']:.2%}")
        """
        logger.info(
            f"Running Monte Carlo simulation: "
            f"{self.n_simulations} simulations, {sampling_method} sampling"
        )
        
        # Extract PnL from trades
        trade_pnls = np.array([t.pnl for t in trades if t.pnl is not None])
        
        if len(trade_pnls) == 0:
            logger.warning("No valid trades found")
            return self._empty_results()
        
        logger.debug(f"Analyzing {len(trade_pnls)} trades")
        
        # Run simulations based on method
        if sampling_method == 'bootstrap':
            equity_curves, returns, drawdowns = self._bootstrap_simulation(
                trade_pnls, initial_capital
            )
        elif sampling_method == 'random_shuffle':
            equity_curves, returns, drawdowns = self._shuffle_simulation(
                trade_pnls, initial_capital
            )
        elif sampling_method == 'block':
            equity_curves, returns, drawdowns = self._block_simulation(
                trade_pnls, initial_capital
            )
        else:
            raise ValueError(f"Unknown sampling method: {sampling_method}")
        
        # Calculate statistics
        results = self._calculate_statistics(
            equity_curves, returns, drawdowns, initial_capital
        )
        
        logger.info(
            f"Simulation complete: "
            f"Median return={results['median_return']:.2%}, "
            f"Prob(loss)={results['probability_of_loss']:.2%}"
        )
        
        return results
    
    def _bootstrap_simulation(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run bootstrap simulation (sampling with replacement).
        
        Args:
            trade_pnls: Array of trade PnL values
            initial_capital: Starting capital
        
        Returns:
            Tuple of (equity_curves, returns, drawdowns)
        """
        n_trades = len(trade_pnls)
        equity_curves = np.zeros((self.n_simulations, n_trades + 1))
        equity_curves[:, 0] = initial_capital
        
        returns = np.zeros(self.n_simulations)
        drawdowns = np.zeros(self.n_simulations)
        
        for i in range(self.n_simulations):
            # Sample with replacement
            sampled_indices = np.random.choice(n_trades, size=n_trades, replace=True)
            sampled_pnls = trade_pnls[sampled_indices]
            
            # Build equity curve
            equity_curve = initial_capital + np.cumsum(sampled_pnls)
            equity_curves[i, 1:] = equity_curve
            
            # Calculate return
            returns[i] = (equity_curve[-1] - initial_capital) / initial_capital
            
            # Calculate max drawdown
            drawdowns[i] = self._calculate_max_drawdown(equity_curve)
        
        return equity_curves, returns, drawdowns
    
    def _shuffle_simulation(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run random shuffle simulation (permutation without replacement).
        
        Args:
            trade_pnls: Array of trade PnL values
            initial_capital: Starting capital
        
        Returns:
            Tuple of (equity_curves, returns, drawdowns)
        """
        n_trades = len(trade_pnls)
        equity_curves = np.zeros((self.n_simulations, n_trades + 1))
        equity_curves[:, 0] = initial_capital
        
        returns = np.zeros(self.n_simulations)
        drawdowns = np.zeros(self.n_simulations)
        
        for i in range(self.n_simulations):
            # Shuffle without replacement
            shuffled_indices = np.random.permutation(n_trades)
            shuffled_pnls = trade_pnls[shuffled_indices]
            
            # Build equity curve
            equity_curve = initial_capital + np.cumsum(shuffled_pnls)
            equity_curves[i, 1:] = equity_curve
            
            # Calculate return
            returns[i] = (equity_curve[-1] - initial_capital) / initial_capital
            
            # Calculate max drawdown
            drawdowns[i] = self._calculate_max_drawdown(equity_curve)
        
        return equity_curves, returns, drawdowns
    
    def _block_simulation(
        self,
        trade_pnls: np.ndarray,
        initial_capital: float,
        block_size: int = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run block bootstrap simulation (preserve autocorrelation).
        
        Args:
            trade_pnls: Array of trade PnL values
            initial_capital: Starting capital
            block_size: Size of blocks (default: sqrt(n_trades))
        
        Returns:
            Tuple of (equity_curves, returns, drawdowns)
        """
        n_trades = len(trade_pnls)
        block_size = block_size or int(np.sqrt(n_trades))
        
        equity_curves = np.zeros((self.n_simulations, n_trades + 1))
        equity_curves[:, 0] = initial_capital
        
        returns = np.zeros(self.n_simulations)
        drawdowns = np.zeros(self.n_simulations)
        
        for i in range(self.n_simulations):
            # Create blocks
            blocks = []
            for start in range(0, n_trades, block_size):
                end = min(start + block_size, n_trades)
                blocks.append(trade_pnls[start:end])
            
            # Shuffle blocks
            np.random.shuffle(blocks)
            
            # Concatenate and trim to original length
            shuffled_pnls = np.concatenate(blocks)[:n_trades]
            
            # Build equity curve
            equity_curve = initial_capital + np.cumsum(shuffled_pnls)
            equity_curves[i, 1:] = equity_curve
            
            # Calculate return
            returns[i] = (equity_curve[-1] - initial_capital) / initial_capital
            
            # Calculate max drawdown
            drawdowns[i] = self._calculate_max_drawdown(equity_curve)
        
        return equity_curves, returns, drawdowns
    
    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> float:
        """
        Calculate maximum drawdown percentage from equity curve.
        
        Args:
            equity_curve: Array of equity values
        
        Returns:
            Maximum drawdown as percentage
        """
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max * 100
        return abs(np.min(drawdown))
    
    def _calculate_statistics(
        self,
        equity_curves: np.ndarray,
        returns: np.ndarray,
        drawdowns: np.ndarray,
        initial_capital: float
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics from simulation results.
        
        Args:
            equity_curves: Array of simulated equity curves
            returns: Array of final returns
            drawdowns: Array of max drawdowns
            initial_capital: Starting capital
        
        Returns:
            Dictionary with all statistics
        """
        # Basic statistics
        median_return = np.median(returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Probability of loss
        probability_of_loss = np.mean(returns < 0)
        
        # Percentiles
        percentiles = {}
        for cl in self.confidence_levels:
            percentile = np.percentile(returns, (1 - cl) * 100)
            percentiles[f"{int(cl*100)}pct_worst_case"] = percentile
        
        # Drawdown statistics
        median_drawdown = np.median(drawdowns)
        mean_drawdown = np.mean(drawdowns)
        worst_drawdown = np.max(drawdowns)
        
        # Confidence intervals for drawdowns
        drawdown_percentiles = {}
        for cl in self.confidence_levels:
            percentile = np.percentile(drawdowns, cl * 100)
            drawdown_percentiles[f"{int(cl*100)}pct_drawdown"] = percentile
        
        # Best and worst cases
        best_case_return = np.max(returns)
        worst_case_return = np.min(returns)
        
        # Success rate
        success_rate = np.mean(returns > 0)
        
        return {
            'simulated_equity_curves': equity_curves,
            'return_distribution': returns,
            'drawdown_distribution': drawdowns,
            'median_return': median_return,
            'mean_return': mean_return,
            'std_return': std_return,
            'probability_of_loss': probability_of_loss,
            'success_rate': success_rate,
            'best_case_return': best_case_return,
            'worst_case_return': worst_case_return,
            'percentiles': percentiles,
            'median_drawdown': median_drawdown,
            'mean_drawdown': mean_drawdown,
            'worst_drawdown': worst_drawdown,
            'drawdown_percentiles': drawdown_percentiles,
            'n_simulations': self.n_simulations,
            'initial_capital': initial_capital
        }
    
    def _empty_results(self) -> Dict[str, Any]:
        """Return empty results dictionary when no trades available."""
        return {
            'simulated_equity_curves': np.array([]),
            'return_distribution': np.array([]),
            'drawdown_distribution': np.array([]),
            'median_return': 0.0,
            'mean_return': 0.0,
            'std_return': 0.0,
            'probability_of_loss': 0.0,
            'success_rate': 0.0,
            'best_case_return': 0.0,
            'worst_case_return': 0.0,
            'percentiles': {},
            'median_drawdown': 0.0,
            'mean_drawdown': 0.0,
            'worst_drawdown': 0.0,
            'drawdown_percentiles': {},
            'n_simulations': self.n_simulations,
            'error': 'No valid trades to simulate'
        }
    
    def get_confidence_interval(
        self,
        distribution: np.ndarray,
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for a distribution.
        
        Args:
            distribution: Array of values
            confidence_level: Confidence level (default: 0.95)
        
        Returns:
            Tuple of (lower_bound, upper_bound)
        
        Example:
            >>> ci = simulator.get_confidence_interval(returns, 0.95)
            >>> print(f"95% CI: {ci[0]:.2%} to {ci[1]:.2%}")
        """
        alpha = 1 - confidence_level
        lower = np.percentile(distribution, alpha / 2 * 100)
        upper = np.percentile(distribution, (1 - alpha / 2) * 100)
        return lower, upper


def run_monte_carlo(
    trades: List[Any],
    n_simulations: int = 1000,
    initial_capital: float = 100000.0,
    sampling_method: str = 'bootstrap',
    confidence_levels: List[float] = None,
    random_seed: int = None
) -> Dict[str, Any]:
    """
    Convenience function to run Monte Carlo simulation.
    
    Args:
        trades: List of trade objects
        n_simulations: Number of simulations (default: 1000)
        initial_capital: Starting capital (default: 100,000)
        sampling_method: Sampling method ('bootstrap', 'random_shuffle', 'block')
        confidence_levels: Confidence levels for statistics
        random_seed: Random seed for reproducibility
    
    Returns:
        Dictionary with simulation results
    
    Example:
        >>> results = run_monte_carlo(trades, n_simulations=5000)
        >>> print(f"Median return: {results['median_return']:.2%}")
    """
    simulator = MonteCarloSimulator(
        n_simulations=n_simulations,
        confidence_levels=confidence_levels,
        random_seed=random_seed
    )
    
    return simulator.run_simulation(
        trades=trades,
        initial_capital=initial_capital,
        sampling_method=sampling_method
    )

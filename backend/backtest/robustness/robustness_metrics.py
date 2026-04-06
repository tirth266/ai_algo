"""
Robustness Metrics Module

Calculate comprehensive robustness statistics for trading strategies.

Metrics:
- Probability of ruin
- Expected drawdown
- Return stability
- Equity volatility
- Robustness score

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class RobustnessMetrics:
    """
    Calculate robustness metrics for trading strategies.
    
    Evaluates strategy stability and reliability across different
    market conditions and trade sequences.
    
    Usage:
        >>> calculator = RobustnessMetrics()
        >>> metrics = calculator.calculate_all(equity_curves, trades)
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize robustness metrics calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 2%)
        
        Example:
            >>> calc = RobustnessMetrics(risk_free_rate=0.03)
        """
        self.risk_free_rate = risk_free_rate
        
        logger.info(
            f"RobustnessMetrics initialized "
            f"(risk-free rate: {risk_free_rate*100:.1f}%)"
        )
    
    def calculate_probability_of_ruin(
        self,
        equity_curves: np.ndarray,
        ruin_threshold: float = 0.50
    ) -> float:
        """
        Calculate probability of ruin (losing X% of initial capital).
        
        Args:
            equity_curves: Array of equity curves (n_simulations x n_periods)
            ruin_threshold: Drawdown threshold for ruin (default: 50%)
        
        Returns:
            Probability of ruin as decimal
        
        Example:
            >>> prob_ruin = calc.calculate_probability_of_ruin(equity_curves)
            >>> print(f"Probability of ruin: {prob_ruin:.2%}")
        """
        if len(equity_curves) == 0:
            return 0.0
        
        initial_capital = equity_curves[0, 0]
        
        # Calculate maximum drawdown for each simulation
        max_drawdowns = []
        
        for curve in equity_curves:
            running_max = np.maximum.accumulate(curve)
            drawdown = (curve - running_max) / running_max
            max_dd = np.min(drawdown)
            max_drawdowns.append(max_dd)
        
        max_drawdowns = np.array(max_drawdowns)
        
        # Probability of exceeding ruin threshold
        prob_ruin = np.mean(max_drawdowns < -ruin_threshold)
        
        logger.debug(f"Probability of ruin calculated: {prob_ruin:.4f}")
        
        return prob_ruin
    
    def calculate_expected_drawdown(
        self,
        equity_curves: np.ndarray
    ) -> float:
        """
        Calculate expected (average) maximum drawdown.
        
        Args:
            equity_curves: Array of equity curves
        
        Returns:
            Expected maximum drawdown as percentage
        
        Example:
            >>> exp_dd = calc.calculate_expected_drawdown(equity_curves)
            >>> print(f"Expected drawdown: {exp_dd:.2f}%")
        """
        if len(equity_curves) == 0:
            return 0.0
        
        max_drawdowns = []
        
        for curve in equity_curves:
            running_max = np.maximum.accumulate(curve)
            drawdown = (curve - running_max) / running_max * 100
            max_dd = abs(np.min(drawdown))
            max_drawdowns.append(max_dd)
        
        expected_dd = np.mean(max_drawdowns)
        
        logger.debug(f"Expected drawdown calculated: {expected_dd:.2f}%")
        
        return expected_dd
    
    def calculate_return_stability(
        self,
        returns: np.ndarray
    ) -> float:
        """
        Calculate return stability score (inverse of coefficient of variation).
        
        Higher score indicates more stable returns.
        
        Args:
            returns: Array of returns from simulations
        
        Returns:
            Stability score (0 to infinity, higher is better)
        
        Example:
            >>> stability = calc.calculate_return_stability(returns)
            >>> print(f"Return stability: {stability:.2f}")
        """
        if len(returns) == 0 or np.mean(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Coefficient of variation
        cv = std_return / abs(mean_return)
        
        # Stability score (inverse of CV)
        stability = 1.0 / (1.0 + cv)
        
        logger.debug(f"Return stability calculated: {stability:.4f}")
        
        return stability
    
    def calculate_equity_volatility(
        self,
        equity_curves: np.ndarray
    ) -> float:
        """
        Calculate average equity curve volatility.
        
        Args:
            equity_curves: Array of equity curves
        
        Returns:
            Average volatility across all simulations
        
        Example:
            >>> vol = calc.calculate_equity_volatility(equity_curves)
            >>> print(f"Equity volatility: {vol:.4f}")
        """
        if len(equity_curves) == 0:
            return 0.0
        
        volatilities = []
        
        for curve in equity_curves:
            # Calculate returns
            returns = np.diff(curve) / curve[:-1]
            
            # Annualized volatility (assuming daily returns)
            volatility = np.std(returns) * np.sqrt(252)
            volatilities.append(volatility)
        
        avg_volatility = np.mean(volatilities)
        
        logger.debug(f"Equity volatility calculated: {avg_volatility:.4f}")
        
        return avg_volatility
    
    def calculate_robustness_score(
        self,
        probability_of_loss: float,
        expected_drawdown: float,
        return_stability: float,
        success_rate: float,
        weights: Dict[str, float] = None
    ) -> float:
        """
        Calculate overall robustness score (0-100 scale).
        
        Args:
            probability_of_loss: Probability of losing money
            expected_drawdown: Expected maximum drawdown (%)
            return_stability: Return stability score
            success_rate: Success rate (win percentage)
            weights: Metric weights (optional)
        
        Returns:
            Robustness score (0-100)
        
        Example:
            >>> score = calc.calculate_robustness_score(
            ...     prob_loss, exp_dd, stability, success_rate
            ... )
            >>> print(f"Robustness score: {score:.1f}/100")
        """
        # Default weights
        if weights is None:
            weights = {
                'probability_of_loss': 0.30,
                'expected_drawdown': 0.25,
                'return_stability': 0.25,
                'success_rate': 0.20
            }
        
        # Normalize metrics to 0-1 scale (higher is better)
        norm_prob_loss = 1.0 - min(probability_of_loss, 1.0)
        norm_drawdown = 1.0 - min(expected_drawdown / 100.0, 1.0)
        norm_stability = min(return_stability, 1.0)
        norm_success = min(success_rate, 1.0)
        
        # Weighted average
        score = (
            weights['probability_of_loss'] * norm_prob_loss +
            weights['expected_drawdown'] * norm_drawdown +
            weights['return_stability'] * norm_stability +
            weights['success_rate'] * norm_success
        )
        
        # Scale to 0-100
        score = score * 100
        
        logger.info(f"Robustness score calculated: {score:.1f}/100")
        
        return score
    
    def calculate_value_at_risk(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk (VaR) at given confidence level.
        
        Args:
            returns: Array of returns
            confidence_level: Confidence level (default: 0.95)
        
        Returns:
            VaR as positive percentage
        
        Example:
            >>> var = calc.calculate_value_at_risk(returns, 0.99)
            >>> print(f"99% VaR: {var:.2f}%")
        """
        if len(returns) == 0:
            return 0.0
        
        var = abs(np.percentile(returns, (1 - confidence_level) * 100))
        
        logger.debug(
            f"{int(confidence_level*100)}% VaR calculated: {var:.4f}"
        )
        
        return var
    
    def calculate_conditional_var(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).
        
        Average loss in worst (1-confidence_level)% of cases.
        
        Args:
            returns: Array of returns
            confidence_level: Confidence level (default: 0.95)
        
        Returns:
            CVaR as positive percentage
        
        Example:
            >>> cvar = calc.calculate_conditional_var(returns, 0.95)
            >>> print(f"95% CVaR: {cvar:.2f}%")
        """
        if len(returns) == 0:
            return 0.0
        
        var = np.percentile(returns, (1 - confidence_level) * 100)
        cvar = abs(np.mean(returns[returns <= var]))
        
        logger.debug(
            f"{int(confidence_level*100)}% CVaR calculated: {cvar:.4f}"
        )
        
        return cvar
    
    def calculate_calmar_ratio(
        self,
        annualized_return: float,
        max_drawdown: float
    ) -> float:
        """
        Calculate Calmar ratio (return / max drawdown).
        
        Args:
            annualized_return: Annualized return
            max_drawdown: Maximum drawdown (as positive percentage)
        
        Returns:
            Calmar ratio
        
        Example:
            >>> calmar = calc.calculate_calmar_ratio(0.15, 0.25)
            >>> print(f"Calmar ratio: {calmar:.2f}")
        """
        if max_drawdown == 0:
            return float('inf') if annualized_return > 0 else 0.0
        
        calmar = annualized_return / max_drawdown
        
        logger.debug(f"Calmar ratio calculated: {calmar:.2f}")
        
        return calmar
    
    def calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        target_return: float = 0.0
    ) -> float:
        """
        Calculate Sortino ratio (downside risk-adjusted return).
        
        Args:
            returns: Array of returns
            target_return: Target return (default: 0)
        
        Returns:
            Sortino ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Separate downside returns
        downside_returns = returns[returns < target_return]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        # Calculate downside deviation
        downside_deviation = np.sqrt(np.mean((downside_returns - target_return) ** 2))
        
        if downside_deviation == 0:
            return float('inf')
        
        # Calculate Sortino ratio
        mean_return = np.mean(returns)
        sortino = (mean_return - target_return) / downside_deviation
        
        logger.debug(f"Sortino ratio calculated: {sortino:.2f}")
        
        return sortino
    
    def calculate_all(
        self,
        equity_curves: np.ndarray,
        returns: np.ndarray,
        success_rate: float
    ) -> Dict[str, Any]:
        """
        Calculate all robustness metrics.
        
        Args:
            equity_curves: Array of equity curves
            returns: Array of returns
            success_rate: Success rate (win percentage)
        
        Returns:
            Dictionary with all metrics
        
        Example:
            >>> metrics = calc.calculate_all(equity_curves, returns, 0.65)
            >>> for metric, value in metrics.items():
            ...     print(f"{metric}: {value}")
        """
        logger.info("Calculating all robustness metrics")
        
        # Basic metrics
        prob_ruin = self.calculate_probability_of_ruin(equity_curves)
        exp_drawdown = self.calculate_expected_drawdown(equity_curves)
        return_stability = self.calculate_return_stability(returns)
        equity_volatility = self.calculate_equity_volatility(equity_curves)
        
        # Risk metrics
        var_95 = self.calculate_value_at_risk(returns, 0.95)
        cvar_95 = self.calculate_conditional_var(returns, 0.95)
        var_99 = self.calculate_value_at_risk(returns, 0.99)
        cvar_99 = self.calculate_conditional_var(returns, 0.99)
        
        # Probability of loss
        prob_loss = np.mean(returns < 0)
        
        # Robustness score
        robustness_score = self.calculate_robustness_score(
            probability_of_loss=prob_loss,
            expected_drawdown=exp_drawdown,
            return_stability=return_stability,
            success_rate=success_rate
        )
        
        # Additional statistics
        median_return = np.median(returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Compile results
        metrics = {
            'probability_of_ruin': prob_ruin,
            'expected_drawdown': exp_drawdown,
            'return_stability': return_stability,
            'equity_volatility': equity_volatility,
            'robustness_score': robustness_score,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'var_99': var_99,
            'cvar_99': cvar_99,
            'probability_of_loss': prob_loss,
            'median_return': median_return,
            'mean_return': mean_return,
            'std_return': std_return,
            'success_rate': success_rate
        }
        
        logger.info(
            f"Robustness metrics calculated: "
            f"Score={robustness_score:.1f}/100, "
            f"Prob(loss)={prob_loss:.2%}"
        )
        
        return metrics

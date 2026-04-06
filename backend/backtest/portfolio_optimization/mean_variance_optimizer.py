"""
Mean-Variance Optimizer Module

Implement Modern Portfolio Theory (MPT) optimization.

Methods:
- Maximum Sharpe Ratio Portfolio
- Minimum Volatility Portfolio
- Equal Risk Contribution
- Maximum Return Portfolio

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer:
    """
    Optimize portfolio weights using Modern Portfolio Theory.
    
    Implements various optimization objectives including maximum Sharpe ratio,
    minimum volatility, and equal risk contribution.
    
    Usage:
        >>> optimizer = MeanVarianceOptimizer()
        >>> weights = optimizer.optimize_max_sharpe(returns, cov_matrix)
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        annualization_factor: int = 252,
        max_iterations: int = 1000
    ):
        """
        Initialize mean-variance optimizer.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 5%)
            annualization_factor: Trading days per year
            max_iterations: Maximum optimization iterations
        
        Example:
            >>> optimizer = MeanVarianceOptimizer(
            ...     risk_free_rate=0.03,
            ...     max_iterations=500
            ... )
        """
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.max_iterations = max_iterations
        
        logger.info(
            f"MeanVarianceOptimizer initialized: "
            f"risk_free_rate={risk_free_rate:.2%}"
        )
    
    def optimize_max_sharpe(
        self,
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Find portfolio weights that maximize Sharpe ratio.
        
        Args:
            returns: DataFrame with asset returns
            cov_matrix: Covariance matrix of returns
            constraints: Additional constraints (optional)
                       Example: {'min_weight': 0.0, 'max_weight': 1.0}
        
        Returns:
            Dictionary of optimal asset weights
        
        Example:
            >>> weights = optimizer.optimize_max_sharpe(returns, cov_matrix)
            >>> print(f"AAPL weight: {weights['AAPL']:.2%}")
        """
        n_assets = len(returns.columns)
        
        # Expected returns (annualized)
        expected_returns = returns.mean() * self.annualization_factor
        
        # Objective function (negative Sharpe ratio)
        def negative_sharpe(weights):
            port_return = np.sum(expected_returns * weights)
            port_volatility = np.sqrt(weights.T @ cov_matrix.values @ weights)
            sharpe = (port_return - self.risk_free_rate) / port_volatility
            return -sharpe  # Minimize negative Sharpe
        
        # Constraints
        constraints_list = self._create_constraints(n_assets, constraints)
        
        # Bounds
        bounds = self._create_bounds(n_assets, constraints)
        
        # Initial guess (equal weights)
        init_weights = np.array([1.0 / n_assets] * n_assets)
        
        # Optimize
        result = minimize(
            negative_sharpe,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'maxiter': self.max_iterations}
        )
        
        if not result.success:
            logger.warning(f"Optimization may not have converged: {result.message}")
        
        # Extract optimal weights
        optimal_weights = result.x
        asset_names = returns.columns.tolist()
        
        weights_dict = dict(zip(asset_names, optimal_weights))
        
        logger.info(f"Max Sharpe optimization completed")
        logger.info(f"Optimal Sharpe Ratio: {-result.fun:.4f}")
        
        return weights_dict
    
    def optimize_min_volatility(
        self,
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Find portfolio weights that minimize volatility.
        
        Args:
            returns: DataFrame with asset returns
            cov_matrix: Covariance matrix of returns
            constraints: Additional constraints (optional)
        
        Returns:
            Dictionary of optimal asset weights
        
        Example:
            >>> weights = optimizer.optimize_min_volatility(returns, cov_matrix)
        """
        n_assets = len(returns.columns)
        
        # Objective function (variance)
        def portfolio_variance(weights):
            return weights.T @ cov_matrix.values @ weights
        
        # Constraints
        constraints_list = self._create_constraints(n_assets, constraints)
        
        # Bounds
        bounds = self._create_bounds(n_assets, constraints)
        
        # Initial guess
        init_weights = np.array([1.0 / n_assets] * n_assets)
        
        # Optimize
        result = minimize(
            portfolio_variance,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'maxiter': self.max_iterations}
        )
        
        if not result.success:
            logger.warning(f"Optimization may not have converged: {result.message}")
        
        # Extract optimal weights
        optimal_weights = result.x
        asset_names = returns.columns.tolist()
        
        weights_dict = dict(zip(asset_names, optimal_weights))
        
        port_volatility = np.sqrt(result.fun) * 100
        logger.info(f"Min Volatility optimization completed")
        logger.info(f"Optimal Volatility: {port_volatility:.2f}%")
        
        return weights_dict
    
    def optimize_equal_risk_contribution(
        self,
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Find portfolio weights with equal risk contribution from each asset.
        
        Args:
            returns: DataFrame with asset returns
            cov_matrix: Covariance matrix of returns
        
        Returns:
            Dictionary of asset weights
        
        Example:
            >>> weights = optimizer.optimize_equal_risk_contribution(returns, cov_matrix)
        """
        n_assets = len(returns.columns)
        
        # Risk contribution objective
        def risk_contribution_objective(weights):
            # Portfolio variance
            port_variance = weights.T @ cov_matrix.values @ weights
            port_volatility = np.sqrt(port_variance)
            
            # Marginal risk contribution
            marginal_risk = (cov_matrix.values @ weights) / port_volatility
            
            # Risk contribution
            risk_contrib = weights * marginal_risk
            
            # Target: equal risk contribution (1/n for each asset)
            target_risk = port_volatility / n_assets
            
            # Sum of squared differences
            objective = np.sum((risk_contrib - target_risk) ** 2)
            
            return objective
        
        # Constraints (weights sum to 1)
        constraints = ({
            'type': 'eq',
            'fun': lambda x: np.sum(x) - 1.0
        })
        
        # Bounds (long-only)
        bounds = tuple((0.0, 1.0) for _ in range(n_assets))
        
        # Initial guess
        init_weights = np.array([1.0 / n_assets] * n_assets)
        
        # Optimize
        result = minimize(
            risk_contribution_objective,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': self.max_iterations}
        )
        
        if not result.success:
            logger.warning(f"Optimization may not have converged: {result.message}")
        
        # Extract weights
        optimal_weights = result.x
        asset_names = returns.columns.tolist()
        
        weights_dict = dict(zip(asset_names, optimal_weights))
        
        logger.info(f"Equal Risk Contribution optimization completed")
        
        return weights_dict
    
    def optimize_target_return(
        self,
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame,
        target_return: float,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Find minimum volatility portfolio for a target return.
        
        Args:
            returns: DataFrame with asset returns
            cov_matrix: Covariance matrix of returns
            target_return: Target annualized return
            constraints: Additional constraints (optional)
        
        Returns:
            Dictionary of asset weights
        
        Example:
            >>> weights = optimizer.optimize_target_return(returns, cov_matrix, target_return=0.15)
        """
        n_assets = len(returns.columns)
        
        # Expected returns (annualized)
        expected_returns = returns.mean() * self.annualization_factor
        
        # Objective function (variance)
        def portfolio_variance(weights):
            return weights.T @ cov_matrix.values @ weights
        
        # Constraints
        constraints_list = self._create_constraints(n_assets, constraints)
        
        # Add target return constraint
        constraints_list.append({
            'type': 'eq',
            'fun': lambda w: np.sum(expected_returns * w) - target_return
        })
        
        # Bounds
        bounds = self._create_bounds(n_assets, constraints)
        
        # Initial guess
        init_weights = np.array([1.0 / n_assets] * n_assets)
        
        # Optimize
        result = minimize(
            portfolio_variance,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'maxiter': self.max_iterations}
        )
        
        if not result.success:
            logger.warning(f"Optimization may not have converged: {result.message}")
        
        # Extract weights
        optimal_weights = result.x
        asset_names = returns.columns.tolist()
        
        weights_dict = dict(zip(asset_names, optimal_weights))
        
        logger.info(f"Target Return ({target_return:.2%}) optimization completed")
        
        return weights_dict
    
    def _create_constraints(
        self,
        n_assets: int,
        custom_constraints: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Create optimization constraints."""
        # Default constraint: weights sum to 1
        constraints = [{
            'type': 'eq',
            'fun': lambda x: np.sum(x) - 1.0
        }]
        
        # Add custom constraints if provided
        if custom_constraints:
            if 'min_portfolio_return' in custom_constraints:
                constraints.append({
                    'type': 'ineq',
                    'fun': lambda w: np.sum(self.expected_returns * w) - custom_constraints['min_portfolio_return']
                })
        
        return constraints
    
    def _create_bounds(
        self,
        n_assets: int,
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[float, float]]:
        """Create optimization bounds."""
        if constraints and 'min_weight' in constraints and 'max_weight' in constraints:
            min_w = constraints['min_weight']
            max_w = constraints['max_weight']
            return [(min_w, max_w) for _ in range(n_assets)]
        
        # Default: long-only (0 to 1)
        return [(0.0, 1.0) for _ in range(n_assets)]
    
    def calculate_portfolio_metrics(
        self,
        weights: Dict[str, float],
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate portfolio performance metrics.
        
        Args:
            weights: Asset weights dictionary
            returns: DataFrame with asset returns
            cov_matrix: Covariance matrix
        
        Returns:
            Dictionary with portfolio metrics
        
        Example:
            >>> metrics = optimizer.calculate_portfolio_metrics(weights, returns, cov_matrix)
            >>> print(f"Portfolio Sharpe: {metrics['sharpe_ratio']:.2f}")
        """
        # Convert weights to array
        weight_array = np.array([weights[col] for col in returns.columns])
        
        # Expected returns (annualized)
        expected_returns = returns.mean() * self.annualization_factor
        
        # Portfolio return
        port_return = np.sum(expected_returns * weight_array)
        
        # Portfolio volatility
        port_volatility = np.sqrt(weight_array.T @ cov_matrix.values @ weight_array)
        
        # Sharpe ratio
        sharpe_ratio = (port_return - self.risk_free_rate) / port_volatility
        
        return {
            'expected_return': port_return,
            'volatility': port_volatility,
            'sharpe_ratio': sharpe_ratio,
            'risk_free_rate': self.risk_free_rate
        }


def optimize_portfolio(
    returns: pd.DataFrame,
    method: str = 'max_sharpe',
    risk_free_rate: float = 0.05,
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function for portfolio optimization.
    
    Args:
        returns: DataFrame with asset returns
        method: Optimization method ('max_sharpe', 'min_volatility', 'erc')
        risk_free_rate: Annual risk-free rate
        constraints: Additional constraints
    
    Returns:
        Dictionary with weights and metrics
    
    Example:
        >>> results = optimize_portfolio(returns, method='max_sharpe')
        >>> print(f"Optimal weights: {results['weights']}")
    """
    # Create calculator for covariance
    from .portfolio_returns import PortfolioReturnsCalculator
    
    calc = PortfolioReturnsCalculator()
    cov_matrix = calc.build_covariance_matrix(returns)
    
    # Create optimizer
    optimizer = MeanVarianceOptimizer(risk_free_rate=risk_free_rate)
    
    # Run optimization based on method
    if method == 'max_sharpe':
        weights = optimizer.optimize_max_sharpe(returns, cov_matrix, constraints)
    elif method == 'min_volatility':
        weights = optimizer.optimize_min_volatility(returns, cov_matrix, constraints)
    elif method == 'erc' or method == 'equal_risk_contribution':
        weights = optimizer.optimize_equal_risk_contribution(returns, cov_matrix)
    else:
        raise ValueError(f"Unknown optimization method: {method}")
    
    # Calculate metrics
    metrics = optimizer.calculate_portfolio_metrics(weights, returns, cov_matrix)
    
    return {
        'weights': weights,
        'metrics': metrics,
        'method': method,
        'risk_free_rate': risk_free_rate
    }

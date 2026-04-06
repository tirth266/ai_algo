"""
Portfolio Risk Models Module

Calculate comprehensive portfolio risk metrics.

Metrics:
- Portfolio volatility
- Value at Risk (VaR)
- Conditional Value at Risk (CVaR)
- Correlation matrix
- Diversification ratio

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
from scipy import stats

logger = logging.getLogger(__name__)


class PortfolioRiskCalculator:
    """
    Calculate portfolio risk metrics.
    
    Provides comprehensive risk analysis including VaR, CVaR,
    correlation analysis, and diversification measures.
    
    Usage:
        >>> risk_calc = PortfolioRiskCalculator()
        >>> var = risk_calc.calculate_var(returns, weights, confidence=0.95)
    """
    
    def __init__(
        self,
        confidence_levels: List[float] = None,
        annualization_factor: int = 252
    ):
        """
        Initialize portfolio risk calculator.
        
        Args:
            confidence_levels: Confidence levels for VaR/CVaR (default: [0.90, 0.95, 0.99])
            annualization_factor: Trading days per year
        
        Example:
            >>> risk_calc = PortfolioRiskCalculator(
            ...     confidence_levels=[0.95, 0.99]
            ... )
        """
        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]
        
        self.confidence_levels = confidence_levels
        self.annualization_factor = annualization_factor
        
        logger.info(f"PortfolioRiskCalculator initialized")
    
    def calculate_portfolio_volatility(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
        cov_matrix: Optional[pd.DataFrame] = None
    ) -> float:
        """
        Calculate portfolio volatility (standard deviation).
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
            cov_matrix: Pre-computed covariance matrix (optional)
        
        Returns:
            Annualized portfolio volatility
        
        Example:
            >>> vol = risk_calc.calculate_portfolio_volatility(returns, weights)
            >>> print(f"Portfolio volatility: {vol:.2%}")
        """
        if cov_matrix is None:
            cov_matrix = returns.cov() * self.annualization_factor
        
        weight_array = np.array([weights[col] for col in returns.columns])
        
        # Portfolio variance
        port_variance = weight_array.T @ cov_matrix.values @ weight_array
        
        # Portfolio volatility
        port_volatility = np.sqrt(port_variance)
        
        return port_volatility
    
    def calculate_value_at_risk(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
        confidence: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
            confidence: Confidence level (e.g., 0.95 for 95% VaR)
            method: Calculation method ('historical', 'parametric')
        
        Returns:
            VaR as positive number (loss)
        
        Example:
            >>> var_95 = risk_calc.calculate_value_at_risk(returns, weights, confidence=0.95)
            >>> print(f"95% VaR: {var_95:.2%}")
        """
        # Calculate portfolio returns
        port_returns = self._calculate_portfolio_returns(returns, weights)
        
        if method == 'historical':
            # Historical VaR
            var = -np.percentile(port_returns, (1 - confidence) * 100)
        
        elif method == 'parametric':
            # Parametric VaR (assuming normal distribution)
            mean_return = port_returns.mean()
            std_return = port_returns.std()
            var = -(mean_return + std_return * stats.norm.ppf(1 - confidence))
        
        else:
            raise ValueError(f"Unknown VaR method: {method}")
        
        return var
    
    def calculate_conditional_var(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
        confidence: float = 0.95,
        var_threshold: Optional[float] = None
    ) -> float:
        """
        Calculate Conditional Value at Risk (CVaR / Expected Shortfall).
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
            confidence: Confidence level
            var_threshold: Pre-computed VaR (optional)
        
        Returns:
            CVaR as positive number (expected loss beyond VaR)
        
        Example:
            >>> cvar = risk_calc.calculate_conditional_var(returns, weights, confidence=0.95)
        """
        # Calculate portfolio returns
        port_returns = self._calculate_portfolio_returns(returns, weights)
        
        # Get VaR threshold if not provided
        if var_threshold is None:
            var_threshold = -self.calculate_value_at_risk(returns, weights, confidence)
        
        # CVaR: average of returns below VaR
        tail_returns = port_returns[port_returns <= var_threshold]
        cvar = -tail_returns.mean()
        
        return cvar
    
    def build_correlation_matrix(
        self,
        returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Build correlation matrix from returns.
        
        Args:
            returns: DataFrame with asset returns
        
        Returns:
            Correlation matrix as DataFrame
        
        Example:
            >>> corr_matrix = risk_calc.build_correlation_matrix(returns)
        """
        corr_matrix = returns.corr()
        
        logger.info(f"Built correlation matrix: {corr_matrix.shape}")
        return corr_matrix
    
    def calculate_diversification_ratio(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate portfolio diversification ratio.
        
        Ratio of weighted average asset volatility to portfolio volatility.
        Higher ratio = better diversification.
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
        
        Returns:
            Diversification ratio (>1 indicates diversification benefit)
        
        Example:
            >>> div_ratio = risk_calc.calculate_diversification_ratio(returns, weights)
            >>> print(f"Diversification Ratio: {div_ratio:.2f}")
        """
        weight_array = np.array([weights[col] for col in returns.columns])
        
        # Individual asset volatilities (annualized)
        asset_vols = returns.std() * np.sqrt(self.annualization_factor)
        
        # Weighted average volatility
        weighted_avg_vol = np.sum(weight_array * asset_vols)
        
        # Portfolio volatility
        port_vol = self.calculate_portfolio_volatility(returns, weights)
        
        # Diversification ratio
        div_ratio = weighted_avg_vol / port_vol
        
        return div_ratio
    
    def calculate_max_drawdown(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate maximum drawdown of portfolio.
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
        
        Returns:
            Maximum drawdown as positive number
        
        Example:
            >>> max_dd = risk_calc.calculate_max_drawdown(returns, weights)
            >>> print(f"Maximum Drawdown: {max_dd:.2%}")
        """
        # Calculate portfolio returns
        port_returns = self._calculate_portfolio_returns(returns, weights)
        
        # Calculate cumulative returns
        cum_returns = (1 + port_returns).cumprod()
        
        # Running maximum
        running_max = cum_returns.expanding().max()
        
        # Drawdowns
        drawdowns = (cum_returns - running_max) / running_max
        
        # Maximum drawdown
        max_drawdown = abs(drawdowns.min())
        
        return max_drawdown
    
    def calculate_risk_contributions(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
        cov_matrix: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Calculate each asset's contribution to portfolio risk.
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
            cov_matrix: Covariance matrix (optional)
        
        Returns:
            Dictionary of risk contributions
        
        Example:
            >>> contributions = risk_calc.calculate_risk_contributions(returns, weights)
        """
        if cov_matrix is None:
            cov_matrix = returns.cov() * self.annualization_factor
        
        weight_array = np.array([weights[col] for col in returns.columns])
        
        # Portfolio volatility
        port_vol = self.calculate_portfolio_volatility(returns, weights, cov_matrix)
        
        # Marginal risk contribution
        marginal_risk = (cov_matrix.values @ weight_array) / port_vol
        
        # Risk contribution
        risk_contrib = weight_array * marginal_risk
        
        # Percentage contribution
        risk_contrib_pct = risk_contrib / port_vol
        
        # Convert to dictionary
        asset_names = returns.columns.tolist()
        contributions_dict = dict(zip(asset_names, risk_contrib_pct))
        
        return contributions_dict
    
    def _calculate_portfolio_returns(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> pd.Series:
        """Calculate portfolio returns series."""
        weight_array = np.array([weights[col] for col in returns.columns])
        port_returns = (returns * weight_array).sum(axis=1)
        return port_returns
    
    def calculate_all_risk_metrics(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Args:
            returns: DataFrame with asset returns
            weights: Asset weights dictionary
        
        Returns:
            Dictionary with all risk metrics
        
        Example:
            >>> all_metrics = risk_calc.calculate_all_risk_metrics(returns, weights)
        """
        # Basic metrics
        volatility = self.calculate_portfolio_volatility(returns, weights)
        
        # VaR and CVaR at different confidence levels
        var_metrics = {}
        cvar_metrics = {}
        
        for confidence in self.confidence_levels:
            conf_name = f"{int(confidence*100)}%"
            var_metrics[conf_name] = self.calculate_value_at_risk(
                returns, weights, confidence
            )
            cvar_metrics[conf_name] = self.calculate_conditional_var(
                returns, weights, confidence
            )
        
        # Other metrics
        div_ratio = self.calculate_diversification_ratio(returns, weights)
        max_dd = self.calculate_max_drawdown(returns, weights)
        corr_matrix = self.build_correlation_matrix(returns)
        risk_contrib = self.calculate_risk_contributions(returns, weights)
        
        return {
            'volatility': volatility,
            'var': var_metrics,
            'cvar': cvar_metrics,
            'diversification_ratio': div_ratio,
            'max_drawdown': max_dd,
            'correlation_matrix': corr_matrix,
            'risk_contributions': risk_contrib
        }


def analyze_portfolio_risk(
    returns: pd.DataFrame,
    weights: Dict[str, float],
    confidence_levels: List[float] = None
) -> Dict[str, Any]:
    """
    Convenience function for comprehensive risk analysis.
    
    Args:
        returns: DataFrame with asset returns
        weights: Asset weights dictionary
        confidence_levels: Confidence levels for VaR/CVaR
    
    Returns:
        Dictionary with all risk metrics
    
    Example:
        >>> risk_analysis = analyze_portfolio_risk(returns, weights)
    """
    calculator = PortfolioRiskCalculator(confidence_levels=confidence_levels)
    
    return calculator.calculate_all_risk_metrics(returns, weights)

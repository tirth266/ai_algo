"""
Portfolio Returns Module

Calculate return series for multiple assets or strategies.

Features:
- Compute daily returns
- Align time series
- Handle missing data
- Build covariance matrix

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PortfolioReturnsCalculator:
    """
    Calculate and process portfolio return series.
    
    Handles multiple assets, aligns time series, and computes
    covariance matrices for portfolio optimization.
    
    Usage:
        >>> calculator = PortfolioReturnsCalculator()
        >>> returns_df, cov_matrix = calculator.calculate_returns(prices_df)
    """
    
    def __init__(
        self,
        return_type: str = 'log',
        annualization_factor: int = 252,
        min_history: int = 60
    ):
        """
        Initialize portfolio returns calculator.
        
        Args:
            return_type: Type of return calculation ('simple' or 'log')
            annualization_factor: Number of trading days per year (default: 252)
            min_history: Minimum number of observations required
        
        Example:
            >>> calc = PortfolioReturnsCalculator(
            ...     return_type='log',
            ...     annualization_factor=252
            ... )
        """
        self.return_type = return_type
        self.annualization_factor = annualization_factor
        self.min_history = min_history
        
        logger.info(
            f"PortfolioReturnsCalculator initialized: "
            f"return_type={return_type}, annualization_factor={annualization_factor}"
        )
    
    def calculate_returns(
        self,
        prices: pd.DataFrame,
        method: str = None
    ) -> pd.DataFrame:
        """
        Calculate return series from price data.
        
        Args:
            prices: DataFrame with asset prices (columns = assets, index = dates)
            method: Override return type ('simple' or 'log')
        
        Returns:
            DataFrame with return series
        
        Example:
            >>> prices = pd.DataFrame({
            ...     'AAPL': [100, 102, 101, 103],
            ...     'GOOGL': [200, 205, 203, 207]
            ... })
            >>> returns = calculator.calculate_returns(prices)
        """
        if prices.empty:
            raise ValueError("Price data cannot be empty")
        
        # Determine return type
        return_method = method or self.return_type
        
        # Handle missing data
        prices_clean = self._handle_missing_data(prices)
        
        # Calculate returns
        if return_method == 'log':
            returns = np.log(prices_clean / prices_clean.shift(1))
        else:  # simple returns
            returns = prices_clean.pct_change()
        
        # Remove first row (NaN from pct_change)
        returns = returns.dropna(how='all')
        
        # Validate minimum history
        if len(returns) < self.min_history:
            logger.warning(
                f"Insufficient return history: {len(returns)} < {self.min_history}"
            )
        
        logger.info(f"Calculated {return_method} returns for {len(returns.columns)} assets")
        return returns
    
    def build_covariance_matrix(
        self,
        returns: pd.DataFrame,
        method: str = 'sample',
        shrinkage_target: str = 'constant_correlation'
    ) -> pd.DataFrame:
        """
        Build covariance matrix from return series.
        
        Args:
            returns: DataFrame with return series
            method: Estimation method ('sample', 'shrunk', 'exponential')
            shrinkage_target: Target for shrinkage estimation
        
        Returns:
            Covariance matrix as DataFrame
        
        Example:
            >>> cov_matrix = calculator.build_covariance_matrix(returns)
        """
        if returns.empty:
            raise ValueError("Returns data cannot be empty")
        
        if method == 'sample':
            cov_matrix = returns.cov() * self.annualization_factor
        
        elif method == 'exponential':
            # Exponentially weighted covariance
            cov_matrix = returns.ewm(span=60).cov().iloc[-len(returns.columns):]
            cov_matrix = cov_matrix * self.annualization_factor
        
        elif method == 'shrunk':
            cov_matrix = self._shrink_covariance(returns, shrinkage_target)
        
        else:
            raise ValueError(f"Unknown covariance method: {method}")
        
        logger.info(f"Built {method} covariance matrix: {cov_matrix.shape}")
        return cov_matrix
    
    def _handle_missing_data(
        self,
        prices: pd.DataFrame,
        method: str = 'forward_fill'
    ) -> pd.DataFrame:
        """Handle missing price data."""
        if method == 'forward_fill':
            prices_filled = prices.fillna(method='ffill')
        elif method == 'interpolate':
            prices_filled = prices.interpolate(method='linear')
        else:
            prices_filled = prices.dropna()
        
        # Fill any remaining NaN at the beginning
        prices_filled = prices_filled.fillna(method='bfill')
        
        return prices_filled
    
    def _shrink_covariance(
        self,
        returns: pd.DataFrame,
        target: str = 'constant_correlation'
    ) -> pd.DataFrame:
        """Apply Ledoit-Wolf shrinkage to covariance matrix."""
        n_assets, n_obs = returns.shape
        
        # Sample covariance
        sample_cov = returns.cov() * self.annualization_factor
        
        if target == 'constant_correlation':
            # Constant correlation model
            std_devs = np.sqrt(np.diag(sample_cov))
            avg_corr = (sample_cov / np.outer(std_devs, std_devs)).mean().mean()
            
            # Shrinkage target
            target_cov = avg_corr * np.outer(std_devs, std_devs)
            np.fill_diagonal(target_cov.values, np.diag(sample_cov))
        
        elif target == 'diagonal':
            # Diagonal matrix
            target_cov = pd.DataFrame(
                np.diag(np.diag(sample_cov)),
                index=sample_cov.index,
                columns=sample_cov.columns
            )
        
        else:
            raise ValueError(f"Unknown shrinkage target: {target}")
        
        # Optimal shrinkage intensity (simplified Ledoit-Wolf)
        shrinkage = (1 / n_obs) * (1 - target) if n_obs > 0 else 0.5
        
        # Shrunk covariance
        shrunk_cov = (1 - shrinkage) * sample_cov + shrinkage * target_cov
        
        return shrunk_cov
    
    def align_time_series(
        self,
        price_dict: Dict[str, pd.Series],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Align multiple price series to common time period.
        
        Args:
            price_dict: Dictionary of asset name to price series
            start_date: Start date for alignment (optional)
            end_date: End date for alignment (optional)
        
        Returns:
            DataFrame with aligned price series
        
        Example:
            >>> prices_aligned = calculator.align_time_series(price_dict)
        """
        # Combine into DataFrame
        prices_df = pd.DataFrame(price_dict)
        
        # Apply date range
        if start_date:
            prices_df = prices_df[prices_df.index >= start_date]
        if end_date:
            prices_df = prices_df[prices_df.index <= end_date]
        
        # Drop rows with any missing data
        prices_df = prices_df.dropna()
        
        logger.info(
            f"Aligned {len(prices_df.columns)} series from "
            f"{prices_df.index[0]} to {prices_df.index[-1]}"
        )
        
        return prices_df
    
    def calculate_annualized_metrics(
        self,
        returns: pd.DataFrame
    ) -> Dict[str, pd.Series]:
        """
        Calculate annualized return and volatility for each asset.
        
        Args:
            returns: DataFrame with return series
        
        Returns:
            Dictionary with annualized metrics
        
        Example:
            >>> metrics = calculator.calculate_annualized_metrics(returns)
            >>> print(f"AAPL annualized return: {metrics['annual_return']['AAPL']:.2%}")
        """
        # Annualized return
        annual_return = returns.mean() * self.annualization_factor
        
        # Annualized volatility
        annual_vol = returns.std() * np.sqrt(self.annualization_factor)
        
        # Sharpe ratio (assuming 0 risk-free rate)
        sharpe = annual_return / annual_vol
        
        return {
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe
        }


def calculate_portfolio_returns(
    prices: pd.DataFrame,
    return_type: str = 'log',
    annualization_factor: int = 252
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience function to calculate returns and covariance matrix.
    
    Args:
        prices: DataFrame with asset prices
        return_type: Type of return calculation
        annualization_factor: Trading days per year
    
    Returns:
        Tuple of (returns_df, cov_matrix)
    
    Example:
        >>> returns, cov = calculate_portfolio_returns(prices_df)
    """
    calculator = PortfolioReturnsCalculator(
        return_type=return_type,
        annualization_factor=annualization_factor
    )
    
    returns = calculator.calculate_returns(prices)
    cov_matrix = calculator.build_covariance_matrix(returns)
    
    return returns, cov_matrix


def prepare_returns_for_optimization(
    prices: Dict[str, pd.Series],
    min_history: int = 252,
    return_type: str = 'simple'
) -> pd.DataFrame:
    """
    Prepare return series specifically for portfolio optimization.
    
    Args:
        prices: Dictionary of asset prices
        min_history: Minimum required history
        return_type: Type of return calculation
    
    Returns:
        Cleaned returns DataFrame ready for optimization
    
    Example:
        >>> returns = prepare_returns_for_optimization(price_dict)
    """
    calculator = PortfolioReturnsCalculator(
        return_type=return_type,
        min_history=min_history
    )
    
    # Align time series
    prices_aligned = calculator.align_time_series(prices)
    
    # Calculate returns
    returns = calculator.calculate_returns(prices_aligned)
    
    # Validate
    if len(returns) < min_history:
        raise ValueError(
            f"Insufficient return history: {len(returns)} < {min_history}"
        )
    
    return returns

"""
Historical Data Loader Module

Load and prepare historical OHLCV data for backtesting.

Features:
- CSV file loading
- Data validation
- Timeframe resampling
- Large dataset support
- Missing data handling

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import os

from ..utils.data_validator import (
    validate_ohlcv_dataframe,
    check_time_order,
    check_missing_values,
    clean_ohlcv_data,
    prepare_data_for_backtest
)

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Load and prepare historical market data.
    
    Supports CSV files with OHLCV data.
    Handles validation, cleaning, and resampling.
    
    Example CSV format:
    timestamp,open,high,low,close,volume
    2024-01-01 09:15:00,100.5,101.2,99.8,100.9,50000
    
    Usage:
        >>> loader = DataLoader()
        >>> df = loader.load_csv('data/RELIANCE.csv')
    """
    
    def __init__(self):
        """Initialize data loader."""
        self._loaded_files: Dict[str, pd.DataFrame] = {}
        
        logger.info("DataLoader initialized")
    
    def load_csv(
        self,
        filepath: str,
        symbol: str = None,
        date_column: str = 'timestamp',
        parse_dates: bool = True,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Load historical data from CSV file.
        
        Args:
            filepath: Path to CSV file
            symbol: Symbol name (for caching)
            date_column: Name of date/timestamp column
            parse_dates: Parse date column as datetime
            validate: Validate OHLCV data after loading
        
        Returns:
            DataFrame with OHLCV data
        
        Example:
            >>> df = loader.load_csv('historical/RELIANCE_5m.csv')
        """
        try:
            # Check if file exists
            if not os.path.exists(filepath):
                logger.error(f"File not found: {filepath}")
                raise FileNotFoundError(f"Data file not found: {filepath}")
            
            logger.info(f"Loading data from {filepath}...")
            
            # Load CSV
            df = pd.read_csv(
                filepath,
                parse_dates=[date_column] if parse_dates else False,
                index_col=date_column if parse_dates else None
            )
            
            # Validate required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_columns if col not in df.columns]
            
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                raise ValueError(f"Missing columns: {missing_cols}")
            
            # Prepare data (sort, clean, validate)
            if validate:
                logger.debug("Validating and cleaning data...")
                df = prepare_data_for_backtest(df, symbol)
            else:
                # At least sort by index if it's datetime
                if isinstance(df.index, pd.DatetimeIndex):
                    df = df.sort_index()
            
            # Store in cache
            cache_key = symbol or filepath
            self._loaded_files[cache_key] = df
            
            logger.info(
                f"Loaded {len(df)} rows from {filepath} "
                f"({df.index.min()} to {df.index.max()})"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}", exc_info=True)
            raise
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data quality.
        
        Checks:
        - Required columns exist
        - No negative prices
        - High >= Low
        - No NaN values
        - Reasonable volume
        - Datetime index
        - No duplicate timestamps
        
        Args:
            df: DataFrame to validate
        
        Returns:
            True if valid
        
        Example:
            >>> if loader.validate_data(df):
            ...     print("Data quality OK")
        """
        is_valid, issues = validate_ohlcv_dataframe(df)
        
        if not is_valid:
            for issue in issues:
                logger.warning(f"Data quality issue: {issue}")
        
        return is_valid
    
    def resample_timeframe(
        self,
        df: pd.DataFrame,
        target_timeframe: str
    ) -> pd.DataFrame:
        """
        Resample data to different timeframe.
        
        Supported timeframes:
        - '1min', '5min', '15min', '30min'
        - '1h', '2h', '4h'
        - '1D', '1W', '1M'
        
        Args:
            df: Original DataFrame
            target_timeframe: Target timeframe
        
        Returns:
            Resampled DataFrame
        
        Example:
            >>> daily = loader.resample_timeframe(df, '1D')
        """
        logger.info(f"Resampling to {target_timeframe}...")
        
        # Map timeframes to pandas offset
        offset_map = {
            '1min': '1T',
            '5min': '5T',
            '15min': '15T',
            '30min': '30T',
            '1h': '1H',
            '2h': '2H',
            '4h': '4H',
            '1D': '1D',
            '1W': '1W',
            '1M': '1M'
        }
        
        offset = offset_map.get(target_timeframe)
        if not offset:
            logger.error(f"Unknown timeframe: {target_timeframe}")
            raise ValueError(f"Unknown timeframe: {target_timeframe}")
        
        # Resample OHLCV
        resampled = df.resample(offset).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # Remove rows with all NaN
        resampled = resampled.dropna(how='all')
        
        logger.info(
            f"Resampled from {len(df)} to {len(resampled)} candles "
            f"({target_timeframe})"
        )
        
        return resampled
    
    def clean_data(
        self,
        df: pd.DataFrame,
        fill_method: str = 'ffill'
    ) -> pd.DataFrame:
        """
        Clean and prepare data for backtesting.
        
        Operations:
        - Sort by date
        - Remove duplicates
        - Fill missing values
        - Validate structure
        
        Args:
            df: DataFrame to clean
            fill_method: Method to fill NaN ('ffill', 'bfill', 'drop')
        
        Returns:
            Cleaned DataFrame
        
        Example:
            >>> df_clean = loader.clean_data(df, fill_method='ffill')
        """
        logger.info("Cleaning data...")
        
        # Use the comprehensive cleaning function
        df_cleaned = clean_ohlcv_data(df, fill_method=fill_method, sort_by_time=True)
        
        logger.info(f"Data cleaned: {len(df_cleaned)} rows")
        return df_cleaned
    
    def get_cached_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get previously loaded data from cache.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Cached DataFrame or None
        """
        return self._loaded_files.get(symbol)
    
    def clear_cache(self):
        """Clear all cached data."""
        self._loaded_files.clear()
        logger.info("Data cache cleared")
    
    def generate_mock_data(
        self,
        symbol: str = 'TEST',
        start_date: datetime = None,
        num_bars: int = 1000,
        base_price: float = 1000.0,
        volatility: float = 0.02
    ) -> pd.DataFrame:
        """
        Generate realistic mock OHLCV data for testing.
        
        Uses geometric Brownian motion for price simulation.
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            num_bars: Number of bars to generate
            base_price: Starting price
            volatility: Price volatility (default: 2%)
        
        Returns:
            DataFrame with generated OHLCV data
        
        Example:
            >>> df = loader.generate_mock_data(num_bars=5000)
        """
        if start_date is None:
            start_date = datetime(2024, 1, 1)
        
        logger.info(
            f"Generating {num_bars} mock bars for {symbol}..."
        )
        
        # Generate timestamps (1-minute bars)
        timestamps = pd.date_range(
            start=start_date,
            periods=num_bars,
            freq='1min'
        )
        
        # Generate returns using geometric Brownian motion
        drift = 0.0001  # Small upward drift
        returns = np.random.normal(drift, volatility, num_bars)
        
        # Generate close prices
        close_prices = base_price * np.cumprod(1 + returns)
        
        # Generate OHLC from close prices
        opens = np.roll(close_prices, 1)
        opens[0] = base_price
        
        # Add intrabar variation
        high_variation = np.abs(np.random.randn(num_bars)) * volatility * close_prices
        low_variation = np.abs(np.random.randn(num_bars)) * volatility * close_prices
        
        highs = np.maximum(opens, close_prices) + high_variation
        lows = np.minimum(opens, close_prices) - low_variation
        
        # Ensure proper OHLC relationships
        highs = np.maximum(highs, np.maximum(opens, close_prices))
        lows = np.minimum(lows, np.minimum(opens, close_prices))
        
        # Generate volume
        base_volume = 10000
        volumes = base_volume + np.random.randint(-5000, 5000, num_bars)
        volumes = np.maximum(volumes, 1000)  # Minimum volume
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': close_prices,
            'volume': volumes.astype(int)
        }, index=timestamps)
        
        df.index.name = 'timestamp'
        
        logger.info(
            f"Generated mock data: {base_price:.2f} to {close_prices[-1]:.2f} "
            f"({len(df)} bars)"
        )
        
        return df


# Global loader instance
_data_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """
    Get or create global data loader instance.
    
    Returns:
        DataLoader instance
    
    Example:
        >>> loader = get_data_loader()
        >>> df = loader.load_csv('data.csv')
    """
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
    
    return _data_loader


# Convenience functions
def load_historical_data(
    filepath: str,
    symbol: str = None
) -> pd.DataFrame:
    """
    Load historical data from CSV.
    
    Args:
        filepath: Path to CSV file
        symbol: Symbol name for caching
    
    Returns:
        DataFrame with OHLCV data
    """
    loader = get_data_loader()
    return loader.load_csv(filepath, symbol)


def generate_test_data(
    num_bars: int = 1000,
    base_price: float = 1000.0
) -> pd.DataFrame:
    """
    Generate mock data for testing.
    
    Args:
        num_bars: Number of bars
        base_price: Starting price
    
    Returns:
        DataFrame with OHLCV data
    """
    loader = get_data_loader()
    return loader.generate_mock_data(num_bars=num_bars, base_price=base_price)

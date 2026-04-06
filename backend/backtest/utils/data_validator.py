"""
Data Validation Utility Module

Validate OHLCV data quality for backtesting.

Features:
- DataFrame structure validation
- Time order verification
- Missing value detection
- Data quality checks

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


def validate_ohlcv_dataframe(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate OHLCV DataFrame structure and quality.
    
    Checks:
    - Required columns exist (open, high, low, close, volume)
    - Datetime index
    - No duplicate timestamps
    - Numeric dtypes
    - No negative prices
    - High >= Low
    - Open/Close within High-Low range
    
    Args:
        df: DataFrame to validate
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    
    Example:
        >>> is_valid, issues = validate_ohlcv_dataframe(df)
        >>> if not is_valid:
        ...     print(f"Validation failed: {issues}")
    """
    issues = []
    
    # Check if DataFrame is empty
    if df.empty:
        issues.append("DataFrame is empty")
        return False, issues
    
    # Check required columns
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")
        return False, issues
    
    # Check datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        # Try to check if 'timestamp' or 'datetime' column exists
        if 'timestamp' in df.columns:
            issues.append("Index should be datetime (use 'timestamp' column as index)")
        elif 'datetime' in df.columns:
            issues.append("Index should be datetime (use 'datetime' column as index)")
        else:
            issues.append("DataFrame index is not datetime type")
    
    # Check for duplicate timestamps
    if isinstance(df.index, pd.DatetimeIndex):
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate timestamps found")
    
    # Check numeric dtypes
    for col in required_columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            issues.append(f"Column '{col}' is not numeric (dtype: {df[col].dtype})")
    
    # Check for NaN values
    nan_counts = df[required_columns].isna().sum()
    for col, count in nan_counts.items():
        if count > 0:
            issues.append(f"Column '{col}' contains {count} NaN values")
    
    # Check for negative prices
    if (df['open'] < 0).any():
        issues.append("Negative open prices detected")
    
    if (df['high'] < 0).any():
        issues.append("Negative high prices detected")
    
    if (df['low'] < 0).any():
        issues.append("Negative low prices detected")
    
    if (df['close'] < 0).any():
        issues.append("Negative close prices detected")
    
    # Check High >= Low
    invalid_hl = (df['high'] < df['low']).sum()
    if invalid_hl > 0:
        issues.append(f"{invalid_hl} candles with High < Low")
    
    # Check Open within High-Low range
    invalid_open = ((df['open'] < df['low']) | (df['open'] > df['high'])).sum()
    if invalid_open > 0:
        issues.append(f"{invalid_open} candles with Open outside High-Low range")
    
    # Check Close within High-Low range
    invalid_close = ((df['close'] < df['low']) | (df['close'] > df['high'])).sum()
    if invalid_close > 0:
        issues.append(f"{invalid_close} candles with Close outside High-Low range")
    
    # Check volume
    if (df['volume'] < 0).any():
        issues.append("Negative volume detected")
    
    is_valid = len(issues) == 0
    
    if is_valid:
        logger.info("OHLCV DataFrame validation passed")
    else:
        logger.warning(f"OHLCV DataFrame validation failed: {len(issues)} issue(s)")
        for issue in issues:
            logger.warning(f"  - {issue}")
    
    return is_valid, issues


def check_time_order(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check if DataFrame is sorted by time.
    
    Args:
        df: DataFrame with datetime index
        
    Returns:
        Tuple of (is_sorted_ascending, message)
    
    Example:
        >>> is_sorted, msg = check_time_order(df)
        >>> if not is_sorted:
        ...     df = df.sort_index()
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        return False, "Index is not datetime type"
    
    if df.empty:
        return True, "Empty DataFrame"
    
    # Check if ascending
    is_ascending = df.index.is_monotonic_increasing
    
    # Check if descending
    is_descending = df.index.is_monotonic_decreasing
    
    if is_ascending:
        return True, "Data is sorted in ascending order"
    elif is_descending:
        return False, "Data is sorted in descending order (should be ascending)"
    else:
        return False, "Data is not sorted chronologically"


def check_missing_values(df: pd.DataFrame) -> dict:
    """
    Check for missing values in DataFrame.
    
    Args:
        df: DataFrame to check
        
    Returns:
        Dictionary with missing value statistics
        
    Example:
        >>> stats = check_missing_values(df)
        >>> print(f"Total missing: {stats['total_missing']}")
    """
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Count missing values per column
    missing_counts = {}
    total_missing = 0
    
    for col in required_columns:
        if col in df.columns:
            count = df[col].isna().sum()
            missing_counts[col] = int(count)
            total_missing += count
        else:
            missing_counts[col] = None  # Column doesn't exist
    
    # Find rows with any missing values
    rows_with_missing = df[required_columns].isna().any(axis=1).sum()
    
    # Calculate percentage
    total_cells = len(df) * len(required_columns)
    missing_percentage = (total_missing / total_cells * 100) if total_cells > 0 else 0
    
    return {
        'total_missing': int(total_missing),
        'missing_percentage': round(missing_percentage, 4),
        'rows_with_missing': int(rows_with_missing),
        'by_column': missing_counts
    }


def clean_ohlcv_data(
    df: pd.DataFrame,
    fill_method: str = 'ffill',
    sort_by_time: bool = True
) -> pd.DataFrame:
    """
    Clean OHLCV data by handling missing values and sorting.
    
    Args:
        df: DataFrame to clean
        fill_method: Method to fill NaN ('ffill', 'bfill', 'drop')
        sort_by_time: Sort by datetime index
        
    Returns:
        Cleaned DataFrame
        
    Example:
        >>> df_clean = clean_ohlcv_data(df, fill_method='ffill')
    """
    logger.info(f"Cleaning OHLCV data ({len(df)} rows)...")
    
    # Make a copy
    df = df.copy()
    
    # Sort by time if requested
    if sort_by_time and isinstance(df.index, pd.DatetimeIndex):
        df = df.sort_index()
        logger.debug("Sorted by datetime index")
    
    # Remove duplicate timestamps
    if isinstance(df.index, pd.DatetimeIndex):
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            df = df[~df.index.duplicated(keep='first')]
            logger.info(f"Removed {duplicates} duplicate timestamps")
    
    # Fill missing values
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    
    if fill_method == 'ffill':
        df[required_columns] = df[required_columns].fillna(method='ffill')
        logger.debug("Applied forward fill")
    elif fill_method == 'bfill':
        df[required_columns] = df[required_columns].fillna(method='bfill')
        logger.debug("Applied backward fill")
    elif fill_method == 'drop':
        initial_len = len(df)
        df = df.dropna(subset=required_columns)
        dropped = initial_len - len(df)
        if dropped > 0:
            logger.info(f"Dropped {dropped} rows with missing values")
    else:
        logger.warning(f"Unknown fill method: {fill_method}")
    
    # Final backward fill to handle any remaining NaN at the start
    df[required_columns] = df[required_columns].fillna(method='bfill')
    
    logger.info(f"Data cleaning completed ({len(df)} rows remaining)")
    
    return df


def prepare_data_for_backtest(
    df: pd.DataFrame,
    symbol: str = None
) -> pd.DataFrame:
    """
    Complete data preparation pipeline for backtesting.
    
    Steps:
    1. Validate structure
    2. Check time order
    3. Check missing values
    4. Clean data
    5. Final validation
    
    Args:
        df: Raw OHLCV DataFrame
        symbol: Symbol name for logging
        
    Returns:
        Prepared DataFrame ready for backtesting
        
    Raises:
        ValueError: If data cannot be prepared
        
    Example:
        >>> df_prepared = prepare_data_for_backtest(df, 'RELIANCE')
    """
    symbol_str = f" ({symbol})" if symbol else ""
    logger.info(f"Preparing data{symbol_str}...")
    
    # Step 1: Validate structure
    is_valid, issues = validate_ohlcv_dataframe(df)
    
    if not is_valid:
        # Check if issues are critical
        critical_issues = [i for i in issues if 'Missing required' in i or 'empty' in i.lower()]
        if critical_issues:
            raise ValueError(f"Invalid OHLCV data format: {critical_issues}")
    
    # Step 2: Check and fix time order
    if isinstance(df.index, pd.DatetimeIndex):
        is_sorted, msg = check_time_order(df)
        if not is_sorted:
            logger.warning(f"Data not properly sorted: {msg}. Sorting now...")
            df = df.sort_index()
    
    # Step 3: Check missing values
    missing_stats = check_missing_values(df)
    if missing_stats['total_missing'] > 0:
        logger.info(f"Found {missing_stats['total_missing']} missing values")
    
    # Step 4: Clean data
    df = clean_ohlcv_data(df, fill_method='ffill', sort_by_time=False)
    
    # Step 5: Final validation
    is_valid, issues = validate_ohlcv_dataframe(df)
    
    if not is_valid:
        raise ValueError(f"Data preparation failed: {issues}")
    
    logger.info(f"Data preparation completed successfully{symbol_str}")
    
    return df

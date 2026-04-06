"""
Data Normalization Utilities

Ensures consistent data format across all strategies to prevent:
- Datetime timezone mismatches
- NaN values from misaligned indices
- Type conversion errors
- Unpacking errors from malformed signals

Usage:
    >>> normalizer = DataNormalizer()
    >>> clean_data = normalizer.normalize(data)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalizes OHLCV data for consistent processing.
    
    Handles:
    - Timezone conversion (UTC/IST)
    - Index alignment
    - NaN removal
    - Type validation
    - Signal safety checks
    """
    
    def __init__(self, target_timezone: str = 'Asia/Kolkata'):
        """
        Initialize data normalizer.
        
        Args:
            target_timezone: Target timezone for normalization (default: IST)
        """
        self.target_timezone = target_timezone
        
    def normalize(
        self,
        data: pd.DataFrame,
        symbol: str = 'UNKNOWN'
    ) -> Optional[pd.DataFrame]:
        """
        Normalize OHLCV data.
        
        Args:
            data: Raw OHLCV DataFrame
            symbol: Trading symbol (for logging)
        
        Returns:
            Cleaned DataFrame or None if invalid
        
        Process:
        1. Validate input
        2. Normalize datetime index
        3. Remove NaN values
        4. Align columns
        5. Validate data integrity
        """
        try:
            if data is None or len(data) == 0:
                logger.warning(f"{symbol}: No data provided for normalization")
                return None
            
            # Make a copy to avoid modifying original
            df = data.copy()
            
            # Step 1: Normalize datetime index
            df = self._normalize_datetime_index(df, symbol)
            
            # Step 2: Remove NaN values
            df = self._remove_nan_values(df, symbol)
            
            # Step 3: Validate OHLCV columns
            df = self._validate_columns(df, symbol)
            
            # Step 4: Sort by timestamp
            df.sort_index(inplace=True)
            
            # Step 5: Remove duplicates
            df = self._remove_duplicates(df, symbol)
            
            logger.info(
                f"{symbol}: Normalized {len(df)} bars "
                f"from {df.index[0]} to {df.index[-1]}"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"{symbol}: Normalization failed: {e}", exc_info=True)
            return None
    
    def _normalize_datetime_index(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """Convert index to consistent datetime format."""
        
        # Check if index is already datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            # Try to convert 'timestamp' or 'date' column
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            else:
                logger.warning(f"{symbol}: No datetime column found, using row numbers")
                df.index = pd.to_datetime(range(len(df)), unit='s')
        
        # Ensure timezone-aware (convert to UTC first)
        if df.index.tz is None:
            # Naive datetime - assume UTC
            df.index = df.index.tz_localize('UTC')
        else:
            # Has timezone - convert to UTC
            df.index = df.index.tz_convert('UTC')
        
        # Convert to target timezone (IST)
        df.index = df.index.tz_convert(self.target_timezone)
        
        return df
    
    def _remove_nan_values(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """Remove rows with NaN values."""
        
        initial_len = len(df)
        
        # Remove rows where any OHLCV column is NaN
        ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
        existing_cols = [col for col in ohlcv_cols if col in df.columns]
        
        if existing_cols:
            df = df.dropna(subset=existing_cols)
            removed = initial_len - len(df)
            if removed > 0:
                logger.warning(f"{symbol}: Removed {removed} rows with NaN values")
        
        # Forward fill then backward fill for other columns
        df = df.ffill().bfill()
        
        return df
    
    def _validate_columns(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """Ensure required columns exist and have correct types."""
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Check for missing columns
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"{symbol}: Missing required columns: {missing}")
        
        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def _remove_duplicates(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """Remove duplicate timestamps."""
        
        initial_len = len(df)
        df = df[~df.index.duplicated(keep='first')]
        
        removed = initial_len - len(df)
        if removed > 0:
            logger.warning(f"{symbol}: Removed {removed} duplicate timestamps")
        
        return df
    
    @staticmethod
    def safe_extract_signal(
        signal: Optional[Dict[str, Any]],
        key: str,
        default: Any = None
    ) -> Any:
        """
        Safely extract value from signal dictionary.
        
        Prevents "too many values to unpack" errors by:
        - Checking if signal exists
        - Checking if key exists
        - Validating value type
        
        Args:
            signal: Signal dictionary (may be None)
            key: Key to extract
            default: Default value if key missing
        
        Returns:
            Extracted value or default
        
        Example:
            >>> action = DataNormalizer.safe_extract_signal(signal, 'action', 'HOLD')
        """
        if signal is None:
            return default
        
        if not isinstance(signal, dict):
            logger.warning(f"Expected dict, got {type(signal)}")
            return default
        
        value = signal.get(key, default)
        
        # Check if value is a list/tuple when it should be scalar
        if isinstance(value, (list, tuple)) and not isinstance(default, (list, tuple)):
            logger.warning(f"Key '{key}' returned {type(value)} instead of scalar")
            # Return first element if it's a sequence
            return value[0] if len(value) > 0 else default
        
        return value
    
    @staticmethod
    def validate_signal_structure(signal: Dict[str, Any]) -> bool:
        """
        Validate that signal has required structure.
        
        Required fields:
        - action: 'BUY', 'SELL', or 'HOLD'
        - quantity: non-negative integer
        - price: positive float
        
        Args:
            signal: Signal dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(signal, dict):
            return False
        
        # Check action
        action = signal.get('action')
        if action not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        # Check quantity
        quantity = signal.get('quantity')
        if not isinstance(quantity, (int, float)) or quantity < 0:
            return False
        
        # Check price
        price = signal.get('price')
        if not isinstance(price, (int, float)) or price <= 0:
            return False
        
        return True


def normalize_data(
    data: pd.DataFrame,
    symbol: str = 'UNKNOWN'
) -> Optional[pd.DataFrame]:
    """
    Convenience function to normalize data.
    
    Args:
        data: Raw OHLCV DataFrame
        symbol: Trading symbol
    
    Returns:
        Normalized DataFrame
    
    Example:
        >>> clean_data = normalize_data(raw_data, 'RELIANCE')
    """
    normalizer = DataNormalizer()
    return normalizer.normalize(data, symbol)

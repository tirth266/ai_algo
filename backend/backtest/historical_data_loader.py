"""
Historical Data Loader Module

Handles loading and validation of historical market data for backtesting.

Supports:
- CSV file loading with standard OHLCV format
- Data validation and cleaning
- Timezone handling
- Missing data detection

Input Format (CSV):
timestamp,open,high,low,close,volume
2024-01-01 09:15:00,22500.0,22550.0,22480.0,22520.0,10000
"""

import pandas as pd
from typing import Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """
    Loader for historical market data.
    
    Responsibilities:
    - Load data from CSV files
    - Validate data format and integrity
    - Clean and preprocess data
    - Handle missing values
    """
    
    def __init__(self):
        """Initialize the data loader."""
        self.required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
    def load_csv(
        self, 
        filepath: Union[str, Path],
        date_column: str = 'timestamp',
        parse_dates: bool = True
    ) -> pd.DataFrame:
        """
        Load historical data from CSV file.
        
        Args:
            filepath: Path to CSV file
            date_column: Name of timestamp column (default: 'timestamp')
            parse_dates: Whether to parse dates (default: True)
        
        Returns:
            pd.DataFrame: Loaded and validated data
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns are missing
        """
        filepath = Path(filepath)
        
        logger.info(f"Loading data from {filepath}")
        
        # Check file exists
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        try:
            # Read CSV
            df = pd.read_csv(filepath)
            
            logger.info(f"Loaded {len(df)} rows from {filepath}")
            
            # Validate columns
            self._validate_columns(df)
            
            # Parse dates
            if parse_dates:
                df[date_column] = pd.to_datetime(df[date_column])
                df.set_index(date_column, inplace=True)
            
            # Sort by timestamp
            df.sort_index(inplace=True)
            
            # Clean data
            df = self._clean_data(df)
            
            # Validate data integrity
            self._validate_data(df)
            
            logger.info(f"Data loaded successfully: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}", exc_info=True)
            raise
    
    def _validate_columns(self, df: pd.DataFrame):
        """Validate that all required columns exist."""
        missing = [col for col in self.required_columns if col not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and preprocess data.
        
        - Remove rows with NaN values
        - Remove duplicate indices
        - Ensure numeric types
        """
        # Remove NaN values
        initial_len = len(df)
        df = df.dropna()
        if len(df) < initial_len:
            logger.warning(f"Removed {initial_len - len(df)} rows with NaN values")
        
        # Remove duplicates
        initial_len = len(df)
        df = df[~df.index.duplicated(keep='first')]
        if len(df) < initial_len:
            logger.warning(f"Removed {initial_len - len(df)} duplicate rows")
        
        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def _validate_data(self, df: pd.DataFrame):
        """
        Validate data integrity.
        
        Checks:
        - High >= Low
        - Open, Close within High-Low range
        - Positive volume
        - No zero prices
        """
        issues = []
        
        # Check high >= low
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            issues.append(f"{len(invalid_hl)} rows where high < low")
        
        # Check open within range
        invalid_open = df[(df['open'] > df['high']) | (df['open'] < df['low'])]
        if len(invalid_open) > 0:
            issues.append(f"{len(invalid_open)} rows where open outside high-low range")
        
        # Check close within range
        invalid_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
        if len(invalid_close) > 0:
            issues.append(f"{len(invalid_close)} rows where close outside high-low range")
        
        # Check positive volume
        invalid_vol = df[df['volume'] <= 0]
        if len(invalid_vol) > 0:
            issues.append(f"{len(invalid_vol)} rows with non-positive volume")
        
        # Check positive prices
        invalid_prices = df[(df['open'] <= 0) | (df['high'] <= 0) | (df['low'] <= 0) | (df['close'] <= 0)]
        if len(invalid_prices) > 0:
            issues.append(f"{len(invalid_prices)} rows with non-positive prices")
        
        if issues:
            warning_msg = "Data validation warnings:\n" + "\n".join(f"  - {issue}" for issue in issues)
            logger.warning(warning_msg)
    
    def load_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Load data from an existing DataFrame.
        
        Validates and cleans the data.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            pd.DataFrame: Validated and cleaned data
        """
        logger.info(f"Validating DataFrame with {len(df)} rows")
        
        # Validate columns
        self._validate_columns(df)
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
        
        # Clean data
        df = self._clean_data(df)
        
        # Validate
        self._validate_data(df)
        
        logger.info(f"DataFrame validation complete: {len(df)} bars")
        
        return df


def load_csv_data(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Convenience function to load CSV data.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        pd.DataFrame: Loaded data
    
    Example:
        >>> data = load_csv_data("data/NIFTY_5min.csv")
        >>> print(data.head())
    """
    loader = HistoricalDataLoader()
    return loader.load_csv(filepath)

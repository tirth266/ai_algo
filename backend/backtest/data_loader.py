"""
Backtesting Data Loader Module

Fetches historical market data from Zerodha for backtesting.
Supports multiple timeframes and date ranges.

Features:
- Fetch historical data from Zerodha Kite API
- Cache data locally to avoid repeated API calls
- Support for 1min, 5min, 15min, 1day timeframes
- Date range filtering
- Data validation and cleaning
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import os

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """
    Historical data loader for backtesting.
    
    Responsibilities:
    - Fetch historical OHLCV data from Zerodha
    - Cache data locally (JSON/CSV)
    - Validate and clean data
    - Support multiple symbols and timeframes
    """
    
    def __init__(self, cache_dir: str = 'backtest/cache'):
        """
        Initialize data loader.
        
        Args:
            cache_dir: Directory to cache historical data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Timeframe mapping for Zerodha API
        self.timeframe_map = {
            '1minute': 'minute',
            '5minute': '5minute',
            '15minute': '15minute',
            '30minute': '30minute',
            '60minute': '60minute',
            '1day': 'day'
        }
        
        logger.info(f"BacktestDataLoader initialized with cache: {self.cache_dir}")
    
    def load_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        kite_client: Any = None
    ) -> Optional[pd.DataFrame]:
        """
        Load historical data for backtesting.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            timeframe: Candle timeframe ('1minute', '5minute', '15minute', '1day')
            start_date: Start date for historical data
            end_date: End date for historical data
            kite_client: Zerodha KiteConnect client instance
        
        Returns:
            DataFrame with OHLCV data or None if failed
            
        Example:
            >>> loader = BacktestDataLoader()
            >>> data = loader.load_historical_data(
            ...     symbol='RELIANCE',
            ...     timeframe='5minute',
            ...     start_date=datetime(2024, 1, 1),
            ...     end_date=datetime(2024, 12, 31)
            ... )
        """
        try:
            # Check cache first
            cached_file = self._get_cache_path(symbol, timeframe, start_date, end_date)
            if cached_file.exists():
                logger.info(f"Loading cached data from {cached_file}")
                return self._load_from_cache(cached_file)
            
            # Fetch from Zerodha if client provided
            if kite_client is not None:
                logger.info(f"Fetching data from Zerodha for {symbol}")
                data = self._fetch_from_zerodha(
                    kite_client, symbol, timeframe, start_date, end_date
                )
                
                if data is not None and len(data) > 0:
                    # Save to cache
                    self._save_to_cache(data, cached_file)
                    return data
            
            # Fallback to generating mock data
            logger.warning(f"Generating mock data for {symbol} (no Kite client)")
            data = self._generate_mock_data(symbol, timeframe, start_date, end_date)
            
            if len(data) > 0:
                self._save_to_cache(data, cached_file)
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading historical data: {str(e)}", exc_info=True)
            return None
    
    def _fetch_from_zerodha(
        self,
        kite_client: Any,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Zerodha Kite API.
        
        Args:
            kite_client: KiteConnect client instance
            symbol: Stock symbol
            timeframe: Candle timeframe
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Get instrument token for symbol
            instrument_token = self._get_instrument_token(kite_client, symbol)
            
            if instrument_token is None:
                logger.error(f"Instrument token not found for {symbol}")
                return None
            
            # Map timeframe to Zerodha format
            zerodha_timeframe = self.timeframe_map.get(timeframe, '5minute')
            
            logger.info(
                f"Fetching {zerodha_timeframe} candles for {symbol} "
                f"from {start_date.date()} to {end_date.date()}"
            )
            
            # Fetch historical data
            candles = kite_client.historical_data(
                instrument_token=instrument_token,
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d'),
                interval=zerodha_timeframe
            )
            
            logger.info(f"Fetched {len(candles)} candles from Zerodha")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            if len(df) == 0:
                logger.warning(f"No data returned for {symbol}")
                return None
            
            # CRITICAL FIX: Proper datetime handling with UTC
            df['date'] = pd.to_datetime(df['date'], utc=True)
            df.set_index('date', inplace=True)
            
            # Ensure index is timezone-aware
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            
            # Rename columns to standard format
            df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }, inplace=True)
            
            # Select only required columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Sort by date
            df.sort_index(inplace=True)
            
            # Validate data
            self._validate_data(df)
            
            logger.info(
                f"Successfully loaded {len(df)} bars for {symbol} "
                f"from {df.index[0].date()} to {df.index[-1].date()}"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching from Zerodha: {str(e)}", exc_info=True)
            return None
    
    def _get_instrument_token(self, kite_client: Any, symbol: str) -> Optional[int]:
        """
        Get instrument token for symbol from Kite.
        
        Args:
            kite_client: KiteConnect client
            symbol: Stock symbol
        
        Returns:
            Instrument token or None
        """
        try:
            # Get all instruments
            instruments = kite_client.instruments(exchange='NSE')
            
            # Find instrument for symbol
            for inst in instruments:
                if inst['tradingsymbol'] == symbol:
                    logger.info(f"Found instrument for {symbol}: {inst['instrument_token']}")
                    return inst['instrument_token']
            
            logger.warning(f"Instrument not found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting instrument token: {str(e)}")
            return None
    
    def _validate_data(self, df: pd.DataFrame):
        """Validate historical data."""
        # Check for NaN values
        if df.isnull().any().any():
            nan_count = df.isnull().sum().sum()
            logger.warning(f"Data contains {nan_count} NaN values")
        
        # Check high >= low
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            logger.warning(f"{len(invalid_hl)} rows where high < low")
        
        # Check positive volume
        invalid_vol = df[df['volume'] <= 0]
        if len(invalid_vol) > 0:
            logger.warning(f"{len(invalid_vol)} rows with non-positive volume")
    
    def _generate_mock_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Generate mock historical data for testing.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with mock OHLCV data
        """
        logger.info(f"Generating mock data for {symbol}")
        
        # Convert string dates to datetime if needed
        if isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            from datetime import datetime
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Calculate number of candles based on timeframe
        days_diff = (end_date - start_date).days
        
        if 'minute' in timeframe:
            minutes_per_day = 375  # 6.25 hours of trading
            interval_minutes = int(timeframe.replace('minute', ''))
            total_candles = min(int(days_diff * minutes_per_day / interval_minutes), 10000)
        else:  # daily
            total_candles = days_diff
        
        total_candles = max(total_candles, 100)  # Minimum 100 candles
        
        # Generate realistic price data using random walk
        import numpy as np
        
        np.random.seed(hash(symbol) % 2**32)  # Reproducible results per symbol
        
        # Starting price based on symbol (mock)
        base_price = 1000 + (hash(symbol) % 2000)
        
        # Generate returns with slight upward drift
        daily_drift = 0.0003  # Small positive drift
        daily_volatility = 0.02  # 2% daily volatility
        
        returns = np.random.normal(daily_drift, daily_volatility, total_candles)
        
        # Calculate close prices
        close_prices = base_price * np.cumprod(1 + returns)
        
        # Generate OHLC from close
        data = []
        current_date = start_date
        
        if 'minute' in timeframe:
            interval_minutes = int(timeframe.replace('minute', ''))
            step = timedelta(minutes=interval_minutes)
        else:
            step = timedelta(days=1)
        
        for i in range(total_candles):
            open_price = close_prices[i] * (1 + np.random.uniform(-0.005, 0.005))
            high_price = max(open_price, close_prices[i]) * (1 + np.random.uniform(0, 0.01))
            low_price = min(open_price, close_prices[i]) * (1 - np.random.uniform(0, 0.01))
            volume = int(np.random.uniform(10000, 100000))
            
            data.append({
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_prices[i], 2),
                'volume': volume
            })
            
            current_date += step
            if current_date > end_date:
                break
        
        # Create DataFrame
        dates = pd.date_range(start=start_date, periods=len(data), freq=self._get_pandas_freq(timeframe))
        
        # Ensure UTC timezone
        if dates.tz is None:
            dates = dates.tz_localize('UTC')
        
        df = pd.DataFrame(data, index=dates)
        df.index.name = 'timestamp'
        
        # Reset index to make datetime a column
        df = df.reset_index()
        df = df.rename(columns={'index': 'datetime', 'timestamp': 'datetime'})
        
        logger.info(f"Generated {len(df)} mock candles for {symbol}")
        
        return df
    
    def _get_pandas_freq(self, timeframe: str) -> str:
        """Convert timeframe string to pandas frequency."""
        freq_map = {
            '1minute': '1T',
            '5minute': '5T',
            '15minute': '15T',
            '30minute': '30T',
            '60minute': '60T',
            '1day': 'D'
        }
        return freq_map.get(timeframe, '5T')
    
    def _get_cache_path(
        self,
        symbol: str,
        timeframe: str,
        start_date: any,  # Can be str or datetime
        end_date: any     # Can be str or datetime
    ) -> Path:
        """Generate cache file path."""
        # Convert strings to datetime if needed
        if isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            from datetime import datetime
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        filename = (
            f"{symbol}_{timeframe}_"
            f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pkl"
        )
        return self.cache_dir / filename
    
    def _load_from_cache(self, filepath: Path) -> Optional[pd.DataFrame]:
        """Load data from cache file."""
        try:
            df = pd.read_pickle(filepath)
            logger.info(f"Loaded {len(df)} rows from cache: {filepath}")
            return df
        except Exception as e:
            logger.error(f"Error loading cache: {str(e)}")
            return None
    
    def _save_to_cache(self, df: pd.DataFrame, filepath: Path):
        """Save data to cache file."""
        try:
            df.to_pickle(filepath)
            logger.info(f"Saved {len(df)} rows to cache: {filepath}")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")


def load_backtest_data(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    kite_client: Any = None
) -> Optional[pd.DataFrame]:
    """
    Convenience function to load backtest data.
    
    Args:
        symbol: Stock symbol
        timeframe: Candle timeframe
        start_date: Start date string ('YYYY-MM-DD')
        end_date: End date string ('YYYY-MM-DD')
        kite_client: Zerodha KiteConnect client
    
    Returns:
        DataFrame with OHLCV data
    
    Example:
        >>> data = load_backtest_data(
        ...     symbol='RELIANCE',
        ...     timeframe='5minute',
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31'
        ... )
    """
    loader = BacktestDataLoader()
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    return loader.load_historical_data(symbol, timeframe, start, end, kite_client)

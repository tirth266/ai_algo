"""
Market Data Service

Responsible for fetching and managing market data from Zerodha Kite Connect API.
Returns data in pandas DataFrame format for strategy consumption.
"""

from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for fetching market data from broker API.
    
    Provides methods to get LTP (Last Traded Price) and historical candles.
    Currently uses mock data - replace with actual Zerodha API calls.
    """
    
    def __init__(self, kite_client=None):
        """
        Initialize the market data service.
        
        Args:
            kite_client: Zerodha Kite Connect client instance (optional)
        """
        self.kite = kite_client
        self.instrument_mapping = self._load_instrument_mapping()
    
    def _load_instrument_mapping(self) -> Dict[str, str]:
        """
        Load symbol to instrument token mapping.
        
        In production, this would fetch from Zerodha or load from cache.
        
        Returns:
            Dict mapping symbols to their instrument tokens
        """
        # Mock mapping for common instruments
        # TODO: Replace with actual instrument master download from Zerodha
        return {
            'NIFTY': '256265',
            'BANKNIFTY': '26010',
            'RELIANCE': '738561',
            'TCS': '4267265',
            'INFY': '475393',
            'HDFCBANK': '415745',
            'ICICIBANK': '4172417',
        }
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get Last Traded Price for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'NIFTY', 'RELIANCE')
        
        Returns:
            float: Last traded price
            None: If data unavailable
        """
        try:
            if not self.kite:
                # Mock data when no live connection
                logger.warning(f"No kite client - returning mock LTP for {symbol}")
                return self._get_mock_ltp(symbol)
            
            # TODO: Implement actual Zerodha quote fetch
            # quote = self.kite.quote(f"NSE:{symbol}")
            # return quote['last_price']
            
            return self._get_mock_ltp(symbol)
            
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {str(e)}")
            return None
    
    def get_candles(
        self, 
        symbol: str, 
        timeframe: str = '5minute',
        lookback_days: int = 10
    ) -> pd.DataFrame:
        """
        Get historical OHLCV candle data.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle interval ('1minute', '5minute', '15minute', 'hour', 'day')
            lookback_days: Number of days to look back
        
        Returns:
            pd.DataFrame: OHLCV data with columns:
                         ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        try:
            if not self.kite:
                # Return mock data when no live connection
                logger.warning(f"No kite client - returning mock candles for {symbol}")
                return self._get_mock_candles(symbol, timeframe, lookback_days)
            
            # TODO: Implement actual Zerodha historical API call
            # instrument_token = self.instrument_mapping.get(symbol)
            # from_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            # to_date = datetime.now().strftime('%Y-%m-%d')
            # candles = self.kite.historical_data(instrument_token, from_date, to_date, timeframe)
            # df = pd.DataFrame(candles)
            # return df
            
            return self._get_mock_candles(symbol, timeframe, lookback_days)
            
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {str(e)}")
            return pd.DataFrame()
    
    def _get_mock_ltp(self, symbol: str) -> float:
        """
        Generate mock LTP for testing purposes.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            float: Mock last traded price
        """
        # Base prices for different symbols
        base_prices = {
            'NIFTY': 22500.0,
            'BANKNIFTY': 47000.0,
            'RELIANCE': 2900.0,
            'TCS': 4100.0,
            'INFY': 1600.0,
            'HDFCBANK': 1500.0,
            'ICICIBANK': 1100.0,
        }
        
        base = base_prices.get(symbol.upper(), 100.0)
        # Add small random variation
        import random
        variation = random.uniform(-0.001, 0.001)  # ±0.1%
        return round(base * (1 + variation), 2)
    
    def _get_mock_candles(
        self, 
        symbol: str, 
        timeframe: str,
        lookback_days: int
    ) -> pd.DataFrame:
        """
        Generate realistic mock OHLCV data using geometric Brownian motion.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle interval
            lookback_days: Days of data to generate
        
        Returns:
            pd.DataFrame: Mock OHLCV data
        """
        import numpy as np
        
        # Determine number of candles based on timeframe
        candles_per_day = {
            '1minute': 390,   # 6.5 hours * 60
            '5minute': 78,    # 6.5 hours * 12
            '15minute': 26,   # 6.5 hours * 4
            '30minute': 13,
            'hour': 6,
            'day': 1
        }
        
        num_candles = lookback_days * candles_per_day.get(timeframe, 78)
        
        # Base price and volatility
        base_price = self._get_mock_ltp(symbol)
        volatility = 0.02  # 2% daily volatility
        
        # Generate price series using geometric Brownian motion
        np.random.seed(42)  # For reproducibility
        returns = np.random.normal(0, volatility / np.sqrt(252), num_candles)
        close_prices = base_price * np.cumprod(1 + returns)
        
        # Generate OHLC from close prices
        data = []
        for i in range(num_candles):
            open_price = close_prices[i] * (1 + np.random.uniform(-0.001, 0.001))
            high_price = max(open_price, close_prices[i]) * (1 + abs(np.random.normal(0, 0.002)))
            low_price = min(open_price, close_prices[i]) * (1 - abs(np.random.normal(0, 0.002)))
            volume = int(np.random.uniform(10000, 100000))
            
            # Generate timestamp (working backwards from now)
            timestamp = datetime.now() - timedelta(minutes=(num_candles - i) * int(timeframe.replace('minute', '').replace('hour', '60').replace('day', '1440') or '5'))
            
            data.append({
                'timestamp': timestamp,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_prices[i], 2),
                'volume': volume
            })
        
        df = pd.DataFrame(data)
        return df
    
    def get_instrument_token(self, symbol: str) -> Optional[str]:
        """
        Get instrument token for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Instrument token string or None
        """
        return self.instrument_mapping.get(symbol)
    
    def update_instrument_mapping(self, mapping: Dict[str, str]):
        """
        Update or add instrument mappings.
        
        Args:
            mapping: Dictionary of symbol:token pairs
        """
        self.instrument_mapping.update(mapping)
        logger.info(f"Updated instrument mapping with {len(mapping)} symbols")

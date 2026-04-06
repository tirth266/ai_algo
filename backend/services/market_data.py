"""
Market Data Service Module

Provides market data access for trading engine.
Handles data fetching, caching, and normalization.
Integrates with Zerodha Kite Connect API for real market data.

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import numpy as np
import time
import sys
sys.path.insert(0, 'backend')

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Market data service for fetching OHLCV candles.
    
    Features:
    - Fetch real-time or historical data from Zerodha
    - Cache management (30 second TTL)
    - Data normalization
    - Fallback to mock data for testing
    - Retry logic for API failures
    
    Example:
        >>> mds = MarketDataService()
        >>> candles = mds.get_candles('RELIANCE', timeframe='5m', limit=100)
        >>> print(f"Fetched {len(candles)} bars")
    """
    
    def __init__(self):
        """Initialize market data service."""
        # Cache for candle data
        self._cache: Dict[str, tuple] = {}  # symbol -> (candles, timestamp)
        self._cache_ttl = 30  # Cache TTL in seconds (reduced from 60)
        
        # Instrument token cache
        self._instrument_tokens: Dict[str, int] = {}
        
        logger.info("MarketDataService initialized")
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str = '1m',
        limit: int = 500
    ) -> Optional[pd.DataFrame]:
        """
        Get OHLCV candles for symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE', 'TCS')
            timeframe: Candle timeframe ('1m', '5m', '15m', '30m', '60m', 'D')
            limit: Number of candles to fetch (default: 500)
        
        Returns:
            DataFrame with OHLCV data or None
        
        Example:
            >>> candles = mds.get_candles('RELIANCE', timeframe='5m', limit=100)
            >>> if candles is not None:
            ...     print(f"Latest close: {candles['close'].iloc[-1]}")
        """
        try:
            logger.info(f"Fetching {limit} candles for {symbol} ({timeframe})")
            
            # Check cache first
            cached_data = self._get_from_cache(symbol)
            if cached_data is not None:
                logger.debug(f"Cache hit for {symbol}")
                return cached_data
            
            # Try to fetch from Zerodha
            candles = self._fetch_candles_from_source(symbol, timeframe, limit)
            
            if candles is not None:
                # Cache the data
                self._add_to_cache(symbol, candles)
                return candles
            
            # Fallback to mock data
            logger.warning(f"Using mock data for {symbol}")
            return self._generate_mock_data(symbol, limit)
            
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {str(e)}", exc_info=True)
            return self._generate_mock_data(symbol, limit)
    
    def _fetch_candles_from_source(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> Optional[pd.DataFrame]:
        """
        Fetch candles from Zerodha Kite Connect API.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE', 'TCS')
            timeframe: Candle timeframe ('1m', '5m', '15m', etc.)
            limit: Number of candles to fetch
        
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            logger.info(f"Fetching {limit} candles for {symbol} ({timeframe}) from Zerodha")
            
            # Get authenticated Kite client
            from trading.zerodha_auto_login import get_kite_client
            kite = get_kite_client(auto_renew=True)
            
            if kite is None:
                logger.error("Failed to get Kite client")
                return None
            
            # Get instrument token for symbol
            instrument_token = self._get_instrument_token(symbol, kite)
            if instrument_token is None:
                logger.warning(f"Could not find instrument token for {symbol}")
                return None
            
            # Map timeframe to Zerodha interval
            zerodha_interval = self._map_timeframe(timeframe)
            
            # Calculate date range based on limit and timeframe
            from_date, to_date = self._calculate_date_range(timeframe, limit)
            
            # Fetch historical data with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    candles = kite.historical_data(
                        instrument_token=instrument_token,
                        from_date=from_date,
                        to_date=to_date,
                        interval=zerodha_interval
                    )
                    break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise
            
            if not candles:
                logger.warning(f"No data returned for {symbol}")
                return None
            
            # Convert to DataFrame
            df = self._convert_to_dataframe(candles)
            
            logger.info(f"Successfully fetched {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching from Zerodha for {symbol}: {str(e)}", exc_info=True)
            return None
    
    def _get_instrument_token(self, symbol: str, kite) -> Optional[int]:
        """
        Get instrument token for a given symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            kite: Kite client instance
        
        Returns:
            Instrument token or None
        """
        # Check cache first
        if symbol in self._instrument_tokens:
            return self._instrument_tokens[symbol]
        
        try:
            # Load all instruments for NSE
            instruments = kite.instruments("NSE")
            
            # Find matching symbol
            for inst in instruments:
                if inst['tradingsymbol'] == symbol or inst['name'] == symbol:
                    token = int(inst['instrument_token'])
                    self._instrument_tokens[symbol] = token
                    logger.debug(f"Found instrument for {symbol}: {token}")
                    return token
            
            # Try with "EQ" suffix (common for Indian stocks)
            for inst in instruments:
                if inst['tradingsymbol'] == f"{symbol}-EQ":
                    token = int(inst['instrument_token'])
                    self._instrument_tokens[symbol] = token
                    logger.debug(f"Found instrument for {symbol}-EQ: {token}")
                    return token
            
            logger.warning(f"Instrument token not found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting instrument token for {symbol}: {str(e)}")
            return None
    
    def _map_timeframe(self, timeframe: str) -> str:
        """
        Map application timeframe to Zerodha interval format.
        
        Args:
            timeframe: Application timeframe ('1m', '5m', '15m', etc.)
        
        Returns:
            Zerodha interval string
        """
        mapping = {
            '1m': 'minute',
            '5m': '5minute',
            '15m': '15minute',
            '30m': '30minute',
            '60m': '60minute',
            '1h': '60minute',
            'D': 'day',
            '1d': 'day'
        }
        
        return mapping.get(timeframe, '5minute')
    
    def _calculate_date_range(self, timeframe: str, limit: int) -> tuple:
        """
        Calculate from_date and to_date based on timeframe and limit.
        
        Args:
            timeframe: Candle timeframe
            limit: Number of candles needed
        
        Returns:
            Tuple of (from_date, to_date) as datetime objects
        """
        # Estimate minutes per candle
        minutes_per_candle = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '60m': 60,
            '1h': 60,
            'D': 1440,  # 24 hours
            '1d': 1440
        }
        
        minutes_per_candle_val = minutes_per_candle.get(timeframe, 5)
        
        # Calculate total minutes needed
        total_minutes = minutes_per_candle_val * limit
        
        # To date is now
        to_date = datetime.now()
        
        # From date is calculated backwards
        from_date = to_date - timedelta(minutes=total_minutes + 1440)  # Add 1 day buffer
        
        return from_date, to_date
    
    def _convert_to_dataframe(self, candles: list) -> pd.DataFrame:
        """
        Convert Zerodha candles list to pandas DataFrame.
        
        Args:
            candles: List of candle dictionaries from Zerodha API
        
        Returns:
            DataFrame with OHLCV data
        """
        if not candles:
            return pd.DataFrame()
        
        # Extract data
        data = []
        for candle in candles:
            data.append({
                'datetime': candle['date'],
                'open': candle['open'],
                'high': candle['high'],
                'low': candle['low'],
                'close': candle['close'],
                'volume': candle['volume']
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Set datetime as index
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # Ensure proper data types
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Sort by datetime
        df.sort_index(inplace=True)
        
        return df
    
    def _generate_mock_data(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        """
        Generate realistic mock OHLCV data for testing.
        
        Args:
            symbol: Stock symbol
            limit: Number of bars to generate
        
        Returns:
            DataFrame with simulated OHLCV data
        """
        logger.info(f"Generating mock data for {symbol} ({limit} bars)")
        
        # Set random seed based on symbol for reproducibility
        np.random.seed(hash(symbol) % (2**32))
        
        # Generate base price based on symbol
        base_price = np.random.uniform(500, 3000)
        
        # Generate timestamps
        end_date = datetime.now()
        timestamps = [
            end_date - timedelta(minutes=i)
            for i in range(limit)
        ]
        timestamps.reverse()
        
        # Generate realistic price movements
        drift = np.random.randn() * 0.0001  # Small drift
        volatility = 0.02  # 2% volatility
        
        returns = np.random.normal(drift, volatility, limit)
        
        # Add some trending behavior
        trend = np.sin(np.linspace(0, 8 * np.pi, limit)) * 0.005
        returns = returns + trend
        
        # Calculate close prices
        close_prices = base_price * (1 + returns).cumprod()
        
        # Generate OHLC from close prices
        for i in range(limit):
            open_price = close_prices[i] * (1 + np.random.uniform(-0.005, 0.005))
            high_price = max(open_price, close_prices[i]) * (1 + np.abs(np.random.randn()) * 0.005)
            low_price = min(open_price, close_prices[i]) * (1 - np.abs(np.random.randn()) * 0.005)
            
            if i == 0:
                open_prices = [open_price]
                high_prices = [high_price]
                low_prices = [low_price]
            else:
                open_prices.append(open_price)
                high_prices.append(high_price)
                low_prices.append(low_price)
        
        # Generate volume
        base_volume = np.random.randint(5000, 20000)
        volume = base_volume * (1 + np.random.randn(limit) * 0.3)
        volume = np.maximum(volume, 1000).astype(int)
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volume
        }, index=pd.DatetimeIndex(timestamps))
        
        # Ensure proper OHLC relationships
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        logger.info(
            f"Generated mock data: {limit} bars, "
            f"price range: {df['close'].min():.2f} - {df['close'].max():.2f}"
        )
        
        return df
    
    def _get_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get candles from cache if not expired."""
        if symbol in self._cache:
            candles, timestamp = self._cache[symbol]
            age = (datetime.now() - timestamp).total_seconds()
            
            if age < self._cache_ttl:
                return candles
            else:
                # Cache expired
                del self._cache[symbol]
                logger.debug(f"Cache expired for {symbol}")
        
        return None
    
    def _add_to_cache(self, symbol: str, candles: pd.DataFrame):
        """Add candles to cache."""
        self._cache[symbol] = (candles, datetime.now())
        logger.debug(f"Cached {len(candles)} candles for {symbol}")
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._instrument_tokens.clear()
        logger.info("Market data cache cleared")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Latest price or None
        """
        candles = self.get_candles(symbol, limit=1)
        if candles is not None and len(candles) > 0:
            return float(candles['close'].iloc[-1])
        return None
    
    def get_price_change(
        self,
        symbol: str,
        periods: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get price change over specified periods.
        
        Args:
            symbol: Stock symbol
            periods: Number of periods to compare (default: 1)
        
        Returns:
            Dict with price change info or None
        """
        candles = self.get_candles(symbol, limit=periods + 1)
        
        if candles is None or len(candles) <= periods:
            return None
        
        current_price = float(candles['close'].iloc[-1])
        previous_price = float(candles['close'].iloc[-(periods + 1)])
        
        change = current_price - previous_price
        change_pct = (change / previous_price) * 100
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'previous_price': previous_price,
            'change': change,
            'change_pct': change_pct
        }


# Global instance
_mds_instance: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    """
    Get or create global market data service instance.
    
    Returns:
        MarketDataService instance
    """
    global _mds_instance
    
    if _mds_instance is None:
        _mds_instance = MarketDataService()
    
    return _mds_instance


if __name__ == "__main__":
    # Test the market data service
    logging.basicConfig(level=logging.INFO)
    
    mds = get_market_data_service()
    
    # Test fetching candles
    test_symbols = ['RELIANCE', 'TCS', 'INFY']
    
    for symbol in test_symbols:
        print(f"\n{'='*60}")
        print(f"Testing {symbol}")
        print('='*60)
        
        candles = mds.get_candles(symbol, limit=100)
        
        if candles is not None:
            print(f"Candles fetched: {len(candles)}")
            print(f"Latest close: ₹{candles['close'].iloc[-1]:.2f}")
            print(f"High: ₹{candles['high'].max():.2f}")
            print(f"Low: ₹{candles['low'].min():.2f}")
            
            # Get price change
            change_info = mds.get_price_change(symbol, periods=10)
            if change_info:
                print(
                    f"Price change: {change_info['change']:+.2f} "
                    f"({change_info['change_pct']:+.2f}%)"
                )
        else:
            print("Failed to fetch data")

# -------------------------------------------------------------------------
# ANGEL ONE WEBSOCKET CLIENT
# -------------------------------------------------------------------------
try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except ImportError:
    SmartWebSocketV2 = None

class PriceStore:
    def __init__(self):
        self.prices = {}

    def update_price(self, token: str, price: float):
        self.prices[token] = price

    def get_price(self, token: str) -> Optional[float]:
        return self.prices.get(token)

    def get_all_prices(self):
        return self.prices

global_price_store = PriceStore()

class MarketDataWebSocket:
    """
    Streaming WebSocket client for Angel One SmartApi.
    """
    def __init__(self, auth_token=None, feed_token=None):
        from dotenv import load_dotenv
        load_dotenv()
        
        self.auth_token = auth_token or os.getenv("ANGEL_ONE_AUTH_TOKEN")
        self.api_key = os.getenv("ANGEL_ONE_API_KEY")
        self.client_code = os.getenv("ANGEL_ONE_CLIENT_ID")
        self.feed_token = feed_token or os.getenv("ANGEL_ONE_FEED_TOKEN")

        if not all([self.auth_token, self.api_key, self.client_code, self.feed_token]):
            logger.warning("Missing required websocket credentials. Ensure AUTH_TOKEN, API_KEY, CLIENT_ID and FEED_TOKEN are available.")

        self.sws = None

    def _on_data(self, ws, message):
        logger.info(f"Angel One Market Data Received: {message}")
        try:
            if isinstance(message, dict):
                token = message.get("token")
                price = message.get("last_traded_price", message.get("ltp"))
                if token and price is not None:
                    # Clean null characters if token comes as raw bytes formatted string
                    token_str = str(token).strip('\x00')
                    global_price_store.update_price(token_str, float(price))
            elif isinstance(message, list):
                for item in message:
                    if isinstance(item, dict):
                        token = item.get("token")
                        price = item.get("last_traded_price", item.get("ltp"))
                        if token and price is not None:
                            token_str = str(token).strip('\x00')
                            global_price_store.update_price(token_str, float(price))
        except Exception as e:
            logger.error(f"Error parsing websocket data: {e}")

    def _on_open(self, ws):
        logger.info("Angel One WebSocket connected successfully")
        self._subscribe_initial()

    def _reauth_and_reconnect(self):
        logger.info("Attempting to re-authenticate to refresh FEED_TOKEN...")
        try:
            from SmartApi import SmartConnect
            import pyotp
            import time
            time.sleep(2)  # Delay before reconnect
            
            api_key = os.getenv("ANGEL_ONE_API_KEY")
            client_id = os.getenv("ANGEL_ONE_CLIENT_ID")
            totp_seed = os.getenv("ANGEL_ONE_TOTP_SEED")
            
            if api_key and client_id and totp_seed and totp_seed != 'your_totp_seed_here':
                obj = SmartConnect(api_key=api_key)
                totp = pyotp.TOTP(totp_seed).now()
                data = obj.generateSession(client_id, client_id, totp)
                if data['status']:
                    self.feed_token = obj.getfeedToken()
                    self.auth_token = data['data']['jwtToken']
                    logger.info("Re-authenticated successfully. Reconnecting WebSocket...")
                    # Reset websocket
                    self.sws = None
                    self.connect()
                else:
                    logger.error("Re-authentication failed. Cannot reconnect.")
            else:
                logger.warning("Missing credentials for re-auth. Trying to reconnect without it.")
                self.sws = None
                self.connect()
        except Exception as e:
            logger.error(f"Error during re-auth: {e}")

    def _on_error(self, ws, error):
        logger.error(f"Angel One WebSocket Error: {error}")
        self._reauth_and_reconnect()
        
    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"Angel One WebSocket closed: {close_status_code} - {close_msg}")
        self._reauth_and_reconnect()

    def connect(self):
        if not SmartWebSocketV2:
            logger.error("smartapi-python is not installed.")
            return
            
        if not self.sws:
            try:
                self.sws = SmartWebSocketV2(
                    self.auth_token,
                    self.api_key,
                    self.client_code,
                    self.feed_token
                )
                self.sws.on_open = self._on_open
                self.sws.on_data = self._on_data
                self.sws.on_error = self._on_error
                self.sws.on_close = self._on_close

                logger.info("Connecting to Angel One WebSocket...")
                self.sws.connect()
            except Exception as e:
                logger.error(f"Failed to initialize Angel One WebSocket: {e}")

    def _subscribe_initial(self):
        """
        Example initial subscription. Override or call subscribe() explicitly.
        """
        pass

    def subscribe(self, tokens, exchange=1, mode=1, action=1):
        if self.sws:
            try:
                token_list = [{"exchangeType": exchange, "tokens": tokens}]
                self.sws.subscribe("stream_action", mode, token_list)
                logger.info(f"Subscribed to tokens: {tokens} on exchange type: {exchange} mode: {mode}")
            except Exception as e:
                logger.error(f"Error subscribing on Angel One WebSocket: {e}")
        else:
            logger.error("Angel One WebSocket is not connected yet.")

    def close(self):
        if self.sws:
            self.sws.close()


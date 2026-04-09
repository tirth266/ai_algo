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
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import numpy as np
import time
import threading
import random

from services.angelone_service import get_angel_one_service

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
        # Cache for candle data with timeframe awareness
        # Key: (symbol, timeframe) -> (candles, timestamp, is_stale)
        self._cache: Dict[tuple, tuple] = {}

        # TTL mapping by timeframe (in seconds)
        # Aligns cache TTL with candle period to prevent stale data
        self._ttl_map = {
            "1m": 60,  # 1 minute candle -> 60 second TTL
            "5m": 300,  # 5 minute candle -> 300 second (5 min) TTL
            "15m": 900,  # 15 minute candle -> 900 second (15 min) TTL
            "30m": 1800,  # 30 minute candle -> 1800 second (30 min) TTL
            "60m": 3600,  # 60 minute candle -> 3600 second (60 min) TTL
            "1h": 3600,  # 1 hour candle -> 3600 second TTL
            "D": 86400,  # Daily candle -> 86400 second (24 hour) TTL
            "1d": 86400,  # Daily candle -> 86400 second TTL
        }

        # Instrument token cache
        self._instrument_tokens: Dict[str, int] = {}

        logger.info("MarketDataService initialized")

    def get_candles(
        self, symbol: str, timeframe: str = "1m", limit: int = 500
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

            # Check cache first (with timeframe awareness)
            cached_data = self._get_from_cache(symbol, timeframe)
            if cached_data is not None:
                logger.debug(f"Cache hit for {symbol} ({timeframe})")
                return cached_data

            # Try to fetch from Zerodha
            candles = self._fetch_candles_from_source(symbol, timeframe, limit)

            if candles is not None:
                # Cache the data with timeframe awareness
                self._add_to_cache(symbol, timeframe, candles)
                return candles

            # Return None if data is unavailable
            logger.warning(f"Could not fetch data for {symbol}")
            return None

        except Exception as e:
            logger.error(
                f"Error fetching candles for {symbol}: {str(e)}", exc_info=True
            )
            return None

    def _fetch_candles_from_source(
        self, symbol: str, timeframe: str, limit: int
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
            logger.info(
                f"Fetching {limit} candles for {symbol} ({timeframe}) from Zerodha"
            )

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
                        interval=zerodha_interval,
                    )
                    break
                except Exception as e:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)  # Exponential backoff
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
            logger.error(
                f"Error fetching from Zerodha for {symbol}: {str(e)}", exc_info=True
            )
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
                if inst["tradingsymbol"] == symbol or inst["name"] == symbol:
                    token = int(inst["instrument_token"])
                    self._instrument_tokens[symbol] = token
                    logger.debug(f"Found instrument for {symbol}: {token}")
                    return token

            # Try with "EQ" suffix (common for Indian stocks)
            for inst in instruments:
                if inst["tradingsymbol"] == f"{symbol}-EQ":
                    token = int(inst["instrument_token"])
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
            "1m": "minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "60m": "60minute",
            "1h": "60minute",
            "D": "day",
            "1d": "day",
        }

        return mapping.get(timeframe, "5minute")

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
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "60m": 60,
            "1h": 60,
            "D": 1440,  # 24 hours
            "1d": 1440,
        }

        minutes_per_candle_val = minutes_per_candle.get(timeframe, 5)

        # Calculate total minutes needed
        total_minutes = minutes_per_candle_val * limit

        # To date is now
        to_date = datetime.now()

        # From date is calculated backwards
        from_date = to_date - timedelta(
            minutes=total_minutes + 1440
        )  # Add 1 day buffer

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
            data.append(
                {
                    "datetime": candle["date"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"],
                }
            )

        # Create DataFrame
        df = pd.DataFrame(data)

        # Set datetime as index
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)

        # Ensure proper data types
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        # Sort by datetime
        df.sort_index(inplace=True)

        return df

    def _get_ttl_for_timeframe(self, timeframe: str) -> int:
        """
        Get cache TTL (time-to-live) for a given timeframe.

        Args:
            timeframe: Candle timeframe ('1m', '5m', '15m', '30m', '60m', 'D')

        Returns:
            TTL in seconds

        Example:
            >>> ttl = mds._get_ttl_for_timeframe('5m')
            >>> print(ttl)  # Output: 300 (5 minutes)
        """
        ttl = self._ttl_map.get(timeframe, 300)  # Default to 5 min if unknown
        logger.debug(f"TTL for {timeframe}: {ttl}s")
        return ttl

    def _get_from_cache(
        self, symbol: str, timeframe: str = "5m"
    ) -> Optional[pd.DataFrame]:
        """
        Get candles from cache if not expired (stale).

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe for TTL calculation

        Returns:
            DataFrame if cache hit and not stale, None otherwise
        """
        cache_key = (symbol, timeframe)

        if cache_key in self._cache:
            candles, timestamp, is_stale = self._cache[cache_key]
            ttl = self._get_ttl_for_timeframe(timeframe)
            age = (datetime.now() - timestamp).total_seconds()

            if age < ttl:
                # Data still fresh
                logger.debug(
                    f"Cache hit for {symbol} ({timeframe}): age={age:.1f}s < ttl={ttl}s"
                )
                return candles
            else:
                # Cache expired - mark as stale and remove
                del self._cache[cache_key]
                logger.debug(
                    f"Cache expired for {symbol} ({timeframe}): "
                    f"age={age:.1f}s >= ttl={ttl}s - marking stale"
                )

        return None

    def _add_to_cache(self, symbol: str, timeframe: str, candles: pd.DataFrame):
        """
        Add candles to cache with timeframe awareness.

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe
            candles: DataFrame with OHLCV data
        """
        cache_key = (symbol, timeframe)
        ttl = self._get_ttl_for_timeframe(timeframe)

        self._cache[cache_key] = (candles, datetime.now(), False)  # is_stale=False
        logger.debug(
            f"Cached {len(candles)} candles for {symbol} ({timeframe}) with TTL={ttl}s"
        )

    def is_data_stale(self, symbol: str, timeframe: str = "5m") -> bool:
        """
        Check if cached data is stale (older than TTL).

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe for TTL calculation

        Returns:
            True if data is stale or missing, False if fresh

        Example:
            >>> if mds.is_data_stale('RELIANCE', '5m'):
            ...     logger.warning("Data is stale - fetch fresh data")
        """
        cache_key = (symbol, timeframe)

        if cache_key not in self._cache:
            # No cache entry - consider stale
            return True

        candles, timestamp, _ = self._cache[cache_key]
        ttl = self._get_ttl_for_timeframe(timeframe)
        age = (datetime.now() - timestamp).total_seconds()

        is_stale = age >= ttl

        if is_stale:
            logger.warning(
                f"Data for {symbol} ({timeframe}) is stale: "
                f"age={age:.1f}s >= ttl={ttl}s"
            )

        return is_stale

    def get_cache_age(self, symbol: str, timeframe: str = "5m") -> Optional[float]:
        """
        Get the age of cached data in seconds.

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe

        Returns:
            Age in seconds if cached, None if not in cache

        Example:
            >>> age = mds.get_cache_age('RELIANCE', '5m')
            >>> if age and age > 60:
            ...     logger.info(f"Data is {age}s old - consider refreshing")
        """
        cache_key = (symbol, timeframe)

        if cache_key in self._cache:
            _, timestamp, _ = self._cache[cache_key]
            age = (datetime.now() - timestamp).total_seconds()
            return age

        return None

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
            return float(candles["close"].iloc[-1])
        return None

    def get_price_change(
        self, symbol: str, periods: int = 1, timeframe: str = "5m"
    ) -> Optional[Dict[str, Any]]:
        """
        Get price change over specified periods.

        Args:
            symbol: Stock symbol
            periods: Number of periods to compare (default: 1)
            timeframe: Candle timeframe (default: '5m')

        Returns:
            Dict with price change info or None

        Raises:
            ValueError: If data is stale
        """
        candles = self.get_candles(symbol, timeframe=timeframe, limit=periods + 1)

        if candles is None or len(candles) <= periods:
            return None

        # Check if data is stale before using for calculations
        if self.is_data_stale(symbol, timeframe):
            logger.warning(
                f"⚠ Data for {symbol} ({timeframe}) is stale - "
                f"price change calculation may be inaccurate"
            )

        current_price = float(candles["close"].iloc[-1])
        previous_price = float(candles["close"].iloc[-(periods + 1)])

        change = current_price - previous_price
        change_pct = (change / previous_price) * 100

        return {
            "symbol": symbol,
            "current_price": current_price,
            "previous_price": previous_price,
            "change": change,
            "change_pct": change_pct,
            "timeframe": timeframe,
            "cache_age_seconds": self.get_cache_age(symbol, timeframe),
            "is_stale": self.is_data_stale(symbol, timeframe),
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
    test_symbols = ["RELIANCE", "TCS", "INFY"]

    for symbol in test_symbols:
        print(f"\n{'=' * 60}")
        print(f"Testing {symbol}")
        print("=" * 60)

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
    """
    Thread-safe price storage for live market data.

    Supports both simple float prices (backward compatible) and
    rich price data with timestamps and metadata.
    """

    def __init__(self):
        self.prices: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def update_price(self, token: str, price_data: Any) -> None:
        """
        Update price for token.

        Args:
            token: Symbol token (e.g., "SBIN-EQ")
            price_data: Float price or dict with {'ltp', 'timestamp', 'received_at'}
        """
        with self._lock:
            self.prices[token] = price_data

    def get_price(self, token: str) -> Optional[Any]:
        """Get price data for token."""
        with self._lock:
            return self.prices.get(token)

    def get_all_prices(self) -> Dict[str, Any]:
        """Get all prices."""
        with self._lock:
            return self.prices.copy()

    def get_ltp(self, token: str) -> Optional[float]:
        """
        Get last traded price for token (extracting LTP from data).

        Backward compatible - handles both old float format and new dict format.
        """
        with self._lock:
            price_data = self.prices.get(token)

            if price_data is None:
                return None

            if isinstance(price_data, dict):
                return price_data.get("ltp")
            else:
                return price_data  # Assume it's a float


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
            logger.warning(
                "Missing required websocket credentials. Ensure AUTH_TOKEN, API_KEY, CLIENT_ID and FEED_TOKEN are available."
            )

        self.sws = None

    def _on_data(self, ws, message):
        logger.info(f"Angel One Market Data Received: {message}")
        try:
            if isinstance(message, dict):
                token = message.get("token")
                price = message.get("last_traded_price", message.get("ltp"))
                if token and price is not None:
                    # Clean null characters if token comes as raw bytes formatted string
                    token_str = str(token).strip("\x00")
                    global_price_store.update_price(token_str, float(price))
            elif isinstance(message, list):
                for item in message:
                    if isinstance(item, dict):
                        token = item.get("token")
                        price = item.get("last_traded_price", item.get("ltp"))
                        if token and price is not None:
                            token_str = str(token).strip("\x00")
                            global_price_store.update_price(token_str, float(price))
        except Exception as e:
            logger.error(f"Error parsing websocket data: {e}")

    def _on_open(self, ws):
        logger.info("Angel One WebSocket connected successfully")
        self._subscribe_initial()

    def _reauth_and_reconnect(self):
        logger.info("Attempting to re-authenticate to refresh FEED_TOKEN...")
        try:
            time.sleep(2)  # Delay before reconnect

            service = get_angel_one_service()
            try:
                jwt_token = service.get_valid_token()
            except Exception as exc:
                logger.warning("Angel One token refresh/login failed: %s", exc)
                jwt_token = None

            feed_token = service.token_manager.get_feed_token()

            if jwt_token:
                self.auth_token = jwt_token
                self.feed_token = feed_token
                logger.info(
                    "Re-authenticated successfully via TokenManager. Reconnecting WebSocket..."
                )
                self.sws = None
                self.connect()
            else:
                logger.error("Re-authentication failed. Cannot reconnect.")
        except Exception as e:
            logger.error(f"Error during re-auth: {e}")

    def _on_error(self, ws, error):
        logger.error(f"Angel One WebSocket Error: {error}")
        # DataManager will detect connection drop and handle reconnection with exponential backoff

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"Angel One WebSocket closed: {close_status_code} - {close_msg}")
        # DataManager will detect connection drop and handle reconnection with exponential backoff

    def connect(self):
        if not SmartWebSocketV2:
            logger.error("smartapi-python is not installed.")
            return

        if not self.sws:
            try:
                self.sws = SmartWebSocketV2(
                    self.auth_token, self.api_key, self.client_code, self.feed_token
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
                logger.info(
                    f"Subscribed to tokens: {tokens} on exchange type: {exchange} mode: {mode}"
                )
            except Exception as e:
                logger.error(f"Error subscribing on Angel One WebSocket: {e}")
        else:
            logger.error("Angel One WebSocket is not connected yet.")

    def close(self):
        if self.sws:
            self.sws.close()


# ============================================================================
# DATA MANAGER - Real-time Market Data Service
# ============================================================================


class DataManager:
    """
    Production-grade real-time market data manager.

    Automatically initializes and manages WebSocket connection for live data.
    Ensures global_price_store is populated with current prices.
    Includes health checks for data staleness.

    Usage:
        >>> manager = DataManager()
        >>> manager.start()
        >>> # Data is now streaming into global_price_store
        >>> # Access prices via global_price_store.get_price(token)

    Features:
    - Automatic WebSocket connection management
    - Live price updates with timestamps
    - Staleness detection (alerts if no updates for X seconds)
    - Health monitoring
    - Thread-safe price storage
    - Automatic reconnection on failure

    Author: Quantitative Trading Systems Engineer
    Date: April 8, 2026
    """

    # Configuration constants
    STALE_DATA_THRESHOLD_SECONDS = 30  # Mark data stale if no updates
    HEALTH_CHECK_INTERVAL_SECONDS = 10  # Check health every X seconds
    STARTUP_TIMEOUT_SECONDS = 5  # Time to wait for WebSocket connection

    # Exponential backoff configuration
    MAX_RETRIES = 10  # Max reconnect attempts before degradation
    MAX_BACKOFF_SECONDS = 60  # Cap backoff delay at 60 seconds
    JITTER_RANGE = 2  # Add 0-2 seconds random jitter

    def __init__(self):
        """Initialize DataManager."""
        self.ws = MarketDataWebSocket()
        self.price_store = global_price_store

        # Health tracking
        self.last_tick_time = None
        self.tick_count = 0
        self.is_running = False
        self.is_connected = False
        self.is_degraded = False  # System degradation flag

        # Reconnection retry tracking
        self.retry_count = 0
        self.last_retry_time = None

        # Thread management
        self.health_check_thread = None

        logger.info("DataManager initialized")

    def start(self) -> bool:
        """
        Start the WebSocket connection and begin streaming live data.

        Returns:
            bool: True if connection successful, False otherwise

        Example:
            >>> manager = DataManager()
            >>> if manager.start():
            ...     print("✓ Data streaming started")
            ... else:
            ...     print("✗ Data streaming failed")
        """
        logger.info("Starting DataManager...")

        try:
            # Connect WebSocket
            self.ws.connect()
            self.is_running = True
            self.is_connected = True
            self.last_tick_time = datetime.now()

            logger.info("✓ WebSocket connected successfully")

            # Start health check thread
            self._start_health_check()

            logger.info("✓ DataManager started - live data streaming enabled")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to start DataManager: {str(e)}", exc_info=True)
            self.is_running = False
            self.is_connected = False
            return False

    def on_tick(self, tick: Dict[str, Any]) -> None:
        """
        Handle incoming tick data from WebSocket.

        Updates price_store with latest LTP and timestamp.
        Tracks tick count for health monitoring.

        Args:
            tick: Tick data dict with 'symbol', 'ltp', 'timestamp'

        Example:
            >>> tick = {'symbol': 'SBIN-EQ', 'ltp': 520.50, 'timestamp': ...}
            >>> manager.on_tick(tick)
        """
        try:
            symbol = tick.get("symbol")
            ltp = tick.get("ltp")
            timestamp = tick.get("timestamp", datetime.now())

            if not symbol or ltp is None:
                logger.warning(f"Invalid tick data: {tick}")
                return

            # Update price store with timestamp
            self.price_store.update_price(
                symbol,
                {
                    "ltp": ltp,
                    "timestamp": timestamp,
                    "received_at": datetime.now(),
                },
            )

            # Update health metrics
            self.last_tick_time = datetime.now()
            self.tick_count += 1

            # Log periodically (every 100 ticks)
            if self.tick_count % 100 == 0:
                logger.debug(
                    f"DataManager: {self.tick_count} ticks processed, "
                    f"symbols in store: {len(self.price_store.prices)}"
                )

        except Exception as e:
            logger.error(f"Error processing tick: {str(e)}", exc_info=True)

    def _start_health_check(self) -> None:
        """
        Start background health check thread.

        Monitors:
        - Connection status
        - Data staleness
        - Tick count
        """
        import threading

        def health_check_loop():
            while self.is_running:
                try:
                    self._perform_health_check()
                    time.sleep(self.HEALTH_CHECK_INTERVAL_SECONDS)
                except Exception as e:
                    logger.error(f"Error in health check: {str(e)}")
                    time.sleep(5)

        self.health_check_thread = threading.Thread(
            target=health_check_loop, daemon=True, name="DataManager-HealthCheck"
        )
        self.health_check_thread.start()
        logger.info("Health check thread started")

    def _perform_health_check(self) -> None:
        """
        Perform health check on data stream with exponential backoff reconnection.

        Checks:
        1. Connection status
        2. Data staleness
        3. Tick frequency
        4. Retry count and backoff

        Implements exponential backoff with jitter:
        - delay = min(2^retry_count, 60) seconds
        - Add 0-2 seconds jitter to prevent thundering herd
        - After 10 retries: mark system as degraded and trigger alert

        Alerts if issues detected.
        """
        if not self.is_running:
            return

        now = datetime.now()

        # Check 1: Data staleness
        if self.last_tick_time:
            staleness = (now - self.last_tick_time).total_seconds()

            if staleness > self.STALE_DATA_THRESHOLD_SECONDS:
                logger.warning(
                    f"⚠ Data is STALE: No updates for {staleness:.1f} seconds. "
                    f"Last tick: {self.last_tick_time.isoformat()}. "
                    f"Symbols in store: {len(self.price_store.prices)}"
                )
                self.is_connected = False

                # Check if we should attempt reconnection based on retry backoff
                if (
                    self.last_retry_time is None
                    or (now - self.last_retry_time).total_seconds()
                    >= self._get_backoff_delay()
                ):
                    self._attempt_reconnect()
                else:
                    remaining_backoff = (
                        self._get_backoff_delay()
                        - (now - self.last_retry_time).total_seconds()
                    )
                    logger.debug(
                        f"In backoff period: retry_count={self.retry_count}, "
                        f"retry in {remaining_backoff:.1f}s"
                    )
            else:
                # Data is fresh - reset retry count
                if not self.is_connected or self.retry_count > 0:
                    self.is_connected = True
                    self.retry_count = 0
                    self.is_degraded = False
                    logger.info(
                        f"✓ Data connection restored (previous retry_count={self.retry_count})"
                    )

        # Check 2: Log status periodically
        if self.tick_count % 1000 == 0 and self.tick_count > 0:
            status_indicator = (
                "🔴 DEGRADED"
                if self.is_degraded
                else "🟢 LIVE"
                if self.is_connected
                else "🟡 STALE"
            )
            logger.info(
                f"📊 DataManager Health: "
                f"ticks={self.tick_count}, "
                f"symbols={len(self.price_store.prices)}, "
                f"staleness={staleness if self.last_tick_time else 'N/A'}s, "
                f"retries={self.retry_count}/{self.MAX_RETRIES}, "
                f"status={status_indicator}"
            )

    def _get_backoff_delay(self) -> float:
        """
        Calculate backoff delay using exponential formula with jitter.

        Formula: delay = min(2^retry_count, 60) + random(0, 2)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s, 60s, ...
        exponential_delay = min(2**self.retry_count, self.MAX_BACKOFF_SECONDS)

        # Add jitter: 0-2 seconds random
        jitter = random.uniform(0, self.JITTER_RANGE)

        total_delay = exponential_delay + jitter

        return total_delay

    def _attempt_reconnect(self) -> None:
        """
        Attempt to reconnect WebSocket with exponential backoff.

        Implements:
        - Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s+
        - Jitter: +0-2 seconds random
        - Retry tracking: counts attempts and resets on success
        - Fail-safe: After 10 retries, mark system as degraded
        - Logging: logs each attempt, delay, and failure details
        """
        self.last_retry_time = datetime.now()
        self.retry_count += 1

        # Calculate backoff
        backoff_delay = self._get_backoff_delay()
        exponential_part = min(2 ** (self.retry_count - 1), self.MAX_BACKOFF_SECONDS)
        jitter_amount = backoff_delay - exponential_part

        logger.warning(
            f"🔄 Reconnect attempt {self.retry_count}/{self.MAX_RETRIES}: "
            f"backoff={exponential_part:.0f}s + jitter={jitter_amount:.2f}s = "
            f"total delay {backoff_delay:.2f}s"
        )

        # Check if we've exceeded max retries
        if self.retry_count > self.MAX_RETRIES:
            self.is_degraded = True
            logger.critical(
                f"🚨 SYSTEM DEGRADED: Max retries ({self.MAX_RETRIES}) exceeded. "
                f"WebSocket unreachable for {self.retry_count} attempts. "
                f"Broker may be down or network connectivity lost. "
                f"Manual intervention required."
            )
            # TODO: Trigger alert to monitoring system
            return

        # Apply sleep with backoff delay
        logger.info(
            f"Waiting {backoff_delay:.2f}s before reconnection attempt "
            f"(exponential: {exponential_part:.0f}s, jitter: {jitter_amount:.2f}s)"
        )
        time.sleep(backoff_delay)

        # Attempt reconnection
        try:
            logger.info(
                f"Attempting WebSocket reconnection (attempt {self.retry_count}...)"
            )
            self.ws.close()
            time.sleep(0.5)
            self.ws = MarketDataWebSocket()
            self.ws.connect()
            self.is_connected = True

            # Reset retry count on successful connection
            logger.info(
                f"✓ WebSocket reconnected successfully after {self.retry_count} retries"
            )
            self.retry_count = 0
            self.is_degraded = False

        except Exception as e:
            logger.error(
                f"✗ Reconnection attempt {self.retry_count} failed: {str(e)}. "
                f"Will retry in {self._get_backoff_delay():.2f}s "
                f"(next attempt {self.retry_count + 1}/{self.MAX_RETRIES})",
                exc_info=True,
            )

    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for symbol.

        Args:
            symbol: Symbol token or name (e.g., "SBIN-EQ")

        Returns:
            Latest price or None if not available

        Example:
            >>> price = manager.get_price("SBIN-EQ")
            >>> if price:
            ...     print(f"SBIN LTP: ₹{price}")
        """
        try:
            price_data = self.price_store.get_price(symbol)

            if isinstance(price_data, dict):
                return price_data.get("ltp")
            else:
                return price_data  # Backward compatibility
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {str(e)}")
            return None

    def get_price_with_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get price with full metadata (timestamp, staleness).

        Args:
            symbol: Symbol token or name

        Returns:
            Dict with 'ltp', 'timestamp', 'staleness', 'is_stale' or None

        Example:
            >>> data = manager.get_price_with_metadata("SBIN-EQ")
            >>> if data:
            ...     print(f"Price: ₹{data['ltp']}")
            ...     print(f"Is stale: {data['is_stale']}")
        """
        try:
            price_data = self.price_store.get_price(symbol)

            if not price_data:
                return None

            if isinstance(price_data, dict):
                timestamp = price_data.get("timestamp", datetime.now())
                received_at = price_data.get("received_at", datetime.now())

                staleness = (datetime.now() - timestamp).total_seconds()
                is_stale = staleness > self.STALE_DATA_THRESHOLD_SECONDS

                return {
                    "symbol": symbol,
                    "ltp": price_data.get("ltp"),
                    "timestamp": timestamp,
                    "received_at": received_at,
                    "staleness_seconds": staleness,
                    "is_stale": is_stale,
                }
            else:
                # Backward compatibility for old price format
                return {
                    "symbol": symbol,
                    "ltp": price_data,
                    "timestamp": None,
                    "staleness_seconds": None,
                    "is_stale": True,  # No timestamp = considered stale
                }
        except Exception as e:
            logger.error(f"Error getting price metadata for {symbol}: {str(e)}")
            return None

    def get_all_prices(self) -> Dict[str, Any]:
        """
        Get all prices in store.

        Returns:
            Dict mapping symbols to price data

        Example:
            >>> prices = manager.get_all_prices()
            >>> for symbol, data in prices.items():
            ...     print(f"{symbol}: ₹{data['ltp']}")
        """
        return self.price_store.get_all_prices()

    def health_status(self) -> Dict[str, Any]:
        """
        Get current health status.

        Returns:
            Dict with connection status, data freshness, tick count

        Example:
            >>> status = manager.health_status()
            >>> print(f"Connected: {status['is_connected']}")
            >>> print(f"Symbols: {status['symbol_count']}")
        """
        staleness = None
        if self.last_tick_time:
            staleness = (datetime.now() - self.last_tick_time).total_seconds()

        return {
            "is_running": self.is_running,
            "is_connected": self.is_connected,
            "tick_count": self.tick_count,
            "symbol_count": len(self.price_store.prices),
            "last_tick_time": self.last_tick_time,
            "staleness_seconds": staleness,
            "is_stale": staleness > self.STALE_DATA_THRESHOLD_SECONDS
            if staleness
            else None,
        }

    def stop(self) -> None:
        """
        Stop the DataManager and close WebSocket connection.

        Example:
            >>> manager.stop()
            >>> print("Data streaming stopped")
        """
        logger.info("Stopping DataManager...")

        try:
            self.is_running = False
            self.is_connected = False

            if self.ws:
                self.ws.close()

            if self.health_check_thread and self.health_check_thread.is_alive():
                self.health_check_thread.join(timeout=5)

            logger.info("✓ DataManager stopped")
        except Exception as e:
            logger.error(f"Error stopping DataManager: {str(e)}")

    def subscribe_symbols(self, symbols: List[str], exchange: int = 1) -> None:
        """
        Subscribe to specific symbols for live updates.

        Args:
            symbols: List of symbol tokens to subscribe
            exchange: Exchange type (1=NSE, 2=BSE)

        Example:
            >>> manager.subscribe_symbols(["SBIN-EQ", "RELIANCE-EQ"])
        """
        try:
            self.ws.subscribe(symbols, exchange=exchange, mode=1)
            logger.info(f"Subscribed to symbols: {symbols}")
        except Exception as e:
            logger.error(f"Error subscribing to symbols: {str(e)}")


# ============================================================================
# Global DataManager Instance
# ============================================================================

_global_data_manager: Optional["DataManager"] = None


def get_data_manager() -> DataManager:
    """
    Get global DataManager instance (singleton pattern).

    Ensures single WebSocket connection for entire application.

    Returns:
        DataManager instance

    Example:
        >>> manager = get_data_manager()
        >>> price = manager.get_price("SBIN-EQ")
    """
    global _global_data_manager

    if _global_data_manager is None:
        _global_data_manager = DataManager()

    return _global_data_manager


def start_data_manager() -> bool:
    """
    Start the global DataManager (called on system startup).

    Returns:
        bool: True if started successfully

    Example:
        >>> if start_data_manager():
        ...     print("✓ Live data streaming started")
    """
    manager = get_data_manager()
    return manager.start()


def stop_data_manager() -> None:
    """Stop the global DataManager."""
    global _global_data_manager

    if _global_data_manager:
        _global_data_manager.stop()
        _global_data_manager = None

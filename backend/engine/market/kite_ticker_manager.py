"""
Kite WebSocket Manager for Real-Time Market Data

Manages live ticker connection, reconnection, and candle streaming.

Author: Quantitative Trading Systems Engineer
Date: March 22, 2026
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class KiteTickerManager:
    """
    Manages Zerodha Kite WebSocket connection.
    
    Features:
    - Auto-reconnection with exponential backoff
    - Live LTP streaming
    - 1-minute candle construction
    - Callback system for price updates
    
    Usage:
        >>> ticker = KiteTickerManager()
        >>> await ticker.connect(api_key, access_token)
        >>> ticker.subscribe('NSE:RELIANCE')
        >>> ticker.on_tick = lambda tick: print(tick)
    """
    
    def __init__(self):
        """Initialize Kite Ticker Manager"""
        self.ws = None
        self.api_key = None
        self.access_token = None
        self.connected = False
        self.subscribed_tokens: Dict[str, int] = {}
        self.candles: Dict[str, List[Dict]] = {}
        self.callbacks: List[Callable] = []
        
        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 2  # seconds
        
        logger.info("KiteTickerManager initialized")
    
    async def connect(self, api_key: str, access_token: str) -> bool:
        """
        Connect to Kite WebSocket.
        
        Args:
            api_key: Kite API key
            access_token: Access token from login
            
        Returns:
            Connection status
        """
        try:
            self.api_key = api_key
            self.access_token = access_token
            
            # Import KiteConnect
            from kite_connect import KiteTicker
            
            self.ws = KiteTicker(api_key=self.api_key, access_token=self.access_token)
            
            # Register callbacks
            self.ws.on_ticks = self._on_ticks
            self.ws.on_connect = self._on_connect
            self.ws.on_close = self._on_close
            self.ws.on_error = self._on_error
            self.ws.on_reconnect = self._on_reconnect
            self.ws.on_noreconnect = self._on_noreconnect
            
            # Start WebSocket (non-blocking)
            self.ws.connect(threaded=True)
            
            # Wait for connection
            await asyncio.sleep(2)
            
            if self.connected:
                logger.info("Connected to Kite WebSocket")
                return True
            else:
                logger.error("Connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}", exc_info=True)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        if self.ws:
            self.ws.close()
            self.connected = False
            logger.info("Disconnected from Kite WebSocket")
    
    def subscribe(self, symbol: str, exchange: str = 'NSE') -> bool:
        """
        Subscribe to instrument ticks.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange segment
            
        Returns:
            Subscription status
        """
        try:
            if not self.connected:
                logger.error("Not connected to WebSocket")
                return False
            
            # Get instrument token
            instrument_token = self._get_instrument_token(symbol, exchange)
            
            if not instrument_token:
                logger.error(f"Instrument token not found for {symbol}")
                return False
            
            # Subscribe
            self.ws.subscribe([instrument_token])
            self.ws.set_mode(self.ws.MODE_QUOTE, [instrument_token])
            
            # Track subscription
            self.subscribed_tokens[symbol] = instrument_token
            
            # Initialize candle storage
            self.candles[symbol] = []
            
            logger.info(f"Subscribed to {symbol} (token: {instrument_token})")
            return True
            
        except Exception as e:
            logger.error(f"Subscription failed: {str(e)}")
            return False
    
    def unsubscribe(self, symbol: str) -> bool:
        """Unsubscribe from instrument"""
        if symbol not in self.subscribed_tokens:
            return False
        
        try:
            token = self.subscribed_tokens[symbol]
            self.ws.unsubscribe([token])
            del self.subscribed_tokens[symbol]
            
            logger.info(f"Unsubscribed {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Unsubscription failed: {str(e)}")
            return False
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """Get last traded price for symbol"""
        # This would be populated by _on_ticks callback
        # For now, return None (will be implemented with real data)
        return None
    
    def get_candle(self, symbol: str, timeframe: str = '1minute') -> Optional[Dict]:
        """Get current incomplete candle"""
        if symbol not in self.candles or not self.candles[symbol]:
            return None
        
        return self.candles[symbol][-1]
    
    def register_callback(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for tick events"""
        self.callbacks.append(callback)
        logger.debug(f"Callback registered: {callback.__name__}")
    
    def _on_ticks(self, ws, ticks: List[Dict]) -> None:
        """
        Handle incoming ticks.
        
        Args:
            ws: WebSocket instance
            ticks: List of tick data
        """
        try:
            for tick in ticks:
                # Find symbol for this token
                symbol = None
                for sym, token in self.subscribed_tokens.items():
                    if token == tick['instrument_token']:
                        symbol = sym
                        break
                
                if not symbol:
                    continue
                
                # Process tick
                tick_data = {
                    'symbol': symbol,
                    'instrument_token': tick['instrument_token'],
                    'last_price': tick.get('last_price', 0),
                    'ohlc': tick.get('ohlc', {}),
                    'depth': tick.get('depth', {}),
                    'timestamp': datetime.now(),
                    'exchange_timestamp': tick.get('exchange_timestamp')
                }
                
                # Update/build candle
                self._update_candle(symbol, tick_data)
                
                # Call registered callbacks
                for callback in self.callbacks:
                    try:
                        callback(tick_data)
                    except Exception as e:
                        logger.error(f"Callback error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing ticks: {str(e)}")
    
    def _update_candle(self, symbol: str, tick_data: Dict) -> None:
        """
        Update current candle or create new one.
        
        Args:
            symbol: Trading symbol
            tick_data: Tick information
        """
        current_time = datetime.now()
        current_minute = current_time.replace(second=0, microsecond=0)
        
        candles = self.candles[symbol]
        
        # Check if we need a new candle
        if not candles or candles[-1]['timestamp'] != current_minute:
            # Create new candle
            new_candle = {
                'symbol': symbol,
                'timestamp': current_minute,
                'open': tick_data['last_price'],
                'high': tick_data['last_price'],
                'low': tick_data['last_price'],
                'close': tick_data['last_price'],
                'volume': 0
            }
            candles.append(new_candle)
        else:
            # Update existing candle
            candle = candles[-1]
            candle['high'] = max(candle['high'], tick_data['last_price'])
            candle['low'] = min(candle['low'], tick_data['last_price'])
            candle['close'] = tick_data['last_price']
            candle['volume'] += 1
    
    def _on_connect(self, ws, response: str) -> None:
        """WebSocket connected"""
        logger.info("WebSocket connected")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Resubscribe to all tokens
        for symbol, token in self.subscribed_tokens.items():
            try:
                ws.subscribe([token])
                ws.set_mode(ws.MODE_QUOTE, [token])
            except Exception as e:
                logger.error(f"Resubscription failed for {symbol}: {str(e)}")
    
    def _on_close(self, ws, code: int, reason: str) -> None:
        """WebSocket closed"""
        logger.info(f"WebSocket closed: {code} - {reason}")
        self.connected = False
    
    def _on_error(self, ws, code: int, reason: str) -> None:
        """WebSocket error"""
        logger.error(f"WebSocket error: {code} - {reason}")
    
    def _on_reconnect(self, ws, attempt: int) -> None:
        """Reconnection attempt"""
        logger.info(f"Reconnecting (attempt {attempt})")
        self.reconnect_attempts = attempt
    
    def _on_noreconnect(self, ws, attempt: int) -> None:
        """Reconnection failed"""
        logger.error(f"Reconnection failed after {attempt} attempts")
        self.connected = False
    
    def _get_instrument_token(self, symbol: str, exchange: str) -> Optional[int]:
        """
        Get instrument token for symbol.
        
        This would normally query from instrument master list.
        For now, returns mock tokens.
        """
        # TODO: Load from NSE instrument master
        mock_tokens = {
            'RELIANCE': 738561,
            'TCS': 4267265,
            'INFY': 408065,
            'HDFCBANK': 415745,
            'NIFTY50': 256265
        }
        
        return mock_tokens.get(symbol.upper())


# Global ticker instance
_ticker_manager: Optional[KiteTickerManager] = None


def get_ticker_manager() -> KiteTickerManager:
    """Get or create global ticker manager"""
    global _ticker_manager
    
    if _ticker_manager is None:
        _ticker_manager = KiteTickerManager()
    
    return _ticker_manager

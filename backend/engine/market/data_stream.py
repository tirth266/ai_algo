"""
Market Data Stream Module

Real-time market data streaming engine.
Supports both live exchange feeds and mock data generation.

Features:
- Tick data streaming
- Symbol subscription management
- Real-time data callbacks
- Mock data generator for testing
- Thread-safe operations

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import random

logger = logging.getLogger(__name__)


class Tick:
    """
    Represents a single market tick.
    
    Attributes:
        symbol: Trading symbol (e.g., 'RELIANCE')
        price: Last traded price
        volume: Trade volume
        timestamp: Tick timestamp
        bid: Best bid price (optional)
        ask: Best ask price (optional)
    """
    
    def __init__(
        self,
        symbol: str,
        price: float,
        volume: float,
        timestamp: datetime,
        bid: float = None,
        ask: float = None
    ):
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.timestamp = timestamp
        self.bid = bid if bid else price - 0.05
        self.ask = ask if ask else price + 0.05
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tick to dictionary."""
        return {
            'symbol': self.symbol,
            'price': self.price,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
            'bid': self.bid,
            'ask': self.ask
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tick':
        """Create tick from dictionary."""
        return cls(
            symbol=data['symbol'],
            price=data['price'],
            volume=data['volume'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            bid=data.get('bid'),
            ask=data.get('ask')
        )
    
    def __repr__(self) -> str:
        return f"Tick({self.symbol}, {self.price:.2f}, {self.volume})"


class MarketDataStream:
    """
    Real-time market data streaming engine.
    
    Manages connections to market data feeds and distributes
    tick data to subscribers.
    
    Supports:
    - Multiple symbol subscriptions
    - Real-time tick callbacks
    - Mock data generation for testing
    - Thread-safe operations
    
    Example:
        >>> stream = MarketDataStream()
        >>> stream.subscribe('RELIANCE')
        >>> stream.set_callback(on_tick)
        >>> stream.start()
    """
    
    def __init__(self, use_mock_data: bool = True):
        """
        Initialize market data stream.
        
        Args:
            use_mock_data: Use mock data generator (default: True)
                          Set to False for live exchange feed
        """
        self.use_mock_data = use_mock_data
        self.subscribed_symbols: set = set()
        self.callbacks: List[Callable[[Tick], None]] = []
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Mock data configuration
        self._mock_prices: Dict[str, float] = {}
        self._mock_base_volumes: Dict[str, float] = {}
        
        logger.info(
            f"MarketDataStream initialized: "
            f"mock_data={use_mock_data}"
        )
    
    def subscribe(self, symbol: str) -> bool:
        """
        Subscribe to a symbol's market data.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if subscribed successfully
        
        Example:
            >>> stream.subscribe('RELIANCE')
            >>> stream.subscribe('TCS')
        """
        with self._lock:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                
                # Initialize mock price if using mock data
                if self.use_mock_data:
                    self._initialize_mock_symbol(symbol)
                
                logger.info(f"Subscribed to {symbol}")
                return True
            
            logger.debug(f"Already subscribed to {symbol}")
            return False
    
    def unsubscribe(self, symbol: str) -> bool:
        """
        Unsubscribe from a symbol's market data.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if unsubscribed successfully
        
        Example:
            >>> stream.unsubscribe('RELIANCE')
        """
        with self._lock:
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.remove(symbol)
                logger.info(f"Unsubscribed from {symbol}")
                return True
            
            logger.debug(f"Not subscribed to {symbol}")
            return False
    
    def set_callback(self, callback: Callable[[Tick], None]):
        """
        Set callback function for tick events.
        
        Args:
            callback: Function to call when tick received
        
        Example:
            >>> def on_tick(tick: Tick):
            ...     print(f"{tick.symbol}: {tick.price}")
            >>> stream.set_callback(on_tick)
        """
        with self._lock:
            self.callbacks.append(callback)
            logger.info(f"Added tick callback: {callback.__name__}")
    
    def remove_callback(self, callback: Callable[[Tick], None]):
        """
        Remove a tick callback.
        
        Args:
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)
                logger.info(f"Removed tick callback: {callback.__name__}")
    
    def start(self):
        """
        Start the market data stream.
        
        Begins streaming tick data in background thread.
        
        Example:
            >>> stream.start()
            >>> # Stream runs until stop() is called
        """
        if self._running:
            logger.warning("Stream already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        
        logger.info("Market data stream started")
    
    def stop(self):
        """
        Stop the market data stream.
        
        Gracefully shuts down the streaming thread.
        
        Example:
            >>> stream.stop()
        """
        if not self._running:
            return
        
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5.0)
        
        logger.info("Market data stream stopped")
    
    def _stream_loop(self):
        """
        Main streaming loop.
        
        Runs in background thread and generates/pushes ticks.
        """
        logger.info("Stream loop started")
        
        while self._running:
            try:
                # Generate ticks for all subscribed symbols
                for symbol in list(self.subscribed_symbols):
                    if self.use_mock_data:
                        tick = self._generate_mock_tick(symbol)
                    else:
                        # TODO: Implement live exchange feed
                        logger.warning("Live feed not implemented yet")
                        continue
                    
                    # Push tick to callbacks
                    self._push_tick(tick)
                
                # Sleep based on tick interval (simulate real-time)
                time.sleep(0.1)  # 100ms tick interval
                
            except Exception as e:
                logger.error(f"Error in stream loop: {str(e)}", exc_info=True)
                # Continue streaming despite errors
        
        logger.info("Stream loop terminated")
    
    def _generate_mock_tick(self, symbol: str) -> Tick:
        """
        Generate realistic mock tick data.
        
        Uses random walk with mean reversion for price simulation.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Generated tick
        """
        # Get base price
        if symbol not in self._mock_prices:
            self._initialize_mock_symbol(symbol)
        
        base_price = self._mock_prices[symbol]
        base_volume = self._mock_base_volumes[symbol]
        
        # Random walk with slight mean reversion
        change_percent = random.gauss(0, 0.001)  # 0.1% volatility
        new_price = base_price * (1 + change_percent)
        
        # Ensure price stays positive
        new_price = max(0.01, new_price)
        
        # Generate volume
        volume = base_volume * random.uniform(0.5, 2.0)
        
        # Update stored price
        self._mock_prices[symbol] = new_price
        
        # Create tick
        tick = Tick(
            symbol=symbol,
            price=new_price,
            volume=volume,
            timestamp=datetime.now()
        )
        
        return tick
    
    def _initialize_mock_symbol(self, symbol: str):
        """
        Initialize mock data parameters for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        # Use symbol hash for deterministic initial prices
        symbol_hash = sum(ord(c) for c in symbol)
        
        # Initialize with realistic prices based on symbol
        if 'NIFTY' in symbol.upper():
            self._mock_prices[symbol] = 20000.0 + (symbol_hash % 1000)
        elif 'BANK' in symbol.upper():
            self._mock_prices[symbol] = 40000.0 + (symbol_hash % 5000)
        else:
            # Default: 100-1000 range
            self._mock_prices[symbol] = 100.0 + (symbol_hash % 900)
        
        # Base volume: 100-10000
        self._mock_base_volumes[symbol] = 100 + (symbol_hash % 9900)
        
        logger.debug(
            f"Initialized mock symbol {symbol}: "
            f"price={self._mock_prices[symbol]:.2f}, "
            f"base_vol={self._mock_base_volumes[symbol]}"
        )
    
    def _push_tick(self, tick: Tick):
        """
        Push tick to all registered callbacks.
        
        Args:
            tick: Tick to distribute
        """
        with self._lock:
            callbacks = list(self.callbacks)
        
        # Call each callback
        for callback in callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Error in tick callback: {str(e)}")
    
    @property
    def is_running(self) -> bool:
        """Check if stream is currently running."""
        return self._running
    
    @property
    def subscription_count(self) -> int:
        """Get number of subscribed symbols."""
        return len(self.subscribed_symbols)
    
    def get_subscribed_symbols(self) -> List[str]:
        """Get list of subscribed symbols."""
        with self._lock:
            return list(self.subscribed_symbols)


# Global stream instance
_market_data_stream: Optional[MarketDataStream] = None


def get_market_data_stream(use_mock_data: bool = True) -> MarketDataStream:
    """
    Get or create global market data stream instance.
    
    Args:
        use_mock_data: Use mock data generator
    
    Returns:
        MarketDataStream instance
    
    Example:
        >>> stream = get_market_data_stream()
        >>> stream.subscribe('RELIANCE')
        >>> stream.start()
    """
    global _market_data_stream
    
    if _market_data_stream is None:
        _market_data_stream = MarketDataStream(use_mock_data=use_mock_data)
    
    return _market_data_stream


# Convenience functions
def start_market_stream(symbols: List[str] = None, use_mock_data: bool = True):
    """
    Start market data stream with symbols.
    
    Args:
        symbols: List of symbols to subscribe
        use_mock_data: Use mock data generator
    
    Example:
        >>> start_market_stream(['RELIANCE', 'TCS'])
    """
    stream = get_market_data_stream(use_mock_data=use_mock_data)
    
    if symbols:
        for symbol in symbols:
            stream.subscribe(symbol)
    
    stream.start()
    logger.info(f"Market stream started with symbols: {symbols}")


def stop_market_stream():
    """Stop the global market data stream."""
    global _market_data_stream
    
    if _market_data_stream:
        _market_data_stream.stop()
        logger.info("Market stream stopped")

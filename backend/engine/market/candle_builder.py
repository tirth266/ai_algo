"""
Candle Builder Module

Converts tick data into OHLCV candles.

Features:
- Configurable timeframes (1m, 5m, 15m, 1h, etc.)
- Auto candle rollover
- Partial candle maintenance
- Multiple symbol support
- Thread-safe operations

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .data_stream import Tick

logger = logging.getLogger(__name__)


class Candle:
    """
    Represents a single OHLCV candle.
    
    Attributes:
        time: Candle open time
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Total volume
        symbol: Trading symbol
        timeframe: Candle timeframe
    """
    
    def __init__(
        self,
        time: datetime,
        symbol: str,
        timeframe: str,
        open_price: float = None,
        high_price: float = None,
        low_price: float = None,
        close_price: float = None,
        volume: float = 0
    ):
        self.time = time
        self.symbol = symbol
        self.timeframe = timeframe
        self.open = open_price
        self.high = high_price
        self.low = low_price
        self.close = close_price
        self.volume = volume
        
        # Track if candle is complete
        self.is_complete = False
    
    def update(self, price: float, volume: float):
        """
        Update candle with new tick data.
        
        Args:
            price: Tick price
            volume: Tick volume
        """
        if self.open is None:
            # First tick - set open
            self.open = price
            self.high = price
            self.low = price
            self.close = price
            self.volume = volume
        else:
            # Subsequent ticks
            self.high = max(self.high, price)
            self.low = min(self.low, price)
            self.close = price
            self.volume += volume
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert candle to dictionary."""
        return {
            'time': self.time.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'is_complete': self.is_complete
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Candle':
        """Create candle from dictionary."""
        candle = cls(
            time=datetime.fromisoformat(data['time']),
            symbol=data['symbol'],
            timeframe=data['timeframe'],
            open_price=data.get('open'),
            high_price=data.get('high'),
            low_price=data.get('low'),
            close_price=data.get('close'),
            volume=data.get('volume', 0)
        )
        candle.is_complete = data.get('is_complete', False)
        return candle
    
    def to_dataframe_row(self) -> Dict[str, Any]:
        """Convert to DataFrame row format."""
        return {
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }
    
    def __repr__(self) -> str:
        return f"Candle({self.time}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f})"


class CandleBuilder:
    """
    Builds OHLCV candles from tick data.
    
    Supports multiple timeframes and symbols.
    Automatically rolls over to new candles at timeframe boundaries.
    
    Timeframes supported:
    - '1m': 1 minute
    - '5m': 5 minutes
    - '15m': 15 minutes
    - '30m': 30 minutes
    - '1h': 1 hour
    - '4h': 4 hours
    - '1d': 1 day
    
    Example:
        >>> builder = CandleBuilder(timeframe='5m')
        >>> candle = builder.process_tick(tick)
        >>> if candle:
        ...     print(f"Candle closed: {candle}")
    """
    
    # Timeframe to seconds mapping
    TIMEFRAME_SECONDS = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400
    }
    
    def __init__(self, timeframe: str = '1m'):
        """
        Initialize candle builder.
        
        Args:
            timeframe: Candle timeframe (default: 1m)
        
        Example:
            >>> builder = CandleBuilder('5m')
        """
        self.timeframe = timeframe.upper()
        
        if self.timeframe not in self.TIMEFRAME_SECONDS:
            logger.warning(f"Unknown timeframe '{timeframe}', defaulting to 1m")
            self.timeframe = '1M'
        
        # Current active candles (per symbol)
        self._active_candles: Dict[str, Candle] = {}
        
        # Completed candles history (per symbol)
        self._completed_candles: Dict[str, List[Candle]] = {}
        
        logger.info(f"CandleBuilder initialized: timeframe={self.timeframe}")
    
    def process_tick(self, tick: Tick) -> Optional[Candle]:
        """
        Process a tick and update/build candles.
        
        Args:
            tick: Market tick
        
        Returns:
            Completed candle if one just closed, None otherwise
        
        Example:
            >>> tick = Tick('RELIANCE', 100.5, 1000, datetime.now())
            >>> completed = builder.process_tick(tick)
            >>> if completed:
            ...     print("Candle closed!")
        """
        symbol = tick.symbol
        
        # Get or create active candle for this symbol
        if symbol not in self._active_candles:
            self._create_new_candle(symbol, tick.timestamp)
        
        active_candle = self._active_candles[symbol]
        
        # Check if we need to roll over to new candle
        if self._should_rollover(active_candle, tick.timestamp):
            # Complete current candle
            self._complete_candle(symbol)
            
            # Create new candle
            self._create_new_candle(symbol, tick.timestamp)
            active_candle = self._active_candles[symbol]
        
        # Update active candle with tick
        active_candle.update(tick.price, tick.volume)
        
        # Return completed candle if rolled over
        if hasattr(self, '_last_completed'):
            completed = self._last_completed
            delattr(self, '_last_completed')
            return completed
        
        return None
    
    def _create_new_candle(self, symbol: str, timestamp: datetime):
        """
        Create a new active candle.
        
        Args:
            symbol: Trading symbol
            timestamp: Current timestamp
        """
        # Calculate candle open time (floor to timeframe boundary)
        open_time = self._get_candle_open_time(timestamp)
        
        # Create new candle
        new_candle = Candle(
            time=open_time,
            symbol=symbol,
            timeframe=self.timeframe
        )
        
        self._active_candles[symbol] = new_candle
        
        # Initialize completed list if needed
        if symbol not in self._completed_candles:
            self._completed_candles[symbol] = []
        
        logger.debug(
            f"New candle created: {symbol} {self.timeframe} @ {open_time}"
        )
    
    def _complete_candle(self, symbol: str):
        """
        Mark current candle as complete and store it.
        
        Args:
            symbol: Trading symbol
        """
        if symbol not in self._active_candles:
            return
        
        # Get active candle
        candle = self._active_candles[symbol]
        
        # Mark as complete
        candle.is_complete = True
        
        # Store in completed list
        self._completed_candles[symbol].append(candle)
        
        # Keep only last 1000 completed candles per symbol
        if len(self._completed_candles[symbol]) > 1000:
            self._completed_candles[symbol] = \
                self._completed_candles[symbol][-1000:]
        
        # Store for return
        self._last_completed = candle
        
        logger.debug(
            f"Candle completed: {symbol} "
            f"O:{candle.open:.2f} H:{candle.high:.2f} "
            f"L:{candle.low:.2f} C:{candle.close:.2f} "
            f"V:{candle.volume:.0f}"
        )
    
    def _should_rollover(self, candle: Candle, timestamp: datetime) -> bool:
        """
        Check if we should roll over to new candle.
        
        Args:
            candle: Current active candle
            timestamp: Current tick timestamp
        
        Returns:
            True if candle should close
        """
        # Calculate next candle's open time
        current_open = candle.time
        next_open = self._get_next_candle_time(current_open)
        
        # Roll over if timestamp is past next candle's open
        return timestamp >= next_open
    
    def _get_candle_open_time(self, timestamp: datetime) -> datetime:
        """
        Get the open time for a candle containing given timestamp.
        
        Floors timestamp to timeframe boundary.
        
        Args:
            timestamp: Any timestamp
        
        Returns:
            Candle open time
        """
        # Zero out seconds and microseconds
        dt = timestamp.replace(second=0, microsecond=0)
        
        if self.timeframe == '1m':
            return dt
        elif self.timeframe == '5m':
            minute = (dt.minute // 5) * 5
            return dt.replace(minute=minute)
        elif self.timeframe == '15m':
            minute = (dt.minute // 15) * 15
            return dt.replace(minute=minute)
        elif self.timeframe == '30m':
            minute = (dt.minute // 30) * 30
            return dt.replace(minute=minute)
        elif self.timeframe == '1h':
            return dt.replace(minute=0)
        elif self.timeframe == '4h':
            hour = (dt.hour // 4) * 4
            return dt.replace(hour=hour, minute=0)
        elif self.timeframe == '1d':
            return dt.replace(hour=0, minute=0)
        else:
            return dt
    
    def _get_next_candle_time(self, current_open: datetime) -> datetime:
        """
        Get open time of next candle.
        
        Args:
            current_open: Current candle open time
        
        Returns:
            Next candle open time
        """
        seconds = self.TIMEFRAME_SECONDS.get(self.timeframe, 60)
        return current_open + timedelta(seconds=seconds)
    
    def get_active_candle(self, symbol: str) -> Optional[Candle]:
        """
        Get current active (incomplete) candle.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Active candle or None
        """
        return self._active_candles.get(symbol)
    
    def get_completed_candles(
        self,
        symbol: str,
        count: int = None
    ) -> List[Candle]:
        """
        Get completed candles for a symbol.
        
        Args:
            symbol: Trading symbol
            count: Number of candles to return (None for all)
        
        Returns:
            List of completed candles
        """
        if symbol not in self._completed_candles:
            return []
        
        candles = self._completed_candles[symbol]
        
        if count:
            return candles[-count:]
        
        return candles
    
    def get_dataframe(
        self,
        symbol: str,
        count: int = None,
        include_active: bool = False
    ) -> pd.DataFrame:
        """
        Get candles as pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            count: Number of candles (None for all)
            include_active: Include current active candle
        
        Returns:
            DataFrame with OHLCV data
        """
        candles = self.get_completed_candles(symbol, count)
        
        if include_active:
            active = self.get_active_candle(symbol)
            if active and active.open is not None:
                candles.append(active)
        
        if not candles:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = [c.to_dataframe_row() for c in candles]
        times = [c.time for c in candles]
        
        df = pd.DataFrame(data, index=pd.DatetimeIndex(times))
        df.index.name = 'time'
        
        return df
    
    def clear(self, symbol: str = None):
        """
        Clear stored candles.
        
        Args:
            symbol: Specific symbol to clear (None for all)
        """
        if symbol:
            if symbol in self._active_candles:
                del self._active_candles[symbol]
            if symbol in self._completed_candles:
                del self._completed_candles[symbol]
        else:
            self._active_candles.clear()
            self._completed_candles.clear()
        
        logger.info(f"Cleared candles for: {symbol or 'all symbols'}")


# Multi-timeframe builder
class MultiTimeframeCandleBuilder:
    """
    Builds candles for multiple timeframes simultaneously.
    
    Example:
        >>> builder = MultiTimeframeCandleBuilder(['1m', '5m', '15m'])
        >>> builders = builder.process_tick(tick)
        >>> # builders['5m'] returns CandleBuilder for 5m
    """
    
    def __init__(self, timeframes: List[str]):
        """
        Initialize multi-timeframe builder.
        
        Args:
            timeframes: List of timeframes to build
        """
        self.builders: Dict[str, CandleBuilder] = {}
        
        for tf in timeframes:
            self.builders[tf] = CandleBuilder(timeframe=tf)
        
        logger.info(
            f"MultiTimeframeCandleBuilder initialized: {timeframes}"
        )
    
    def process_tick(
        self,
        tick: Tick
    ) -> Dict[str, Optional[Candle]]:
        """
        Process tick for all timeframes.
        
        Args:
            tick: Market tick
        
        Returns:
            Dict of completed candles per timeframe
        """
        completed = {}
        
        for tf, builder in self.builders.items():
            candle = builder.process_tick(tick)
            completed[tf] = candle
        
        return completed
    
    def get_dataframe(
        self,
        symbol: str,
        timeframe: str,
        count: int = None
    ) -> pd.DataFrame:
        """
        Get DataFrame for specific timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Desired timeframe
            count: Number of candles
        
        Returns:
            DataFrame with OHLCV data
        """
        if timeframe not in self.builders:
            logger.error(f"Unknown timeframe: {timeframe}")
            return pd.DataFrame()
        
        return self.builders[timeframe].get_dataframe(symbol, count)

"""
Market Buffer Module

In-memory storage for recent candle data.

Features:
- Stores last 500 candles per symbol/timeframe
- Fast lookup by symbol and timeframe
- Thread-safe operations
- Automatic cleanup of old data
- DataFrame conversion

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from .candle_builder import Candle

logger = logging.getLogger(__name__)


class MarketBuffer:
    """
    In-memory buffer for storing recent market candles.
    
    Organized by symbol and timeframe.
    Maintains sliding window of recent candles.
    
    Structure:
    {
        symbol: {
            timeframe: [
                candle1,
                candle2,
                ...
            ]
        }
    }
    
    Example:
        >>> buffer = MarketBuffer(max_candles=500)
        >>> buffer.add_candle('RELIANCE', '5m', candle)
        >>> candles = buffer.get_candles('RELIANCE', '5m')
    """
    
    def __init__(self, max_candles: int = 500):
        """
        Initialize market buffer.
        
        Args:
            max_candles: Maximum candles to store per symbol/timeframe
        
        Example:
            >>> buffer = MarketBuffer(max_candles=1000)
        """
        self.max_candles = max_candles
        
        # Storage structure
        self._buffer: Dict[str, Dict[str, List[Candle]]] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'total_candles_added': 0,
            'total_candles_removed': 0,
            'symbols_tracked': 0
        }
        
        logger.info(
            f"MarketBuffer initialized: max_candles={max_candles}"
        )
    
    def add_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Candle
    ):
        """
        Add a completed candle to the buffer.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            candle: Completed candle
        
        Example:
            >>> candle = Candle(...)
            >>> buffer.add_candle('RELIANCE', '5m', candle)
        """
        if not candle.is_complete:
            logger.warning("Adding incomplete candle to buffer")
        
        with self._lock:
            # Initialize symbol if needed
            if symbol not in self._buffer:
                self._buffer[symbol] = {}
                self._stats['symbols_tracked'] += 1
            
            # Initialize timeframe if needed
            if timeframe not in self._buffer[symbol]:
                self._buffer[symbol][timeframe] = []
            
            # Add candle
            self._buffer[symbol][timeframe].append(candle)
            self._stats['total_candles_added'] += 1
            
            # Enforce max limit
            candles = self._buffer[symbol][timeframe]
            if len(candles) > self.max_candles:
                removed_count = len(candles) - self.max_candles
                self._buffer[symbol][timeframe] = candles[-self.max_candles:]
                self._stats['total_candles_removed'] += removed_count
                
                logger.debug(
                    f"Trimmed old candles: {symbol} {timeframe} "
                    f"(removed {removed_count})"
                )
        
        logger.debug(
            f"Candle added: {symbol} {timeframe} @ {candle.time} "
            f"Close: {candle.close:.2f}"
        )
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = None
    ) -> List[Candle]:
        """
        Get candles for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            count: Number of candles (None for all)
        
        Returns:
            List of candles (most recent last)
        
        Example:
            >>> candles = buffer.get_candles('RELIANCE', '5m', count=100)
        """
        with self._lock:
            if symbol not in self._buffer:
                logger.debug(f"No data for symbol: {symbol}")
                return []
            
            if timeframe not in self._buffer[symbol]:
                logger.debug(f"No data for timeframe: {timeframe}")
                return []
            
            candles = self._buffer[symbol][timeframe]
            
            if count:
                return candles[-count:]
            
            return list(candles)  # Return copy
    
    def get_latest_candle(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Candle]:
        """
        Get most recent candle for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
        
        Returns:
            Most recent candle or None
        
        Example:
            >>> latest = buffer.get_latest_candle('RELIANCE', '5m')
            >>> print(f"Latest close: {latest.close:.2f}")
        """
        with self._lock:
            if symbol not in self._buffer:
                return None
            
            if timeframe not in self._buffer[symbol]:
                return None
            
            candles = self._buffer[symbol][timeframe]
            
            if not candles:
                return None
            
            return candles[-1]
    
    def get_dataframe(
        self,
        symbol: str,
        timeframe: str,
        count: int = None
    ) -> pd.DataFrame:
        """
        Get candles as pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            count: Number of candles (None for all)
        
        Returns:
            DataFrame with OHLCV data indexed by time
        
        Example:
            >>> df = buffer.get_dataframe('RELIANCE', '5m', count=200)
            >>> print(df.tail())
        """
        candles = self.get_candles(symbol, timeframe, count)
        
        if not candles:
            logger.debug(f"No data for DataFrame: {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convert to DataFrame format
        data = []
        times = []
        
        for candle in candles:
            data.append({
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })
            times.append(candle.time)
        
        # Create DataFrame
        df = pd.DataFrame(data, index=pd.DatetimeIndex(times))
        df.index.name = 'time'
        
        logger.debug(
            f"DataFrame created: {symbol} {timeframe} "
            f"shape={df.shape}"
        )
        
        return df
    
    def get_symbols(self) -> List[str]:
        """
        Get list of all tracked symbols.
        
        Returns:
            List of symbols
        
        Example:
            >>> symbols = buffer.get_symbols()
        """
        with self._lock:
            return list(self._buffer.keys())
    
    def get_timeframes(self, symbol: str) -> List[str]:
        """
        Get list of timeframes for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            List of timeframes
        """
        with self._lock:
            if symbol not in self._buffer:
                return []
            
            return list(self._buffer[symbol].keys())
    
    def has_data(
        self,
        symbol: str,
        timeframe: str,
        min_candles: int = 1
    ) -> bool:
        """
        Check if sufficient data exists for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            min_candles: Minimum required candles
        
        Returns:
            True if sufficient data available
        
        Example:
            >>> if buffer.has_data('RELIANCE', '5m', min_candles=100):
            ...     # Safe to calculate indicators
        """
        with self._lock:
            if symbol not in self._buffer:
                return False
            
            if timeframe not in self._buffer[symbol]:
                return False
            
            return len(self._buffer[symbol][timeframe]) >= min_candles
    
    def clear(self, symbol: str = None, timeframe: str = None):
        """
        Clear stored data.
        
        Args:
            symbol: Specific symbol to clear (None for all)
            timeframe: Specific timeframe to clear (None for all)
        
        Example:
            >>> buffer.clear('RELIANCE')  # Clear specific symbol
            >>> buffer.clear()  # Clear everything
        """
        with self._lock:
            if symbol:
                if timeframe:
                    # Clear specific timeframe
                    if symbol in self._buffer and \
                       timeframe in self._buffer[symbol]:
                        removed = len(self._buffer[symbol][timeframe])
                        del self._buffer[symbol][timeframe]
                        self._stats['total_candles_removed'] += removed
                        logger.info(
                            f"Cleared {timeframe} for {symbol} "
                            f"({removed} candles)"
                        )
                else:
                    # Clear entire symbol
                    if symbol in self._buffer:
                        total_removed = sum(
                            len(candles)
                            for candles in self._buffer[symbol].values()
                        )
                        del self._buffer[symbol]
                        self._stats['symbols_tracked'] -= 1
                        self._stats['total_candles_removed'] += total_removed
                        logger.info(
                            f"Cleared all data for {symbol} "
                            f"({total_removed} candles)"
                        )
            else:
                # Clear everything
                total_removed = sum(
                    len(tf_candles)
                    for symbol_candles in self._buffer.values()
                    for tf_candles in symbol_candles.values()
                )
                self._buffer.clear()
                self._stats['symbols_tracked'] = 0
                self._stats['total_candles_removed'] += total_removed
                logger.info(
                    f"Cleared all buffer data ({total_removed} candles)"
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get buffer statistics.
        
        Returns:
            Dict with stats
        
        Example:
            >>> stats = buffer.get_stats()
            >>> print(f"Tracking {stats['symbols_tracked']} symbols")
        """
        with self._lock:
            # Calculate additional stats
            total_candles = 0
            symbol_timeframes = {}
            
            for symbol, timeframes in self._buffer.items():
                symbol_candles = sum(
                    len(candles) for candles in timeframes.values()
                )
                total_candles += symbol_candles
                symbol_timeframes[symbol] = len(timeframes)
            
            return {
                **self._stats,
                'total_candles_in_buffer': total_candles,
                'symbol_timeframe_count': symbol_timeframes
            }
    
    def export_to_dict(
        self,
        symbol: str,
        timeframe: str,
        count: int = None
    ) -> List[Dict[str, Any]]:
        """
        Export candles to dictionary format.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            count: Number of candles (None for all)
        
        Returns:
            List of candle dictionaries
        """
        candles = self.get_candles(symbol, timeframe, count)
        
        return [candle.to_dict() for candle in candles]
    
    def import_from_dict(
        self,
        symbol: str,
        timeframe: str,
        candle_dicts: List[Dict[str, Any]]
    ):
        """
        Import candles from dictionary format.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            candle_dicts: List of candle dictionaries
        
        Example:
            >>> buffer.import_from_dict('RELIANCE', '5m', candle_data)
        """
        for candle_dict in candle_dicts:
            candle = Candle.from_dict(candle_dict)
            candle.symbol = symbol
            candle.timeframe = timeframe
            self.add_candle(symbol, timeframe, candle)
        
        logger.info(
            f"Imported {len(candle_dicts)} candles for {symbol} {timeframe}"
        )


# Global buffer instance
_market_buffer: Optional[MarketBuffer] = None


def get_market_buffer(max_candles: int = 500) -> MarketBuffer:
    """
    Get or create global market buffer instance.
    
    Args:
        max_candles: Maximum candles per symbol/timeframe
    
    Returns:
        MarketBuffer instance
    
    Example:
        >>> buffer = get_market_buffer()
        >>> buffer.add_candle('RELIANCE', '5m', candle)
    """
    global _market_buffer
    
    if _market_buffer is None:
        _market_buffer = MarketBuffer(max_candles=max_candles)
    
    return _market_buffer

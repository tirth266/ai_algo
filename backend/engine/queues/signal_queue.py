"""
Signal Queue Module

Thread-safe queue for storing and distributing trading signals.

Features:
- FIFO queue operations
- Maximum size limit (last 100 signals)
- Signal retrieval by type/symbol
- Thread-safe operations
- Signal persistence hooks

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import threading
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class SignalQueue:
    """
    Thread-safe queue for trading signals.
    
    Maintains a rolling window of recent signals.
    Supports filtering and retrieval operations.
    
    Example:
        >>> queue = SignalQueue(max_size=100)
        >>> queue.push_signal(signal)
        >>> recent = queue.get_recent_signals(count=10)
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize signal queue.
        
        Args:
            max_size: Maximum signals to store (default: 100)
        
        Example:
            >>> queue = SignalQueue(max_size=50)
        """
        self.max_size = max_size
        
        # Internal storage
        self._queue: deque = deque(maxlen=max_size)
        
        # Indexing for fast lookup
        self._by_symbol: Dict[str, deque] = {}
        self._by_type: Dict[str, deque] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'signals_dropped': 0
        }
        
        logger.info(f"SignalQueue initialized: max_size={max_size}")
    
    def push_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Add a signal to the queue.
        
        Args:
            signal: Signal dictionary
        
        Returns:
            True if added successfully
        
        Example:
            >>> signal = {'type': 'BUY', 'symbol': 'RELIANCE', ...}
            >>> queue.push_signal(signal)
        """
        if not signal:
            logger.warning("Attempted to push None signal")
            return False
        
        try:
            with self._lock:
                # Add timestamp if not present
                if 'queued_at' not in signal:
                    signal['queued_at'] = datetime.now().isoformat()
                
                # Add to main queue
                self._queue.append(signal)
                
                # Update statistics
                self._stats['total_signals'] += 1
                
                signal_type = signal.get('type', 'UNKNOWN')
                if signal_type == 'BUY':
                    self._stats['buy_signals'] += 1
                elif signal_type == 'SELL':
                    self._stats['sell_signals'] += 1
                
                # Add to symbol index
                symbol = signal.get('symbol', 'UNKNOWN')
                if symbol not in self._by_symbol:
                    self._by_symbol[symbol] = deque(maxlen=self.max_size)
                self._by_symbol[symbol].append(signal)
                
                # Add to type index
                if signal_type not in self._by_type:
                    self._by_type[signal_type] = deque(maxlen=self.max_size)
                self._by_type[signal_type].append(signal)
                
                # Handle dropped signals (when max_size exceeded)
                if len(self._queue) == self.max_size:
                    # Check if oldest signal was dropped
                    pass  # deque handles this automatically
                
                logger.debug(
                    f"Signal queued: {signal_type} {symbol} "
                    f"confidence={signal.get('confidence', 0):.2%}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error pushing signal to queue: {str(e)}")
            return False
    
    def get_signal(self) -> Optional[Dict[str, Any]]:
        """
        Get and remove the oldest signal from queue.
        
        Returns:
            Oldest signal or None if queue is empty
        
        Example:
            >>> signal = queue.get_signal()
            >>> if signal:
            ...     process_signal(signal)
        """
        with self._lock:
            if not self._queue:
                return None
            
            signal = self._queue.popleft()
            
            logger.debug(
                f"Signal dequeued: {signal.get('type')} "
                f"{signal.get('symbol')}"
            )
            
            return signal
    
    def peek_signal(self) -> Optional[Dict[str, Any]]:
        """
        Peek at the oldest signal without removing it.
        
        Returns:
            Oldest signal or None if queue is empty
        
        Example:
            >>> signal = queue.peek_signal()
            >>> print(f"Next signal: {signal['type']}")
        """
        with self._lock:
            if not self._queue:
                return None
            
            return self._queue[0]
    
    def get_recent_signals(
        self,
        count: int = None,
        symbol: str = None,
        signal_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent signals with optional filtering.
        
        Args:
            count: Number of signals (None for all)
            symbol: Filter by symbol
            signal_type: Filter by type (BUY/SELL)
        
        Returns:
            List of signals (most recent last)
        
        Example:
            >>> buys = queue.get_recent_signals(signal_type='BUY')
            >>> reliance = queue.get_recent_signals(symbol='RELIANCE')
        """
        with self._lock:
            if symbol:
                # Get from symbol index
                if symbol not in self._by_symbol:
                    return []
                
                signals = list(self._by_symbol[symbol])
            
            elif signal_type:
                # Get from type index
                if signal_type not in self._by_type:
                    return []
                
                signals = list(self._by_type[signal_type])
            
            else:
                # Get from main queue
                signals = list(self._queue)
            
            # Apply count limit
            if count:
                signals = signals[-count:]
            
            return signals
    
    def get_all_signals(self) -> List[Dict[str, Any]]:
        """
        Get all signals in queue.
        
        Returns:
            List of all signals
        
        Example:
            >>> all_signals = queue.get_all_signals()
        """
        with self._lock:
            return list(self._queue)
    
    def clear(self, symbol: str = None, signal_type: str = None):
        """
        Clear signals from queue.
        
        Args:
            symbol: Clear only specific symbol (None for all)
            signal_type: Clear only specific type (None for all)
        
        Example:
            >>> queue.clear(symbol='RELIANCE')
            >>> queue.clear(signal_type='BUY')
        """
        with self._lock:
            if symbol:
                # Clear specific symbol
                if symbol in self._by_symbol:
                    self._by_symbol[symbol].clear()
                
                # Remove from main queue
                self._queue = deque(
                    [s for s in self._queue if s.get('symbol') != symbol],
                    maxlen=self.max_size
                )
                
                logger.info(f"Cleared signals for {symbol}")
            
            elif signal_type:
                # Clear specific type
                if signal_type in self._by_type:
                    self._by_type[signal_type].clear()
                
                # Remove from main queue
                self._queue = deque(
                    [s for s in self._queue if s.get('type') != signal_type],
                    maxlen=self.max_size
                )
                
                logger.info(f"Cleared {signal_type} signals")
            
            else:
                # Clear everything
                self._queue.clear()
                self._by_symbol.clear()
                self._by_type.clear()
                
                logger.info("Cleared all signals")
    
    def size(self) -> int:
        """
        Get current queue size.
        
        Returns:
            Number of signals in queue
        
        Example:
            >>> print(f"Queue size: {queue.size()}")
        """
        with self._lock:
            return len(self._queue)
    
    def is_empty(self) -> bool:
        """
        Check if queue is empty.
        
        Returns:
            True if empty
        
        Example:
            >>> if queue.is_empty():
            ...     print("No pending signals")
        """
        with self._lock:
            return len(self._queue) == 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Stats dictionary
        
        Example:
            >>> stats = queue.get_stats()
            >>> print(f"Total signals: {stats['total_signals']}")
        """
        with self._lock:
            return {
                **self._stats,
                'current_size': len(self._queue),
                'symbols_tracked': len(self._by_symbol),
                'types_tracked': len(self._by_type)
            }
    
    def export_to_list(self) -> List[Dict[str, Any]]:
        """
        Export all signals to list.
        
        Returns:
            List of signal dictionaries
        
        Example:
            >>> signals = queue.export_to_list()
        """
        with self._lock:
            return [dict(signal) for signal in self._queue]
    
    def import_from_list(self, signals: List[Dict[str, Any]]):
        """
        Import signals from list.
        
        Args:
            signals: List of signal dictionaries
        
        Example:
            >>> queue.import_from_list(saved_signals)
        """
        for signal in signals:
            self.push_signal(signal)
        
        logger.info(f"Imported {len(signals)} signals")


# Global signal queue instance
_signal_queue: Optional[SignalQueue] = None


def get_signal_queue(max_size: int = 100) -> SignalQueue:
    """
    Get or create global signal queue instance.
    
    Args:
        max_size: Maximum queue size
    
    Returns:
        SignalQueue instance
    
    Example:
        >>> queue = get_signal_queue()
        >>> queue.push_signal(signal)
    """
    global _signal_queue
    
    if _signal_queue is None:
        _signal_queue = SignalQueue(max_size=max_size)
    
    return _signal_queue


# Convenience functions
def push_signal(signal: Dict[str, Any]):
    """Push signal to global queue."""
    queue = get_signal_queue()
    return queue.push_signal(signal)


def get_signal() -> Optional[Dict[str, Any]]:
    """Get signal from global queue."""
    queue = get_signal_queue()
    return queue.get_signal()


def get_recent_signals(count: int = 10) -> List[Dict[str, Any]]:
    """Get recent signals from global queue."""
    queue = get_signal_queue()
    return queue.get_recent_signals(count=count)

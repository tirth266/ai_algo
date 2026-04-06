"""
Candle Simulator Module

Simulate historical market movement candle-by-candle.

Features:
- Sequential candle replay
- Real-time simulation mode
- Speed control
- Progress tracking
- State management

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CandleSimulator:
    """
    Simulate historical market movement.
    
    Replays candles one at a time to simulate live trading.
    Maintains state for incremental processing.
    
    Usage:
        >>> simulator = CandleSimulator(df)
        >>> while simulator.has_next():
        ...     candle = simulator.next_candle()
        ...     process(candle)
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize candle simulator.
        
        Args:
            df: DataFrame with historical OHLCV data
        
        Example:
            >>> simulator = CandleSimulator(historical_data)
        """
        self.df = df.reset_index(drop=False)
        self.total_candles = len(df)
        
        # Current position
        self._current_idx = 0
        
        # Available data (grows as we progress)
        self._available_data = pd.DataFrame(columns=df.columns)
        
        # Statistics
        self._steps = 0
        
        logger.info(
            f"CandleSimulator initialized with {self.total_candles} candles"
        )
    
    def next_candle(self) -> Optional[Dict[str, Any]]:
        """
        Get next candle in sequence.
        
        Returns:
            Candle as dictionary or None if finished
        
        Example:
            >>> candle = simulator.next_candle()
            >>> print(f"Processing: {candle['close']}")
        """
        if not self.has_next():
            return None
        
        # Get current candle
        current_row = self.df.iloc[self._current_idx]
        
        # Convert to dictionary
        candle = {
            'time': current_row.get('timestamp') or current_row.get('time'),
            'open': float(current_row['open']),
            'high': float(current_row['high']),
            'low': float(current_row['low']),
            'close': float(current_row['close']),
            'volume': float(current_row['volume'])
        }
        
        # Add to available data
        new_row = pd.DataFrame([current_row])
        self._available_data = pd.concat(
            [self._available_data, new_row],
            ignore_index=True
        )
        
        # Advance position
        self._current_idx += 1
        self._steps += 1
        
        logger.debug(
            f"Candle {self._current_idx}/{self.total_candles}: "
            f"O:{candle['open']:.2f} H:{candle['high']:.2f} "
            f"L:{candle['low']:.2f} C:{candle['close']:.2f}"
        )
        
        return candle
    
    def has_next(self) -> bool:
        """
        Check if more candles available.
        
        Returns:
            True if more candles exist
        
        Example:
            >>> while simulator.has_next():
            ...     candle = simulator.next_candle()
        """
        return self._current_idx < self.total_candles
    
    def reset(self):
        """
        Reset simulator to beginning.
        
        Example:
            >>> simulator.reset()
            >>> # Start over
        """
        self._current_idx = 0
        self._available_data = pd.DataFrame(columns=self.df.columns)
        self._steps = 0
        
        logger.info("Simulator reset")
    
    def get_available_data(self) -> pd.DataFrame:
        """
        Get all candles processed so far.
        
        Returns:
            DataFrame with available candles
        
        Example:
            >>> historical = simulator.get_available_data()
            >>> indicators = calculate_indicators(historical)
        """
        return self._available_data.copy()
    
    def get_current_candle(self) -> Optional[Dict[str, Any]]:
        """
        Get current candle without advancing.
        
        Returns:
            Current candle or None
        
        Example:
            >>> current = simulator.get_current_candle()
        """
        if self._current_idx >= self.total_candles:
            return None
        
        row = self.df.iloc[self._current_idx]
        
        return {
            'time': row.get('timestamp') or row.get('time'),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume'])
        }
    
    def get_progress(self) -> float:
        """
        Get simulation progress percentage.
        
        Returns:
            Progress as decimal (0.0 to 1.0)
        
        Example:
            >>> progress = simulator.get_progress()
            >>> print(f"{progress*100:.1f}% complete")
        """
        return self._current_idx / self.total_candles
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get simulation statistics.
        
        Returns:
            Stats dictionary
        
        Example:
            >>> stats = simulator.get_stats()
            >>> print(f"Processed: {stats['candles_processed']}")
        """
        return {
            'total_candles': self.total_candles,
            'candles_processed': self._current_idx,
            'candles_remaining': self.total_candles - self._current_idx,
            'progress_percent': round(self.get_progress() * 100, 2),
            'steps': self._steps
        }
    
    def skip_to(self, index: int):
        """
        Skip to specific position.
        
        Args:
            index: Position to skip to
        
        Example:
            >>> simulator.skip_to(1000)  # Jump to bar 1000
        """
        if index < 0 or index > self.total_candles:
            logger.error(f"Invalid skip position: {index}")
            return
        
        self._current_idx = index
        
        # Rebuild available data up to this point
        self._available_data = self.df.iloc[:index].copy()
        
        logger.info(f"Skipped to position {index}")
    
    def skip_bars(self, num_bars: int):
        """
        Skip forward by number of bars.
        
        Args:
            num_bars: Number of bars to skip
        
        Example:
            >>> simulator.skip_bars(100)  # Skip 100 bars
        """
        new_idx = self._current_idx + num_bars
        self.skip_to(min(new_idx, self.total_candles))
    
    def run_batch(self, num_candles: int) -> list:
        """
        Process multiple candles at once.
        
        Args:
            num_candles: Number of candles to process
        
        Returns:
            List of candles processed
        
        Example:
            >>> batch = simulator.run_batch(100)
            >>> # Process 100 candles
        """
        candles = []
        
        for _ in range(num_candles):
            if not self.has_next():
                break
            
            candle = self.next_candle()
            candles.append(candle)
        
        return candles


# Vectorized simulator for faster backtesting
class VectorizedSimulator:
    """
    Vectorized simulator for faster backtesting.
    
    Processes all data at once using vectorized operations.
    Much faster but doesn't support incremental processing.
    
    Usage:
        >>> vsim = VectorizedSimulator(df)
        >>> results = vsim.run_all(strategy)
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize vectorized simulator.
        
        Args:
            df: DataFrame with historical OHLCV data
        """
        self.df = df
        self.total_candles = len(df)
        
        logger.info(
            f"VectorizedSimulator initialized with {self.total_candles} candles"
        )
    
    def get_rolling_window(
        self,
        window_size: int
    ) -> list:
        """
        Get rolling windows of data.
        
        Each window contains `window_size` candles ending at that point.
        
        Args:
            window_size: Size of rolling window
        
        Returns:
            List of DataFrames (one per window)
        
        Example:
            >>> windows = vsim.get_rolling_window(100)
            >>> for i, window in enumerate(windows):
            ...     # Process window ending at bar i
        """
        if window_size > self.total_candles:
            logger.warning(
                f"Window size ({window_size}) exceeds data length "
                f"({self.total_candles})"
            )
            window_size = self.total_candles
        
        windows = []
        
        for i in range(window_size, self.total_candles + 1):
            window = self.df.iloc[i-window_size:i].copy()
            windows.append(window)
        
        logger.info(f"Created {len(windows)} rolling windows")
        return windows
    
    def apply_strategy_vectorized(
        self,
        strategy_func,
        window_size: int = 100
    ) -> pd.DataFrame:
        """
        Apply strategy function to all windows.
        
        Args:
            strategy_func: Function that takes DataFrame and returns signal
            window_size: Rolling window size
        
        Returns:
            DataFrame with signals
        
        Example:
            >>> signals = vsim.apply_strategy_vectorized(generate_signal, 100)
        """
        windows = self.get_rolling_window(window_size)
        
        signals = []
        
        for window in windows:
            try:
                signal = strategy_func(window)
                signals.append(signal)
            except Exception as e:
                logger.error(f"Strategy error: {str(e)}")
                signals.append(None)
        
        # Create signals DataFrame
        result_df = pd.DataFrame(signals)
        result_df.index = self.df.index[window_size-1:]
        
        return result_df

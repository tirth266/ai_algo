"""
Engine Runner Module

Main orchestrator for the real-time trading engine.

Coordinates all components:
- Market data stream
- Candle building
- Market buffer
- Indicator pipeline
- Signal pipeline
- Signal queue

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import engine components
from market.data_stream import (
    get_market_data_stream,
    MarketDataStream,
    Tick,
    start_market_stream,
    stop_market_stream
)
from market.candle_builder import CandleBuilder, MultiTimeframeCandleBuilder
from market.market_buffer import get_market_buffer, MarketBuffer
from pipeline.indicator_pipeline import get_indicator_pipeline, IndicatorPipeline
from pipeline.signal_pipeline import get_signal_pipeline, SignalPipeline
from queues.signal_queue import get_signal_queue, SignalQueue
from utils.time_utils import MarketHours

logger = logging.getLogger(__name__)


class EngineRunner:
    """
    Main trading engine orchestrator.
    
    Runs the complete data processing pipeline:
    Market Data → Candles → Indicators → Signals → Queue
    
    Features:
    - Real-time processing
    - Multiple symbols support
    - Multiple timeframes support
    - Error recovery
    - Performance monitoring
    - Graceful shutdown
    
    Example:
        >>> engine = EngineRunner(
        ...     symbols=['RELIANCE', 'TCS'],
        ...     timeframes=['1m', '5m']
        ... )
        >>> engine.start()
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None,
        use_mock_data: bool = True
    ):
        """
        Initialize trading engine.
        
        Args:
            symbols: List of symbols to trade (default: ['RELIANCE'])
            timeframes: List of timeframes (default: ['1m', '5m'])
            use_mock_data: Use mock data generator
        
        Example:
            >>> engine = EngineRunner(
            ...     symbols=['RELIANCE', 'INFY'],
            ...     timeframes=['5m', '15m']
            ... )
        """
        # Configuration
        self.symbols = symbols or ['RELIANCE']
        self.timeframes = timeframes or ['1m', '5m']
        self.use_mock_data = use_mock_data
        
        # Components
        self.data_stream: Optional[MarketDataStream] = None
        self.candle_builders: Dict[str, MultiTimeframeCandleBuilder] = {}
        self.market_buffer: Optional[MarketBuffer] = None
        self.indicator_pipeline: Optional[IndicatorPipeline] = None
        self.signal_pipelines: Dict[str, SignalPipeline] = {}
        self.signal_queue: Optional[SignalQueue] = None
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'ticks_processed': 0,
            'candles_closed': 0,
            'indicators_calculated': 0,
            'signals_generated': 0,
            'errors': 0,
            'start_time': None,
            'last_tick_time': None
        }
        
        logger.info(
            f"EngineRunner initialized: "
            f"symbols={self.symbols}, "
            f"timeframes={self.timeframes}"
        )
    
    def initialize(self):
        """
        Initialize all engine components.
        
        Called automatically on start(), but can be called
        explicitly for early initialization.
        
        Example:
            >>> engine.initialize()
            >>> # Components ready but not running
        """
        # Initialize market data stream
        self.data_stream = get_market_data_stream(
            use_mock_data=self.use_mock_data
        )
        
        # Subscribe to all symbols
        for symbol in self.symbols:
            self.data_stream.subscribe(symbol)
        
        # Create candle builders for each symbol
        for symbol in self.symbols:
            self.candle_builders[symbol] = MultiTimeframeCandleBuilder(
                self.timeframes
            )
        
        # Initialize market buffer
        self.market_buffer = get_market_buffer(max_candles=500)
        
        # Initialize indicator pipeline
        self.indicator_pipeline = get_indicator_pipeline()
        
        # Initialize signal pipelines for each symbol
        for symbol in self.symbols:
            self.signal_pipelines[symbol] = get_signal_pipeline(symbol)
        
        # Initialize signal queue
        self.signal_queue = get_signal_queue(max_size=100)
        
        # Set up tick callback
        self.data_stream.set_callback(self._on_tick)
        
        logger.info("All engine components initialized")
    
    def start(self):
        """
        Start the trading engine.
        
        Begins real-time processing loop.
        
        Example:
            >>> engine.start()
            >>> # Engine runs until stop() is called
        """
        if self._running:
            logger.warning("Engine already running")
            return
        
        # Initialize if needed
        if not self.data_stream:
            self.initialize()
        
        # Start market data stream
        self.data_stream.start()
        
        # Mark as running
        self._running = True
        self._stats['start_time'] = datetime.now()
        
        logger.info("Trading engine started")
    
    def stop(self):
        """
        Stop the trading engine.
        
        Gracefully shuts down all components.
        
        Example:
            >>> engine.stop()
        """
        if not self._running:
            return
        
        self._running = False
        
        # Stop market data stream
        if self.data_stream:
            self.data_stream.stop()
        
        logger.info("Trading engine stopped")
    
    def _on_tick(self, tick: Tick):
        """
        Process incoming tick from market data stream.
        
        This is the main entry point for the data processing pipeline.
        
        Flow:
        1. Build candles from tick
        2. Store completed candles in buffer
        3. Run indicators on latest candles
        4. Generate signals
        5. Queue signals
        
        Args:
            tick: Market tick
        """
        try:
            with self._lock:
                self._stats['ticks_processed'] += 1
                self._stats['last_tick_time'] = datetime.now()
            
            symbol = tick.symbol
            
            # Get candle builder for this symbol
            if symbol not in self.candle_builders:
                logger.warning(f"No candle builder for {symbol}")
                return
            
            builder = self.candle_builders[symbol]
            
            # Process tick through candle builder
            completed_candles = builder.process_tick(tick)
            
            # Process any completed candles
            for timeframe, candle in completed_candles.items():
                if candle:
                    self._process_completed_candle(symbol, timeframe, candle)
            
        except Exception as e:
            logger.error(f"Error processing tick: {str(e)}", exc_info=True)
            
            with self._lock:
                self._stats['errors'] += 1
    
    def _process_completed_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Any
    ):
        """
        Process a completed candle.
        
        Steps:
        1. Add to market buffer
        2. Get recent candles
        3. Run indicator pipeline
        4. Run signal pipeline
        5. Queue signal if generated
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            candle: Completed candle
        """
        try:
            # Add to buffer
            self.market_buffer.add_candle(symbol, timeframe, candle)
            
            with self._lock:
                self._stats['candles_closed'] += 1
            
            logger.debug(
                f"Candle closed: {symbol} {timeframe} "
                f"O:{candle.open:.2f} H:{candle.high:.2f} "
                f"L:{candle.low:.2f} C:{candle.close:.2f}"
            )
            
            # Get recent candles for indicators
            candles_df = self.market_buffer.get_dataframe(
                symbol, timeframe, count=200
            )
            
            if len(candles_df) < 20:
                logger.debug(f"Insufficient data for {symbol} {timeframe}")
                return
            
            # Run indicator pipeline
            indicators = self.indicator_pipeline.run(
                candles_df,
                symbol=symbol
            )
            
            with self._lock:
                self._stats['indicators_calculated'] += 1
            
            # Run signal pipeline
            signal_pipeline = self.signal_pipelines.get(symbol)
            
            if not signal_pipeline:
                logger.warning(f"No signal pipeline for {symbol}")
                return
            
            signal = signal_pipeline.run(candles_df, indicators, symbol)
            
            # Queue signal if generated
            if signal:
                self.signal_queue.push_signal(signal)
                
                with self._lock:
                    self._stats['signals_generated'] += 1
                
                logger.info(
                    f"Signal queued: {signal['type']} {symbol} "
                    f"confidence={signal['confidence']:.2%}"
                )
            
        except Exception as e:
            logger.error(
                f"Error processing completed candle: {str(e)}",
                exc_info=True
            )
            
            with self._lock:
                self._stats['errors'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get engine statistics.
        
        Returns:
            Stats dictionary
        
        Example:
            >>> stats = engine.get_stats()
            >>> print(f"Ticks: {stats['ticks_processed']}")
        """
        with self._lock:
            stats = dict(self._stats)
        
        # Add component stats
        stats['market_buffer'] = self.market_buffer.get_stats() \
            if self.market_buffer else {}
        
        stats['indicator_pipeline'] = self.indicator_pipeline.get_stats() \
            if self.indicator_pipeline else {}
        
        stats['signal_queue'] = self.signal_queue.get_stats() \
            if self.signal_queue else {}
        
        # Aggregate signal stats
        total_signals = sum(
            p.get_stats()['signals_generated']
            for p in self.signal_pipelines.values()
        )
        stats['total_signals'] = total_signals
        
        return stats
    
    def get_recent_signals(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recently generated signals.
        
        Args:
            count: Number of signals to return
        
        Returns:
            List of signals
        
        Example:
            >>> signals = engine.get_recent_signals(5)
        """
        if not self.signal_queue:
            return []
        
        return self.signal_queue.get_recent_signals(count=count)
    
    def is_running(self) -> bool:
        """Check if engine is currently running."""
        return self._running


# Global engine instance
_engine_instance: Optional[EngineRunner] = None


def get_engine(
    symbols: List[str] = None,
    timeframes: List[str] = None,
    use_mock_data: bool = True
) -> EngineRunner:
    """
    Get or create global engine instance.
    
    Args:
        symbols: Symbols to trade
        timeframes: Timeframes to monitor
        use_mock_data: Use mock data generator
    
    Returns:
        EngineRunner instance
    
    Example:
        >>> engine = get_engine(['RELIANCE'], ['5m'])
        >>> engine.start()
    """
    global _engine_instance
    
    if _engine_instance is None:
        _engine_instance = EngineRunner(
            symbols=symbols,
            timeframes=timeframes,
            use_mock_data=use_mock_data
        )
    
    return _engine_instance


def start_trading_engine(
    symbols: List[str] = None,
    timeframes: List[str] = None,
    use_mock_data: bool = True
):
    """
    Start trading engine with configuration.
    
    Args:
        symbols: Symbols to trade
        timeframes: Timeframes to monitor
        use_mock_data: Use mock data generator
    
    Example:
        >>> start_trading_engine(['RELIANCE', 'TCS'], ['5m', '15m'])
    """
    engine = get_engine(symbols, timeframes, use_mock_data)
    engine.initialize()
    engine.start()
    
    logger.info(f"Trading engine started with symbols: {symbols}")


def stop_trading_engine():
    """Stop the global trading engine."""
    global _engine_instance
    
    if _engine_instance:
        _engine_instance.stop()
        logger.info("Trading engine stopped")

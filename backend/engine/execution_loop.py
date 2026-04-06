"""
Execution Loop Module

Continuous trading loop that runs at regular intervals.
Fetches new data, recalculates indicators, and updates signals.

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import time
import threading
import logging
from typing import List, Optional, Callable
from datetime import datetime
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class ExecutionLoop:
    """
    Continuous execution loop for real-time signal generation.
    
    Features:
    - Runs every N seconds (default: 60)
    - Processes multiple symbols
    - Updates signal cache
    - Supports callbacks for signal changes
    
    Example:
        >>> loop = ExecutionLoop(symbols=['RELIANCE', 'TCS'], interval=60)
        >>> loop.start()
        >>> # Loop runs every 60 seconds in background
    """
    
    def __init__(
        self,
        symbols: List[str],
        interval: int = 60,
        auto_start: bool = False
    ):
        """
        Initialize execution loop.
        
        Args:
            symbols: List of symbols to monitor
            interval: Update interval in seconds (default: 60)
            auto_start: Whether to start loop immediately
        """
        # Lazy import to avoid circular imports
        from engine.trading_engine import get_trading_engine
        
        self.symbols = symbols
        self.interval = interval
        self.trading_engine = get_trading_engine()
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self._signal_callbacks: List[Callable] = []
        
        # Statistics
        self.last_run_time: Optional[datetime] = None
        self.total_runs = 0
        self.signals_generated = 0
        
        logger.info(
            f"ExecutionLoop initialized: "
            f"symbols={len(symbols)}, interval={interval}s"
        )
    
    def start(self):
        """Start the execution loop in a background thread."""
        if self._running:
            logger.warning("Execution loop already running")
            return
        
        logger.info("Starting execution loop")
        
        self._running = True
        self._stop_event.clear()
        
        # Create and start thread
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("Execution loop started successfully")
    
    def stop(self):
        """Stop the execution loop."""
        if not self._running:
            return
        
        logger.info("Stopping execution loop")
        
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Execution loop stopped")
    
    def _run_loop(self):
        """Main loop execution logic."""
        while self._running and not self._stop_event.is_set():
            try:
                # Record start time
                run_start = datetime.now()
                self.last_run_time = run_start
                
                logger.info(f"=== Execution Loop Run #{self.total_runs + 1} ===")
                
                # Process each symbol
                for symbol in self.symbols:
                    signal = self._process_symbol(symbol)
                    
                    if signal:
                        self.signals_generated += 1
                        
                        # Trigger callbacks
                        self._trigger_callbacks(signal)
                
                # Update statistics
                self.total_runs += 1
                
                # Calculate next run time
                elapsed = (datetime.now() - run_start).total_seconds()
                sleep_time = max(0, self.interval - elapsed)
                
                logger.info(
                    f"Run complete in {elapsed:.2f}s. "
                    f"Next run in {sleep_time:.2f}s"
                )
                
                # Wait until next interval
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in execution loop: {str(e)}", exc_info=True)
                # Still wait before retry
                self._stop_event.wait(self.interval)
    
    def _process_symbol(self, symbol: str) -> Optional[dict]:
        """
        Process single symbol and generate signal.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Signal dict or None
        """
        try:
            logger.debug(f"Processing {symbol}")
            
            # Generate signal
            signal = self.trading_engine.generate_signal(symbol)
            
            if signal:
                logger.info(
                    f"{symbol}: {signal['signal']} signal "
                    f"(confidence: {signal['confidence']:.2f})"
                )
                return signal
            else:
                logger.debug(f"No signal for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")
            return None
    
    def on_signal(self, callback: Callable):
        """
        Register callback for signal events.
        
        Args:
            callback: Function to call when signal generated
                     Signature: callback(signal: dict)
        
        Example:
            >>> def my_callback(signal):
            ...     print(f"New signal: {signal['symbol']} - {signal['signal']}")
            >>> loop.on_signal(my_callback)
        """
        self._signal_callbacks.append(callback)
        logger.debug(f"Signal callback registered: {callback.__name__}")
    
    def _trigger_callbacks(self, signal: dict):
        """Trigger all registered callbacks with signal."""
        for callback in self._signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {str(e)}")
    
    def get_status(self) -> dict:
        """
        Get execution loop status.
        
        Returns:
            Dict with loop status and statistics
        """
        return {
            'running': self._running,
            'symbols': self.symbols,
            'interval': self.interval,
            'last_run': self.last_run_time.isoformat() if self.last_run_time else None,
            'total_runs': self.total_runs,
            'signals_generated': self.signals_generated
        }
    
    def add_symbol(self, symbol: str):
        """Add symbol to monitoring list."""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            logger.info(f"Added {symbol} to execution loop")
    
    def remove_symbol(self, symbol: str):
        """Remove symbol from monitoring list."""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            logger.info(f"Removed {symbol} from execution loop")


# Global execution loop instance
_loop_instance: Optional[ExecutionLoop] = None


def get_execution_loop(symbols: List[str], interval: int = 60) -> ExecutionLoop:
    """
    Get or create global execution loop instance.
    
    Args:
        symbols: List of symbols to monitor
        interval: Update interval in seconds
    
    Returns:
        ExecutionLoop instance
    """
    global _loop_instance
    
    if _loop_instance is None:
        # Lazy import to avoid circular imports
        _loop_instance = ExecutionLoop(symbols=symbols, interval=interval)
    
    return _loop_instance


if __name__ == "__main__":
    # Test the execution loop
    logging.basicConfig(level=logging.INFO)
    
    # Define callback
    def signal_handler(signal):
        print(f"\n{'='*60}")
        print(f"🚨 SIGNAL ALERT 🚨")
        print(f"{'='*60}")
        print(f"Symbol: {signal['symbol']}")
        print(f"Signal: {signal['signal']}")
        print(f"Confidence: {signal['confidence']:.2%}")
        print(f"Price: ₹{signal['price']:.2f}")
        print(f"Time: {signal['timestamp']}")
        print(f"Reasons:")
        for reason in signal['reason']:
            print(f"  ✓ {reason}")
        print(f"{'='*60}\n")
    
    # Create loop with test symbols
    loop = ExecutionLoop(
        symbols=['RELIANCE', 'TCS', 'INFY'],
        interval=60  # Run every 60 seconds
    )
    
    # Register callback
    loop.on_signal(signal_handler)
    
    print("\nStarting execution loop...")
    print("Press Ctrl+C to stop\n")
    
    # Start loop
    loop.start()
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping execution loop...")
        loop.stop()
        print("Stopped.")

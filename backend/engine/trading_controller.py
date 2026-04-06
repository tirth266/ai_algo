"""
Trading Controller

Central control system for UI-driven trading operations.
Handles start/stop trading, strategy execution, and status tracking.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class TradingState(Enum):
    """Trading state enumeration."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class TradingController:
    """
    Central trading controller for UI-driven operations.
    
    Features:
    - Start/Stop trading from UI
    - Manual strategy execution
    - Real-time status tracking
    - Automatic trade execution loop
    - Error handling and recovery
    """
    
    # Singleton instance
    _instance: Optional['TradingController'] = None
    
    def __new__(cls):
        """Singleton pattern to ensure single controller instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize trading controller."""
        if self._initialized:
            return
            
        self._initialized = True
        
        # State variables
        self.trading_active = False
        self.last_run_time: Optional[datetime] = None
        self.active_strategy: str = "PowerStrategy"
        self.current_state = TradingState.STOPPED
        
        # Statistics
        self.total_trades_today = 0
        self.daily_pnl = 0.0
        self.signals_generated = 0
        self.orders_placed = 0
        
        # Threading
        self._trading_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Components (lazy loaded)
        self._strategy_manager = None
        self._market_data_service = None
        self._order_repository = None
        self._trade_repository = None
        self._position_repository = None
        
        # Configuration
        self.run_interval = 60  # seconds
        
        logger.info("TradingController initialized")
    
    def _get_components(self):
        """Lazy load trading components."""
        if self._strategy_manager is None:
            try:
                from engine.strategy_manager import get_strategy_manager
                self._strategy_manager = get_strategy_manager()
                logger.info("Strategy manager loaded")
            except Exception as e:
                logger.warning(f"Failed to load strategy manager: {e}")
        
        if self._market_data_service is None:
            try:
                from services.market_data import get_market_data_service
                self._market_data_service = get_market_data_service()
                logger.info("Market data service loaded")
            except Exception as e:
                logger.warning(f"Failed to load market data service: {e}")
        
        if self._order_repository is None:
            try:
                from database.session import session_scope
                from repositories.order_repository import OrderRepository
                self._session_scope = session_scope
                self._order_repository = lambda session: OrderRepository(session)
                logger.info("Order repository loaded")
            except Exception as e:
                logger.warning(f"Failed to load order repository: {e}")
    
    def start_trading(self, strategy_name: str = "PowerStrategy") -> Dict[str, Any]:
        """
        Start automated trading.
        
        Args:
            strategy_name: Name of strategy to use
        
        Returns:
            Status dictionary with success flag and message
        """
        with self._lock:
            if self.trading_active:
                return {
                    'success': False,
                    'message': 'Trading is already active',
                    'state': self.current_state.value
                }
            
            try:
                # Load components
                self._get_components()
                
                # Set strategy
                self.active_strategy = strategy_name
                self.trading_active = True
                self.current_state = TradingState.RUNNING
                self._stop_event.clear()
                
                # Start trading thread
                self._trading_thread = threading.Thread(
                    target=self._trading_loop,
                    daemon=True,
                    name='TradingLoop'
                )
                self._trading_thread.start()
                
                logger.info(f"Trading started with strategy: {strategy_name}")
                
                return {
                    'success': True,
                    'message': f'Trading started with {strategy_name}',
                    'state': self.current_state.value,
                    'strategy': self.active_strategy
                }
                
            except Exception as e:
                logger.error(f"Failed to start trading: {e}", exc_info=True)
                self.current_state = TradingState.ERROR
                return {
                    'success': False,
                    'message': f'Failed to start trading: {str(e)}',
                    'state': self.current_state.value
                }
    
    def stop_trading(self) -> Dict[str, Any]:
        """
        Stop automated trading.
        
        Returns:
            Status dictionary
        """
        with self._lock:
            if not self.trading_active:
                return {
                    'success': False,
                    'message': 'Trading is not active',
                    'state': self.current_state.value
                }
            
            try:
                self.trading_active = False
                self.current_state = TradingState.STOPPED
                self._stop_event.set()
                
                # Wait for thread to finish
                if self._trading_thread and self._trading_thread.is_alive():
                    self._trading_thread.join(timeout=5.0)
                
                logger.info("Trading stopped")
                
                return {
                    'success': True,
                    'message': 'Trading stopped successfully',
                    'state': self.current_state.value
                }
                
            except Exception as e:
                logger.error(f"Error stopping trading: {e}")
                return {
                    'success': False,
                    'message': f'Error stopping trading: {str(e)}',
                    'state': self.current_state.value
                }
    
    def run_strategy_once(self) -> Dict[str, Any]:
        """
        Manually run strategy evaluation once.
        
        Returns:
            Results dictionary with signals and actions taken
        """
        try:
            logger.info(f"Manual strategy run requested: {self.active_strategy}")
            
            # Get components
            self._get_components()
            
            if not self._strategy_manager:
                return {
                    'success': False,
                    'message': 'Strategy manager not available',
                    'signals': []
                }
            
            # Run strategies
            results = {
                'success': True,
                'timestamp': datetime.utcnow().isoformat(),
                'strategy': self.active_strategy,
                'signals': [],
                'orders': []
            }
            
            # Example: Run for major symbols
            test_symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']
            
            for symbol in test_symbols:
                try:
                    # Fetch market data
                    if self._market_data_service:
                        candles = self._market_data_service.get_candles(
                            symbol=symbol,
                            timeframe='5m',
                            limit=100
                        )
                        
                        if candles is not None:
                            # Generate signal
                            signal = self._strategy_manager.generate_signal(symbol, candles)
                            
                            if signal:
                                results['signals'].append({
                                    'symbol': symbol,
                                    'signal': signal.get('signal', 'HOLD'),
                                    'confidence': signal.get('confidence', 0.0),
                                    'price': signal.get('price', 0.0)
                                })
                                
                                self.signals_generated += 1
                                
                                logger.info(
                                    f"Signal for {symbol}: {signal.get('signal')} "
                                    f"(confidence: {signal.get('confidence'):.2f})"
                                )
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
            
            self.last_run_time = datetime.utcnow()
            
            return results
            
        except Exception as e:
            logger.error(f"Strategy run failed: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Strategy run failed: {str(e)}',
                'signals': []
            }
    
    def _trading_loop(self):
        """Main trading loop that runs while trading is active."""
        logger.info("Trading loop started")
        
        while self.trading_active and not self._stop_event.is_set():
            try:
                # Run strategy evaluation
                self.run_strategy_once()
                
                # Update last run time
                self.last_run_time = datetime.utcnow()
                
                # Wait for next iteration
                wait_time = self.run_interval
                for _ in range(wait_time * 10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                # Continue loop despite errors
                time.sleep(5)  # Brief pause on error
        
        logger.info("Trading loop exited")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current trading status.
        
        Returns:
            Status dictionary with all state variables
        """
        return {
            'trading_active': self.trading_active,
            'state': self.current_state.value,
            'active_strategy': self.active_strategy,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'total_trades_today': self.total_trades_today,
            'daily_pnl': self.daily_pnl,
            'signals_generated': self.signals_generated,
            'orders_placed': self.orders_placed,
            'uptime': self._get_uptime()
        }
    
    def _get_uptime(self) -> Optional[str]:
        """Calculate uptime since last start."""
        if self.last_run_time:
            delta = datetime.utcnow() - self.last_run_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent trading logs.
        
        Args:
            limit: Maximum number of log entries
        
        Returns:
            List of log entries
        """
        # This would integrate with the logging system
        # For now, return placeholder
        return [
            {
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'message': 'Trading controller initialized',
                'component': 'controller'
            }
        ]
    
    def reset_statistics(self):
        """Reset daily statistics."""
        with self._lock:
            self.total_trades_today = 0
            self.daily_pnl = 0.0
            self.signals_generated = 0
            self.orders_placed = 0
            logger.info("Statistics reset")


# Global controller instance
def get_trading_controller() -> TradingController:
    """
    Get global trading controller instance.
    
    Returns:
        TradingController singleton
    """
    return TradingController()


if __name__ == "__main__":
    # Test the controller
    logging.basicConfig(level=logging.INFO)
    
    controller = TradingController()
    
    print("Testing Trading Controller...")
    print(f"Initial status: {controller.get_status()}")
    
    # Test start
    result = controller.start_trading()
    print(f"Start result: {result}")
    
    # Wait a bit
    time.sleep(2)
    
    # Test status
    print(f"Status after start: {controller.get_status()}")
    
    # Test stop
    result = controller.stop_trading()
    print(f"Stop result: {result}")
    
    print("\n✓ Controller test complete")

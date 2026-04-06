"""
Strategy Manager Module

Central orchestrator for managing strategy lifecycle.
Handles registration, starting, stopping, and monitoring of active strategies.
"""

from typing import Dict, List, Optional, Any, Type
import uuid
from datetime import datetime
import logging
import threading

from .base_strategy import BaseStrategy
from .market_data_service import MarketDataService

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages the lifecycle of trading strategies.
    
    Responsibilities:
    - Register strategy instances
    - Start/stop individual strategies
    - Track active strategies
    - Provide strategy metadata
    
    # TODO: register strategies from strategy_registry
    """
    
    def __init__(self, market_data_service: MarketDataService):
        """
        Initialize the strategy manager.
        
        Args:
            market_data_service: Service for fetching market data
        """
        self.market_data_service = market_data_service
        
        # In-memory storage for strategies
        # Structure: {strategy_id: strategy_instance}
        self.strategies: Dict[str, BaseStrategy] = {}
        
        # Strategy metadata
        # Structure: {strategy_id: {name, symbol, timeframe, status, created_at}}
        self.strategy_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Lock for thread-safe operations
        self._lock = threading.Lock()
        
        logger.info("StrategyManager initialized")
    
    def register_strategy(
        self, 
        strategy_class: Type[BaseStrategy],
        config: Dict[str, Any]
    ) -> str:
        """
        Register a new strategy instance.
        
        Args:
            strategy_class: Class type (must inherit from BaseStrategy)
            config: Strategy configuration dictionary
        
        Returns:
            str: Unique strategy ID
        
        Raises:
            ValueError: If strategy_class doesn't inherit from BaseStrategy
        """
        # Validate strategy class
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError("strategy_class must inherit from BaseStrategy")
        
        # Generate unique ID
        strategy_id = f"STRAT-{uuid.uuid4().hex[:8].upper()}"
        
        with self._lock:
            # Create strategy instance
            strategy = strategy_class(config)
            
            # Store strategy
            self.strategies[strategy_id] = strategy
            
            # Store metadata
            self.strategy_metadata[strategy_id] = {
                'name': config.get('name', 'Unnamed Strategy'),
                'symbol': config.get('symbol', ''),
                'timeframe': config.get('timeframe', '5minute'),
                'status': 'registered',  # registered, running, stopped
                'created_at': datetime.now().isoformat(),
                'started_at': None,
                'stopped_at': None
            }
        
        logger.info(f"Registered strategy {strategy_id}: {config.get('name')}")
        return strategy_id
    
    def start_strategy(self, strategy_id: str) -> bool:
        """
        Start a registered strategy.
        
        Args:
            strategy_id: Unique strategy identifier
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        with self._lock:
            if strategy_id not in self.strategies:
                logger.error(f"Strategy {strategy_id} not found")
                return False
            
            strategy = self.strategies[strategy_id]
            
            # Check if already running
            if self.strategy_metadata[strategy_id]['status'] == 'running':
                logger.warning(f"Strategy {strategy_id} is already running")
                return False
            
            # Start the strategy
            try:
                strategy.start()
                
                # Update metadata
                self.strategy_metadata[strategy_id]['status'] = 'running'
                self.strategy_metadata[strategy_id]['started_at'] = datetime.now().isoformat()
                
                logger.info(f"Started strategy {strategy_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error starting strategy {strategy_id}: {str(e)}")
                return False
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """
        Stop a running strategy.
        
        Args:
            strategy_id: Unique strategy identifier
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        with self._lock:
            if strategy_id not in self.strategies:
                logger.error(f"Strategy {strategy_id} not found")
                return False
            
            strategy = self.strategies[strategy_id]
            
            # Check if already stopped
            if self.strategy_metadata[strategy_id]['status'] == 'stopped':
                logger.warning(f"Strategy {strategy_id} is already stopped")
                return False
            
            # Stop the strategy
            try:
                strategy.stop()
                
                # Update metadata
                self.strategy_metadata[strategy_id]['status'] = 'stopped'
                self.strategy_metadata[strategy_id]['stopped_at'] = datetime.now().isoformat()
                
                logger.info(f"Stopped strategy {strategy_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error stopping strategy {strategy_id}: {str(e)}")
                return False
    
    def list_strategies(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all strategies with optional status filter.
        
        Args:
            status_filter: Filter by status ('registered', 'running', 'stopped')
                          None returns all strategies
        
        Returns:
            List[Dict]: List of strategy metadata dictionaries
        """
        with self._lock:
            strategies_list = []
            
            for strategy_id, metadata in self.strategy_metadata.items():
                # Apply filter if provided
                if status_filter and metadata['status'] != status_filter:
                    continue
                
                # Create response object
                strategy_info = {
                    'strategy_id': strategy_id,
                    **metadata
                }
                strategies_list.append(strategy_info)
            
            return strategies_list
    
    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """
        Get strategy instance by ID.
        
        Args:
            strategy_id: Unique strategy identifier
        
        Returns:
            BaseStrategy instance or None
        """
        with self._lock:
            return self.strategies.get(strategy_id)
    
    def get_strategy_metadata(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific strategy.
        
        Args:
            strategy_id: Unique strategy identifier
        
        Returns:
            Dict containing strategy metadata or None
        """
        with self._lock:
            return self.strategy_metadata.get(strategy_id)
    
    def get_active_strategies(self) -> List[str]:
        """
        Get list of currently running strategy IDs.
        
        Returns:
            List[str]: List of active strategy IDs
        """
        with self._lock:
            return [
                sid for sid, meta in self.strategy_metadata.items()
                if meta['status'] == 'running'
            ]
    
    def unregister_strategy(self, strategy_id: str) -> bool:
        """
        Remove a strategy from the manager.
        
        Args:
            strategy_id: Unique strategy identifier
        
        Returns:
            bool: True if unregistered successfully
        """
        with self._lock:
            if strategy_id not in self.strategies:
                logger.error(f"Strategy {strategy_id} not found")
                return False
            
            # Stop if running
            if self.strategy_metadata[strategy_id]['status'] == 'running':
                self.stop_strategy(strategy_id)
            
            # Remove from storage
            del self.strategies[strategy_id]
            del self.strategy_metadata[strategy_id]
            
            logger.info(f"Unregistered strategy {strategy_id}")
            return True
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get strategy statistics.
        
        Returns:
            Dict with counts of strategies by status
        """
        with self._lock:
            stats = {
                'total': len(self.strategies),
                'running': 0,
                'registered': 0,
                'stopped': 0
            }
            
            for metadata in self.strategy_metadata.values():
                status = metadata['status']
                if status in stats:
                    stats[status] += 1
            
            return stats

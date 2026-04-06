"""
Base Strategy Module

Defines the abstract base class for all trading strategies.
All custom strategies must inherit from this class and implement generate_signal().
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Provides the interface that all strategies must follow.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the strategy with configuration.
        
        Args:
            config: Strategy configuration parameters
                   Example: {'symbol': 'NIFTY', 'timeframe': '5minute'}
        """
        self.config = config
        self.name = config.get('name', 'Unnamed Strategy')
        self.symbol = config.get('symbol', '')
        self.timeframe = config.get('timeframe', '5minute')
        self.is_active = False
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on market data.
        
        This method MUST be implemented by all concrete strategy classes.
        
        Args:
            data: Historical OHLCV data in pandas DataFrame format
                  Columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        Returns:
            Optional[Dict]: Trading signal dictionary with structure:
                           {
                               'action': 'BUY' | 'SELL' | 'EXIT',
                               'quantity': int,
                               'price': float,
                               'reason': str
                           }
            None: No signal generated
        """
        pass
    
    def start(self):
        """Called when the strategy is started."""
        self.is_active = True
        print(f"[{self.name}] Strategy started")
    
    def stop(self):
        """Called when the strategy is stopped."""
        self.is_active = False
        print(f"[{self.name}] Strategy stopped")
    
    def on_fill(self, order_data: Dict[str, Any]):
        """
        Called when an order is filled/executed.
        
        Override this method to handle position updates.
        
        Args:
            order_data: Order execution details
        """
        pass
    
    def on_error(self, error: Exception):
        """
        Called when an error occurs during strategy execution.
        
        Override this method to handle errors gracefully.
        
        Args:
            error: Exception object
        """
        print(f"[{self.name}] Error occurred: {str(error)}")

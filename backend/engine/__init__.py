"""
Strategy Engine Module

Infrastructure for running automated trading strategies.

Components:
- BaseStrategy: Abstract base class for all strategies
- MarketDataService: Fetch market data from broker API
- StrategyManager: Lifecycle management for strategies
- ExecutionLoop: Background thread for continuous strategy execution
"""

from .base_strategy import BaseStrategy
from .market_data_service import MarketDataService
from .strategy_manager import StrategyManager
from .execution_loop import ExecutionLoop

__all__ = [
    'BaseStrategy',
    'MarketDataService',
    'StrategyManager',
    'ExecutionLoop',
]

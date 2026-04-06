"""
Backtest Module

Professional backtesting engine for algorithmic trading strategies.

Components:
- BacktestEngine: Main orchestrator for running backtests
- TradeSimulator: Realistic trade execution simulation
- PerformanceMetrics: Calculate trading performance statistics
- EquityCurve: Track account equity over time
- HistoricalDataLoader: Load and validate historical data

Usage:
    >>> from backtest.backtest_engine import BacktestEngine
    >>> engine = BacktestEngine()
    >>> results = engine.run(strategy=MyStrategy, data=data, initial_capital=100000)
"""

from .historical_data_loader import HistoricalDataLoader, load_csv_data
from .trade_simulator import TradeSimulator
from .performance_metrics import PerformanceMetrics
from .equity_curve import EquityCurve
from .backtest_engine import BacktestEngine

__all__ = [
    # Main engine
    'BacktestEngine',
    
    # Components
    'TradeSimulator',
    'PerformanceMetrics',
    'EquityCurve',
    'HistoricalDataLoader',
    
    # Utilities
    'load_csv_data',
]

"""
Live Trading Execution Engine Package

Professional live trading execution system for algorithmic trading.

This package provides:
- Broker interface abstraction (Zerodha Kite Connect)
- Order management with retry logic
- Real-time risk management
- Live strategy execution
- Dashboard data provider
- Complete trading orchestration

Usage:
    from trading import run_live_trading
    
    run_live_trading(
        strategy_class=LuxAlgoTrendlineStrategy,
        broker='zerodha',
        symbols=['RELIANCE', 'TCS'],
        api_key='your_key',
        access_token='your_token',
        capital=100000
    )

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from .broker_interface import (
    BrokerInterface,
    Order,
    Position,
    OrderError,
    APIError,
    ConnectionError
)

from .order_manager import OrderManager

from .risk_controller import (
    RiskController,
    RiskLimits,
    RiskStatus,
    RiskMetrics
)

from .live_strategy_runner import LiveStrategyRunner

from .trading_dashboard_data import (
    TradingDashboardDataProvider,
    create_dashboard_provider
)

from .live_trading_runner import (
    LiveTradingRunner,
    run_live_trading,
    run_live_trading_async
)

# Optional imports (may not be available)
try:
    from .zerodha_broker import ZerodhaBroker, create_zerodha_broker
except ImportError:
    pass

__all__ = [
    # Main interface
    'run_live_trading',
    'run_live_trading_async',
    'LiveTradingRunner',
    
    # Broker interface
    'BrokerInterface',
    'Order',
    'Position',
    'OrderError',
    'APIError',
    'ConnectionError',
    
    # Order management
    'OrderManager',
    
    # Risk management
    'RiskController',
    'RiskLimits',
    'RiskStatus',
    'RiskMetrics',
    
    # Strategy execution
    'LiveStrategyRunner',
    
    # Dashboard
    'TradingDashboardDataProvider',
    'create_dashboard_provider',
    
    # Broker implementations
    'ZerodhaBroker',
    'create_zerodha_broker'
]

__version__ = '1.0.0'
__author__ = 'Quantitative Trading Systems Engineer'

"""
Live Trading Runner Module

Main entry point for live trading execution.

Example usage:
    from trading.live_trading_runner import run_live_trading

    run_live_trading(
        strategy_class=LuxAlgoTrendlineStrategy,
        broker="zerodha",
        symbols=["RELIANCE","TCS","INFY"],
        capital=100000
    )

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
import signal as system_signal

from .broker_interface import BrokerInterface, ConnectionError
from .order_manager import OrderManager
from .risk_controller import RiskController, RiskLimits
from .live_strategy_runner import LiveStrategyRunner
from .trading_dashboard_data import TradingDashboardDataProvider

logger = logging.getLogger(__name__)


class LiveTradingRunner:
    """
    Main orchestration engine for live trading.

    Coordinates:
    - Broker connection
    - Strategy execution
    - Risk management
    - Order management
    - Dashboard data

    Usage:
        >>> runner = LiveTradingRunner(
        ...     strategy_class=MyStrategy,
        ...     broker_type='zerodha',
        ...     symbols=['RELIANCE', 'TCS']
        ... )
        >>> runner.start()
    """

    def __init__(
        self,
        strategy_class: Type,
        broker_type: str,
        symbols: List[str],
        api_key: str = None,
        access_token: str = None,
        api_secret: str = None,
        initial_capital: float = 100000.0,
        capital_per_trade: float = 25000.0,
        risk_limits: RiskLimits = None,
        heartbeat_interval: int = 60,
        log_level: str = "INFO",
    ):
        """
        Initialize live trading runner.

        Args:
            strategy_class: Strategy class to execute
            broker_type: Broker type ('zerodha', etc.)
            symbols: List of trading symbols
            api_key: Broker API key
            access_token: Broker access token
            api_secret: Broker API secret
            initial_capital: Starting capital
            capital_per_trade: Capital per trade
            risk_limits: Risk limits configuration
            heartbeat_interval: Data refresh interval (seconds)
            log_level: Logging level

        Example:
            >>> runner = LiveTradingRunner(
            ...     strategy_class=LuxAlgoTrendlineStrategy,
            ...     broker_type='zerodha',
            ...     symbols=['RELIANCE', 'TCS'],
            ...     api_key='your_key',
            ...     access_token='your_token'
            ... )
        """
        # Configuration
        self.strategy_class = strategy_class
        self.broker_type = broker_type.lower()
        self.symbols = symbols
        self.api_key = api_key
        self.access_token = access_token
        self.api_secret = api_secret
        self.initial_capital = initial_capital
        self.capital_per_trade = capital_per_trade
        self.risk_limits = risk_limits or RiskLimits()
        self.heartbeat_interval = heartbeat_interval

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Components (initialized on start)
        self.broker: Optional[BrokerInterface] = None
        self.order_manager: Optional[OrderManager] = None
        self.risk_controller: Optional[RiskController] = None
        self.strategy_runner: Optional[LiveStrategyRunner] = None
        self.dashboard_provider: Optional[TradingDashboardDataProvider] = None

        # State
        self.running: bool = False
        self.start_time: Optional[datetime] = None

        logger.info(
            f"LiveTradingRunner initialized: "
            f"broker={broker_type}, symbols={len(symbols)}, capital={initial_capital}"
        )

    def start(self):
        """
        Start live trading.

        Initializes all components and starts the trading loop.

        Example:
            >>> runner.start()
            >>> # Trading now active...
        """
        try:
            logger.info("Starting live trading engine...")

            # Step 1: Connect to broker
            self._connect_broker()

            # Step 2: Initialize order manager
            self.order_manager = OrderManager(self.broker)
            logger.info("Order manager initialized")

            # Step 3: Initialize risk controller
            self.risk_controller = RiskController(
                initial_capital=self.initial_capital, limits=self.risk_limits
            )
            logger.info("Risk controller initialized")

            # Step 4: Initialize strategy runner
            self.strategy_runner = LiveStrategyRunner(
                broker=self.broker,
                strategy_class=self.strategy_class,
                symbols=self.symbols,
                order_manager=self.order_manager,
                risk_controller=self.risk_controller,
                capital_per_trade=self.capital_per_trade,
                heartbeat_interval=self.heartbeat_interval,
            )
            logger.info("Strategy runner initialized")

            # Step 5: Initialize dashboard provider
            self.dashboard_provider = TradingDashboardDataProvider(
                broker=self.broker,
                order_manager=self.order_manager,
                risk_controller=self.risk_controller,
                initial_capital=self.initial_capital,
            )
            logger.info("Dashboard provider initialized")

            # Mark as running
            self.running = True
            self.start_time = datetime.now()

            logger.info("=" * 70)
            logger.info("LIVE TRADING ENGINE STARTED")
            logger.info("=" * 70)
            logger.info(f"Symbols: {self.symbols}")
            logger.info(f"Capital: {self.initial_capital:.2f}")
            logger.info(f"Heartbeat: {self.heartbeat_interval}s")
            logger.info("=" * 70)

            # Step 6: Run trading loop
            asyncio.run(self._run_trading_loop())

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.stop()

        except Exception as e:
            logger.error(f"Failed to start: {str(e)}", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """Stop live trading."""
        logger.info("Stopping live trading engine...")

        self.running = False

        # Stop strategy runner
        if self.strategy_runner:
            asyncio.run(self.strategy_runner.stop())

        # Disconnect broker
        if self.broker:
            self.broker.disconnect()

        logger.info("Live trading engine stopped")

    def _connect_broker(self):
        """Connect to broker based on broker_type."""
        try:
            if self.broker_type == "zerodha":
                from .zerodha_broker import ZerodhaBroker

                self.broker = ZerodhaBroker(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    access_token=self.access_token,
                )

                self.broker.connect(access_token=self.access_token)
                logger.info("Connected to Zerodha")

            else:
                raise ValueError(f"Unsupported broker type: {self.broker_type}")

        except Exception as e:
            logger.error(f"Broker connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to broker: {str(e)}")

    async def _run_trading_loop(self):
        """Run the main trading loop."""
        try:
            await self.strategy_runner.run()

        except Exception as e:
            logger.error(f"Trading loop error: {str(e)}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get current trading status.

        Returns:
            Status dictionary with all metrics

        Example:
            >>> status = runner.get_status()
            >>> print(f"Running: {status['running']}")
        """
        if not self.running:
            return {"status": "STOPPED"}

        # Get dashboard data
        dashboard_data = self.dashboard_provider.get_dashboard_data()

        # Add runner status
        runner_status = (
            self.strategy_runner.get_status() if self.strategy_runner else {}
        )

        return {
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": (
                (datetime.now() - self.start_time).total_seconds()
                if self.start_time
                else 0
            ),
            "broker": self.broker_type,
            "symbols": self.symbols,
            "dashboard": dashboard_data,
            "runner": runner_status,
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data for monitoring."""
        if not self.dashboard_provider:
            return {}

        return self.dashboard_provider.get_dashboard_data()

    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        if not self.risk_controller:
            return {}

        return self.risk_controller.get_risk_report()


def run_live_trading(
    strategy_class: Type,
    broker: str = "zerodha",
    symbols: List[str] = None,
    api_key: str = None,
    access_token: str = None,
    api_secret: str = None,
    capital: float = 100000.0,
    capital_per_trade: float = 25000.0,
    max_daily_loss: float = 5000.0,
    max_drawdown: float = 0.10,
    heartbeat_interval: int = 60,
):
    """
    Convenience function to start live trading.

    Args:
        strategy_class: Strategy class to run
        broker: Broker type ('zerodha')
        symbols: List of trading symbols
        api_key: Broker API key
        access_token: Access token
        api_secret: API secret
        capital: Total capital
        capital_per_trade: Capital per trade
        max_daily_loss: Maximum daily loss limit
        max_drawdown: Maximum drawdown limit
        heartbeat_interval: Data refresh interval

    Example:
        >>> from trading import LuxAlgoTrendlineStrategy
        >>> run_live_trading(
        ...     strategy_class=LuxAlgoTrendlineStrategy,
        ...     broker='zerodha',
        ...     symbols=['RELIANCE', 'TCS', 'INFY'],
        ...     api_key='your_key',
        ...     access_token='your_token',
        ...     capital=100000
        ... )
    """
    # Configure risk limits
    risk_limits = RiskLimits(
        max_daily_loss=max_daily_loss,
        max_portfolio_drawdown=max_drawdown,
        max_position_size=capital_per_trade * 2,
        max_total_exposure=capital * 0.9,
        max_open_trades=len(symbols) if symbols else 5,
    )

    # Create runner
    runner = LiveTradingRunner(
        strategy_class=strategy_class,
        broker_type=broker,
        symbols=symbols or [],
        api_key=api_key,
        access_token=access_token,
        api_secret=api_secret,
        initial_capital=capital,
        capital_per_trade=capital_per_trade,
        risk_limits=risk_limits,
        heartbeat_interval=heartbeat_interval,
    )

    # Start trading
    runner.start()


async def run_live_trading_async(
    strategy_class: Type, broker: str = "zerodha", symbols: List[str] = None, **kwargs
):
    """
    Async version of run_live_trading.

    Args:
        strategy_class: Strategy class
        broker: Broker type
        symbols: Trading symbols
        **kwargs: Additional arguments

    Example:
        >>> await run_live_trading_async(
        ...     strategy_class=MyStrategy,
        ...     symbols=['RELIANCE']
        ... )
    """
    runner = LiveTradingRunner(
        strategy_class=strategy_class,
        broker_type=broker,
        symbols=symbols or [],
        **kwargs,
    )

    runner.start()

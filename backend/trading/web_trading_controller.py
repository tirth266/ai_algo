"""
Web Trading Controller

Enables web-based control of the trading engine.
Integrates with run_daily_trading.py functionality.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

# Add paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

# Import authentication
try:
    from backend.trading.zerodha_auto_login import get_kite_client, is_zerodha_connected
except ImportError:
    from trading.zerodha_auto_login import get_kite_client, is_zerodha_connected

# Import broker
try:
    from backend.trading.zerodha_broker import ZerodhaBroker
    from backend.trading.broker_interface import Order
except ImportError:
    from trading.zerodha_broker import ZerodhaBroker
    from trading.broker_interface import Order

# Import risk engine
try:
    from backend.core.risk_engine import RiskEngine, TradeRequest
except ImportError:
    from core.risk_engine import RiskEngine, TradeRequest

# Import base strategy
try:
    from backend.engine.base_strategy import BaseStrategy
except ImportError:
    from engine.base_strategy import BaseStrategy

# Import configuration
try:
    from backend.config.trading_config import (
        SYMBOLS,
        PRIMARY_TIMEFRAME,
        CAPITAL_PER_TRADE,
        MAX_DAILY_LOSS,
        MAX_POSITIONS,
        TOTAL_CAPITAL,
        STRATEGIES_DIR,
        CHECK_MARKET_HOURS,
        MARKET_OPEN,
        MARKET_CLOSE,
        EXCHANGE,
        DEFAULT_PRODUCT,
        DEFAULT_ORDER_TYPE,
    )
except ImportError:
    from config.trading_config import (
        SYMBOLS,
        PRIMARY_TIMEFRAME,
        CAPITAL_PER_TRADE,
        MAX_DAILY_LOSS,
        MAX_POSITIONS,
        TOTAL_CAPITAL,
        STRATEGIES_DIR,
        CHECK_MARKET_HOURS,
        MARKET_OPEN,
        MARKET_CLOSE,
        EXCHANGE,
        DEFAULT_PRODUCT,
        DEFAULT_ORDER_TYPE,
    )

logger = logging.getLogger(__name__)


class WebTradingController:
    """
    Web-controlled trading engine.

    Provides the same functionality as run_daily_trading.py
    but controlled from web UI instead of command line.
    """

    def __init__(self):
        """Initialize web trading controller."""
        # Initialize components
        self.kite = None
        self.broker = None
        self.strategies = []
        self.risk_manager = None

        # Trading state
        self.running = False
        self.signals_generated = 0
        self.orders_placed = 0

        logger.info("WebTradingController initialized")

    def authenticate(self) -> bool:
        """Authenticate with Zerodha."""
        try:
            logger.info("Authenticating with Zerodha...")

            if is_zerodha_connected():
                logger.info("✓ Zerodha already connected")
            else:
                logger.info("Initiating Zerodha login...")

            # Get authenticated client
            self.kite = get_kite_client(auto_renew=True)

            # Create broker instance
            api_key = os.getenv("ZERODHA_API_KEY")
            access_token = self.kite.access_token

            self.broker = ZerodhaBroker(api_key=api_key, access_token=access_token)

            logger.info("✓ Authentication successful")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False

    def load_strategies(self) -> bool:
        """Load strategies from strategies/ folder dynamically."""
        try:
            logger.info("Loading strategies...")

            strategies_path = project_root / "backend" / STRATEGIES_DIR

            if not strategies_path.exists():
                logger.error(f"Strategies directory not found: {strategies_path}")
                return False

            loaded_count = 0

            # Scan for strategy files
            for file_path in strategies_path.glob("*_strategy.py"):
                if file_path.name.startswith("_"):
                    continue

                try:
                    # Load module dynamically (same as run_daily_trading.py)
                    import importlib.util

                    module_name = file_path.stem
                    spec = importlib.util.spec_from_file_location(
                        module_name, file_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find strategy class
                    strategy_class = None
                    for name in dir(module):
                        obj = getattr(module, name)
                        if (
                            isinstance(obj, type)
                            and issubclass(obj, BaseStrategy)
                            and obj is not BaseStrategy
                        ):
                            strategy_class = obj
                            break

                    if strategy_class:
                        # Create strategy instance
                        config = {
                            "name": module_name,
                            "symbol": SYMBOLS[0] if SYMBOLS else "RELIANCE",
                            "timeframe": PRIMARY_TIMEFRAME,
                        }

                        strategy = strategy_class(config)
                        self.strategies.append(strategy)
                        loaded_count += 1

                        logger.info(f"✓ Loaded strategy: {module_name}")

                except Exception as e:
                    logger.error(f"Failed to load strategy {file_path.name}: {str(e)}")

            if loaded_count == 0:
                logger.warning("No strategies loaded!")
                return False

            # Initialize risk engine
            self.risk_manager = RiskEngine(
                capital=TOTAL_CAPITAL,
                max_risk_per_trade=CAPITAL_PER_TRADE
                / TOTAL_CAPITAL,  # Convert to fraction
                max_daily_loss_pct=MAX_DAILY_LOSS
                / TOTAL_CAPITAL,  # Convert to fraction
                max_open_positions=MAX_POSITIONS,
                max_trades_per_day=10,  # Default
            )

            logger.info(f"✓ Strategies loaded: {loaded_count}")
            return True

        except Exception as e:
            logger.error(f"Failed to load strategies: {str(e)}")
            return False

    def fetch_market_data(
        self, symbol: str, timeframe: str, days: int = 5
    ) -> pd.DataFrame:
        """Fetch market data from Zerodha API."""
        try:
            logger.debug(f"Fetching data for {symbol} ({timeframe})...")

            if not self.kite:
                logger.error("Kite client not initialized")
                return pd.DataFrame()

            # Get instrument token
            instruments = self.kite.instruments(exchange=EXCHANGE)
            instrument = next(
                (i for i in instruments if i["tradingsymbol"] == symbol), None
            )

            if not instrument:
                logger.error(f"Instrument not found for {symbol}")
                return pd.DataFrame()

            token = instrument["instrument_token"]

            # Fetch historical data
            to_date = datetime.now().date()
            from_date = datetime.now().date()

            candles = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=timeframe,
            )

            # Convert to DataFrame
            df = pd.DataFrame(candles)

            if df.empty:
                logger.warning(f"No data received for {symbol}")
                return pd.DataFrame()

            # Rename columns
            df = df.rename(
                columns={
                    "timestamp": "timestamp",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )

            # Ensure timestamp is datetime
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

            logger.debug(f"✓ Fetched {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def run_strategies(self):
        """Run all strategies on all symbols."""
        logger.info("Running strategies...")

        for symbol in SYMBOLS:
            logger.debug(f"Processing {symbol}...")

            # Fetch market data
            data = self.fetch_market_data(symbol, PRIMARY_TIMEFRAME)

            if data.empty:
                logger.warning(f"Skipping {symbol} - no data available")
                continue

            # Run each strategy
            for strategy in self.strategies:
                try:
                    # Set symbol for strategy
                    strategy.symbol = symbol

                    # Generate signal
                    signal = strategy.generate_signal(data)

                    if signal:
                        logger.info(f"\nSignal generated by {strategy.name}:")
                        logger.info(f"  Action: {signal.get('action')}")
                        logger.info(f"  Quantity: {signal.get('quantity')}")
                        logger.info(f"  Reason: {signal.get('reason')}")

                        # Store signal
                        signal["symbol"] = symbol
                        signal["strategy"] = strategy.name
                        signal["timeframe"] = PRIMARY_TIMEFRAME
                        signal["timestamp"] = datetime.now()

                        self.signals_generated += 1

                        # Execute order
                        self.execute_order(signal)

                except Exception as e:
                    logger.error(f"Strategy {strategy.name} error: {str(e)}")
                    strategy.on_error(e)

    def execute_order(self, signal: Dict[str, Any]):
        """Execute trading order after risk check."""
        try:
            symbol = signal["symbol"]
            action = signal.get("action", "")

            # Get current price
            current_price = signal.get("price", 0)

            if not current_price:
                # Fetch from market
                quote = self.kite.quote(f"{EXCHANGE}:{symbol}")
                current_price = quote[f"{EXCHANGE}:{symbol}"]["last_price"]

            # Risk check - SINGLE ENTRY POINT
            trade_request = TradeRequest(
                symbol=symbol,
                direction=action,
                quantity=signal.get("quantity", 1),
                price=current_price,
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit"),
            )

            risk_result = self.risk_manager.validate_trade(trade_request)

            if not risk_result["allowed"]:
                logger.warning(
                    f"Order rejected by risk engine: {risk_result['reason']}"
                )
                return

            # Use adjusted quantity from risk validation
            quantity = risk_result["adjusted_quantity"]

            if quantity <= 0:
                logger.warning(f"Invalid quantity from risk validation: {quantity}")
                return

            # Mark signal as risk-checked
            signal["risk_checked"] = True

            # CRITICAL: Ensure risk validation was performed
            if not trade_request.risk_checked:
                raise RuntimeError(
                    "CRITICAL: Trade attempted without RiskEngine validation"
                )

            # Place order
            logger.info(
                f"Placing order: {action} {quantity} {symbol} @ {current_price:.2f}"
            )

            # Create Order object
            from .broker_interface import Order

            order = Order(
                symbol=symbol,
                quantity=quantity,
                side=action,
                order_type=DEFAULT_ORDER_TYPE,
                price=current_price if DEFAULT_ORDER_TYPE != "MARKET" else None,
                product=DEFAULT_PRODUCT,
            )

            # Place order
            response = self.broker.place_order(order)
            order_id = response.get("order_id")

            # Map action to Zerodha transaction type
            transaction_type = "BUY" if action == "BUY" else "SELL"

            # Place market order
            order_id = self.broker.place_order(
                symbol=symbol,
                exchange=EXCHANGE,
                transaction_type=transaction_type,
                order_type=DEFAULT_ORDER_TYPE,
                quantity=quantity,
                product=DEFAULT_PRODUCT,
            )

            if order_id:
                logger.info(f"✓ Order placed successfully! Order ID: {order_id}")
                self.orders_placed += 1

                # Update risk engine position registry
                if action == "BUY":
                    # Register the new open position
                    self.risk_manager.open_position(trade_request)
                elif action == "SELL":
                    # Close the position (use current price as exit price approximation)
                    self.risk_manager.close_position(
                        symbol=symbol,
                        exit_price=current_price,
                        pnl=0,  # Will be updated when actual P&L is known
                    )

        except Exception as e:
            logger.error(f"Order execution failed: {str(e)}")

    def run_trading_loop(self):
        """Main trading loop - runs continuously."""
        try:
            logger.info("Starting trading loop...")
            self.running = True

            # Authenticate
            if not self.authenticate():
                logger.error("Authentication failed")
                self.running = False
                return

            # Load strategies
            if not self.load_strategies():
                logger.error("Failed to load strategies")
                self.running = False
                return

            logger.info("✓ Trading engine ready - monitoring markets...")

            # Main loop
            while self.running:
                try:
                    # Run strategies
                    self.run_strategies()

                    # Wait for next candle (5 minutes)
                    # In production, use proper scheduling
                    import time

                    for _ in range(300):  # 5 minutes = 300 seconds
                        if not self.running:
                            break
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"Trading loop error: {str(e)}")
                    # Continue loop despite errors

            # Cleanup
            logger.info("Stopping trading loop...")
            self.running = False

        except Exception as e:
            logger.error(f"Trading loop failed: {str(e)}")
            self.running = False
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get current trading status."""
        return {
            "running": self.running,
            "active_strategies": len(self.strategies),
            "broker_connected": self.kite is not None,
            "symbols_monitored": SYMBOLS,
            "signals_generated": self.signals_generated,
            "orders_placed": self.orders_placed,
        }

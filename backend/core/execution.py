"""
Production Trading System - Main Execution Loop

Integrates:
- MasterStrategy for signal generation
- TradeManager for trade lifecycle
- MarketDataService for live data validation

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from strategies.master_strategy import MasterStrategy
from core.trade_manager import TradeManager
from core.indicators import calculate_atr, calculate_ema
from core.risk_engine import RiskEngine, TradeRequest
from core.order_validator import OrderValidator
from core.nse_order_validator import validate_nse_order
from core.trade_logger import TradeLogger
from core.realistic_execution import RealisticExecutor
from analytics.performance import PerformanceAnalyzer
from services.angel_service import get_angel_service, OrderRequest, ApiStatus
from services.market_data import get_market_data_service
from core.broker_reconciliation import BrokerReconciliation
from services.angelone_service import AngelOneService

logger = logging.getLogger(__name__)


class TradingSystem:
    """Main trading system that integrates strategy, risk, and execution."""

    def __init__(
        self,
        capital: float = 100000.0,
        risk_per_trade: float = 0.02,
        max_open_positions: int = 3,
        enable_trailing: bool = True,
        enable_live_trading: bool = False,
    ):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_open_positions = max_open_positions
        self.enable_trailing = enable_trailing
        self.enable_live_trading = enable_live_trading
        self.is_running = False
        self.broker_orders: Dict[str, str] = {}
        self.trading_allowed = True
        self.reconciliation_status: Dict[str, Any] = {}

        self.strategy = MasterStrategy()
        self.trade_manager = TradeManager(capital=capital, risk_per_trade=risk_per_trade)
        self.risk_engine = RiskEngine()
        self.order_validator = OrderValidator()
        self.execution_engine = RealisticExecutor()
        self.trade_logger = TradeLogger()
        self.performance_analyzer = PerformanceAnalyzer()

        # Broker service for live trading
        self.broker_service = None
        if enable_live_trading:
            try:
                self.broker_service = get_angel_service()
            except Exception as e:
                logger.warning(f"Could not initialize broker service: {e}")

        # Run startup broker reconciliation
        self._run_broker_reconciliation()

    def _run_broker_reconciliation(self) -> None:
        """Run broker reconciliation on startup to sync local state with broker."""
        try:
            logger.info("Starting broker reconciliation...")

            # Initialize broker service
            try:
                broker_service = AngelOneService()
            except Exception as e:
                logger.warning(
                    f"Could not initialize broker service: {str(e)} - skipping reconciliation"
                )
                self.trading_allowed = (
                    True  # Allow trading even if broker service unavailable
                )
                return

            # Perform reconciliation
            with BrokerReconciliation(broker_service=broker_service) as reconciliation:
                report = reconciliation.reconcile()

                # Store reconciliation state
                self.reconciliation_status = report
                self.trading_allowed = report.get("trading_allowed", False)

                # Log reconciliation results
                logger.info(f"Broker reconciliation: {report['status']}")
                logger.info(f"Trading allowed: {self.trading_allowed}")

                if report.get("critical_error"):
                    logger.error(
                        "CRITICAL: Broker reconciliation failed - TRADING BLOCKED"
                    )
                    logger.error(f"Error details: {report.get('message')}")
                elif report.get("discrepancies_found"):
                    logger.warning(
                        f"Broker reconciliation: {len(report.get('actions', []))} corrections applied"
                    )
                    # Log each action
                    for action in report.get("actions", []):
                        if action.get("severity") == "error":
                            logger.error(
                                f"  {action['action_type']}: {action['symbol']} - {action['description']}"
                            )
                        else:
                            logger.warning(
                                f"  {action['action_type']}: {action['symbol']} - {action['description']}"
                            )
                else:
                    logger.info("Broker reconciliation: System matches broker state")

        except ImportError:
            logger.warning(
                "BrokerReconciliation module not available - skipping reconciliation"
            )
            self.trading_allowed = True
        except Exception as e:
            logger.error(f"Broker reconciliation error: {str(e)}", exc_info=True)
            self.trading_allowed = False  # Fail-safe: block trading
            self.reconciliation_status = {
                "status": "failed",
                "message": str(e),
                "trading_allowed": False,
            }

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Generate trading signal from strategy."""
        signal = self.strategy.generate_signal(data)

        if signal:
            risk = self.strategy.get_risk_levels()
            return {
                "type": signal,
                "entry": risk["entry_price"],
                "stop_loss": risk["stop_loss"],
                "take_profit": [risk["take_profit"] / 2, risk["take_profit"]],
                "confidence": risk.get("confidence", "low"),
                "reason": risk.get("reason", ""),
            }

        return None

    def open_trade(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Open a new trade based on signal using a modular paper-trading pipeline."""
        # Safeguard: Prevent trading on stale data
        mds = get_market_data_service()
        strategy_timeframe = getattr(self.strategy, "timeframe", "5m")

        # Check primary symbol
        primary_symbol = self.strategy.name if hasattr(self.strategy, "name") else None

        if primary_symbol and mds.is_data_stale(primary_symbol, strategy_timeframe):
            cache_age = mds.get_cache_age(primary_symbol, strategy_timeframe)
            logger.error(
                f"🚨 STALE DATA SAFEGUARD: Cannot open trade for {primary_symbol} "
                f"({strategy_timeframe}) - data is {cache_age}s old. "
                f"Waiting for fresh data..."
            )
            return None

        if not self.trading_allowed:
            logger.error(
                "TRADING BLOCKED: Broker reconciliation failed. "
                "Manual intervention required. Status: "
                f"{self.reconciliation_status.get('message', 'Unknown error')}"
            )
            return None

        signal = self._generate_signal(data)
        if not signal:
            return None

        current_price = data["close"].iloc[-1]
        trade_request = self._build_trade_request(signal, current_price)

        risk_result = self._validate_trade_request(trade_request)
        if not risk_result["allowed"]:
            logger.warning(f"Trade blocked by Risk Engine: {risk_result['reason']}")
            return None

        duplicate_result = self._check_duplicate_position(trade_request.symbol)
        if duplicate_result["duplicate"]:
            logger.warning(
                f"Trade blocked by duplicate position: {duplicate_result['reason']}"
            )
            return None

        order_validation = self._validate_order(
            signal=signal,
            current_price=current_price,
            quantity=int(risk_result["adjusted_quantity"]),
        )
        if not order_validation["valid"]:
            logger.warning(f"Order validation FAILED: {order_validation['reason']}")
            return None

        # Validate NSE-specific order parameters
        nse_validation = validate_nse_order(
            symbol=trade_request.symbol,
            quantity=int(risk_result["adjusted_quantity"]),
            price=current_price,
            order_type=trade_request.direction,
        )
        if not nse_validation.get("valid", False):
            logger.warning(
                f"NSE order validation FAILED: {nse_validation.get('message', 'Unknown error')}"
            )
            return None

        executed_price, slippage = self._apply_slippage(
            direction=trade_request.direction,
            signal_price=signal["entry"],
            current_price=current_price,
        )

        trade = self.trade_manager.open_trade(
            symbol=self.strategy.name,
            direction=signal["type"],
            entry_price=executed_price,
            stop_loss=signal["stop_loss"],
            take_profit_1=signal["take_profit"][0],
            take_profit_2=signal["take_profit"][1],
            quantity=int(risk_result["adjusted_quantity"]),
            confidence=signal.get("confidence", "medium"),
            reason=signal.get("reason", ""),
            persist=False,
        )

        if trade is None:
            logger.error("Trade creation failed, aborting execution pipeline")
            return None

        try:
            self._save_trade_position(
                trade=trade,
                executed_price=executed_price,
                current_price=current_price,
            )
            self._update_pnl_tracker(trade, current_price)
            self._log_trade_open(trade, slippage)

            self.risk_engine.open_position(trade_request)

            logger.info(
                f"Trade opened: {trade.id} | {trade.direction} {trade.quantity} "
                f"{trade.symbol} @ {executed_price:.2f} | slippage={slippage:.2f}"
            )

            # Send to broker if live trading is enabled
            if self.enable_live_trading and self.broker_service:
                broker_order_id = self._send_order_to_broker(
                    trade=trade,
                    executed_price=executed_price,
                    signal=signal,
                )
                if broker_order_id:
                    self.broker_orders[trade.id] = broker_order_id
                    logger.info(
                        f"Trade linked to broker order: trade_id={trade.id}, "
                        f"broker_order_id={broker_order_id}"
                    )
                else:
                    logger.warning(
                        f"Trade created locally but broker order failed: trade_id={trade.id}. "
                        "Trade remains in system but not submitted to broker."
                    )

            return {
                "trade_id": trade.id,
                "signal": signal,
                "broker_order_id": self.broker_orders.get(trade.id),
            }

        except Exception as exc:
            logger.error(f"Trade execution pipeline failed: {exc}")
            self._abort_trade(trade.id)
            return None

    def _generate_signal(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Generate a trade signal from the strategy."""
        return self.generate_signal(data)

    def _build_trade_request(
        self, signal: Dict[str, Any], current_price: float
    ) -> TradeRequest:
        """Build the risk engine payload from signal data."""
        return TradeRequest(
            symbol=self.strategy.name,
            direction=signal["type"],
            quantity=100,
            price=current_price,
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"][1] if signal["take_profit"] else None,
        )

    def _validate_trade_request(self, trade_request: TradeRequest) -> Dict[str, Any]:
        """Validate the trade according to risk rules."""
        return self.risk_engine.validate_trade(trade_request)

    def _check_duplicate_position(self, symbol: str) -> Dict[str, Any]:
        """Check for duplicate open positions before opening a new trade."""
        is_duplicate, reason = self.trade_manager.persistence.check_for_duplicates(
            symbol
        )
        return {"duplicate": is_duplicate, "reason": reason}

    def _validate_order(
        self,
        signal: Dict[str, Any],
        current_price: float,
        quantity: int,
    ) -> Dict[str, Any]:
        """Validate the trade order against platform constraints."""
        return self.order_validator.validate_order(
            symbol=self.strategy.name,
            direction=signal["type"],
            entry_price=signal["entry"],
            current_price=current_price,
            quantity=quantity,
            capital=self.capital,
            open_trades=self.trade_manager.get_open_trades(),
        )

    def _apply_slippage(
        self,
        direction: str,
        signal_price: float,
        current_price: float,
    ) -> Tuple[float, float]:
        """Apply realistic paper-trade slippage to the entry price."""
        executed_price, slippage = self.execution_engine.calculate_entry_price(
            direction=direction,
            signal_price=signal_price,
            current_price=current_price,
        )
        return executed_price, slippage

    def _save_trade_position(
        self,
        trade: Any,
        executed_price: float,
        current_price: float,
    ) -> None:
        """Persist the position and trade record after successful paper execution."""
        self.trade_manager.persistence.save_position(
            symbol=trade.symbol,
            side=trade.direction,
            quantity=trade.quantity,
            entry_price=executed_price,
            stop_loss=trade.stop_loss,
            take_profit_1=trade.take_profit_1,
            take_profit_2=trade.take_profit_2,
            strategy_name=trade.reason or "paper_trade",
            current_price=current_price,
        )

        self.trade_manager.persistence.save_trade(
            symbol=trade.symbol,
            side=trade.direction,
            quantity=trade.quantity,
            entry_price=executed_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit_2,
            status="open",
            strategy_name=trade.reason or "paper_trade",
            entry_time=trade.entry_time,
        )

    def _update_pnl_tracker(self, trade: Any, current_price: float) -> None:
        """Update the PnL tracker after opening a paper trade."""
        self.risk_engine.update_position_pnl(trade.symbol, current_price)

    def _log_trade_open(self, trade: Any, slippage: float) -> None:
        """Log the opened trade with execution metadata."""
        self.trade_logger.log_trade(
            symbol=trade.symbol,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=None,
            quantity=trade.quantity,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit_2,
            fees=0.0,
            slippage=slippage,
            entry_time=trade.entry_time,
            exit_time=None,
            strategy=trade.reason or "paper_trade",
        )

    def _send_order_to_broker(
        self,
        trade: Any,
        executed_price: float,
        signal: Dict[str, Any],
    ) -> Optional[str]:
        """
        Send validated trade order to broker via AngelService.

        This method integrates with the production-grade broker service layer.
        It ensures:
        1. Trade has already been validated by RiskEngine
        2. Order is sent with standardized parameters
        3. Errors are logged with full context

        Args:
            trade: Trade object from TradeManager
            executed_price: Price at which order will be executed
            signal: Signal that triggered the trade

        Returns:
            Broker order ID if successful, None if failed
        """
        try:
            service = get_angel_service()

            # Build order request for broker
            order_request = OrderRequest(
                symbol=trade.symbol,
                direction=trade.direction,
                quantity=trade.quantity,
                price=executed_price,
                order_type="MARKET",  # Use market orders for execution
                stop_loss=trade.stop_loss,
                product="INTRADAY",  # Configurable based on strategy
            )

            logger.info(
                f"Sending order to AngelOne: {order_request.direction} "
                f"{order_request.quantity} {order_request.symbol} "
                f"@ {executed_price:.2f}"
            )

            # Send to broker
            response = service.place_order(order_request)

            if response.is_success():
                broker_order_id = response.data.get("order_id")
                logger.info(
                    f"Order acknowledged by broker: order_id={broker_order_id}, "
                    f"trade_id={trade.id}"
                )

                # Link broker order to local trade
                trade.broker_order_id = broker_order_id
                trade.status = "BROKER_SUBMITTED"

                return broker_order_id

            else:
                logger.error(
                    f"Broker rejected order: status={response.status.value}, "
                    f"message={response.message}, error_code={response.error_code}, "
                    f"retry_count={response.retry_count}"
                )

                # Categorize error for caller
                if response.status == ApiStatus.RATE_LIMIT:
                    logger.warning("Rate limited by broker, will retry next cycle")
                elif response.status == ApiStatus.UNAUTHORIZED:
                    logger.error("Authentication failed, requires manual token refresh")
                elif response.status == ApiStatus.TIMEOUT:
                    logger.warning("Broker connection timeout, will retry")

                return None

        except Exception as e:
            logger.error(f"Exception sending order to broker: {str(e)}", exc_info=True)
            return None

    def reconcile_with_broker(self) -> Dict[str, Any]:
        """
        Reconcile local positions with broker positions.

        This ensures consistency between local trade records and broker's
        authoritative position data after live trading.

        Returns:
            Dict with reconciliation status and any corrections made
        """
        if not self.enable_live_trading or not self.broker_service:
            logger.warning("Live trading not enabled, skipping broker reconciliation")
            return {"status": "skipped", "reason": "live_trading_disabled"}

        logger.info("Starting broker position reconciliation...")

        try:
            # Get positions from broker
            response = self.broker_service.get_positions()

            if not response.is_success():
                logger.error(
                    f"Failed to reconcile with broker: {response.message} "
                    f"(error_code={response.error_code})"
                )
                return {
                    "status": "failed",
                    "reason": response.message,
                    "error_code": response.error_code,
                }

            broker_positions = {
                pos["symbol"]: pos for pos in response.data.get("positions", [])
            }

            # Get local positions
            local_positions = {
                trade.symbol: trade for trade in self.trade_manager.open_trades.values()
            }

            # Reconciliation checks
            corrections = []
            discrepancies = []

            # Check 1: Positions on broker but not locally (shouldn't happen)
            for symbol, broker_pos in broker_positions.items():
                if symbol not in local_positions:
                    discrepancies.append(
                        f"Broker position exists but not in local system: {symbol} "
                        f"qty={broker_pos['quantity']}"
                    )

            # Check 2: Local positions not on broker (order may not have filled)
            for symbol, local_trade in local_positions.items():
                if symbol not in broker_positions:
                    logger.warning(
                        f"Local trade not yet on broker: {symbol} "
                        f"(may still be pending): trade_id={local_trade.id}"
                    )

            # Check 3: Quantity mismatches
            for symbol, broker_pos in broker_positions.items():
                if symbol in local_positions:
                    local_trade = local_positions[symbol]
                    if local_trade.quantity != broker_pos["quantity"]:
                        discrepancies.append(
                            f"Quantity mismatch for {symbol}: "
                            f"local={local_trade.quantity}, broker={broker_pos['quantity']}"
                        )
                        corrections.append(
                            {
                                "action": "update_quantity",
                                "symbol": symbol,
                                "local_quantity": local_trade.quantity,
                                "broker_quantity": broker_pos["quantity"],
                            }
                        )

            reconciliation_result = {
                "status": "success"
                if not discrepancies
                else "completed_with_discrepancies",
                "broker_positions_count": len(broker_positions),
                "local_positions_count": len(local_positions),
                "discrepancies_found": len(discrepancies),
                "corrections_applied": len(corrections),
                "discrepancies": discrepancies,
                "corrections": corrections,
            }

            logger.info(
                f"Broker reconciliation complete: {reconciliation_result['status']}"
            )

            return reconciliation_result

        except Exception as e:
            logger.error(
                f"Exception during broker reconciliation: {str(e)}", exc_info=True
            )
            return {
                "status": "error",
                "reason": str(e),
            }

    def _abort_trade(self, trade_id: str) -> None:
        """Abort a partially created trade and clean up in-memory state."""
        if trade_id in self.trade_manager.open_trades:
            del self.trade_manager.open_trades[trade_id]
            logger.warning(f"Aborted trade pipeline and removed trade {trade_id}")

    def update_trades(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Update all open trades and check for exits."""
        if not self.trade_manager.open_trades:
            return []

        results = []

        current_price = data["close"].iloc[-1]
        atr = (
            calculate_atr(data, 14).iloc[-1]
            if "atr" not in data.columns
            else data["atr"].iloc[-1]
        )
        ema = calculate_ema(data["close"], 20).iloc[-1]

        for trade_id in list(self.trade_manager.open_trades.keys()):
            result = self.trade_manager.manage_trade(trade_id, current_price, atr, ema)

            if result["action"] != "NONE":
                results.append(result)

                # Register trade with risk engine
                if result["action"] in [
                    "STOP_LOSS",
                    "PARTIAL_TP",
                    "FULL_CLOSE",
                    "MANUAL_CLOSE",
                ]:
                    pnl = result.get("realized_pnl", 0)
                    exit_price = result.get("exit_price", current_price)

                    # Close position in risk engine
                    self.risk_engine.close_position(
                        symbol=self.strategy.name, exit_price=exit_price, pnl=pnl
                    )

                    # Log trade
                    trade = self.trade_manager.closed_trades[-1]
                    self.trade_logger.log_trade(
                        {
                            "id": trade.id,
                            "symbol": trade.symbol,
                            "direction": trade.direction,
                            "entry_price": trade.entry_price,
                            "exit_price": result.get("exit_price", 0),
                            "quantity": trade.quantity,
                            "stop_loss": trade.stop_loss,
                            "take_profit_1": trade.take_profit_1,
                            "take_profit_2": trade.take_profit_2,
                            "pnl": pnl,
                            "fees": 40,  # Default brokerage
                            "slippage": 0,
                            "entry_time": trade.entry_time.isoformat()
                            if hasattr(trade.entry_time, "isoformat")
                            else str(trade.entry_time),
                            "exit_time": datetime.now().isoformat(),
                            "exit_reason": result.get("action", ""),
                        }
                    )

                    # Log signal as executed
                    self.trade_logger.log_signal(
                        {
                            "symbol": trade.symbol,
                            "type": trade.direction,
                            "entry": trade.entry_price,
                            "stop_loss": trade.stop_loss,
                            "take_profit": [trade.take_profit_1, trade.take_profit_2],
                            "reason": trade.reason,
                            "executed": True,
                        }
                    )

                    # Check risk status after trade
                    risk_status = self.risk_engine.get_risk_status()
                    if not risk_status["trading_allowed"]:
                        logger.warning(
                            f"Risk limits breached after trade: daily_pnl={risk_status['daily_pnl']:.2f}"
                        )

        return results

    def run_cycle(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Run one complete trading cycle."""
        # Check market data staleness before executing trades
        mds = get_market_data_service()

        # Default timeframe for strategy (typically 5m)
        strategy_timeframe = getattr(self.strategy, "timeframe", "5m")

        # Check for key symbols in the data for staleness
        if hasattr(data.index, "names") and "symbol" in data.index.names:
            # Multi-index data with symbols
            symbols = data.index.get_level_values("symbol").unique()
            for symbol in symbols:
                if mds.is_data_stale(symbol, strategy_timeframe):
                    logger.warning(
                        f"⚠ Market data for {symbol} ({strategy_timeframe}) is STALE - "
                        f"skipping trading cycle to prevent losses on outdated prices"
                    )
                    return {
                        "timestamp": datetime.now(),
                        "signal": None,
                        "exits": [],
                        "open_positions": len(self.trade_manager.open_trades),
                        "performance": self.trade_manager.get_performance(),
                        "stale_data_warning": f"Data for {symbol} is stale - cycle skipped",
                        "cache_age": mds.get_cache_age(symbol, strategy_timeframe),
                    }

        cycle_result = {
            "timestamp": datetime.now(),
            "signal": None,
            "exits": [],
            "open_positions": len(self.trade_manager.open_trades),
            "performance": self.trade_manager.get_performance(),
        }

        if not self.trade_manager.open_trades:
            open_result = self.open_trade(data)
            if open_result:
                cycle_result["signal"] = open_result["signal"]
        else:
            exits = self.update_trades(data)
            if exits:
                cycle_result["exits"] = exits

        return cycle_result

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        risk_status = self.risk_engine.get_risk_status()

        return {
            "is_running": self.is_running,
            "capital": self.capital,
            "open_trades": self.trade_manager.get_open_trades(),
            "performance": self.trade_manager.get_performance(),
            "max_positions": self.max_open_positions,
            "risk": risk_status,
        }

    def start(self):
        """Start the trading system."""
        self.is_running = True
        logger.info("TradingSystem started")

    def stop(self):
        """Stop the trading system."""
        self.is_running = False
        logger.info("TradingSystem stopped")


class Backtester:
    """Backtest the trading system with full lifecycle simulation."""

    def __init__(
        self,
        initial_capital: float = 100000.0,
        risk_per_trade: float = 0.02,
        enable_trailing: bool = True,
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.enable_trailing = enable_trailing

    def run(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Run backtest on historical data."""
        system = TradingSystem(
            capital=self.initial_capital,
            risk_per_trade=self.risk_per_trade,
            enable_trailing=self.enable_trailing,
        )

        equity_curve = []
        trades_log = []

        for i in range(50, len(data)):
            current_data = data.iloc[: i + 1].copy()
            current_candle = current_data.iloc[-1]

            cycle = system.run_cycle(current_data)

            if cycle["signal"]:
                trades_log.append(
                    {
                        "time": current_candle.name,
                        "action": "OPEN",
                        "signal": cycle["signal"],
                    }
                )

            for exit_info in cycle["exits"]:
                trades_log.append(
                    {
                        "time": current_candle.name,
                        "action": exit_info["action"],
                        "trade_id": exit_info.get("trade_id"),
                        "pnl": exit_info.get("realized_pnl", 0),
                    }
                )

            equity = system.trade_manager.capital
            for trade in system.trade_manager.open_trades.values():
                direction = 1 if trade.direction == "BUY" else -1
                equity += (
                    (current_candle["close"] - trade.entry_price)
                    * direction
                    * trade.quantity
                )

            equity_curve.append(
                {
                    "time": current_candle.name,
                    "equity": equity,
                    "open_positions": cycle["open_positions"],
                }
            )

        performance = system.trade_manager.get_performance()

        equity_df = pd.DataFrame(equity_curve)
        max_drawdown = 0.0
        if len(equity_df) > 0:
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (
                (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"] * 100
            )
            max_drawdown = equity_df["drawdown"].min()

        return {
            "initial_capital": self.initial_capital,
            "final_capital": system.trade_manager.capital,
            "return_percent": round(
                (system.trade_manager.capital - self.initial_capital)
                / self.initial_capital
                * 100,
                2,
            ),
            "total_trades": performance["total_trades"],
            "winning_trades": performance["winning_trades"],
            "losing_trades": performance["losing_trades"],
            "win_rate": performance["win_rate"],
            "profit_factor": performance["profit_factor"],
            "max_drawdown": round(max_drawdown, 2),
            "total_pnl": performance["total_pnl"],
            "trades_log": trades_log,
            "equity_curve": equity_curve,
        }


def run_trading_system(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Main function to run the trading system.

    Usage:
        >>> results = run_trading_system(candles)
    """
    backtester = Backtester(
        initial_capital=100000, risk_per_trade=0.02, enable_trailing=True
    )

    results = backtester.run(data)

    return results

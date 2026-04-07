"""
Production Trading System - Main Execution Loop

Integrates:
- MasterStrategy for signal generation
- TradeManager for trade lifecycle

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from ..strategies.master_strategy import MasterStrategy
from ..core.trade_manager import TradeManager
from ..core.indicators import calculate_atr, calculate_ema
from ..core.safety_manager import SafetyManager
from ..core.order_validator import OrderValidator
from ..core.trade_logger import TradeLogger
from ..analytics.performance import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class TradingSystem:
    """
    Production Trading System.

    Integrates:
    - Signal generation (MasterStrategy)
    - Trade execution (TradeManager)
    - Real-time updates
    """

    def __init__(
        self,
        capital: float = 100000.0,
        risk_per_trade: float = 0.02,
        max_open_positions: int = 2,
        enable_trailing: bool = True,
        trailing_method: str = "ATR",
        daily_loss_limit_pct: float = 2.0,
        max_trades_per_day: int = 5,
        cooldown_minutes: int = 5,
        max_slippage_pct: float = 0.5,
    ):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_open_positions = max_open_positions

        self.strategy = MasterStrategy(capital=capital)
        self.trade_manager = TradeManager(
            capital=capital,
            risk_per_trade=risk_per_trade,
            max_open_positions=max_open_positions,
            enable_trailing=enable_trailing,
            trailing_method=trailing_method,
        )

        self.safety_manager = SafetyManager(
            capital=capital,
            daily_loss_limit_pct=daily_loss_limit_pct,
            max_trades_per_day=max_trades_per_day,
            cooldown_minutes=cooldown_minutes,
        )

        self.order_validator = OrderValidator(
            max_open_positions=max_open_positions,
            max_slippage_pct=max_slippage_pct,
        )

        self.trade_logger = TradeLogger()
        self.performance_analyzer = PerformanceAnalyzer()

        self.is_running = False
        self.last_candle_time = None

        logger.info(f"TradingSystem initialized: capital={capital}")

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
        """Open a new trade based on signal."""
        # Check safety manager first
        can_trade, reason = self.safety_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trade blocked by Safety Manager: {reason}")
            return None

        # Check day reset
        self.safety_manager.reset_daily()

        signal = self.generate_signal(data)

        if not signal:
            return None

        current_price = data["close"].iloc[-1]

        # Validate order before execution
        open_trades_list = self.trade_manager.get_open_trades()
        validation = self.order_validator.validate_order(
            symbol=self.strategy.name,
            direction=signal["type"],
            entry_price=signal["entry"],
            current_price=current_price,
            quantity=100,  # Default quantity
            capital=self.capital,
            open_trades=open_trades_list,
        )

        if not validation["valid"]:
            logger.warning(f"Order validation FAILED: {validation['reason']}")
            return None

        if len(self.trade_manager.open_trades) >= self.max_open_positions:
            logger.warning("Max positions reached")
            return None

        trade = self.trade_manager.open_trade(
            symbol=self.strategy.name,
            direction=signal["type"],
            entry_price=signal["entry"],
            stop_loss=signal["stop_loss"],
            take_profit_1=signal["take_profit"][0],
            take_profit_2=signal["take_profit"][1],
            confidence=signal.get("confidence", "medium"),
            reason=signal.get("reason", ""),
        )

        logger.info(f"Trade opened: {trade.id}")

        return {"trade_id": trade.id, "signal": signal}

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

                # Register trade with safety manager
                if result["action"] in [
                    "STOP_LOSS",
                    "PARTIAL_TP",
                    "FULL_CLOSE",
                    "MANUAL_CLOSE",
                ]:
                    pnl = result.get("realized_pnl", 0)
                    is_winning = pnl > 0
                    self.safety_manager.register_trade(pnl, is_winning)

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

                    # Check safety after trade
                    can_trade, reason = self.safety_manager.can_trade()
                    if not can_trade:
                        logger.warning(f"Safety check failed after trade: {reason}")

        return results

    def run_cycle(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Run one complete trading cycle."""
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
        can_trade, reason = self.safety_manager.can_trade()

        return {
            "is_running": self.is_running,
            "capital": self.capital,
            "open_trades": self.trade_manager.get_open_trades(),
            "performance": self.trade_manager.get_performance(),
            "max_positions": self.max_open_positions,
            "safety": self.safety_manager.get_status(),
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

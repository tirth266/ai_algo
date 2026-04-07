"""
Realistic Execution Module

Handles realistic market execution with:
- Slippage simulation
- Trading fees
- Spread adjustment
- Candle-based execution logic

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import logging
from typing import Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of realistic execution."""

    executed_price: float
    slippage_applied: float
    fees_deducted: float
    spread_applied: float
    adjusted: bool


class RealisticExecutor:
    """
    Simulates realistic market execution conditions.
    """

    def __init__(
        self,
        slippage_pct: float = 0.1,
        fee_pct: float = 0.1,
        spread_pct: float = 0.02,
        sl_priority: bool = True,
        log_adjustments: bool = True,
    ):
        self.slippage_pct = slippage_pct
        self.fee_pct = fee_pct
        self.spread_pct = spread_pct
        self.sl_priority = sl_priority
        self.log_adjustments = log_adjustments

        logger.info(
            f"RealisticExecutor initialized: "
            f"slippage={slippage_pct}%, fee={fee_pct}%, spread={spread_pct}%"
        )

    def calculate_entry_price(
        self,
        direction: str,
        signal_price: float,
        current_price: float,
        candle_open: float = None,
    ) -> Tuple[float, float]:
        """
        Calculate realistic entry price with slippage.

        Returns:
            Tuple of (adjusted_price, slippage_applied)
        """
        if direction == "BUY":
            # Buy at higher price (slippage up)
            adjusted = signal_price * (1 + self.slippage_pct / 100)
            slippage = adjusted - signal_price
        else:  # SELL
            # Sell at lower price (slippage down)
            adjusted = signal_price * (1 - self.slippage_pct / 100)
            slippage = signal_price - adjusted

        if self.log_adjustments:
            logger.info(
                f"Entry price adjusted: {signal_price} -> {adjusted} "
                f"({direction}, slippage={slippage:.2f})"
            )

        return adjusted, slippage

    def calculate_exit_price(
        self,
        direction: str,
        target_price: float,
        current_candle: Dict = None,
        sl_triggered: bool = False,
        tp_triggered: bool = False,
    ) -> Tuple[float, Dict]:
        """
        Calculate realistic exit price.

        Uses candle OHLC for realistic fills:
        - For TP: use High for BUY, Low for SELL
        - For SL: use Low for BUY, High for SELL

        If both hit in same candle, prioritize SL (conservative).
        """
        adjusted_price = target_price
        reason = "target"
        slippage = 0.0

        if current_candle and (sl_triggered or tp_triggered):
            high = current_candle.get("high", target_price)
            low = current_candle.get("low", target_price)

            if direction == "BUY":
                if sl_triggered and low <= target_price:
                    # SL hit - use low
                    adjusted_price = low
                    reason = "SL hit (low)"
                elif tp_triggered and high >= target_price:
                    # TP hit - use high
                    adjusted_price = high
                    reason = "TP hit (high)"
            else:  # SELL
                if sl_triggered and high >= target_price:
                    # SL hit - use high
                    adjusted_price = high
                    reason = "SL hit (high)"
                elif tp_triggered and low <= target_price:
                    # TP hit - use low
                    adjusted_price = low
                    reason = "TP hit (low)"

            if self.sl_priority and sl_triggered and tp_triggered:
                # Conservative: prioritize SL
                if direction == "BUY":
                    adjusted_price = low
                    reason = "Both hit - SL prioritized (low)"
                else:
                    adjusted_price = high
                    reason = "Both hit - SL prioritized (high)"

        # Apply slippage to exit
        if direction == "BUY":
            exit_with_slippage = adjusted_price * (1 - self.slippage_pct / 100)
        else:
            exit_with_slippage = adjusted_price * (1 + self.slippage_pct / 100)

        slippage = abs(exit_with_slippage - adjusted_price)
        adjusted_price = exit_with_slippage

        if self.log_adjustments:
            logger.info(
                f"Exit price adjusted: {target_price} -> {adjusted_price} "
                f"({reason}, slippage={slippage:.2f})"
            )

        return adjusted_price, {
            "reason": reason,
            "slippage": slippage,
            "adjusted_from": target_price,
        }

    def calculate_fees(self, price: float, quantity: int) -> float:
        """Calculate trading fees."""
        turnover = price * quantity
        fees = turnover * (self.fee_pct / 100)
        return fees

    def apply_spread(self, direction: str, price: float) -> float:
        """Apply bid-ask spread to price."""
        if direction == "BUY":
            # Buyer pays higher price (ask)
            return price * (1 + self.spread_pct / 100)
        else:  # SELL
            # Seller receives lower price (bid)
            return price * (1 - self.spread_pct / 100)

    def check_candle_execution(
        self,
        direction: str,
        entry_price: float,
        candle: Dict,
        sl_price: float,
        tp_price: float,
    ) -> Tuple[str, float]:
        """
        Check if entry/target hit within candle.

        Returns:
            Tuple of (action, executed_price)

        Actions:
        - "entry_filled" - Entry price reached
        - "sl_hit" - Stop loss hit
        - "tp_hit" - Take profit hit
        - "none" - No execution
        """
        high = candle.get("high", 0)
        low = candle.get("low", 0)

        if direction == "BUY":
            # Check entry
            if entry_price >= low and entry_price <= high:
                return "entry_filled", entry_price

            # Check SL
            if sl_price >= low and sl_price <= high:
                return "sl_hit", sl_price

            # Check TP
            if tp_price >= low and tp_price <= high:
                return "tp_hit", tp_price
        else:  # SELL
            # Check entry
            if entry_price >= low and entry_price <= high:
                return "entry_filled", entry_price

            # Check SL
            if sl_price >= low and sl_price <= high:
                return "sl_hit", sl_price

            # Check TP
            if tp_price >= low and tp_price <= high:
                return "tp_hit", tp_price

        return "none", 0.0

    def simulate_full_trade(
        self,
        direction: str,
        entry_price: float,
        exit_price: float,
        quantity: int,
        current_candle: Dict = None,
        sl_price: float = None,
        tp_price: float = None,
    ) -> Dict:
        """
        Simulate full trade with realistic execution.

        Returns detailed breakdown of execution.
        """
        # Apply entry adjustments
        adjusted_entry, entry_slip = self.calculate_entry_price(
            direction,
            entry_price,
            current_candle.get("close", entry_price) if current_candle else entry_price,
        )

        # Apply spread to entry
        adjusted_entry = self.apply_spread(direction, adjusted_entry)

        # Calculate fees
        entry_fees = self.calculate_fees(adjusted_entry, quantity)

        # Exit calculations
        exit_reason = "manual"
        exit_adjustment = {}

        if current_candle and sl_price and tp_price:
            exit_price_sim, exit_adjustment = self.calculate_exit_price(
                direction,
                exit_price,
                current_candle,
                sl_triggered=True,
                tp_triggered=True,
            )

            if exit_adjustment["reason"] != "target":
                adjusted_entry = exit_price_sim
                exit_reason = exit_adjustment["reason"]

        # Apply spread to exit
        adjusted_exit = self.apply_spread(
            direction, adjusted_entry if exit_reason != "target" else exit_price
        )

        # Calculate exit fees
        exit_fees = self.calculate_fees(adjusted_exit, quantity)

        # Total fees
        total_fees = entry_fees + exit_fees

        # Calculate PnL
        if direction == "BUY":
            pnl = (adjusted_exit - adjusted_entry) * quantity - total_fees
        else:
            pnl = (adjusted_entry - adjusted_exit) * quantity - total_fees

        return {
            "direction": direction,
            "original_entry": entry_price,
            "adjusted_entry": adjusted_entry,
            "entry_slippage": entry_slip,
            "original_exit": exit_price,
            "adjusted_exit": adjusted_exit,
            "exit_reason": exit_reason,
            "quantity": quantity,
            "entry_fees": entry_fees,
            "exit_fees": exit_fees,
            "total_fees": total_fees,
            "pnl_before_fees": pnl + total_fees,
            "pnl_after_fees": pnl,
        }

    def get_config(self) -> Dict:
        """Get executor configuration."""
        return {
            "slippage_pct": self.slippage_pct,
            "fee_pct": self.fee_pct,
            "spread_pct": self.spread_pct,
            "sl_priority": self.sl_priority,
            "log_adjustments": self.log_adjustments,
        }

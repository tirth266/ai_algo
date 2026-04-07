"""
Advanced Position Manager Module

Features:
- Partial take profit (TP1=1:1 50%, TP2=1:2 remaining)
- Trailing stop loss (breakeven at TP1, ATR/EMA trailing)
- Dynamic position sizing
- Risk management (1-2% per trade)
- Position tracking and updates

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeLevel:
    """Represents a take profit or stop loss level."""

    price: float
    quantity_pct: float
    is_active: bool = True
    executed_at: Optional[datetime] = None


@dataclass
class Position:
    """Represents an advanced trading position."""

    id: str
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit_levels: List[TradeLevel] = field(default_factory=list)

    # Trailing settings
    trailing_enabled: bool = True
    trailing_atr_multiplier: float = 1.5
    trailing_ema_period: int = 20

    # State
    current_stop_loss: float = 0.0
    is_closed: bool = False
    partial_exits: List[Dict[str, Any]] = field(default_factory=list)

    # Risk
    risk_per_trade: float = 0.02  # 2%
    capital: float = 100000.0

    def __post_init__(self):
        if self.current_stop_loss == 0.0:
            self.current_stop_loss = self.stop_loss

    @property
    def risk_amount(self) -> float:
        """Calculate risk amount in currency."""
        return abs(self.entry_price - self.stop_loss) * self.quantity

    @property
    def risk_percentage(self) -> float:
        """Calculate risk as percentage of capital."""
        return self.risk_amount / self.capital * 100

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL."""
        if self.direction == "BUY":
            return (
                self.entry_price - self.entry_price
            ) * self.quantity  # Placeholder, use current price
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "current_stop_loss": self.current_stop_loss,
            "take_profit_levels": [
                {
                    "price": tp.price,
                    "quantity_pct": tp.quantity_pct,
                    "is_active": tp.is_active,
                }
                for tp in self.take_profit_levels
            ],
            "partial_exits": self.partial_exits,
            "is_closed": self.is_closed,
            "trailing_enabled": self.trailing_enabled,
            "risk_amount": self.risk_amount,
            "risk_percentage": self.risk_percentage,
        }


class PositionManager:
    """
    Advanced Position Manager.

    Features:
    - Partial take profit execution
    - Trailing stop loss
    - Dynamic position sizing
    - Risk management
    """

    def __init__(
        self,
        capital: float = 100000.0,
        risk_per_trade: float = 0.02,
        tp1_ratio: float = 1.0,
        tp1_close_pct: float = 0.50,
        tp2_ratio: float = 2.0,
        enable_trailing: bool = True,
        trailing_method: str = "ATR",  # "ATR" or "EMA"
        atr_period: int = 14,
        ema_period: int = 20,
        breakeven_at_tp1: bool = True,
    ):
        """
        Initialize Position Manager.

        Args:
            capital: Trading capital
            risk_per_trade: Risk per trade as decimal (0.02 = 2%)
            tp1_ratio: First take profit ratio (1.0 = 1:1)
            tp1_close_pct: Percentage to close at TP1 (0.50 = 50%)
            tp2_ratio: Second take profit ratio (2.0 = 1:2)
            enable_trailing: Enable trailing stop
            trailing_method: Trailing method ("ATR" or "EMA")
            atr_period: ATR period for trailing
            ema_period: EMA period for trailing
            breakeven_at_tp1: Move SL to breakeven at TP1
        """
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.tp1_ratio = tp1_ratio
        self.tp1_close_pct = tp1_close_pct
        self.tp2_ratio = tp2_ratio
        self.enable_trailing = enable_trailing
        self.trailing_method = trailing_method
        self.atr_period = atr_period
        self.ema_period = ema_period
        self.breakeven_at_tp1 = breakeven_at_tp1

        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict[str, Any]] = []

        logger.info(
            f"PositionManager initialized: capital={capital}, risk={risk_per_trade * 100}%, "
            f"TP1={tp1_ratio}R({tp1_close_pct * 100}%), TP2={tp2_ratio}R"
        )

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        prefered_risk: Optional[float] = None,
    ) -> int:
        """
        Calculate dynamic position size based on risk.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            prefered_risk: Optional override risk percentage

        Returns:
            Position quantity
        """
        risk = prefered_risk or self.risk_per_trade
        risk_amount = self.capital * risk

        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0

        quantity = int(risk_amount / risk_per_share)
        return max(1, quantity)

    def calculate_stop_loss(
        self, entry_price: float, atr_value: float, atr_multiplier: float = 1.5
    ) -> float:
        """Calculate ATR-based stop loss."""
        if entry_price > 0:
            if self.direction == "BUY":
                return entry_price - (atr_multiplier * atr_value)
            else:
                return entry_price + (atr_multiplier * atr_value)
        return 0.0

    def calculate_take_profit_levels(
        self, entry_price: float, stop_loss: float, quantity: int
    ) -> List[TradeLevel]:
        """Calculate take profit levels with partial exits."""
        risk = abs(entry_price - stop_loss)

        tp1_price = (
            entry_price + (risk * self.tp1_ratio)
            if self.direction == "BUY"
            else entry_price - (risk * self.tp1_ratio)
        )
        tp2_price = (
            entry_price + (risk * self.tp2_ratio)
            if self.direction == "BUY"
            else entry_price - (risk * self.tp2_ratio)
        )

        return [
            TradeLevel(price=tp1_price, quantity_pct=self.tp1_close_pct),
            TradeLevel(price=tp2_price, quantity_pct=1.0 - self.tp1_close_pct),
        ]

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        atr_value: float = 0.0,
        ema_value: float = 0.0,
        quantity: Optional[int] = None,
    ) -> Position:
        """
        Open a new position with advanced management.

        Args:
            symbol: Trading symbol
            direction: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price
            atr_value: ATR value for trailing
            ema_value: EMA value for trailing
            quantity: Optional fixed quantity

        Returns:
            Position object
        """
        if quantity is None:
            quantity = self.calculate_position_size(entry_price, stop_loss)

        position_id = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        tp_levels = self.calculate_take_profit_levels(entry_price, stop_loss, quantity)

        position = Position(
            id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit_levels=tp_levels,
            trailing_enabled=self.enable_trailing,
            capital=self.capital,
            risk_per_trade=self.risk_per_trade,
        )

        if self.enable_trailing and atr_value > 0:
            position.trailing_atr_multiplier = atr_value
        if self.enable_trailing and ema_value > 0:
            position.trailing_ema_period = self.ema_period

        self.positions[position_id] = position

        logger.info(
            f"Position opened: {position_id} {direction} {quantity} @ {entry_price}, "
            f"SL={stop_loss}, TP1={tp_levels[0].price}, TP2={tp_levels[1].price}"
        )

        return position

    def update_position(
        self,
        position_id: str,
        current_price: float,
        atr_value: float = 0.0,
        ema_value: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Update position and check for exits.

        Args:
            position_id: Position ID
            current_price: Current market price
            atr_value: ATR value
            ema_value: EMA value

        Returns:
            Dict with exit actions {'action': 'NONE'|'PARTIAL_TP'|'FULL_CLOSE'|'STOP_LOSS', ...}
        """
        if position_id not in self.positions:
            return {"action": "NONE"}

        position = self.positions[position_id]

        if position.is_closed:
            return {"action": "NONE"}

        result = {"action": "NONE", "position_id": position_id}

        direction = 1 if position.direction == "BUY" else -1
        pnl = (current_price - position.entry_price) * direction * position.quantity

        for tp_level in position.take_profit_levels:
            if not tp_level.is_active:
                continue

            tp_hit = False
            if position.direction == "BUY" and current_price >= tp_level.price:
                tp_hit = True
            elif position.direction == "SELL" and current_price <= tp_level.price:
                tp_hit = True

            if tp_hit:
                close_qty = int(position.quantity * tp_level.quantity_pct)

                exit_price = current_price
                realized_pnl = (
                    (exit_price - position.entry_price) * direction * close_qty
                )

                position.partial_exits.append(
                    {
                        "level": tp_level.price,
                        "quantity": close_qty,
                        "price": exit_price,
                        "pnl": realized_pnl,
                        "at": datetime.now().isoformat(),
                    }
                )

                tp_level.is_active = False

                result["action"] = "PARTIAL_TP"
                result["exit_quantity"] = close_qty
                result["exit_price"] = exit_price
                result["realized_pnl"] = realized_pnl
                result["remaining_quantity"] = position.quantity - close_qty

                if self.breakeven_at_tp1:
                    position.current_stop_loss = position.entry_price
                    result["new_stop_loss"] = position.entry_price

                logger.info(
                    f"TP hit: {position_id} - closed {close_qty} @ {exit_price}, PnL: {realized_pnl}"
                )

                position.quantity -= close_qty

                if position.quantity <= 0:
                    position.is_closed = True
                    self.closed_positions.append(position.to_dict())
                    del self.positions[position_id]
                    result["action"] = "FULL_CLOSE"

                break

        if not position.is_closed and position.trailing_enabled:
            new_sl = position.current_stop_loss

            if self.trailing_method == "ATR" and atr_value > 0:
                if position.direction == "BUY":
                    new_sl = current_price - (
                        position.trailing_atr_multiplier * atr_value
                    )
                    if new_sl > position.current_stop_loss:
                        position.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl
                else:
                    new_sl = current_price + (
                        position.trailing_atr_multiplier * atr_value
                    )
                    if new_sl < position.current_stop_loss:
                        position.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl

            elif self.trailing_method == "EMA" and ema_value > 0:
                if position.direction == "BUY":
                    new_sl = ema_value
                    if new_sl > position.current_stop_loss:
                        position.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl
                else:
                    new_sl = ema_value
                    if new_sl < position.current_stop_loss:
                        position.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl

        if not position.is_closed:
            sl_triggered = False
            if (
                position.direction == "BUY"
                and current_price <= position.current_stop_loss
            ):
                sl_triggered = True
            elif (
                position.direction == "SELL"
                and current_price >= position.current_stop_loss
            ):
                sl_triggered = True

            if sl_triggered:
                exit_price = current_price
                realized_pnl = (
                    (exit_price - position.entry_price) * direction * position.quantity
                )

                position.partial_exits.append(
                    {
                        "level": position.current_stop_loss,
                        "quantity": position.quantity,
                        "price": exit_price,
                        "pnl": realized_pnl,
                        "at": datetime.now().isoformat(),
                        "reason": "STOP_LOSS",
                    }
                )

                result["action"] = "STOP_LOSS"
                result["exit_quantity"] = position.quantity
                result["exit_price"] = exit_price
                result["realized_pnl"] = realized_pnl

                position.is_closed = True
                self.closed_positions.append(position.to_dict())
                del self.positions[position_id]

                logger.info(
                    f"SL hit: {position_id} - closed @ {exit_price}, PnL: {realized_pnl}"
                )

        return result

    def close_position(self, position_id: str, current_price: float) -> Dict[str, Any]:
        """Manually close a position."""
        if position_id not in self.positions:
            return {"action": "NONE", "error": "Position not found"}

        position = self.positions[position_id]

        direction = 1 if position.direction == "BUY" else -1
        exit_price = current_price
        realized_pnl = (
            (exit_price - position.entry_price) * direction * position.quantity
        )

        position.partial_exits.append(
            {
                "level": current_price,
                "quantity": position.quantity,
                "price": exit_price,
                "pnl": realized_pnl,
                "at": datetime.now().isoformat(),
                "reason": "MANUAL",
            }
        )

        result = {
            "action": "MANUAL_CLOSE",
            "position_id": position_id,
            "exit_quantity": position.quantity,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
        }

        position.is_closed = True
        self.closed_positions.append(position.to_dict())
        del self.positions[position_id]

        logger.info(
            f"Position closed manually: {position_id} @ {exit_price}, PnL: {realized_pnl}"
        )

        return result

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return [pos.to_dict() for pos in self.positions.values()]

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics."""
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
            }

        all_pnl = []
        for pos in self.closed_positions:
            for exit_info in pos.get("partial_exits", []):
                all_pnl.append(exit_info.get("pnl", 0))

        if not all_pnl:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
            }

        wins = [p for p in all_pnl if p > 0]
        losses = [p for p in all_pnl if p < 0]

        total_trades = len(all_pnl)
        winning_trades = len(wins)
        losing_trades = len(losses)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(sum(all_pnl), 2),
            "avg_win": round(sum(wins) / winning_trades, 2)
            if winning_trades > 0
            else 0,
            "avg_loss": round(sum(losses) / losing_trades, 2)
            if losing_trades > 0
            else 0,
            "profit_factor": round(profit_factor, 2),
        }


def create_managed_signal(
    candles: pd.DataFrame,
    direction: str,
    entry_price: float,
    stop_loss: float,
    capital: float = 100000.0,
    risk_per_trade: float = 0.02,
    tp1_ratio: float = 1.0,
    tp2_ratio: float = 2.0,
    enable_trailing: bool = True,
) -> Dict[str, Any]:
    """
    Create a managed signal with position management.

    Returns signal dict with:
    - entry: Entry price
    - stop_loss: SL price
    - take_profit: [tp1, tp2] levels
    - position_size: Dynamic quantity
    - management: {partial_exit, trailing_stop} flags
    """
    pm = PositionManager(
        capital=capital,
        risk_per_trade=risk_per_trade,
        tp1_ratio=tp1_ratio,
        tp2_ratio=tp2_ratio,
        enable_trailing=enable_trailing,
    )

    quantity = pm.calculate_position_size(entry_price, stop_loss)
    risk_amount = abs(entry_price - stop_loss) * quantity
    risk_pct = risk_amount / capital * 100

    risk = abs(entry_price - stop_loss)
    tp1_price = (
        entry_price + (risk * tp1_ratio)
        if direction == "BUY"
        else entry_price - (risk * tp1_ratio)
    )
    tp2_price = (
        entry_price + (risk * tp2_ratio)
        if direction == "BUY"
        else entry_price - (risk * tp2_ratio)
    )
    tp_levels = [
        TradeLevel(price=tp1_price, quantity_pct=0.50),
        TradeLevel(price=tp2_price, quantity_pct=0.50),
    ]

    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "take_profit": [tp_levels[0].price, tp_levels[1].price],
        "position_size": quantity,
        "risk_amount": round(risk_amount, 2),
        "risk_percentage": round(risk_pct, 2),
        "management": {
            "partial_exit": True,
            "partial_exit_tp1": tp1_ratio,
            "partial_exit_tp2": tp2_ratio,
            "trailing_stop": enable_trailing,
            "breakeven_at_tp1": True,
        },
    }

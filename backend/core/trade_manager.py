"""
Trade Lifecycle Manager Module

Manages trade lifecycle including:
- Trade execution
- Partial exits (TP1, TP2)
- Trailing stop loss
- Break-even protection
- Risk management

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from core.realistic_execution import RealisticExecutor
from config.execution_config import get_execution_config
from core.position_persistence import PositionPersistence
from utils.alert_manager import get_alert_manager

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"


class TradeDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExitReason(Enum):
    TAKE_PROFIT_1 = "TP1"
    TAKE_PROFIT_2 = "TP2"
    STOP_LOSS = "STOP_LOSS"
    MANUAL = "MANUAL"
    TIME_BASED = "TIME_BASED"


@dataclass
class Trade:
    """Represents a single trade."""

    id: str
    symbol: str
    direction: str
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit_1: float
    take_profit_2: float

    current_stop_loss: float = 0.0
    status: str = "OPEN"
    entry_time: datetime = field(default_factory=datetime.now)
    exit_time: Optional[datetime] = None

    partial_exits: List[Dict] = field(default_factory=list)
    realized_pnl: float = 0.0

    confidence: str = "low"
    reason: str = ""

    def __post_init__(self):
        if self.current_stop_loss == 0.0:
            self.current_stop_loss = self.stop_loss

    @property
    def is_open(self) -> bool:
        return self.status in [TradeStatus.OPEN.value, TradeStatus.PARTIAL.value]

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def risk_amount(self) -> float:
        return self.risk_per_share * self.quantity


class TradeManager:
    """
    Manages trade lifecycle.

    Features:
    - Partial take profit (50% at 1:1, 50% at 1:2)
    - Trailing stop loss (ATR or EMA based)
    - Break-even after TP1 hit
    - Max position control
    """

    def __init__(
        self,
        capital: float = 100000.0,
        risk_per_trade: float = 0.02,
        max_open_positions: int = 2,
        tp1_ratio: float = 1.0,
        tp1_close_pct: float = 0.50,
        tp2_ratio: float = 2.0,
        enable_trailing: bool = True,
        trailing_method: str = "ATR",
        atr_period: int = 14,
        ema_period: int = 20,
        atr_multiplier: float = 1.5,
        breakeven_at_tp1: bool = True,
    ):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_open_positions = max_open_positions

        self.tp1_ratio = tp1_ratio
        self.tp1_close_pct = tp1_close_pct
        self.tp2_ratio = tp2_ratio

        self.enable_trailing = enable_trailing
        self.trailing_method = trailing_method
        self.atr_period = atr_period
        self.ema_period = ema_period
        self.atr_multiplier = atr_multiplier
        self.breakeven_at_tp1 = breakeven_at_tp1

        # Load execution config
        exec_config = get_execution_config()
        self.executor = RealisticExecutor(
            slippage_pct=exec_config.slippage_pct,
            fee_pct=exec_config.fee_pct,
            spread_pct=exec_config.spread_pct,
            sl_priority=exec_config.sl_priority,
            log_adjustments=exec_config.log_adjustments,
        )

        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        
        # Initialize persistence layer
        self.persistence = PositionPersistence()

        logger.info(
            f"TradeManager initialized: capital={capital}, "
            f"risk={risk_per_trade * 100}%, max_positions={max_open_positions}"
        )

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> int:
        """Calculate position size based on risk."""
        risk = self.capital * self.risk_per_trade
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return 0

        quantity = int(risk / risk_per_share)
        return max(1, quantity)

    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        quantity: Optional[int] = None,
        confidence: str = "medium",
        reason: str = "",
        persist: bool = True,
    ) -> Optional[Trade]:
        """
        Open a new trade with duplicate prevention.
        
        Args:
            symbol: Stock symbol
            direction: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss level
            take_profit_1: First target
            take_profit_2: Second target
            quantity: Position size
            confidence: Signal confidence
            reason: Signal reason
            
        Returns:
            Trade object if opened, None if duplicate detected
        """
        # DUPLICATE CHECK: Query database (source of truth)
        is_duplicate, reason_msg = self.persistence.check_for_duplicates(symbol)
        
        if is_duplicate:
            alert_message = (
                "Trade rejected\n"
                f"Symbol: {symbol}\n"
                f"Reason: Duplicate detected\n"
                f"Details: {reason_msg}"
            )
            get_alert_manager().send(alert_message, level='WARNING')
            logger.error(
                f"TRADE REJECTED [{symbol}] — DUPLICATE DETECTED: {reason_msg} | "
                f"Signal: {direction} @ {entry_price}"
            )
            return None
        
        if quantity is None:
            quantity = self.calculate_position_size(entry_price, stop_loss)

        if len(self.open_trades) >= self.max_open_positions:
            logger.warning(f"Max positions reached: {self.max_open_positions}")

        trade_id = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        trade = Trade(
            id=trade_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            current_stop_loss=stop_loss,
            confidence=confidence,
            reason=reason,
        )

        self.open_trades[trade_id] = trade

        if persist:
            try:
                self.persistence.save_trade(
                    symbol=symbol,
                    side=direction,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit_2,
                    status="open",
                    strategy_name=reason or "signal_based",
                    entry_time=trade.entry_time,
                )
            except Exception as e:
                logger.error(f"Failed to persist trade: {str(e)}")

        logger.info(
            f"Trade opened: {trade_id} {direction} {quantity} @ {entry_price}, "
            f"SL={stop_loss}, TP1={take_profit_1}, TP2={take_profit_2}"
        )

        alert_message = (
            "Trade executed\n"
            f"Symbol: {symbol}\n"
            f"Action: {direction}\n"
            f"Quantity: {quantity}\n"
            f"Price: {entry_price:.2f}\n"
            f"Reason: {reason or 'signal_based'}"
        )
        get_alert_manager().send(alert_message, level='INFO')

        return trade

    def manage_trade(
        self,
        trade_id: str,
        current_price: float,
        atr_value: float = 0.0,
        ema_value: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Manage trade and check for exits.

        Returns:
            Dict with exit actions
        """
        if trade_id not in self.open_trades:
            return {"action": "NONE"}

        trade = self.open_trades[trade_id]

        if not trade.is_open:
            return {"action": "NONE"}

        result = {
            "action": "NONE",
            "trade_id": trade_id,
            "current_price": current_price,
            "unrealized_pnl": 0.0,
        }

        direction = 1 if trade.direction == "BUY" else -1
        pnl = (current_price - trade.entry_price) * direction * trade.quantity
        result["unrealized_pnl"] = pnl

        tp1_hit = False
        tp2_hit = False

        if trade.direction == "BUY":
            if current_price >= trade.take_profit_1:
                tp1_hit = True
            if current_price >= trade.take_profit_2:
                tp2_hit = True
        else:
            if current_price <= trade.take_profit_1:
                tp1_hit = True
            if current_price <= trade.take_profit_2:
                tp2_hit = True

        if tp1_hit or tp2_hit:
            close_pct = (
                self.tp1_close_pct
                if not any(e["tp_level"] == 1 for e in trade.partial_exits)
                else (1 - self.tp1_close_pct)
            )
            close_qty = int(trade.quantity * close_pct)

            exit_price = current_price
            realized_pnl = (exit_price - trade.entry_price) * direction * close_qty

            tp_level = (
                1 if not any(e["tp_level"] == 1 for e in trade.partial_exits) else 2
            )

            trade.partial_exits.append(
                {
                    "tp_level": tp_level,
                    "price": exit_price,
                    "quantity": close_qty,
                    "pnl": realized_pnl,
                    "at": datetime.now(),
                }
            )

            trade.realized_pnl += realized_pnl
            trade.quantity -= close_qty

            if tp_level == 1 and self.breakeven_at_tp1:
                trade.current_stop_loss = trade.entry_price
                result["new_stop_loss"] = trade.entry_price

            result["action"] = "PARTIAL_TP"
            result["exit_quantity"] = close_qty
            result["exit_price"] = exit_price
            result["realized_pnl"] = realized_pnl
            result["remaining_quantity"] = trade.quantity

            logger.info(f"TP hit: {trade_id} - closed {close_qty} @ {exit_price}")

            if trade.quantity <= 0:
                trade.status = TradeStatus.CLOSED.value
                trade.exit_time = datetime.now()
                self.closed_trades.append(trade)
                del self.open_trades[trade_id]
                result["action"] = "FULL_CLOSE"
                
                # Persist trade closure to database
                try:
                    self.persistence.save_trade(
                        symbol=trade.symbol,
                        side=trade.direction,
                        quantity=trade.quantity,
                        entry_price=trade.entry_price,
                        exit_price=current_price,
                        stop_loss=trade.stop_loss,
                        take_profit=trade.take_profit_2,
                        status="closed",
                        exit_reason="TAKE_PROFIT",
                        strategy_name=trade.reason or "signal_based",
                        entry_time=trade.entry_time,
                        exit_time=trade.exit_time,
                        pnl=trade.realized_pnl,
                    )
                except Exception as e:
                    logger.error(f"Failed to persist trade closure: {str(e)}")

            return result

        if self.enable_trailing:
            new_sl = trade.current_stop_loss

            if self.trailing_method == "ATR" and atr_value > 0:
                if trade.direction == "BUY":
                    new_sl = current_price - (self.atr_multiplier * atr_value)
                    if new_sl > trade.current_stop_loss:
                        trade.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl
                else:
                    new_sl = current_price + (self.atr_multiplier * atr_value)
                    if new_sl < trade.current_stop_loss:
                        trade.current_stop_loss = new_sl
                        result["new_stop_loss"] = new_sl

            elif self.trailing_method == "EMA" and ema_value > 0:
                if trade.direction == "BUY":
                    if ema_value > trade.current_stop_loss:
                        trade.current_stop_loss = ema_value
                        result["new_stop_loss"] = ema_value
                else:
                    if ema_value < trade.current_stop_loss:
                        trade.current_stop_loss = ema_value
                        result["new_stop_loss"] = ema_value

        sl_triggered = False
        if trade.direction == "BUY" and current_price <= trade.current_stop_loss:
            sl_triggered = True
        elif trade.direction == "SELL" and current_price >= trade.current_stop_loss:
            sl_triggered = True

        if sl_triggered:
            exit_price = current_price
            realized_pnl = (exit_price - trade.entry_price) * direction * trade.quantity

            trade.partial_exits.append(
                {
                    "tp_level": 0,
                    "price": exit_price,
                    "quantity": trade.quantity,
                    "pnl": realized_pnl,
                    "reason": ExitReason.STOP_LOSS.value,
                    "at": datetime.now(),
                }
            )

            trade.realized_pnl = realized_pnl
            trade.status = TradeStatus.CLOSED.value
            trade.exit_time = datetime.now()

            result["action"] = "STOP_LOSS"
            result["exit_quantity"] = trade.quantity
            result["exit_price"] = exit_price
            result["realized_pnl"] = realized_pnl

            self.closed_trades.append(trade)
            del self.open_trades[trade_id]
            
            # Persist trade closure to database
            try:
                self.persistence.save_trade(
                    symbol=trade.symbol,
                    side=trade.direction,
                    quantity=trade.quantity,
                    entry_price=trade.entry_price,
                    exit_price=exit_price,
                    stop_loss=trade.stop_loss,
                    take_profit=trade.take_profit_2,
                    status="closed",
                    exit_reason="STOP_LOSS",
                    strategy_name=trade.reason or "signal_based",
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    pnl=trade.realized_pnl,
                )
            except Exception as e:
                logger.error(f"Failed to persist stop loss closure: {str(e)}")

            logger.info(f"SL hit: {trade_id} @ {exit_price}, PnL: {realized_pnl}")

        return result

    def close_trade(self, trade_id: str, current_price: float) -> Dict[str, Any]:
        """Manually close a trade."""
        if trade_id not in self.open_trades:
            return {"action": "NONE", "error": "Trade not found"}

        trade = self.open_trades[trade_id]

        direction = 1 if trade.direction == "BUY" else -1
        exit_price = current_price
        realized_pnl = (exit_price - trade.entry_price) * direction * trade.quantity

        trade.realized_pnl = realized_pnl
        trade.status = TradeStatus.CLOSED.value
        trade.exit_time = datetime.now()

        trade.partial_exits.append(
            {
                "tp_level": 0,
                "price": exit_price,
                "quantity": trade.quantity,
                "pnl": realized_pnl,
                "reason": ExitReason.MANUAL.value,
                "at": datetime.now(),
            }
        )

        result = {
            "action": "MANUAL_CLOSE",
            "trade_id": trade_id,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
        }

        self.closed_trades.append(trade)
        del self.open_trades[trade_id]
        
        # Persist manual trade closure to database
        try:
            self.persistence.save_trade(
                symbol=trade.symbol,
                side=trade.direction,
                quantity=trade.quantity,
                entry_price=trade.entry_price,
                exit_price=exit_price,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit_2,
                status="closed",
                exit_reason="MANUAL",
                strategy_name=trade.reason or "signal_based",
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                pnl=trade.realized_pnl,
            )
        except Exception as e:
            logger.error(f"Failed to persist manual closure: {str(e)}")

        logger.info(
            f"Trade closed manually: {trade_id} @ {exit_price}, PnL: {realized_pnl}"
        )

        return result

    def load_trades_from_database(self) -> int:
        """
        Load open trades from database on startup.
        
        Restores in-memory state from persisted trades to prevent data loss on restart.
        
        Returns:
            Number of trades loaded
        """
        try:
            loaded_trades = self.persistence.load_open_trades()
            count = 0
            
            for trade_data in loaded_trades:
                trade_id = trade_data['id']
                
                # Recreate Trade object from persisted data
                trade = Trade(
                    id=trade_id,
                    symbol=trade_data['symbol'],
                    direction=trade_data['direction'],
                    entry_price=trade_data['entry_price'],
                    quantity=trade_data['quantity'],
                    stop_loss=trade_data['stop_loss'],
                    take_profit_1=trade_data.get('take_profit_1', 0),
                    take_profit_2=trade_data.get('take_profit_2', 0),
                    current_stop_loss=trade_data['stop_loss'],
                    status='OPEN',
                    entry_time=trade_data.get('entry_time', datetime.now()),
                )
                
                self.open_trades[trade_id] = trade
                count += 1
                
            logger.info(f"Loaded {count} trades from database")
            return count
            
        except Exception as e:
            logger.error(f"Failed to load trades from database: {str(e)}")
            return 0

    def get_open_trades(self) -> List[Dict]:
        """Get all open trades."""
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "quantity": t.quantity,
                "stop_loss": t.stop_loss,
                "current_stop_loss": t.current_stop_loss,
                "take_profit_1": t.take_profit_1,
                "take_profit_2": t.take_profit_2,
                "status": t.status,
                "confidence": t.confidence,
                "reason": t.reason,
            }
            for t in self.open_trades.values()
        ]

    def get_performance(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
            }

        all_pnl = [t.realized_pnl for t in self.closed_trades]

        wins = [p for p in all_pnl if p > 0]
        losses = [p for p in all_pnl if p < 0]

        total = len(all_pnl)
        winning = len(wins)
        losing = len(losses)

        win_rate = (winning / total * 100) if total > 0 else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return {
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(sum(all_pnl), 2),
            "avg_win": round(sum(wins) / winning, 2) if winning > 0 else 0,
            "avg_loss": round(sum(losses) / losing, 2) if losing > 0 else 0,
            "profit_factor": round(profit_factor, 2),
        }

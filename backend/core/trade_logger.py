"""
Trade Logger Module

Logs every executed trade to CSV with complete trade details.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import csv
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from threading import Lock

logger = logging.getLogger(__name__)


class TradeLogger:
    """
    Logs executed trades to CSV with complete details.

    Fields:
        - trade_id: Unique identifier
        - symbol: Trading symbol
        - direction: BUY or SELL
        - entry_price: Entry price
        - exit_price: Exit price
        - quantity: Number of shares
        - stop_loss: Stop loss price
        - take_profit: Take profit price
        - pnl: Profit/Loss
        - fees: Total fees paid
        - slippage: Slippage cost
        - entry_time: Entry timestamp
        - exit_time: Exit timestamp
        - result: WIN or LOSS
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, log_dir: str = "logs/trades"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "logs/trades"):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.trade_log_file = self.log_dir / "trades.csv"
        self._init_trade_file()

        self._initialized = True
        logger.info(f"TradeLogger initialized: {self.trade_log_file}")

    def _init_trade_file(self):
        """Initialize trade log CSV with headers."""
        if not self.trade_log_file.exists():
            with open(self.trade_log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "trade_id",
                        "symbol",
                        "direction",
                        "entry_price",
                        "exit_price",
                        "quantity",
                        "stop_loss",
                        "take_profit",
                        "pnl",
                        "fees",
                        "slippage",
                        "entry_time",
                        "exit_time",
                        "result",
                        "strategy",
                        "duration_minutes",
                    ]
                )

    def log_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: Optional[float],
        quantity: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        fees: float = 0.0,
        slippage: float = 0.0,
        entry_time: Optional[datetime] = None,
        exit_time: Optional[datetime] = None,
        strategy: str = "UNKNOWN",
    ) -> str:
        """
        Log a completed trade.

        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            entry_price: Entry price
            exit_price: Exit price (None if still open)
            quantity: Number of shares
            stop_loss: Stop loss price
            take_profit: Take profit price
            fees: Total fees
            slippage: Slippage cost
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            strategy: Strategy name

        Returns:
            trade_id: Unique trade identifier
        """
        trade_id = str(uuid.uuid4())[:8]

        if entry_time is None:
            entry_time = datetime.now()
        if exit_time is None:
            exit_time = datetime.now()

        pnl = self._calculate_pnl(direction, entry_price, exit_price, quantity)
        result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"

        duration_minutes = (
            int((exit_time - entry_time).total_seconds() / 60)
            if exit_time and entry_time
            else 0
        )

        try:
            with open(self.trade_log_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        trade_id,
                        symbol,
                        direction,
                        entry_price,
                        exit_price,
                        quantity,
                        stop_loss,
                        take_profit,
                        round(pnl, 2),
                        fees,
                        slippage,
                        entry_time.isoformat(),
                        exit_time.isoformat(),
                        result,
                        strategy,
                        duration_minutes,
                    ]
                )
            logger.info(
                f"Trade logged: {trade_id} | {symbol} | {direction} | PnL: {pnl:.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

        return trade_id

    def _calculate_pnl(
        self,
        direction: str,
        entry_price: float,
        exit_price: Optional[float],
        quantity: int,
    ) -> float:
        """Calculate PnL based on direction."""
        if exit_price is None:
            return 0.0

        if direction.upper() == "BUY":
            return (exit_price - entry_price) * quantity
        else:
            return (entry_price - exit_price) * quantity

    def get_trades(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Retrieve logged trades.

        Args:
            limit: Maximum trades to return
            symbol: Filter by symbol
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of trade dictionaries
        """
        trades = []

        try:
            if self.trade_log_file.exists():
                with open(self.trade_log_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if symbol and row.get("symbol") != symbol:
                            continue

                        if start_date:
                            entry_time = row.get("entry_time", "")
                            if entry_time and entry_time < start_date.isoformat():
                                continue

                        if end_date:
                            entry_time = row.get("entry_time", "")
                            if entry_time and entry_time > end_date.isoformat():
                                continue

                        trades.append(row)
        except Exception as e:
            logger.error(f"Failed to read trades: {e}")

        return trades[-limit:] if len(trades) > limit else trades

    def get_recent_trades(self, count: int = 10) -> List[Dict]:
        """Get most recent trades."""
        return self.get_trades(limit=count)

    def clear_logs(self):
        """Clear all trade logs (use with caution)."""
        try:
            if self.trade_log_file.exists():
                self.trade_log_file.unlink()
                self._init_trade_file()
                logger.warning("Trade logs cleared")
        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")

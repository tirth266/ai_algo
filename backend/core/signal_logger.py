"""
Signal Logger Module

Logs all trading signals, even if not executed, for analysis and debugging.

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
from enum import Enum

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Signal types."""

    BUY = "BUY"
    SELL = "SELL"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    NO_SIGNAL = "NO_SIGNAL"


class SignalLogger:
    """
    Logs all signals (executed and rejected) for analysis.

    Fields:
        - signal_id: Unique identifier
        - timestamp: Signal generation time
        - symbol: Trading symbol
        - signal_type: BUY, SELL, CLOSE_LONG, CLOSE_SHORT
        - entry: Suggested entry price
        - stop_loss: Stop loss price
        - take_profit: Take profit price
        - reason: Why signal was generated or rejected
        - executed: Whether signal was executed
        - execution_price: Actual execution price (if executed)
        - strategy: Strategy that generated signal
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, log_dir: str = "logs/signals"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "logs/signals"):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.signal_log_file = self.log_dir / "signals.csv"
        self._init_signal_file()

        self._initialized = True
        logger.info(f"SignalLogger initialized: {self.signal_log_file}")

    def _init_signal_file(self):
        """Initialize signal log CSV with headers."""
        if not self.signal_log_file.exists():
            with open(self.signal_log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "signal_id",
                        "timestamp",
                        "symbol",
                        "signal_type",
                        "entry",
                        "stop_loss",
                        "take_profit",
                        "reason",
                        "executed",
                        "execution_price",
                        "strategy",
                        "confidence",
                        "market_condition",
                    ]
                )

    def log_signal(
        self,
        symbol: str,
        signal_type: str,
        entry: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reason: str = "",
        executed: bool = False,
        execution_price: Optional[float] = None,
        strategy: str = "UNKNOWN",
        confidence: float = 0.0,
        market_condition: str = "UNKNOWN",
    ) -> str:
        """
        Log a trading signal.

        Args:
            symbol: Trading symbol
            signal_type: Signal type (BUY, SELL, etc.)
            entry: Suggested entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            reason: Why signal was generated
            executed: Whether signal was executed
            execution_price: Actual execution price
            strategy: Strategy name
            confidence: Signal confidence (0-1)
            market_condition: Current market condition

        Returns:
            signal_id: Unique signal identifier
        """
        signal_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()

        try:
            with open(self.signal_log_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        signal_id,
                        timestamp.isoformat(),
                        symbol,
                        signal_type,
                        entry,
                        stop_loss,
                        take_profit,
                        reason,
                        "TRUE" if executed else "FALSE",
                        execution_price,
                        strategy,
                        round(confidence, 2),
                        market_condition,
                    ]
                )

            status = "EXECUTED" if executed else "REJECTED"
            logger.debug(
                f"Signal logged: {signal_id} | {symbol} | {signal_type} | {status}"
            )
        except Exception as e:
            logger.error(f"Failed to log signal: {e}")

        return signal_id

    def log_rejected_signal(
        self,
        symbol: str,
        signal_type: str,
        entry: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float],
        reason: str,
        strategy: str = "UNKNOWN",
        confidence: float = 0.0,
    ):
        """
        Log a rejected signal with rejection reason.

        Args:
            symbol: Trading symbol
            signal_type: Signal type
            entry: Suggested entry
            stop_loss: Stop loss
            take_profit: Take profit
            reason: Why signal was rejected
            strategy: Strategy name
            confidence: Signal confidence
        """
        return self.log_signal(
            symbol=symbol,
            signal_type=signal_type,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"REJECTED: {reason}",
            executed=False,
            execution_price=None,
            strategy=strategy,
            confidence=confidence,
        )

    def log_executed_signal(
        self,
        symbol: str,
        signal_type: str,
        entry: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        execution_price: float,
        reason: str,
        strategy: str = "UNKNOWN",
        confidence: float = 0.0,
        market_condition: str = "UNKNOWN",
    ):
        """
        Log an executed signal.

        Args:
            symbol: Trading symbol
            signal_type: Signal type
            entry: Suggested entry price
            stop_loss: Stop loss
            take_profit: Take profit
            execution_price: Actual execution price
            reason: Why signal was executed
            strategy: Strategy name
            confidence: Signal confidence
            market_condition: Market condition
        """
        return self.log_signal(
            symbol=symbol,
            signal_type=signal_type,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            executed=True,
            execution_price=execution_price,
            strategy=strategy,
            confidence=confidence,
            market_condition=market_condition,
        )

    def get_signals(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
        executed_only: bool = False,
        strategy: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Retrieve logged signals.

        Args:
            limit: Maximum signals to return
            symbol: Filter by symbol
            executed_only: Only executed signals
            strategy: Filter by strategy
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of signal dictionaries
        """
        signals = []

        try:
            if self.signal_log_file.exists():
                with open(self.signal_log_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if symbol and row.get("symbol") != symbol:
                            continue

                        if executed_only and row.get("executed") != "TRUE":
                            continue

                        if strategy and row.get("strategy") != strategy:
                            continue

                        if start_date:
                            ts = row.get("timestamp", "")
                            if ts and ts < start_date.isoformat():
                                continue

                        if end_date:
                            ts = row.get("timestamp", "")
                            if ts and ts > end_date.isoformat():
                                continue

                        signals.append(row)
        except Exception as e:
            logger.error(f"Failed to read signals: {e}")

        return signals[-limit:] if len(signals) > limit else signals

    def get_execution_rate(self) -> float:
        """Calculate signal execution rate."""
        try:
            if self.signal_log_file.exists():
                with open(self.signal_log_file, "r") as f:
                    reader = csv.DictReader(f)
                    total = 0
                    executed = 0
                    for row in reader:
                        total += 1
                        if row.get("executed") == "TRUE":
                            executed += 1
                    return (executed / total * 100) if total > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to calculate execution rate: {e}")
        return 0.0

    def get_rejected_reasons(self) -> Dict[str, int]:
        """Get count of rejection reasons."""
        reasons = {}

        try:
            if self.signal_log_file.exists():
                with open(self.signal_log_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("executed") == "FALSE":
                            reason = row.get("reason", "UNKNOWN")
                            if "REJECTED:" in reason:
                                reason = reason.replace("REJECTED:", "").strip()
                            reasons[reason] = reasons.get(reason, 0) + 1
        except Exception as e:
            logger.error(f"Failed to get rejected reasons: {e}")

        return reasons

    def clear_logs(self):
        """Clear all signal logs."""
        try:
            if self.signal_log_file.exists():
                self.signal_log_file.unlink()
                self._init_signal_file()
                logger.warning("Signal logs cleared")
        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")

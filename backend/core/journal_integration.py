"""
Trade Journal Integration Helper

Easy integration with existing trading flow.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class JournalIntegration:
    """
    Helper class for integrating TradeJournal with trading systems.

    Usage:
        journal = JournalIntegration()

        # On signal generation
        journal.log_signal(signal, executed=False, rejection_reason="...")

        # On trade entry
        journal.log_entry(symbol, direction, entry_price, sl, tp, strategy)

        # On trade exit
        journal.log_exit(trade_data)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._journal = None
        return cls._instance

    @property
    def journal(self):
        """Lazy load TradeJournal."""
        if self._journal is None:
            try:
                from backend.core.trade_journal import TradeJournal

                self._journal = TradeJournal()
            except Exception as e:
                logger.error(f"Failed to initialize TradeJournal: {e}")
                return None
        return self._journal

    def log_signal(
        self,
        signal: Dict[str, Any],
        executed: bool = False,
        execution_price: Optional[float] = None,
        rejection_reason: Optional[str] = None,
        market_condition: str = "UNKNOWN",
    ):
        """Log a trading signal."""
        if not self.journal:
            return

        try:
            symbol = signal.get("symbol", "UNKNOWN")
            direction = signal.get("action", "UNKNOWN").upper()
            entry = signal.get("price", signal.get("entry", 0))
            sl = signal.get("stop_loss")
            tp = (
                signal.get("take_profit", [None])[0]
                if signal.get("take_profit")
                else None
            )
            strategy = signal.get("strategy", "UNKNOWN")
            confidence = signal.get("confidence", 0.5)

            if executed:
                self.journal.signal_logger.log_executed_signal(
                    symbol=symbol,
                    signal_type=direction,
                    entry=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    execution_price=execution_price or entry,
                    reason=signal.get("reason", "Signal executed"),
                    strategy=strategy,
                    confidence=confidence,
                    market_condition=market_condition,
                )
            elif rejection_reason:
                self.journal.signal_logger.log_rejected_signal(
                    symbol=symbol,
                    signal_type=direction,
                    entry=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    reason=rejection_reason,
                    strategy=strategy,
                    confidence=confidence,
                )
        except Exception as e:
            logger.error(f"Failed to log signal: {e}")

    def log_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        strategy: str = "UNKNOWN",
        confidence: float = 0.5,
        market_condition: str = "UNKNOWN",
        quantity: int = 1,
        reason: str = "",
    ):
        """Log a trade entry."""
        if not self.journal:
            return

        try:
            self.journal.log_entry(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy,
                confidence=confidence,
                market_condition=market_condition,
                reason=reason or f"Entry: {direction} {symbol} @ {entry_price}",
            )
            logger.info(f"Trade entry logged: {symbol} {direction} @ {entry_price}")
        except Exception as e:
            logger.error(f"Failed to log entry: {e}")

    def log_exit(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        quantity: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        fees: float = 0.0,
        slippage: float = 0.0,
        strategy: str = "UNKNOWN",
        entry_time: Optional[datetime] = None,
        exit_time: Optional[datetime] = None,
        reason: str = "",
    ):
        """Log a trade exit."""
        if not self.journal:
            return

        try:
            self.journal.log_trade(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                fees=fees,
                slippage=slippage,
                entry_time=entry_time,
                exit_time=exit_time,
                strategy=strategy,
            )
            pnl = (
                (exit_price - entry_price) * quantity
                if direction.upper() == "BUY"
                else (entry_price - exit_price) * quantity
            )
            logger.info(f"Trade exit logged: {symbol} | PnL: {pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to log exit: {e}")

    def log_rejected_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        rejection_reason: str,
        strategy: str = "UNKNOWN",
        confidence: float = 0.0,
    ):
        """Log a rejected entry signal."""
        if not self.journal:
            return

        try:
            self.journal.log_rejected_entry(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                rejection_reason=rejection_reason,
                strategy=strategy,
                confidence=confidence,
            )
            logger.info(f"Rejected signal logged: {symbol} - {rejection_reason}")
        except Exception as e:
            logger.error(f"Failed to log rejected entry: {e}")


def get_journal_integration() -> JournalIntegration:
    """Get JournalIntegration singleton."""
    return JournalIntegration()

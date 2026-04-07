"""
Trade Journal Module

Combines TradeLogger and SignalLogger for comprehensive trade journaling.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from .trade_logger import TradeLogger
from .signal_logger import SignalLogger

logger = logging.getLogger(__name__)


class TradeJournal:
    """
    Trade Journal for comprehensive logging and analytics.

    Integrates:
        - TradeLogger: Executed trades
        - SignalLogger: All signals (executed + rejected)
        - Performance analysis
    """

    _instance = None

    def __new__(cls, log_dir: str = "logs"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "logs"):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)

        self.trade_logger = TradeLogger(log_dir=str(self.log_dir / "trades"))
        self.signal_logger = SignalLogger(log_dir=str(self.log_dir / "signals"))

        self._initialized = True
        logger.info("TradeJournal initialized")

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
        Log a completed trade to both trade and signal logs.

        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            entry_price: Entry price
            exit_price: Exit price
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
        trade_id = self.trade_logger.log_trade(
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

        close_direction = "SELL" if direction.upper() == "BUY" else "BUY"
        reason = f"Trade closed: PnL = {(exit_price - entry_price) * quantity if direction.upper() == 'BUY' else (entry_price - exit_price) * quantity:.2f}"

        self.signal_logger.log_signal(
            symbol=symbol,
            signal_type=close_direction,
            entry=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            executed=True,
            execution_price=exit_price,
            strategy=strategy,
        )

        return trade_id

    def log_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        strategy: str = "UNKNOWN",
        confidence: float = 0.0,
        market_condition: str = "UNKNOWN",
        reason: str = "",
    ) -> str:
        """
        Log a new entry signal (executed).

        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss
            take_profit: Take profit
            strategy: Strategy name
            confidence: Signal confidence
            market_condition: Market condition
            reason: Entry reason

        Returns:
            signal_id: Signal identifier
        """
        return self.signal_logger.log_executed_signal(
            symbol=symbol,
            signal_type=direction.upper(),
            entry=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            execution_price=entry_price,
            reason=reason,
            strategy=strategy,
            confidence=confidence,
            market_condition=market_condition,
        )

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
    ) -> str:
        """
        Log a rejected entry signal.

        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss
            take_profit: Take profit
            rejection_reason: Why signal was rejected
            strategy: Strategy name
            confidence: Signal confidence

        Returns:
            signal_id: Signal identifier
        """
        return self.signal_logger.log_rejected_signal(
            symbol=symbol,
            signal_type=direction.upper(),
            entry=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=rejection_reason,
            strategy=strategy,
            confidence=confidence,
        )

    def get_trades(self, **kwargs) -> List[Dict]:
        """Get trades from trade logger."""
        return self.trade_logger.get_trades(**kwargs)

    def get_signals(self, **kwargs) -> List[Dict]:
        """Get signals from signal logger."""
        return self.signal_logger.get_signals(**kwargs)

    def get_performance_summary(self) -> Dict:
        """Get performance summary from trades."""
        from ..analytics.performance import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(log_dir=str(self.log_dir / "trades"))
        return analyzer.analyze_performance()

    def get_full_analytics(self) -> Dict:
        """Get full analytics package."""
        from ..analytics.performance import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(log_dir=str(self.log_dir / "trades"))
        return analyzer.get_full_analytics()

    def get_equity_curve(self) -> List[Dict]:
        """Get equity curve data."""
        from ..analytics.performance import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer(log_dir=str(self.log_dir / "trades"))
        return analyzer.get_equity_curve()

    def get_strategy_breakdown(self) -> Dict:
        """Get strategy-wise performance."""
        trades = self.trade_logger.get_trades(limit=10000)

        strategy_stats = {}

        for trade in trades:
            strategy = trade.get("strategy", "UNKNOWN")
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                    "win_rate": 0.0,
                }

            strategy_stats[strategy]["trades"] += 1
            pnl = float(trade.get("pnl", 0))
            strategy_stats[strategy]["total_pnl"] += pnl

            if pnl > 0:
                strategy_stats[strategy]["wins"] += 1
            else:
                strategy_stats[strategy]["losses"] += 1

        for strategy, stats in strategy_stats.items():
            if stats["trades"] > 0:
                stats["win_rate"] = round(stats["wins"] / stats["trades"] * 100, 2)
            stats["avg_pnl"] = round(stats["total_pnl"] / stats["trades"], 2)

        return strategy_stats

    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict:
        """Get daily trading summary."""
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        trades = self.get_trades(start_date=start_of_day, end_date=end_of_day)

        total_pnl = sum(float(t.get("pnl", 0)) for t in trades)
        wins = len([t for t in trades if float(t.get("pnl", 0)) > 0])
        losses = len([t for t in trades if float(t.get("pnl", 0)) < 0])

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_trades": len(trades),
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": round(wins / len(trades) * 100, 2) if trades else 0,
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(trades), 2) if trades else 0,
        }

    def get_signal_statistics(self) -> Dict:
        """Get signal execution statistics."""
        signals = self.signal_logger.get_signals(limit=10000)

        total = len(signals)
        executed = len([s for s in signals if s.get("executed") == "TRUE"])
        rejected = total - executed

        return {
            "total_signals": total,
            "executed": executed,
            "rejected": rejected,
            "execution_rate": round(executed / total * 100, 2) if total > 0 else 0,
            "rejection_reasons": self.signal_logger.get_rejected_reasons(),
        }

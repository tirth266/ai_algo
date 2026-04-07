"""
Performance Analyzer Module

Analyzes trading performance and generates insights.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import csv
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes trading performance metrics."""

    def __init__(self, log_dir: str = "logs/trades"):
        self.log_dir = Path(log_dir)
        self.trade_log_file = self.log_dir / "trades.csv"
        self.equity_file = self.log_dir / "equity_curve.csv"

        self._init_equity_file()

        logger.info("PerformanceAnalyzer initialized")

    def _init_equity_file(self):
        """Initialize equity curve CSV file."""
        if not self.equity_file.exists():
            with open(self.equity_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "equity", "drawdown", "open_positions"])

    def analyze_performance(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        trades = self._read_trades()

        if not trades:
            return self._empty_metrics()

        total = len(trades)
        wins = [t for t in trades if float(t.get("pnl", 0)) > 0]
        losses = [t for t in trades if float(t.get("pnl", 0)) < 0]

        win_count = len(wins)
        loss_count = len(losses)

        win_rate = (win_count / total * 100) if total > 0 else 0
        loss_rate = (loss_count / total * 100) if total > 0 else 0

        total_pnl = sum(float(t.get("pnl", 0)) for t in trades)

        avg_win = (
            sum(float(t.get("pnl", 0)) for t in wins) / win_count
            if win_count > 0
            else 0
        )
        avg_loss = (
            abs(sum(float(t.get("pnl", 0)) for t in losses)) / loss_count
            if loss_count > 0
            else 0
        )

        gross_profit = sum(float(t.get("pnl", 0)) for t in wins)
        gross_loss = abs(sum(float(t.get("pnl", 0)) for t in losses))

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        expectancy = (win_rate / 100 * avg_win) - (loss_rate / 100 * avg_loss)

        return {
            "total_trades": total,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "largest_win": round(
                max([float(t.get("pnl", 0)) for t in wins]) if wins else 0, 2
            ),
            "largest_loss": round(
                min([float(t.get("pnl", 0)) for t in losses]) if losses else 0, 2
            ),
            "avg_trade_duration": self._avg_duration(trades),
            "best_day": self._best_day(trades),
            "worst_day": self._worst_day(trades),
        }

    def _read_trades(self) -> List[Dict]:
        """Read trades from CSV."""
        trades = []

        try:
            if self.trade_log_file.exists():
                with open(self.trade_log_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        trades.append(row)
        except Exception as e:
            logger.error(f"Failed to read trades: {e}")

        return trades

    def _empty_metrics(self) -> Dict:
        """Return empty metrics."""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "total_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "avg_trade_duration": 0,
            "best_day": "N/A",
            "worst_day": "N/A",
        }

    def _avg_duration(self, trades: List[Dict]) -> int:
        """Calculate average trade duration in minutes."""
        durations = [
            int(t.get("duration_minutes", 0))
            for t in trades
            if t.get("duration_minutes")
        ]
        return round(sum(durations) / len(durations)) if durations else 0

    def _best_day(self, trades: List[Dict]) -> str:
        """Find best trading day."""
        day_pnl = {}

        for t in trades:
            try:
                entry_time = t.get("entry_time", "")
                if entry_time:
                    day = entry_time[:10]
                    if day not in day_pnl:
                        day_pnl[day] = 0
                    day_pnl[day] += float(t.get("pnl", 0))
            except:
                pass

        if day_pnl:
            best = max(day_pnl.items(), key=lambda x: x[1])
            return f"{best[0]} ({best[1]:.2f})"

        return "N/A"

    def _worst_day(self, trades: List[Dict]) -> str:
        """Find worst trading day."""
        day_pnl = {}

        for t in trades:
            try:
                entry_time = t.get("entry_time", "")
                if entry_time:
                    day = entry_time[:10]
                    if day not in day_pnl:
                        day_pnl[day] = 0
                    day_pnl[day] += float(t.get("pnl", 0))
            except:
                pass

        if day_pnl:
            worst = min(day_pnl.items(), key=lambda x: x[1])
            return f"{worst[0]} ({worst[1]:.2f})"

        return "N/A"

    def get_equity_curve(self) -> List[Dict]:
        """Get equity curve data."""
        equity_data = []

        try:
            if self.equity_file.exists():
                with open(self.equity_file, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        equity_data.append(row)
        except Exception as e:
            logger.error(f"Failed to read equity: {e}")

        return equity_data

    def log_equity(self, equity: float, drawdown: float, open_positions: int):
        """Log equity point."""
        try:
            with open(self.equity_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        datetime.now().isoformat(),
                        round(equity, 2),
                        round(drawdown, 2),
                        open_positions,
                    ]
                )
        except Exception as e:
            logger.error(f"Failed to log equity: {e}")

    def get_strategy_performance(self) -> Dict:
        """Get performance grouped by strategy/reason."""
        trades = self._read_trades()

        if not trades:
            return {}

        by_reason = {}

        for t in trades:
            reason = t.get("result", "UNKNOWN")
            if reason not in by_reason:
                by_reason[reason] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}

            by_reason[reason]["trades"] += 1
            pnl = float(t.get("pnl", 0))
            by_reason[reason]["pnl"] += pnl

            if pnl > 0:
                by_reason[reason]["wins"] += 1
            else:
                by_reason[reason]["losses"] += 1

        for reason, stats in by_reason.items():
            if stats["trades"] > 0:
                stats["win_rate"] = round(stats["wins"] / stats["trades"] * 100, 2)
            else:
                stats["win_rate"] = 0

        return by_reason

    def get_full_analytics(self) -> Dict:
        """Get complete analytics package."""
        return {
            "performance": self.analyze_performance(),
            "equity_curve": self.get_equity_curve(),
            "strategy_performance": self.get_strategy_performance(),
            "generated_at": datetime.now().isoformat(),
        }

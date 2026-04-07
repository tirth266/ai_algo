"""
Broker Safety Layer & Kill Switch Module

Features:
- Daily Loss Limit (Kill Switch)
- Max Trades Per Day
- Consecutive Loss Protection
- Cooldown System
- Emergency Stop Controls

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyState(Enum):
    ACTIVE = "active"
    KILL_SWITCH_ARMED = "kill_switch_armed"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    COOLDOWN = "cooldown"
    PAUSED = "paused"


@dataclass
class DailyStats:
    """Daily trading statistics."""

    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    consecutive_losses: int = 0
    last_trade_time: Optional[datetime] = None


class SafetyManager:
    """
    Broker Safety Layer.

    Features:
    - Daily loss limit (kill switch)
    - Max trades per day
    - Consecutive loss protection
    - Cooldown between trades
    """

    def __init__(
        self,
        capital: float = 100000.0,
        daily_loss_limit_pct: float = 2.0,
        max_trades_per_day: int = 5,
        max_consecutive_losses: int = 3,
        cooldown_minutes: int = 5,
        pause_duration_minutes: int = 15,
    ):
        self.capital = capital
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_trades_per_day = max_trades_per_day
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self.pause_duration_minutes = pause_duration_minutes

        self.state = SafetyState.ACTIVE

        self.daily_stats = DailyStats()
        self.last_kill_switch_reason: Optional[str] = None
        self.pause_until: Optional[datetime] = None

        self._is_kill_switch_triggered = False

        logger.info(
            f"SafetyManager initialized: "
            f"capital={capital}, "
            f"daily_loss_limit={daily_loss_limit_pct}%, "
            f"max_trades={max_trades_per_day}, "
            f"cooldown={cooldown_minutes}min"
        )

    def can_trade(self) -> bool:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        # Check kill switch
        if self._is_kill_switch_triggered:
            logger.warning(f"KILL SWITCH ACTIVE: {self.last_kill_switch_reason}")
            return False, f"kill_switch_triggered: {self.last_kill_switch_reason}"

        # Check if in pause mode
        if self.state == SafetyState.PAUSED:
            if self.pause_until and datetime.now() < self.pause_until:
                remaining = (self.pause_until - datetime.now()).seconds // 60
                logger.warning(f"PAUSED: {remaining} min remaining")
                return False, f"paused: {remaining} min remaining"
            else:
                self.state = SafetyState.ACTIVE
                self.daily_stats.consecutive_losses = 0
                logger.info("Pause duration ended, resuming trading")

        # Check cooldown
        if self.state == SafetyState.COOLDOWN:
            if self.daily_stats.last_trade_time:
                elapsed = datetime.now() - self.daily_stats.last_trade_time
                if elapsed < timedelta(minutes=self.cooldown_minutes):
                    remaining = self.cooldown_minutes - (elapsed.seconds // 60)
                    logger.warning(f"COOLDOWN: {remaining} min remaining")
                    return False, f"cooldown: {remaining} min remaining"
            self.state = SafetyState.ACTIVE

        # Check daily loss limit
        daily_loss_pct = abs(self.daily_stats.total_pnl) / self.capital * 100
        if (
            self.daily_stats.total_pnl < 0
            and daily_loss_pct >= self.daily_loss_limit_pct
        ):
            self._trigger_kill_switch(f"daily_loss: {daily_loss_pct:.2f}%")
            return False, f"kill_switch_triggered: {self.last_kill_switch_reason}"

        # Check max trades
        if self.daily_stats.total_trades >= self.max_trades_per_day:
            logger.warning(
                f"MAX TRADES REACHED: {self.daily_stats.total_trades}/{self.max_trades_per_day}"
            )
            return (
                False,
                f"max_trades_reached: {self.daily_stats.total_trades}/{self.max_trades_per_day}",
            )

        return True, "ok"

    def register_trade(self, pnl: float, is_winning: bool):
        """
        Register trade result for daily tracking.

        Args:
            pnl: Profit/Loss from trade
            is_winning: Whether trade was profitable
        """
        self.daily_stats.total_trades += 1
        self.daily_stats.total_pnl += pnl
        self.daily_stats.last_trade_time = datetime.now()

        if is_winning:
            self.daily_stats.winning_trades += 1
            self.daily_stats.consecutive_losses = 0
            logger.info(
                f"WIN: +{pnl:.2f}, Total trades today: {self.daily_stats.total_trades}"
            )
        else:
            self.daily_stats.losing_trades += 1
            self.daily_stats.consecutive_losses += 1
            logger.warning(
                f"LOSS: {pnl:.2f}, Consecutive losses: {self.daily_stats.consecutive_losses}"
            )

            # Check for consecutive losses
            if self.daily_stats.consecutive_losses >= self.max_consecutive_losses:
                self._pause_trading(
                    f"consecutive_losses: {self.daily_stats.consecutive_losses}"
                )

    def _trigger_kill_switch(self, reason: str):
        """Trigger the kill switch."""
        self._is_kill_switch_triggered = True
        self.state = SafetyState.KILL_SWITCH_TRIGGERED
        self.last_kill_switch_reason = reason

        logger.critical(f"*** KILL SWITCH TRIGGERED *** Reason: {reason}")
        logger.critical(f"*** ALL TRADING HALTED ***")
        logger.critical(
            f"*** DAILY STATS: Trades={self.daily_stats.total_trades}, PnL={self.daily_stats.total_pnl:.2f} ***"
        )

    def _pause_trading(self, reason: str):
        """Pause trading due to consecutive losses."""
        self.state = SafetyState.PAUSED
        self.pause_until = datetime.now() + timedelta(
            minutes=self.pause_duration_minutes
        )

        logger.warning(f"*** TRADING PAUSED *** Reason: {reason}")
        logger.warning(f"*** RESUMING AT: {self.pause_until.strftime('%H:%M:%S')} ***")

    def check_daily_loss(self) -> float:
        """Check current daily loss percentage."""
        if self.daily_stats.total_pnl < 0:
            return abs(self.daily_stats.total_pnl) / self.capital * 100
        return 0.0

    def reset_daily(self):
        """Reset daily stats (called at start of new day)."""
        if self.daily_stats.date != datetime.now().strftime("%Y-%m-%d"):
            logger.info(f"New day detected, resetting daily stats")
            logger.info(
                f"Previous day: Trades={self.daily_stats.total_trades}, PnL={self.daily_stats.total_pnl:.2f}"
            )

            self.daily_stats = DailyStats()
            self.state = SafetyState.ACTIVE
            self._is_kill_switch_triggered = False
            self.pause_until = None

    def get_status(self) -> Dict:
        """Get safety system status."""
        can_trade, reason = self.can_trade()

        return {
            "can_trade": can_trade,
            "reason": reason,
            "state": self.state.value,
            "is_kill_switch_active": self._is_kill_switch_triggered,
            "kill_switch_reason": self.last_kill_switch_reason,
            "daily_stats": {
                "date": self.daily_stats.date,
                "total_trades": self.daily_stats.total_trades,
                "winning_trades": self.daily_stats.winning_trades,
                "losing_trades": self.daily_stats.losing_trades,
                "total_pnl": self.daily_stats.total_pnl,
                "consecutive_losses": self.daily_stats.consecutive_losses,
                "daily_loss_pct": round(self.check_daily_loss(), 2),
            },
            "settings": {
                "daily_loss_limit_pct": self.daily_loss_limit_pct,
                "max_trades_per_day": self.max_trades_per_day,
                "max_consecutive_losses": self.max_consecutive_losses,
                "cooldown_minutes": self.cooldown_minutes,
                "pause_duration_minutes": self.pause_duration_minutes,
            },
        }

    def force_kill_switch(self, reason: str = "manual"):
        """Manually trigger the kill switch."""
        self._trigger_kill_switch(f"manual: {reason}")

    def reset_kill_switch(self):
        """Manually reset the kill switch."""
        self._is_kill_switch_triggered = False
        self.state = SafetyState.ACTIVE
        self.last_kill_switch_reason = None
        logger.info("Kill switch manually reset")

    def get_pause_remaining_minutes(self) -> int:
        """Get remaining pause time in minutes."""
        if self.pause_until and datetime.now() < self.pause_until:
            return (self.pause_until - datetime.now()).seconds // 60
        return 0

    def get_cooldown_remaining_minutes(self) -> int:
        """Get remaining cooldown time in minutes."""
        if self.daily_stats.last_trade_time:
            elapsed = datetime.now() - self.daily_stats.last_trade_time
            remaining = self.cooldown_minutes - (elapsed.seconds // 60)
            if remaining > 0:
                return remaining
        return 0

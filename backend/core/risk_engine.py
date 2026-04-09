"""
Unified Risk Engine

Single source of truth for all trading risk management.
Combines functionality from SafetyManager, RiskManager, and RiskController.

Features:
- Pre-trade validation (validate_trade)
- Position tracking and limits
- Daily loss limits
- Risk per trade limits
- Thread-safe operations
- Single entry point for all risk decisions

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
import threading
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from core.position_persistence import PositionPersistence

logger = logging.getLogger(__name__)


@dataclass
class TradeRequest:
    """Standardized trade request for validation."""

    symbol: str
    direction: str  # "BUY" or "SELL"
    quantity: int
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    order_type: str = "market"  # "market", "limit", "stop", etc.
    risk_checked: bool = False  # Set by RiskEngine after validation


@dataclass
class Position:
    """Position tracking."""

    symbol: str
    entry_price: float
    quantity: int
    direction: str
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0


class RiskEngine:
    """
    Unified Risk Engine - Single source of truth for trading risk.

    Responsibilities:
    - Pre-trade validation (validate_trade)
    - Position tracking and limits
    - Daily loss limits
    - Risk per trade limits
    - Thread-safe operations

    Usage:
        >>> engine = RiskEngine(capital=100000, max_risk_per_trade=0.02)
        >>> result = engine.validate_trade(trade_request)
        >>> if result["allowed"]:
        ...     engine.open_position(trade_request)
    """

    def __init__(
        self,
        capital: float = 100000.0,
        max_risk_per_trade: float = 0.02,
        max_daily_loss_pct: float = 0.05,
        max_open_positions: int = 5,
        max_trades_per_day: int = 10,
        stop_loss_required: bool = True,
        cooldown_minutes: int = 5,
    ):
        """
        Initialize RiskEngine.

        Args:
            capital: Total trading capital
            max_risk_per_trade: Max risk per trade as fraction of capital
            max_daily_loss_pct: Max daily loss as fraction of capital
            max_open_positions: Maximum concurrent positions
            max_trades_per_day: Maximum trades per day
            stop_loss_required: Whether stop loss is mandatory
            cooldown_minutes: Cooldown between trades
        """
        if capital <= 0:
            raise ValueError(f"Capital must be > 0, got {capital}")
        if not 0 < max_risk_per_trade <= 1:
            raise ValueError(
                f"max_risk_per_trade must be 0-1, got {max_risk_per_trade}"
            )
        if not 0 < max_daily_loss_pct <= 1:
            raise ValueError(
                f"max_daily_loss_pct must be 0-1, got {max_daily_loss_pct}"
            )

        self.capital = capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = capital * max_daily_loss_pct
        self.max_open_positions = max_open_positions
        self.max_trades_per_day = max_trades_per_day
        self.stop_loss_required = stop_loss_required
        self.cooldown_minutes = cooldown_minutes

        # Thread safety
        self._lock = threading.RLock()

        # State tracking
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        self.trades_today: int = 0
        self.last_trade_time: Optional[datetime] = None
        self.reset_date = datetime.now().date()
        
        # Initialize persistence layer
        self.persistence = PositionPersistence()

        logger.info(
            f"RiskEngine initialized: capital={capital:.0f}, "
            f"max_risk_per_trade={max_risk_per_trade:.1%}, "
            f"max_daily_loss={self.max_daily_loss:.0f}, "
            f"max_positions={max_open_positions}"
        )

    @property
    def open_positions_count(self) -> int:
        """Current number of open positions."""
        with self._lock:
            return len(self.positions)

    def _check_daily_reset(self) -> None:
        """Reset daily stats if new day."""
        today = datetime.now().date()
        if today != self.reset_date:
            logger.info(
                f"New day detected, resetting daily stats | "
                f"previous_pnl={self.daily_pnl:.2f}, trades={self.trades_today}"
            )
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.reset_date = today

    def validate_trade(self, request: TradeRequest) -> Dict[str, Any]:
        """
        SINGLE ENTRY POINT for trade validation.

        Args:
            request: TradeRequest to validate

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "adjusted_quantity": float
            }
        """
        with self._lock:
            self._check_daily_reset()

            # 0. DUPLICATE CHECK (Priority 1: Prevent duplicate entries)
            is_duplicate, dup_reason = self.persistence.check_for_duplicates(request.symbol)
            if is_duplicate:
                logger.error(
                    f"TRADE REJECTED [{request.symbol}] — DUPLICATE: {dup_reason} "
                    f"[{request.direction} {request.quantity} @ {request.price}]"
                )
                return {
                    "allowed": False,
                    "reason": f"Duplicate position detected: {dup_reason}",
                    "adjusted_quantity": 0,
                }

            # 1. Check if trading is halted
            if self._is_trading_halted():
                logger.warning(f"TRADE REJECTED [{request.symbol}] — Trading halted")
                return {
                    "allowed": False,
                    "reason": "Trading halted due to risk limits",
                    "adjusted_quantity": 0,
                }

            # 2. Validate stop loss requirement
            if self.stop_loss_required and request.stop_loss is None:
                logger.warning(
                    f"TRADE REJECTED [{request.symbol}] — Stop loss required"
                )
                return {
                    "allowed": False,
                    "reason": "Stop loss is required for all trades",
                    "adjusted_quantity": 0,
                }

            # 3. Check cooldown period
            if self._is_in_cooldown():
                remaining = self._get_cooldown_remaining_minutes()
                logger.warning(
                    f"TRADE REJECTED [{request.symbol}] — Cooldown active: {remaining} min remaining"
                )
                return {
                    "allowed": False,
                    "reason": f"Cooldown active: {remaining} minutes remaining",
                    "adjusted_quantity": 0,
                }

            # 4. Check max trades per day
            if self.trades_today >= self.max_trades_per_day:
                logger.warning(
                    f"TRADE REJECTED [{request.symbol}] — Max trades reached: "
                    f"{self.trades_today}/{self.max_trades_per_day}"
                )
                return {
                    "allowed": False,
                    "reason": f"Maximum trades per day reached ({self.max_trades_per_day})",
                    "adjusted_quantity": 0,
                }

            # 5. Check max open positions (only for new positions)
            if (
                request.symbol not in self.positions
                and self.open_positions_count >= self.max_open_positions
            ):
                logger.warning(
                    f"TRADE REJECTED [{request.symbol}] — Max positions reached: "
                    f"{self.open_positions_count}/{self.max_open_positions}"
                )
                return {
                    "allowed": False,
                    "reason": f"Maximum open positions reached ({self.max_open_positions})",
                    "adjusted_quantity": 0,
                }

            # 6. Calculate and validate position size
            adjusted_quantity = self._calculate_position_size(request)

            if adjusted_quantity == 0:
                logger.warning(
                    f"TRADE REJECTED [{request.symbol}] — Risk per trade exceeded: "
                    f"required={request.quantity * request.price:.0f}, "
                    f"max={self.capital * self.max_risk_per_trade:.0f}"
                )
                return {
                    "allowed": False,
                    "reason": "Position size exceeds maximum risk per trade",
                    "adjusted_quantity": 0,
                }

            # 7. Mark as risk checked and log approval
            request.risk_checked = True
            logger.info(
                f"TRADE APPROVED [{request.symbol}] | {request.direction} {adjusted_quantity} @ {request.price:.2f} | "
                f"positions={self.open_positions_count}/{self.max_open_positions} | "
                f"daily_pnl={self.daily_pnl:.2f}"
            )

            return {
                "allowed": True,
                "reason": "All risk checks passed",
                "adjusted_quantity": adjusted_quantity,
            }

    def _calculate_position_size(self, request: TradeRequest) -> int:
        """Calculate safe position size based on risk limits."""
        # Maximum capital per trade
        max_capital_per_trade = self.capital * self.max_risk_per_trade

        # For stop loss trades, use risk-based sizing
        if request.stop_loss:
            risk_per_share = abs(request.price - request.stop_loss)
            if risk_per_share > 0:
                max_quantity_by_risk = int(max_capital_per_trade / risk_per_share)
                return min(request.quantity, max_quantity_by_risk)

        # For non-stop loss trades, use capital limit
        max_quantity_by_capital = int(max_capital_per_trade / request.price)
        return min(request.quantity, max_quantity_by_capital)

    def _is_trading_halted(self) -> bool:
        """Check if trading should be halted."""
        return self.daily_pnl <= -self.max_daily_loss

    def _is_in_cooldown(self) -> bool:
        """Check if in cooldown period."""
        if not self.last_trade_time:
            return False

        elapsed = datetime.now() - self.last_trade_time
        return elapsed < timedelta(minutes=self.cooldown_minutes)

    def _get_cooldown_remaining_minutes(self) -> int:
        """Get remaining cooldown time in minutes."""
        if not self.last_trade_time:
            return 0

        elapsed = datetime.now() - self.last_trade_time
        remaining_seconds = self.cooldown_minutes * 60 - elapsed.seconds
        return max(0, remaining_seconds // 60)

    def open_position(self, request: TradeRequest) -> bool:
        """
        Register a new position (call after successful validation).

        Args:
            request: Validated trade request

        Returns:
            True if opened successfully
        """
        with self._lock:
            if request.symbol in self.positions:
                logger.warning(f"Position already exists for {request.symbol}")
                return False

            position = Position(
                symbol=request.symbol,
                entry_price=request.price,
                quantity=request.quantity,
                direction=request.direction,
                entry_time=datetime.now(),
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
            )

            self.positions[request.symbol] = position
            self.trades_today += 1
            self.last_trade_time = datetime.now()

            logger.info(
                f"POSITION OPENED [{request.symbol}] | {request.direction} "
                f"{request.quantity} @ {request.price:.2f} | "
                f"open_positions={self.open_positions_count}"
            )

            return True

    def close_position(self, symbol: str, exit_price: float, pnl: float) -> bool:
        """
        Close a position and update P&L.

        Args:
            symbol: Symbol to close
            exit_price: Exit price
            pnl: Realized P&L

        Returns:
            True if closed successfully
        """
        with self._lock:
            if symbol not in self.positions:
                logger.warning(f"No position found for {symbol}")
                return False

            position = self.positions.pop(symbol)
            self.daily_pnl += pnl

            logger.info(
                f"POSITION CLOSED [{symbol}] | entry={position.entry_price:.2f} "
                f"exit={exit_price:.2f} | pnl={pnl:.2f} | "
                f"daily_pnl={self.daily_pnl:.2f} | "
                f"open_positions={self.open_positions_count}"
            )

            return True

    def update_position_pnl(self, symbol: str, current_price: float) -> None:
        """Update unrealized P&L for a position."""
        with self._lock:
            if symbol in self.positions:
                position = self.positions[symbol]
                if position.direction == "BUY":
                    position.unrealized_pnl = (
                        current_price - position.entry_price
                    ) * position.quantity
                else:  # SELL
                    position.unrealized_pnl = (
                        position.entry_price - current_price
                    ) * position.quantity

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all open positions."""
        with self._lock:
            return {
                symbol: {
                    "entry_price": pos.entry_price,
                    "quantity": pos.quantity,
                    "direction": pos.direction,
                    "entry_time": pos.entry_time.isoformat(),
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for symbol, pos in self.positions.items()
            }

    def get_risk_status(self) -> Dict[str, Any]:
        """Get comprehensive risk status."""
        with self._lock:
            return {
                "trading_allowed": not self._is_trading_halted(),
                "open_positions": self.open_positions_count,
                "max_positions": self.max_open_positions,
                "daily_pnl": self.daily_pnl,
                "max_daily_loss": self.max_daily_loss,
                "trades_today": self.trades_today,
                "max_trades_per_day": self.max_trades_per_day,
                "in_cooldown": self._is_in_cooldown(),
                "cooldown_remaining": self._get_cooldown_remaining_minutes(),
                "positions": self.get_open_positions(),
            }

    def can_trade(self) -> Tuple[bool, str]:
        """
        Legacy compatibility method.

        Returns:
            Tuple of (allowed, reason)
        """
        with self._lock:
            if self._is_trading_halted():
                return False, "Trading halted due to risk limits"
            if self._is_in_cooldown():
                remaining = self._get_cooldown_remaining_minutes()
                return False, f"Cooldown active: {remaining} minutes remaining"
            return True, "Trading allowed"

    def load_positions_from_database(self) -> int:
        """
        Load open positions from database on startup.
        
        Restores in-memory state from persisted positions to prevent data loss on restart.
        
        Returns:
            Number of positions loaded
        """
        with self._lock:
            try:
                loaded_positions = self.persistence.load_open_positions()
                count = 0
                
                for pos_data in loaded_positions:
                    symbol = pos_data['symbol']
                    
                    # Create Position object from persisted data
                    position = Position(
                        symbol=symbol,
                        entry_price=pos_data['entry_price'],
                        quantity=pos_data['quantity'],
                        direction=pos_data['side'].upper(),
                        entry_time=pos_data.get('timestamp', datetime.now()),
                        stop_loss=pos_data.get('stop_loss'),
                        take_profit=pos_data.get('take_profit_2'),
                    )
                    
                    self.positions[symbol] = position
                    count += 1
                    
                logger.info(f"Loaded {count} positions from database into RiskEngine")
                return count
                
            except Exception as e:
                logger.error(f"Failed to load positions from database: {str(e)}")
                return 0


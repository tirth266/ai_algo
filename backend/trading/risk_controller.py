"""
Risk Controller Module

Real-time risk management with controls for:
- Max daily loss
- Max position size
- Max open trades
- Max portfolio drawdown

Example:
    if daily_loss > limit:
        stop trading

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskStatus(Enum):
    """Risk check status."""
    OK = 'OK'
    WARNING = 'WARNING'
    BREACH = 'BREACH'
    HALT = 'HALT'


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    
    # Position limits
    max_position_size: float = 100000.0  # Max value per position
    max_total_exposure: float = 500000.0  # Max total exposure
    max_open_trades: int = 10  # Maximum concurrent positions
    
    # Loss limits
    max_daily_loss: float = 10000.0  # Max daily loss in currency
    max_weekly_loss: float = 40000.0  # Max weekly loss
    max_monthly_loss: float = 150000.0  # Max monthly loss
    
    # Drawdown limits
    max_portfolio_drawdown: float = 0.10  # Max drawdown as percentage
    max_position_drawdown: float = 0.05  # Max per-position drawdown
    
    # Order limits
    max_order_value: float = 50000.0  # Max single order value
    max_order_quantity: int = 1000  # Max shares per order
    
    # Concentration limits
    max_sector_exposure: float = 0.30  # Max sector allocation
    max_single_stock_weight: float = 0.20  # Max weight in single stock


@dataclass
class RiskMetrics:
    """Current risk metrics."""
    
    # PnL metrics
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    total_pnl: float = 0.0
    
    # Exposure metrics
    total_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    net_exposure: float = 0.0
    
    # Position metrics
    open_positions: int = 0
    active_orders: int = 0
    
    # Drawdown metrics
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.now)


class RiskController:
    """
    Real-time risk management and monitoring.
    
    Features:
    - Pre-trade risk checks
    - Post-trade monitoring
    - Daily/weekly/monthly loss limits
    - Position size limits
    - Drawdown monitoring
    - Automatic trading halt on breaches
    
    Usage:
        >>> controller = RiskController(initial_capital=100000)
        >>> if controller.check_order(order, ltp=2500):
        ...     broker.place_order(order)
    """
    
    def __init__(
        self,
        initial_capital: float,
        limits: RiskLimits = None,
        trading_symbol: str = None
    ):
        """
        Initialize risk controller.
        
        Args:
            initial_capital: Starting capital
            limits: Risk limits configuration
            trading_symbol: Trading symbol for tracking
        """
        self.initial_capital = initial_capital
        self.limits = limits or RiskLimits()
        self.trading_symbol = trading_symbol
        
        # State tracking
        self.metrics = RiskMetrics()
        self.metrics.peak_equity = initial_capital
        self.metrics.current_equity = initial_capital
        
        # Daily tracking
        self.today_start_pnl: float = 0.0
        self.today_date: date = date.today()
        
        # Historical tracking
        self.equity_curve: List[float] = [initial_capital]
        self.pnl_history: List[Dict[str, Any]] = []
        
        # Trading status
        self.trading_halted: bool = False
        self.halt_reason: Optional[str] = None
        
        logger.info(
            f"RiskController initialized: capital={initial_capital}, "
            f"max_daily_loss={limits.max_daily_loss}"
        )
    
    def check_order(
        self,
        order: 'Order',
        ltp: float,
        current_positions: List['Position'] = None
    ) -> tuple[bool, RiskStatus, str]:
        """
        Pre-trade risk check for order.
        
        Args:
            order: Order to validate
            ltp: Last traded price
            current_positions: Current positions (optional)
        
        Returns:
            Tuple of (allowed, status, message)
        
        Example:
            >>> allowed, status, msg = controller.check_order(order, ltp=2500)
            >>> if allowed:
            ...     broker.place_order(order)
        """
        if self.trading_halted:
            return False, RiskStatus.HALT, f"Trading halted: {self.halt_reason}"
        
        # Check order value
        order_value = order.quantity * ltp
        
        if order_value > self.limits.max_order_value:
            return (
                False, RiskStatus.BREACH,
                f"Order value {order_value:.2f} exceeds limit {self.limits.max_order_value:.2f}"
            )
        
        # Check order quantity
        if order.quantity > self.limits.max_order_quantity:
            return (
                False, RiskStatus.BREACH,
                f"Order quantity {order.quantity} exceeds limit {self.limits.max_order_quantity}"
            )
        
        # Check total exposure
        current_exposure = sum(pos.value for pos in (current_positions or []))
        new_exposure = current_exposure + order_value
        
        if new_exposure > self.limits.max_total_exposure:
            return (
                False, RiskStatus.BREACH,
                f"Total exposure {new_exposure:.2f} exceeds limit {self.limits.max_total_exposure:.2f}"
            )
        
        # Check position size for this symbol
        if current_positions:
            current_position = next(
                (p for p in current_positions if p.symbol == order.symbol), None
            )
            
            if current_position:
                new_quantity = abs(current_position.quantity) + order.quantity
                new_position_value = new_quantity * ltp
                
                if new_position_value > self.limits.max_position_size:
                    return (
                        False, RiskStatus.BREACH,
                        f"Position size {new_position_value:.2f} exceeds limit"
                    )
        
        # Check open trades limit
        open_count = len(current_positions) if current_positions else 0
        
        if order.side == 'BUY' and open_count >= self.limits.max_open_trades:
            return (
                False, RiskStatus.BREACH,
                f"Open trades {open_count} at maximum limit {self.limits.max_open_trades}"
            )
        
        # Check daily loss limit
        if self.metrics.daily_pnl < -self.limits.max_daily_loss:
            return (
                False, RiskStatus.BREACH,
                f"Daily loss {self.metrics.daily_pnl:.2f} exceeds limit"
            )
        
        # All checks passed
        return True, RiskStatus.OK, "Order approved"
    
    def update_metrics(
        self,
        positions: List['Position'],
        account_balance: Dict[str, Any]
    ):
        """
        Update risk metrics from current state.
        
        Args:
            positions: Current positions
            account_balance: Account balance from broker
        """
        # Reset daily PnL if new day
        today = date.today()
        if today != self.today_date:
            self.today_pnl = 0.0
            self.today_date = today
        
        # Calculate exposures
        long_exposure = sum(p.value for p in positions if p.quantity > 0)
        short_exposure = sum(p.value for p in positions if p.quantity < 0)
        net_exposure = long_exposure - short_exposure
        total_exposure = long_exposure + short_exposure
        
        # Calculate total PnL
        total_pnl = sum(p.pnl for p in positions)
        
        # Update equity
        current_equity = account_balance.get('total_net_value', self.initial_capital)
        self.metrics.current_equity = current_equity
        
        # Update peak equity
        if current_equity > self.metrics.peak_equity:
            self.metrics.peak_equity = current_equity
        
        # Calculate drawdown
        if self.metrics.peak_equity > 0:
            self.metrics.current_drawdown = (
                (self.metrics.peak_equity - current_equity) / self.metrics.peak_equity
            )
        
        # Update metrics
        self.metrics.total_pnl = total_pnl
        self.metrics.long_exposure = long_exposure
        self.metrics.short_exposure = short_exposure
        self.metrics.net_exposure = net_exposure
        self.metrics.total_exposure = total_exposure
        self.metrics.open_positions = len(positions)
        
        # Track equity curve
        self.equity_curve.append(current_equity)
        
        logger.debug(
            f"Risk metrics updated: equity={current_equity:.2f}, "
            f"drawdown={self.metrics.current_drawdown:.2%}"
        )
    
    def check_risk_limits(self) -> tuple[RiskStatus, List[str]]:
        """
        Check all risk limits and return status.
        
        Returns:
            Tuple of (status, list of breach messages)
        
        Example:
            >>> status, breaches = controller.check_risk_limits()
            >>> if status == RiskStatus.HALT:
            ...     controller.halt_trading("Multiple breaches")
        """
        breaches = []
        warnings = []
        
        # Check daily loss
        if self.metrics.daily_pnl < -self.limits.max_daily_loss:
            breaches.append(
                f"Daily loss {self.metrics.daily_pnl:.2f} exceeds {self.limits.max_daily_loss:.2f}"
            )
        elif self.metrics.daily_pnl < -self.limits.max_daily_loss * 0.8:
            warnings.append(
                f"Daily loss approaching limit: {self.metrics.daily_pnl:.2f}"
            )
        
        # Check weekly loss
        if self.metrics.weekly_pnl < -self.limits.max_weekly_loss:
            breaches.append(
                f"Weekly loss {self.metrics.weekly_pnl:.2f} exceeds {self.limits.max_weekly_loss:.2f}"
            )
        
        # Check monthly loss
        if self.metrics.monthly_pnl < -self.limits.max_monthly_loss:
            breaches.append(
                f"Monthly loss {self.metrics.monthly_pnl:.2f} exceeds {self.limits.max_monthly_loss:.2f}"
            )
        
        # Check drawdown
        if self.metrics.current_drawdown > self.limits.max_portfolio_drawdown:
            breaches.append(
                f"Drawdown {self.metrics.current_drawdown:.2%} exceeds "
                f"limit {self.limits.max_portfolio_drawdown:.2%}"
            )
        elif self.metrics.current_drawdown > self.limits.max_portfolio_drawdown * 0.8:
            warnings.append(
                f"Drawdown approaching limit: {self.metrics.current_drawdown:.2%}"
            )
        
        # Check total exposure
        if self.metrics.total_exposure > self.limits.max_total_exposure:
            breaches.append(
                f"Total exposure {self.metrics.total_exposure:.2f} exceeds "
                f"limit {self.limits.max_total_exposure:.2f}"
            )
        
        # Determine status
        if breaches:
            return RiskStatus.BREACH, breaches
        elif warnings:
            return RiskStatus.WARNING, warnings
        else:
            return RiskStatus.OK, []
    
    def halt_trading(self, reason: str):
        """Halt all trading activity."""
        self.trading_halted = True
        self.halt_reason = reason
        logger.critical(f"TRADING HALTED: {reason}")
    
    def resume_trading(self):
        """Resume trading after halt."""
        self.trading_halted = False
        self.halt_reason = None
        logger.info("Trading resumed")
    
    def should_allow_trade(self) -> bool:
        """Check if trading is currently allowed."""
        if self.trading_halted:
            return False
        
        status, _ = self.check_risk_limits()
        
        if status in [RiskStatus.BREACH, RiskStatus.HALT]:
            return False
        
        return True
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        return {
            'status': not self.trading_halted,
            'halt_reason': self.halt_reason,
            'metrics': {
                'daily_pnl': self.metrics.daily_pnl,
                'total_pnl': self.metrics.total_pnl,
                'current_equity': self.metrics.current_equity,
                'peak_equity': self.metrics.peak_equity,
                'drawdown': self.metrics.current_drawdown,
                'total_exposure': self.metrics.total_exposure,
                'open_positions': self.metrics.open_positions
            },
            'limits': {
                'max_daily_loss': self.limits.max_daily_loss,
                'max_drawdown': self.limits.max_portfolio_drawdown,
                'max_exposure': self.limits.max_total_exposure,
                'max_open_trades': self.limits.max_open_trades
            },
            'utilization': {
                'daily_loss_pct': (
                    abs(self.metrics.daily_pnl) / self.limits.max_daily_loss * 100
                    if self.limits.max_daily_loss > 0 else 0
                ),
                'drawdown_pct': self.metrics.current_drawdown * 100,
                'exposure_pct': (
                    self.metrics.total_exposure / self.limits.max_total_exposure * 100
                    if self.limits.max_total_exposure > 0 else 0
                )
            },
            'timestamp': datetime.now().isoformat()
        }

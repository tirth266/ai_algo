"""
NSE-Compliant Order Validation

Validates LIMIT orders against NSE regulations and market parameters.

Features:
- Tick size validation (₹0.01, ₹0.05, ₹1.00, etc.)
- Price band validation (circuit limits ±10%, ±20%)
- Freeze quantity check (max qty per order)
- Slippage guard (price deviation from LTP)
- Comprehensive logging of all rejections

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# NSE Tick Size Rules
# Price ranges define minimum price increment for different price levels
TICK_SIZES = {
    "default": 0.05,  # ₹0.05 for most stocks
    "high_price": {
        "threshold": 500,
        "tick": 1.00,  # ₹1.00 for prices >= ₹500
    },
    "special": {
        "threshold": 5000,
        "tick": 5.00,  # ₹5.00 for prices >= ₹5000
    },
}

# NSE Circuit Breaker Limits
CIRCUIT_LIMITS = {
    "primary": 0.10,  # 10% of LTP (most liquid stocks)
    "secondary": 0.20,  # 20% of LTP (less liquid)
}

# Default freeze quantity cap (max shares per order for high-value stocks)
DEFAULT_FREEZE_QTY = 100000


class InstrumentParams:
    """Parameters for a specific NSE instrument."""

    def __init__(
        self,
        symbol: str,
        ltp: float,
        lot_size: int = 1,
        tick_size: Optional[float] = None,
        circuit_limit: float = 0.10,
        freeze_qty: int = DEFAULT_FREEZE_QTY,
        previous_close: Optional[float] = None,
    ):
        self.symbol = symbol
        self.ltp = ltp
        self.lot_size = lot_size
        self.tick_size = tick_size or self._infer_tick_size(ltp)
        self.circuit_limit = circuit_limit
        self.freeze_qty = freeze_qty
        self.previous_close = previous_close or ltp

    def _infer_tick_size(self, price: float) -> float:
        """Infer tick size based on price level."""
        if price >= TICK_SIZES["special"]["threshold"]:
            return TICK_SIZES["special"]["tick"]
        elif price >= TICK_SIZES["high_price"]["threshold"]:
            return TICK_SIZES["high_price"]["tick"]
        else:
            return TICK_SIZES["default"]

    def get_price_band(self) -> tuple:
        """Get lower and upper price band based on circuit limits."""
        lower = self.previous_close * (1 - self.circuit_limit)
        upper = self.previous_close * (1 + self.circuit_limit)
        return (lower, upper)


class NSEOrderValidator:
    """Validate NSE LIMIT orders for compliance and market safety."""

    def __init__(self, max_slippage_pct: float = 2.0):
        """
        Initialize NSE order validator.

        Args:
            max_slippage_pct: Maximum allowed deviation from LTP (default 2%)
        """
        self.max_slippage_pct = max_slippage_pct
        logger.info(
            "NSEOrderValidator initialized: max_slippage=%s%%",
            max_slippage_pct,
        )

    def validate_order(
        self,
        symbol: str,
        order_type: str,
        quantity: int,
        price: float,
        ltp: float,
        lot_size: int = 1,
        tick_size: Optional[float] = None,
        circuit_limit: float = 0.10,
        freeze_qty: int = DEFAULT_FREEZE_QTY,
        previous_close: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Validate LIMIT order before sending to broker.

        Args:
            symbol: Stock symbol (e.g., 'SBIN-EQ')
            order_type: 'LIMIT', 'MARKET', 'SL', 'SL-M'
            quantity: Order quantity
            price: Limit price (ignored for MARKET orders)
            ltp: Last traded price (current market price)
            lot_size: Minimum trading unit
            tick_size: Minimum price increment (auto-inferred if None)
            circuit_limit: Price band limit (0.10 for ±10%)
            freeze_qty: Maximum qty per order
            previous_close: Previous day close price (defaults to LTP)

        Returns:
            {
                "valid": bool,
                "reason": str,
                "details": dict
            }
        """
        details = {
            "symbol": symbol,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "ltp": ltp,
            "lot_size": lot_size,
        }

        # Only validate LIMIT orders for NSE compliance
        if order_type.upper() not in ["LIMIT", "SL"]:
            logger.info("Skipping NSE validation for %s order type %s", symbol, order_type)
            return {
                "valid": True,
                "reason": "NSE validation skipped for MARKET/SL-M orders",
                "details": details,
            }

        params = InstrumentParams(
            symbol=symbol,
            ltp=ltp,
            lot_size=lot_size,
            tick_size=tick_size,
            circuit_limit=circuit_limit,
            freeze_qty=freeze_qty,
            previous_close=previous_close,
        )

        # Validation sequence
        checks = [
            ("tick_size", self._validate_tick_size, params, price),
            ("price_band", self._validate_price_band, params, price),
            ("slippage", self._validate_slippage, params, price),
            ("quantity_lot", self._validate_quantity_lot, params, quantity),
            ("freeze_qty", self._validate_freeze_qty, params, quantity),
            ("price_positive", self._validate_price_positive, params, price),
        ]

        for check_name, check_func, *args in checks:
            result = check_func(*args)
            if not result["valid"]:
                reason = result["reason"]
                logger.warning(
                    "NSE order rejected [%s]: %s | %s@%.2f qty=%d",
                    check_name,
                    reason,
                    symbol,
                    price,
                    quantity,
                )
                details["failed_check"] = check_name
                return {
                    "valid": False,
                    "reason": reason,
                    "details": details,
                }

        logger.info(
            "NSE order validated: %s %d@%.2f (LTP: %.2f)",
            symbol,
            quantity,
            price,
            ltp,
        )
        return {
            "valid": True,
            "reason": "NSE order validated successfully",
            "details": details,
        }

    def _validate_tick_size(self, params: InstrumentParams, price: float) -> Dict[str, bool]:
        """Validate price matches NSE tick size rules."""
        if price <= 0:
            return {"valid": False, "reason": "price must be > 0"}

        # Round price to tick size and check if it matches
        rounded_price = round(price / params.tick_size) * params.tick_size

        # Allow small floating-point tolerance
        tolerance = params.tick_size / 1000000
        if abs(price - rounded_price) > tolerance:
            return {
                "valid": False,
                "reason": f"tick_size: price ₹{price:.2f} not multiple of ₹{params.tick_size:.2f} "
                f"(nearest: ₹{rounded_price:.2f})",
            }

        return {"valid": True, "reason": ""}

    def _validate_price_band(
        self, params: InstrumentParams, price: float
    ) -> Dict[str, bool]:
        """Validate price is within NSE circuit breaker limits."""
        lower, upper = params.get_price_band()

        if price < lower or price > upper:
            return {
                "valid": False,
                "reason": f"price_band: ₹{price:.2f} outside circuit limits "
                f"(₹{lower:.2f} - ₹{upper:.2f})",
            }

        return {"valid": True, "reason": ""}

    def _validate_slippage(self, params: InstrumentParams, price: float) -> Dict[str, bool]:
        """Validate price deviation from LTP doesn't exceed max slippage."""
        if params.ltp <= 0:
            return {"valid": True, "reason": ""}  # Skip if LTP unavailable

        slippage_pct = abs(price - params.ltp) / params.ltp * 100

        if slippage_pct > self.max_slippage_pct:
            return {
                "valid": False,
                "reason": f"slippage: {slippage_pct:.2f}% from LTP ₹{params.ltp:.2f} "
                f"(limit: {self.max_slippage_pct}%)",
            }

        return {"valid": True, "reason": ""}

    def _validate_quantity_lot(
        self, params: InstrumentParams, quantity: int
    ) -> Dict[str, bool]:
        """Validate quantity is a multiple of lot size."""
        if quantity <= 0:
            return {"valid": False, "reason": "quantity must be > 0"}

        if quantity % params.lot_size != 0:
            return {
                "valid": False,
                "reason": f"quantity: {quantity} not multiple of lot size {params.lot_size}",
            }

        return {"valid": True, "reason": ""}

    def _validate_freeze_qty(
        self, params: InstrumentParams, quantity: int
    ) -> Dict[str, bool]:
        """Validate quantity doesn't exceed freeze limit."""
        if quantity > params.freeze_qty:
            return {
                "valid": False,
                "reason": f"quantity: {quantity} exceeds freeze limit {params.freeze_qty}",
            }

        return {"valid": True, "reason": ""}

    def _validate_price_positive(
        self, params: InstrumentParams, price: float
    ) -> Dict[str, bool]:
        """Validate price is positive."""
        if price <= 0:
            return {"valid": False, "reason": f"price: {price} must be positive"}

        return {"valid": True, "reason": ""}

    def get_suggested_price(
        self, symbol: str, proposed_price: float, ltp: float, tick_size: Optional[float] = None
    ) -> float:
        """Return the nearest valid price based on tick size."""
        if tick_size is None:
            tick_size = TICK_SIZES["default"]

        rounded = round(proposed_price / tick_size) * tick_size

        logger.debug(
            "Suggested price for %s: %.2f -> %.2f (tick: %.2f)",
            symbol,
            proposed_price,
            rounded,
            tick_size,
        )
        return rounded


def validate_nse_order(
    symbol: str,
    order_type: str,
    quantity: int,
    price: float,
    ltp: float,
    lot_size: int = 1,
    tick_size: Optional[float] = None,
    circuit_limit: float = 0.10,
    freeze_qty: int = DEFAULT_FREEZE_QTY,
    previous_close: Optional[float] = None,
    max_slippage_pct: float = 2.0,
) -> Dict[str, Any]:
    """
    Convenience function to validate NSE order.

    Returns:
        {"valid": bool, "reason": str, "details": dict}
    """
    validator = NSEOrderValidator(max_slippage_pct=max_slippage_pct)
    return validator.validate_order(
        symbol=symbol,
        order_type=order_type,
        quantity=quantity,
        price=price,
        ltp=ltp,
        lot_size=lot_size,
        tick_size=tick_size,
        circuit_limit=circuit_limit,
        freeze_qty=freeze_qty,
        previous_close=previous_close,
    )

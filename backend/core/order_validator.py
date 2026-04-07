"""
Order Validation Layer

Validates orders before execution to ensure safety and compliance.

Features:
- Duplicate trade check
- Max open positions check
- Margin check
- Price validation
- Quantity validation
- Market hours check

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, time

logger = logging.getLogger(__name__)


class OrderValidator:
    """
    Order validation for safety before broker execution.
    """

    def __init__(
        self,
        max_open_positions: int = 2,
        max_slippage_pct: float = 0.5,
        min_quantity: int = 1,
        lot_size: int = 1,
        market_start: time = time(9, 15),
        market_end: time = time(15, 30),
    ):
        self.max_open_positions = max_open_positions
        self.max_slippage_pct = max_slippage_pct
        self.min_quantity = min_quantity
        self.lot_size = lot_size
        self.market_start = market_start
        self.market_end = market_end

        logger.info(
            f"OrderValidator initialized: "
            f"max_positions={max_open_positions}, "
            f"max_slippage={max_slippage_pct}%, "
            f"market_hours={market_start}-{market_end}"
        )

    def validate_order(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        quantity: int,
        capital: float,
        open_trades: List[Dict] = None,
    ) -> Dict:
        """
        Validate order before execution.

        Args:
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Proposed entry price
            current_price: Current market price (LTP)
            quantity: Order quantity
            capital: Available capital
            open_trades: List of open trades

        Returns:
            Dict with:
            - valid: bool
            - reason: str
        """
        open_trades = open_trades or []

        # Check 1: Duplicate Trade
        dup_check = self.is_duplicate_trade(symbol, direction, open_trades)
        if not dup_check["valid"]:
            logger.warning(f"DUPLICATE TRADE: {dup_check['reason']}")
            return dup_check

        # Check 2: Max Open Positions
        pos_check = self.check_max_positions(len(open_trades))
        if not pos_check["valid"]:
            logger.warning(f"MAX POSITIONS: {pos_check['reason']}")
            return pos_check

        # Check 3: Quantity
        qty_check = self.check_quantity(quantity)
        if not qty_check["valid"]:
            logger.warning(f"QUANTITY INVALID: {qty_check['reason']}")
            return qty_check

        # Check 4: Price Validation
        price_check = self.validate_price(entry_price, current_price)
        if not price_check["valid"]:
            logger.warning(f"PRICE INVALID: {price_check['reason']}")
            return price_check

        # Check 5: Margin Check
        margin_check = self.check_margin(entry_price, quantity, capital)
        if not margin_check["valid"]:
            logger.warning(f"MARGIN INSUFFICIENT: {margin_check['reason']}")
            return margin_check

        # Check 6: Market Hours
        hours_check = self.check_market_hours()
        if not hours_check["valid"]:
            logger.warning(f"MARKET CLOSED: {hours_check['reason']}")
            return hours_check

        logger.info(f"Order validated: {direction} {quantity} {symbol} @ {entry_price}")

        return {"valid": True, "reason": "order validated"}

    def is_duplicate_trade(
        self, symbol: str, direction: str, open_trades: List[Dict]
    ) -> Dict:
        """Check if trade already exists for symbol + direction."""
        for trade in open_trades:
            if trade.get("symbol") == symbol and trade.get("direction") == direction:
                return {
                    "valid": False,
                    "reason": f"duplicate: {symbol} {direction} already open",
                }

        return {"valid": True, "reason": ""}

    def check_max_positions(self, current_positions: int) -> Dict:
        """Check if max positions reached."""
        if current_positions >= self.max_open_positions:
            return {
                "valid": False,
                "reason": f"max_positions: {self.max_open_positions} open",
            }

        return {"valid": True, "reason": ""}

    def check_quantity(self, quantity: int) -> Dict:
        """Validate order quantity."""
        if quantity < self.min_quantity:
            return {
                "valid": False,
                "reason": f"quantity: {quantity} < {self.min_quantity}",
            }

        if quantity % self.lot_size != 0:
            return {
                "valid": False,
                "reason": f"quantity: {quantity} not multiple of {self.lot_size}",
            }

        return {"valid": True, "reason": ""}

    def validate_price(self, entry_price: float, current_price: float) -> Dict:
        """Validate entry price is close to current price."""
        if current_price <= 0:
            return {"valid": False, "reason": "price: current price not available"}

        if entry_price <= 0:
            return {"valid": False, "reason": "price: invalid entry price"}

        slippage = abs(entry_price - current_price) / current_price * 100

        if slippage > self.max_slippage_pct:
            return {
                "valid": False,
                "reason": f"price: slippage {slippage:.2f}% > {self.max_slippage_pct}%",
            }

        return {"valid": True, "reason": ""}

    def check_margin(self, entry_price: float, quantity: int, capital: float) -> Dict:
        """Check if sufficient margin available."""
        required = entry_price * quantity

        if required > capital:
            return {"valid": False, "reason": f"margin: {required:.2f} > {capital:.2f}"}

        return {"valid": True, "reason": ""}

    def check_market_hours(self) -> Dict:
        """Check if market is open."""
        now = datetime.now().time()

        is_weekend = datetime.now().weekday() >= 5

        if is_weekend:
            return {"valid": False, "reason": "market: closed on weekends"}

        if now < self.market_start or now > self.market_end:
            return {
                "valid": False,
                "reason": f"market: closed ({self.market_start}-{self.market_end})",
            }

        return {"valid": True, "reason": ""}

    def get_status(self) -> Dict:
        """Get validator configuration."""
        return {
            "max_open_positions": self.max_open_positions,
            "max_slippage_pct": self.max_slippage_pct,
            "min_quantity": self.min_quantity,
            "lot_size": self.lot_size,
            "market_start": self.market_start.strftime("%H:%M"),
            "market_end": self.market_end.strftime("%H:%M"),
        }

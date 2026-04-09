"""
Realistic Order Execution Simulator
=====================================

Simulates imperfect real-world order execution for backtesting on Indian
markets (NSE/BSE / AngelOne / Zerodha).

Features implemented
────────────────────
1. Slippage model
   - Percentage-based adverse price move (configurable, default 0.05 %)
   - BUY  → fills at a HIGHER price than the signal price
   - SELL → fills at a LOWER  price than the signal price
   - Optional volatility-scaled slippage (adapts to candle range)

2. Execution delay (signal → fill latency)
   - Configurable n-candle delay (default 1 candle = next-bar execution)
   - Simulates the realistic "cannot trade on the same bar" constraint
   - Pending orders queue processed on the correct future candle

3. Partial fills
   - Random fill ratio drawn from Beta(α, β) distribution
   - Configurable minimum fill threshold
   - Remaining unfilled quantity is cancelled (models thin liquidity)

4. Order rejection
   - Configurable rejection probability per order (default 2 %)
   - Rejection reasons: liquidity, risk-check, circuit-breaker, random

5. All execution events are logged with full audit trail

Usage::

    from backtest.execution.execution_simulator import ExecutionSimulator, ExecutionConfig

    cfg = ExecutionConfig(
        slippage_pct        = 0.0005,   # 0.05 %
        delay_candles       = 1,        # next-bar execution
        enable_partial_fills= True,
        partial_fill_min    = 0.70,     # at least 70 % filled
        rejection_prob      = 0.02,     # 2 % rejection rate
    )
    sim = ExecutionSimulator(config=cfg, seed=42)

    # On each candle (candle_index counts from 0):
    order_id = sim.submit_order(
        candle_index = i,
        symbol       = "RELIANCE",
        side         = "BUY",
        quantity     = 100,
        signal_price = candle["close"],
        candle       = candle,          # dict with open/high/low/close/volume
    )

    # One candle later, process pending orders against the new candle:
    fills = sim.process_pending_orders(candle_index=i+1, candle=next_candle)
    for fill in fills:
        print(fill)   # ExecutionResult dataclass
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Enums ────────────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING   = "PENDING"
    FILLED    = "FILLED"
    PARTIAL   = "PARTIAL"
    REJECTED  = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED   = "EXPIRED"


class RejectionReason(str, Enum):
    LIQUIDITY      = "INSUFFICIENT_LIQUIDITY"
    CIRCUIT_BREAK  = "CIRCUIT_BREAKER_HIT"
    RISK_CHECK     = "RISK_CHECK_FAILED"
    RANDOM         = "RANDOM_BROKER_REJECTION"
    PRICE_BAND     = "ORDER_OUTSIDE_PRICE_BAND"


# ─── Config dataclass ─────────────────────────────────────────────────────────

@dataclass
class ExecutionConfig:
    """
    All execution-simulation parameters in one place.

    Parameters
    ----------
    slippage_pct : float
        Base slippage as a fraction of price (default 0.05 % = 0.0005).
        Applied adversely: BUY fills higher, SELL fills lower.
    volatility_scaled_slippage : bool
        If True, slippage also scales with the candle's intrabar range
        (high-low) / close, capped at 3× the base slippage.  Mimics
        wider bid-ask spreads during volatile bars.
    delay_candles : int
        Number of candles between signal generation and order execution.
        0 = same-bar execution (look-ahead, not recommended).
        1 = next-bar execution (default, realistic for end-of-bar signals).
    order_ttl_candles : int
        Time-to-live for pending orders.  Orders not filled within this
        many candles are automatically cancelled ("expired").
    enable_partial_fills : bool
        Enable partial fill simulation (default True).
    partial_fill_min : float
        Minimum fill ratio (0–1).  E.g. 0.70 means at least 70 % of the
        order quantity will be filled.  The actual ratio is sampled from
        Beta(8, 2) clipped to [partial_fill_min, 1.0].
    rejection_prob : float
        Probability (0–1) that any given order is outright rejected
        before reaching the exchange.  Default 2 % (0.02).
    rejection_on_circuit_break : bool
        Reject orders if the signal price would exceed the candle's
        intraday ±10 % circuit-breaker band.  Default True.
    seed : int | None
        Random seed for reproducibility.
    """
    slippage_pct:                float = 0.0005   # 0.05 %
    volatility_scaled_slippage:  bool  = True
    delay_candles:               int   = 1        # next-bar
    order_ttl_candles:           int   = 5        # cancel after 5 bars
    enable_partial_fills:        bool  = True
    partial_fill_min:            float = 0.70     # minimum 70 % fill
    rejection_prob:              float = 0.02     # 2 % rejection rate
    rejection_on_circuit_break:  bool  = True
    seed:                        Optional[int] = None


# ─── Data classes for orders and execution results ────────────────────────────

@dataclass
class PendingOrder:
    """An order submitted but not yet executed."""
    order_id:       str
    symbol:         str
    side:           OrderSide
    quantity:       int
    signal_price:   float           # price at signal generation
    submitted_at:   int             # candle index of submission
    execute_at:     int             # candle index when it should fill
    expires_at:     int             # candle index when it expires
    metadata:       Dict[str, Any] = field(default_factory=dict)
    status:         OrderStatus = OrderStatus.PENDING


@dataclass
class ExecutionResult:
    """
    Result of attempting to fill a pending order.

    The key fields for strategy logic:
    - ``status``              : FILLED / PARTIAL / REJECTED / EXPIRED
    - ``filled_quantity``     : shares actually executed (0 if rejected)
    - ``fill_price``          : price after slippage (None if not filled)
    - ``slippage_cost``       : total ₹ slippage paid (both legs)
    - ``fill_ratio``          : filled_quantity / requested_quantity
    """
    order_id:           str
    symbol:             str
    side:               OrderSide
    requested_quantity: int
    filled_quantity:    int
    fill_price:         Optional[float]
    signal_price:       float
    slippage_pct_actual: float          # realized slippage as fraction
    slippage_cost:      float           # ₹ slippage = |fill-signal| × qty
    fill_ratio:         float           # filled / requested
    status:             OrderStatus
    rejection_reason:   Optional[RejectionReason]
    submitted_at:       int             # candle index
    filled_at:          int             # candle index
    delay_candles:      int             # actual candles waited
    candle_ohlcv:       Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["side"]             = self.side.value
        d["status"]           = self.status.value
        d["rejection_reason"] = self.rejection_reason.value if self.rejection_reason else None
        return d

    @property
    def is_filled(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.PARTIAL)


# ─── Main simulator ───────────────────────────────────────────────────────────

class ExecutionSimulator:
    """
    Realistic order-execution simulator for backtesting.

    Thread-safety: NOT thread-safe.  Use one instance per backtest run.

    Parameters
    ----------
    config : ExecutionConfig
        Execution parameters (slippage, delay, partials, rejection).
    seed : int | None
        Overrides ``config.seed`` if provided.
    """

    def __init__(
        self,
        config: Optional[ExecutionConfig] = None,
        seed:   Optional[int]             = None,
    ):
        self.config = config or ExecutionConfig()
        _seed = seed if seed is not None else self.config.seed
        self.rng = np.random.default_rng(_seed)
        random.seed(_seed)          # for rejection draws

        # Order queues
        self._pending:  Dict[str, PendingOrder]   = {}   # order_id → PendingOrder
        self._history:  List[ExecutionResult]      = []

        # Counters
        self._total_submitted  = 0
        self._total_filled     = 0
        self._total_partial    = 0
        self._total_rejected   = 0
        self._total_expired    = 0
        self._total_slippage   = 0.0

        logger.info(
            f"ExecutionSimulator ready | "
            f"slippage={self.config.slippage_pct*100:.3f}% | "
            f"delay={self.config.delay_candles} candle(s) | "
            f"partial_fills={self.config.enable_partial_fills} | "
            f"rejection={self.config.rejection_prob*100:.1f}%"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def submit_order(
        self,
        candle_index: int,
        symbol:       str,
        side:         str,             # "BUY" or "SELL"
        quantity:     int,
        signal_price: float,
        candle:       Optional[Dict[str, float]] = None,
        metadata:     Optional[Dict[str, Any]]   = None,
    ) -> str:
        """
        Submit an order for future execution.

        The order enters a pending queue and will be processed after
        ``config.delay_candles`` candles.  Call
        :meth:`process_pending_orders` on every subsequent candle.

        Parameters
        ----------
        candle_index : int
            Zero-based index of the **current** candle (signal bar).
        symbol : str
            Instrument name.
        side : str
            ``"BUY"`` or ``"SELL"``.
        quantity : int
            Requested shares / units.
        signal_price : float
            The price seen by the strategy (usually candle close).
        candle : dict | None
            Full candle dict with keys ``open, high, low, close, volume``.
            Used for circuit-breaker checks on submission.
        metadata : dict | None
            Any additional context you want carried through to the result.

        Returns
        -------
        str
            Unique order ID (UUID).
        """
        order_id = str(uuid.uuid4())[:12]
        side_enum = OrderSide(side.upper())

        execute_at = candle_index + self.config.delay_candles
        expires_at = execute_at + self.config.order_ttl_candles

        order = PendingOrder(
            order_id=order_id,
            symbol=symbol,
            side=side_enum,
            quantity=quantity,
            signal_price=signal_price,
            submitted_at=candle_index,
            execute_at=execute_at,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        self._pending[order_id] = order
        self._total_submitted += 1

        logger.debug(
            f"ORDER QUEUED  [{order_id}] {side} {quantity}×{symbol} "
            f"@ signal ₹{signal_price:.2f} | executes bar {execute_at}"
        )
        return order_id

    def process_pending_orders(
        self,
        candle_index: int,
        candle:       Dict[str, float],
    ) -> List[ExecutionResult]:
        """
        Attempt to fill all pending orders that are due on *candle_index*.

        Call this at the **start** of every bar before strategy logic runs,
        passing the current bar's OHLCV dict.

        Parameters
        ----------
        candle_index : int
            Current bar index.
        candle : dict
            Current bar: ``{"open", "high", "low", "close", "volume"}``.

        Returns
        -------
        List[ExecutionResult]
            One result object per order that was either filled, partially
            filled, rejected, or expired this bar.
        """
        results: List[ExecutionResult] = []
        expired_ids: List[str]         = []

        for order_id, order in list(self._pending.items()):

            # Not yet due
            if candle_index < order.execute_at:
                continue

            # Expired
            if candle_index > order.expires_at:
                result = self._build_result(
                    order, candle_index, candle,
                    status=OrderStatus.EXPIRED,
                )
                expired_ids.append(order_id)
                results.append(result)
                self._total_expired += 1
                logger.debug(f"ORDER EXPIRED [{order_id}]")
                continue

            # Attempt execution
            result = self._attempt_fill(order, candle_index, candle)
            results.append(result)
            expired_ids.append(order_id)  # remove from pending regardless

        # Clean up processed orders
        for oid in expired_ids:
            self._pending.pop(oid, None)

        self._history.extend(results)
        return results

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific pending order. Returns True if found."""
        if order_id in self._pending:
            del self._pending[order_id]
            logger.debug(f"ORDER CANCELLED [{order_id}]")
            return True
        return False

    def cancel_all_pending(self) -> int:
        """Cancel all pending orders. Returns count cancelled."""
        n = len(self._pending)
        self._pending.clear()
        logger.info(f"Cancelled {n} pending orders")
        return n

    # ── Internals ─────────────────────────────────────────────────────────────

    def _attempt_fill(
        self,
        order:        PendingOrder,
        candle_index: int,
        candle:       Dict[str, float],
    ) -> ExecutionResult:
        """Core fill logic: rejection → partial fills → slippage."""

        # ── 1. Order rejection ────────────────────────────────────────────────
        rejection_reason = self._check_rejection(order, candle)
        if rejection_reason is not None:
            self._total_rejected += 1
            logger.debug(
                f"ORDER REJECTED [{order.order_id}] "
                f"reason={rejection_reason.value}"
            )
            return self._build_result(
                order, candle_index, candle,
                status=OrderStatus.REJECTED,
                rejection_reason=rejection_reason,
            )

        # ── 2. Determine fill quantity (partial fills) ────────────────────────
        fill_qty, is_partial = self._determine_fill_quantity(order)
        status = OrderStatus.PARTIAL if is_partial else OrderStatus.FILLED

        # ── 3. Compute fill price with slippage ───────────────────────────────
        fill_price, actual_slippage_pct = self._compute_fill_price(
            order.signal_price, order.side, candle
        )
        slippage_cost = abs(fill_price - order.signal_price) * fill_qty

        # ── 4. Update counters ────────────────────────────────────────────────
        if is_partial:
            self._total_partial += 1
        else:
            self._total_filled += 1
        self._total_slippage += slippage_cost

        delay = candle_index - order.submitted_at
        logger.debug(
            f"ORDER {'PARTIAL' if is_partial else 'FILLED '} [{order.order_id}] "
            f"{order.side.value} {fill_qty}/{order.quantity}×{order.symbol} "
            f"@ ₹{fill_price:.4f} (slip={actual_slippage_pct*100:.4f}%, "
            f"₹{slippage_cost:.2f}) | delay={delay} bar(s)"
        )

        return ExecutionResult(
            order_id            = order.order_id,
            symbol              = order.symbol,
            side                = order.side,
            requested_quantity  = order.quantity,
            filled_quantity     = fill_qty,
            fill_price          = fill_price,
            signal_price        = order.signal_price,
            slippage_pct_actual = actual_slippage_pct,
            slippage_cost       = round(slippage_cost, 4),
            fill_ratio          = fill_qty / order.quantity,
            status              = status,
            rejection_reason    = None,
            submitted_at        = order.submitted_at,
            filled_at           = candle_index,
            delay_candles       = delay,
            candle_ohlcv        = {k: candle.get(k, 0.0)
                                   for k in ("open", "high", "low", "close", "volume")},
        )

    def _check_rejection(
        self,
        order:  PendingOrder,
        candle: Dict[str, float],
    ) -> Optional[RejectionReason]:
        """
        Return a RejectionReason if the order should be rejected, else None.

        Checks (in order):
        1. Circuit-breaker: signal price outside ±10 % of candle open.
        2. Zero volume: no liquidity bar.
        3. Random broker rejection (configurable probability).
        """
        # Circuit-breaker check
        if self.config.rejection_on_circuit_break:
            open_px = candle.get("open", order.signal_price)
            circuit_band = open_px * 0.10
            if abs(order.signal_price - open_px) > circuit_band:
                return RejectionReason.CIRCUIT_BREAK

        # Zero volume = circuit limit hit / no market
        volume = candle.get("volume", 1)
        if volume == 0:
            return RejectionReason.LIQUIDITY

        # Random rejection
        if self.config.rejection_prob > 0:
            if self.rng.random() < self.config.rejection_prob:
                # Vary rejection reason for realism
                reasons = [
                    RejectionReason.RANDOM,
                    RejectionReason.RISK_CHECK,
                    RejectionReason.LIQUIDITY,
                ]
                return self.rng.choice(reasons)  # type: ignore[arg-type]

        return None

    def _determine_fill_quantity(
        self,
        order: PendingOrder,
    ) -> tuple[int, bool]:
        """
        Return (filled_qty, is_partial).

        If partial fills are disabled, always returns full quantity.
        Otherwise samples a fill ratio from Beta(8, 2) clipped to
        [partial_fill_min, 1.0].  Beta(8,2) is right-skewed (usually
        close to full-fill) which matches realistic intraday liquidity.
        """
        if not self.config.enable_partial_fills:
            return order.quantity, False

        # Beta(8, 2): mean ≈ 0.80, concentrated near 1.0
        raw_ratio = float(self.rng.beta(8, 2))
        fill_ratio = np.clip(raw_ratio, self.config.partial_fill_min, 1.0)
        fill_qty   = max(1, int(order.quantity * fill_ratio))

        is_partial = fill_qty < order.quantity
        return fill_qty, is_partial

    def _compute_fill_price(
        self,
        signal_price:  float,
        side:          OrderSide,
        candle:        Dict[str, float],
    ) -> tuple[float, float]:
        """
        Return (fill_price, actual_slippage_fraction).

        Base slippage is ``config.slippage_pct``.
        If ``volatility_scaled_slippage`` is enabled, additional slippage
        is proportional to the candle's price range (high-low)/close,
        capped at 3× the base rate.  This makes execution worse on
        volatile bars — as happens in real Indian markets.
        """
        base_slip = self.config.slippage_pct

        vol_extra = 0.0
        if self.config.volatility_scaled_slippage:
            close  = candle.get("close", signal_price)
            high   = candle.get("high",  signal_price)
            low    = candle.get("low",   signal_price)
            if close > 0:
                candle_range_pct = (high - low) / close
                # Add up to 2× the base slip based on candle range
                vol_extra = min(candle_range_pct * 0.10 * base_slip * 20,
                                2.0 * base_slip)

        total_slip = base_slip + vol_extra

        # Adverse fill: BUY → higher price, SELL → lower price
        if side == OrderSide.BUY:
            fill_price = signal_price * (1.0 + total_slip)
        else:
            fill_price = signal_price * (1.0 - total_slip)

        # Clamp to candle range (can't fill outside the bar's traded range)
        candle_high  = candle.get("high",  fill_price)
        candle_low   = candle.get("low",   fill_price)
        fill_price   = float(np.clip(fill_price, candle_low, candle_high))

        actual_slip  = abs(fill_price - signal_price) / signal_price if signal_price > 0 else 0.0
        return round(fill_price, 4), round(actual_slip, 8)

    @staticmethod
    def _build_result(
        order:            PendingOrder,
        candle_index:     int,
        candle:           Dict[str, float],
        status:           OrderStatus = OrderStatus.EXPIRED,
        rejection_reason: Optional[RejectionReason] = None,
    ) -> ExecutionResult:
        """Build a zero-fill result (rejection / expiry)."""
        return ExecutionResult(
            order_id            = order.order_id,
            symbol              = order.symbol,
            side                = order.side,
            requested_quantity  = order.quantity,
            filled_quantity     = 0,
            fill_price          = None,
            signal_price        = order.signal_price,
            slippage_pct_actual = 0.0,
            slippage_cost       = 0.0,
            fill_ratio          = 0.0,
            status              = status,
            rejection_reason    = rejection_reason,
            submitted_at        = order.submitted_at,
            filled_at           = candle_index,
            delay_candles       = candle_index - order.submitted_at,
            candle_ohlcv        = {k: candle.get(k, 0.0)
                                   for k in ("open", "high", "low", "close", "volume")},
        )

    # ── Reporting ─────────────────────────────────────────────────────────────

    @property
    def pending_count(self) -> int:
        """Number of orders currently in the pending queue."""
        return len(self._pending)

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Aggregate execution quality statistics.

        Returns a dict suitable for inclusion in backtest results.
        """
        filled   = [r for r in self._history if r.status == OrderStatus.FILLED]
        partial  = [r for r in self._history if r.status == OrderStatus.PARTIAL]
        rejected = [r for r in self._history if r.status == OrderStatus.REJECTED]
        expired  = [r for r in self._history if r.status == OrderStatus.EXPIRED]
        all_exec = filled + partial

        avg_slippage_pct = (
            float(np.mean([r.slippage_pct_actual for r in all_exec]))
            if all_exec else 0.0
        )
        avg_delay = (
            float(np.mean([r.delay_candles for r in all_exec]))
            if all_exec else 0.0
        )
        avg_fill_ratio = (
            float(np.mean([r.fill_ratio for r in all_exec]))
            if all_exec else 0.0
        )

        return {
            "total_submitted":      self._total_submitted,
            "total_filled":         self._total_filled,
            "total_partial":        self._total_partial,
            "total_rejected":       self._total_rejected,
            "total_expired":        self._total_expired,
            "fill_rate_pct":        round(
                (self._total_filled + self._total_partial) /
                max(self._total_submitted, 1) * 100, 2
            ),
            "rejection_rate_pct":   round(
                self._total_rejected / max(self._total_submitted, 1) * 100, 2
            ),
            "avg_slippage_pct":     round(avg_slippage_pct * 100, 5),
            "total_slippage_cost":  round(self._total_slippage, 2),
            "avg_delay_candles":    round(avg_delay, 2),
            "avg_fill_ratio":       round(avg_fill_ratio, 4),
            "config": {
                "slippage_pct":          self.config.slippage_pct,
                "volatility_scaled":     self.config.volatility_scaled_slippage,
                "delay_candles":         self.config.delay_candles,
                "enable_partial_fills":  self.config.enable_partial_fills,
                "partial_fill_min":      self.config.partial_fill_min,
                "rejection_prob":        self.config.rejection_prob,
            },
        }

    def get_fill_history(self) -> List[Dict[str, Any]]:
        """Return all execution results as a list of dicts."""
        return [r.to_dict() for r in self._history]

    def reset(self):
        """Reset all state (new backtest run)."""
        self._pending.clear()
        self._history.clear()
        self._total_submitted  = 0
        self._total_filled     = 0
        self._total_partial    = 0
        self._total_rejected   = 0
        self._total_expired    = 0
        self._total_slippage   = 0.0
        logger.info("ExecutionSimulator reset")


# ─── Convenience factory functions ────────────────────────────────────────────

def conservative_execution(seed: Optional[int] = None) -> ExecutionSimulator:
    """
    Minimal-friction execution config.
    Good for liquid large-cap NSE stocks (NIFTY50 constituents).
    """
    return ExecutionSimulator(ExecutionConfig(
        slippage_pct               = 0.0003,   # 0.03 %
        volatility_scaled_slippage = True,
        delay_candles              = 1,
        enable_partial_fills       = True,
        partial_fill_min           = 0.90,
        rejection_prob             = 0.005,
    ), seed=seed)


def realistic_execution(seed: Optional[int] = None) -> ExecutionSimulator:
    """
    Default realistic config for mid-cap NSE stocks.
    """
    return ExecutionSimulator(ExecutionConfig(
        slippage_pct               = 0.0005,   # 0.05 %
        volatility_scaled_slippage = True,
        delay_candles              = 1,
        enable_partial_fills       = True,
        partial_fill_min           = 0.70,
        rejection_prob             = 0.02,
    ), seed=seed)


def harsh_execution(seed: Optional[int] = None) -> ExecutionSimulator:
    """
    High-friction config for small-caps / illiquid instruments.
    Stress-tests strategy robustness.
    """
    return ExecutionSimulator(ExecutionConfig(
        slippage_pct               = 0.0020,   # 0.20 %
        volatility_scaled_slippage = True,
        delay_candles              = 2,        # 2-bar delay
        enable_partial_fills       = True,
        partial_fill_min           = 0.40,     # as low as 40 % fill
        rejection_prob             = 0.05,     # 5 % rejection
    ), seed=seed)


# ─── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sim = realistic_execution(seed=42)

    # Fake candles
    candle_open  = {"open": 2950.0, "high": 2975.0, "low": 2940.0, "close": 2960.0, "volume": 500_000}
    candle_next  = {"open": 2962.0, "high": 2990.0, "low": 2955.0, "close": 2985.0, "volume": 450_000}
    candle_next2 = {"open": 2986.0, "high": 3010.0, "low": 2975.0, "close": 3005.0, "volume": 420_000}

    print("\n" + "=" * 68)
    print("  ExecutionSimulator — Feature Test (RELIANCE 5-min)")
    print("=" * 68)

    # Submit 10 orders at bar 0
    order_ids = []
    for i in range(10):
        oid = sim.submit_order(
            candle_index=0,
            symbol="RELIANCE",
            side="BUY" if i % 2 == 0 else "SELL",
            quantity=100,
            signal_price=candle_open["close"],
            candle=candle_open,
        )
        order_ids.append(oid)

    print(f"\n  Submitted 10 orders | pending={sim.pending_count}")

    # Bar 1 — process
    fills1 = sim.process_pending_orders(1, candle_next)
    print(f"\n  Bar 1 fills: {len(fills1)}")
    for r in fills1:
        tag = f"{r.status.value:8s}" + (f" [{r.rejection_reason.value}]" if r.rejection_reason else "")
        print(
            f"   {r.side.value:4s} {r.filled_quantity:3d}/{r.requested_quantity} "
            f"@ ₹{r.fill_price or 0:,.2f}  slip=₹{r.slippage_cost:.2f}  {tag}"
        )

    # Bar 2 — any remaining?
    fills2 = sim.process_pending_orders(2, candle_next2)
    print(f"\n  Bar 2 fills: {len(fills2)}")

    stats = sim.get_execution_stats()
    print(f"\n  ── Execution Quality Stats ──────────────────────────────")
    print(f"   Fill rate         : {stats['fill_rate_pct']:.1f}%")
    print(f"   Rejection rate    : {stats['rejection_rate_pct']:.1f}%")
    print(f"   Avg slippage      : {stats['avg_slippage_pct']:.4f}%")
    print(f"   Total slip cost   : ₹{stats['total_slippage_cost']:.2f}")
    print(f"   Avg fill ratio    : {stats['avg_fill_ratio']:.2%}")
    print(f"   Avg delay         : {stats['avg_delay_candles']:.1f} candle(s)")
    print("=" * 68 + "\n")

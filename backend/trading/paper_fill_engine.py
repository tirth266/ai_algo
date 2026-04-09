"""
Paper Trading Fill Engine
=========================

Realistic order-fill simulation for paper (virtual) trading.

Replaces exact-price fills with market-microstructure-aware execution:

Features
────────
1. **Slippage model**
   - Base slippage (configurable, default 0.05 %)
   - Randomised extra slippage drawn from Uniform(0, extra_slippage)
   - Total: `slippage = base + random.uniform(0, extra)`

2. **Directional adverse fill**
   - BUY  → executed_price = signal_price × (1 + slippage)   [pays more]
   - SELL → executed_price = signal_price × (1 – slippage)   [receives less]

3. **Market impact (optional)**
   - Larger orders move the price more
   - Impact: `impact = impact_factor × sqrt(quantity / avg_daily_volume)`
   - Added on top of base slippage — configurable

4. **Minimum tick rounding**
   - Prices snapped to nearest ₹ 0.05 (NSE default tick)

5. **Three precision profiles** (convenience constructors)
   - `tight_fill()`   — liquid large-cap (NIFTY50 constituents)
   - `normal_fill()`  — mid-cap NSE stocks  ← default
   - `wide_fill()`    — small-cap / illiquid instruments

6. **Enriched trade record**
   Every processed order carries:
   - `signal_price`    — price at signal time
   - `executed_price`  — actual fill price (after slippage)
   - `slippage_applied`— total slippage fraction applied
   - `slippage_inr`    — ₹ slippage cost (|executed - signal| × qty)
   - `market_impact`   — extra impact fraction from order size

7. **Statistics tracking**
   - Total fills, total slippage cost, avg slippage %, fill history

Usage::

    from trading.paper_fill_engine import PaperFillEngine, FillConfig

    cfg = FillConfig(
        base_slippage    = 0.0005,   # 0.05 %
        extra_slippage   = 0.0003,   # up to 0.03 % extra randomness
        market_impact    = True,
        impact_factor    = 0.001,
        avg_daily_volume = 500_000,
        tick_size        = 0.05,
    )
    engine = PaperFillEngine(config=cfg, seed=42)

    # On a new signal:
    fill = engine.fill(
        side         = "BUY",
        signal_price = 2960.50,
        quantity     = 100,
        symbol       = "RELIANCE",
    )
    print(fill.executed_price)      # e.g. 2962.15
    print(fill.slippage_applied)    # e.g. 0.000556
    print(fill.slippage_inr)        # e.g. 165.0

    # Integration with existing Order object:
    order = Order(symbol="RELIANCE", quantity=100, side="BUY")
    enriched = engine.fill_order(order, signal_price=2960.50)
    # order.executed_price, order.signal_price, order.slippage_applied are now set
"""

from __future__ import annotations

import logging
import math
import random
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# NSE minimum tick size (default)
_DEFAULT_TICK = 0.05


# ─── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class FillConfig:
    """
    All fill-engine parameters in one place.

    Parameters
    ----------
    base_slippage : float
        Minimum slippage fraction always applied (default 0.05 % = 0.0005).
    extra_slippage : float
        Upper bound of random extra slippage drawn from Uniform(0, extra).
        Set to 0 to make slippage deterministic.
    market_impact : bool
        Enable order-size market impact (default True).
    impact_factor : float
        Scales market impact: impact ∝ impact_factor × √(qty / avg_vol).
        Typical range: 0.0005–0.002.
    avg_daily_volume : int
        Reference daily volume used for market impact normalisation.
    tick_size : float
        Minimum price increment (NSE default ₹ 0.05).
    seed : int | None
        Random seed.  None = non-reproducible.
    """
    base_slippage:    float = 0.0005    # 0.05 %
    extra_slippage:   float = 0.0003    # up to +0.03 %
    market_impact:    bool  = True
    impact_factor:    float = 0.001
    avg_daily_volume: int   = 500_000
    tick_size:        float = _DEFAULT_TICK
    seed:             Optional[int] = None


# ─── Fill result dataclass ─────────────────────────────────────────────────────

@dataclass
class FillResult:
    """
    Enriched fill record.  Every field is serialisable to JSON via
    ``fill.to_dict()``.

    Attributes
    ----------
    fill_id : str
        Unique identifier for this fill.
    symbol : str
        Instrument name.
    side : str
        ``"BUY"`` or ``"SELL"``.
    quantity : int
        Filled quantity.
    signal_price : float
        Price at which the strategy generated the signal.
    executed_price : float
        Actual fill price after slippage.  ALWAYS differs from signal_price.
    slippage_applied : float
        Total slippage fraction applied (base + random + impact).
    slippage_inr : float
        Rupee cost of slippage = |executed_price - signal_price| × quantity.
    base_slippage : float
        Deterministic component.
    random_slippage : float
        Randomly sampled component.
    market_impact : float
        Order-size impact component (0 if disabled).
    filled_at : str
        ISO-8601 timestamp of the fill.
    """
    fill_id:          str
    symbol:           str
    side:             str
    quantity:         int
    signal_price:     float
    executed_price:   float
    slippage_applied: float
    slippage_inr:     float
    base_slippage:    float
    random_slippage:  float
    market_impact:    float
    filled_at:        str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points (1 bp = 0.01 %)."""
        return round(self.slippage_applied * 10_000, 2)


# ─── Main fill engine ──────────────────────────────────────────────────────────

class PaperFillEngine:
    """
    Realistic fill engine for paper trading.

    Thread-safety: NOT thread-safe.  Use one instance per paper account.

    Parameters
    ----------
    config : FillConfig | None
        Fill configuration.  Defaults to ``FillConfig()`` (normal profile).
    seed : int | None
        Overrides ``config.seed`` if provided.
    """

    def __init__(
        self,
        config: Optional[FillConfig] = None,
        seed:   Optional[int] = None,
    ):
        self.config = config or FillConfig()
        _seed = seed if seed is not None else self.config.seed
        random.seed(_seed)

        # History and stats
        self._fills:           List[FillResult] = []
        self._total_fills      = 0
        self._total_slip_inr   = 0.0
        self._total_signal_val = 0.0

        logger.info(
            f"PaperFillEngine ready | "
            f"base_slip={self.config.base_slippage*100:.3f}% | "
            f"extra_slip={self.config.extra_slippage*100:.3f}% | "
            f"market_impact={self.config.market_impact}"
        )

    # ── Core fill logic ────────────────────────────────────────────────────────

    def fill(
        self,
        side:         str,
        signal_price: float,
        quantity:     int,
        symbol:       str = "UNKNOWN",
    ) -> FillResult:
        """
        Compute a realistic fill for a paper order.

        Parameters
        ----------
        side : str
            ``"BUY"`` or ``"SELL"`` (case-insensitive).
        signal_price : float
            The price the strategy observed when it generated the signal.
        quantity : int
            Number of shares / units.
        symbol : str
            Instrument name (used for logging and the FillResult).

        Returns
        -------
        FillResult
            Complete fill including ``executed_price``, ``slippage_applied``,
            etc.  ``executed_price`` is ALWAYS != ``signal_price``.
        """
        if signal_price <= 0:
            raise ValueError(f"signal_price must be positive, got {signal_price}")
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")

        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be 'BUY' or 'SELL', got {side}")

        # ── 1. Base slippage ──────────────────────────────────────────────────
        base = self.config.base_slippage

        # ── 2. Random extra slippage ──────────────────────────────────────────
        rand = random.uniform(0.0, self.config.extra_slippage)

        # ── 3. Market impact (size-dependent) ─────────────────────────────────
        impact = 0.0
        if self.config.market_impact and self.config.avg_daily_volume > 0:
            # Impact ∝ √(quantity / avg_daily_volume)
            impact = self.config.impact_factor * math.sqrt(
                quantity / self.config.avg_daily_volume
            )

        total_slip = base + rand + impact

        # ── 4. Directional adverse fill ───────────────────────────────────────
        #       BUY → buy at worse (higher) price
        #       SELL → sell at worse (lower) price
        if side == "BUY":
            raw_exec = signal_price * (1.0 + total_slip)
        else:
            raw_exec = signal_price * (1.0 - total_slip)

        # ── 5. Tick rounding ──────────────────────────────────────────────────
        tick = self.config.tick_size
        executed_price = round(round(raw_exec / tick) * tick, 4)

        # Safety: guarantee executed_price IS NOT signal_price
        # (tick rounding can sometimes snap back to signal_price on tiny moves)
        if executed_price == signal_price:
            if side == "BUY":
                executed_price = round(signal_price + tick, 4)
            else:
                executed_price = max(round(signal_price - tick, 4), tick)

        # Recompute actual slippage fraction after rounding
        actual_slip = abs(executed_price - signal_price) / signal_price

        # ── 6. Rupee slippage cost ────────────────────────────────────────────
        slip_inr = abs(executed_price - signal_price) * quantity

        # ── 7. Build result ───────────────────────────────────────────────────
        result = FillResult(
            fill_id          = str(uuid.uuid4())[:12],
            symbol           = symbol,
            side             = side,
            quantity         = quantity,
            signal_price     = round(signal_price,  4),
            executed_price   = executed_price,
            slippage_applied = round(actual_slip,   8),
            slippage_inr     = round(slip_inr,      4),
            base_slippage    = round(base,          8),
            random_slippage  = round(rand,          8),
            market_impact    = round(impact,        8),
        )

        # ── 8. Update stats ───────────────────────────────────────────────────
        self._fills.append(result)
        self._total_fills      += 1
        self._total_slip_inr   += slip_inr
        self._total_signal_val += signal_price * quantity

        logger.debug(
            f"FILL [{result.fill_id}] {side} {quantity}×{symbol} | "
            f"signal=₹{signal_price:.4f}  exec=₹{executed_price:.4f} | "
            f"slip={actual_slip*100:.4f}% ({result.slippage_bps:.2f} bps) | "
            f"₹{slip_inr:.2f} | "
            f"base={base*100:.4f}% rand={rand*100:.4f}% impact={impact*100:.4f}%"
        )

        return result

    def fill_order(
        self,
        order: Any,             # trading.broker_interface.Order
        signal_price: float,
    ) -> FillResult:
        """
        Fill an existing ``Order`` object in-place AND return the FillResult.

        Sets three new attributes on the order:
        - ``order.signal_price``     — original signal price
        - ``order.executed_price``   — slippage-adjusted fill price
        - ``order.slippage_applied`` — total slippage fraction
        - ``order.slippage_inr``     — Rupee slippage cost

        Also updates ``order.average_price`` and ``order.filled_quantity``
        (used by OrderManager / dashboard).

        Parameters
        ----------
        order : Order
            Existing ``trading.broker_interface.Order`` object.
        signal_price : float
            Price at signal generation time.

        Returns
        -------
        FillResult
            Full fill detail.
        """
        result = self.fill(
            side         = order.side,
            signal_price = signal_price,
            quantity     = order.quantity,
            symbol       = order.symbol,
        )

        # Enrich the order object with fill data
        order.signal_price     = result.signal_price
        order.executed_price   = result.executed_price
        order.slippage_applied = result.slippage_applied
        order.slippage_inr     = result.slippage_inr

        # Update standard Order fields used by downstream components
        order.average_price    = result.executed_price
        order.filled_quantity  = result.quantity
        order.pending_quantity = 0
        order.status           = "OPEN"          # filled, awaiting confirmation

        return result

    # ── Statistics ─────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """
        Aggregate fill quality statistics.

        Returns
        -------
        dict
            Keys: total_fills, total_slippage_inr, avg_slippage_pct,
            avg_slippage_bps, total_signal_value, slippage_pct_of_turnover,
            config.
        """
        avg_slip_pct = (
            sum(f.slippage_applied for f in self._fills) / len(self._fills) * 100
            if self._fills else 0.0
        )
        avg_slip_bps = avg_slip_pct * 100   # 1 % = 100 bps

        return {
            "total_fills":             self._total_fills,
            "total_slippage_inr":      round(self._total_slip_inr, 2),
            "avg_slippage_pct":        round(avg_slip_pct, 5),
            "avg_slippage_bps":        round(avg_slip_bps, 3),
            "total_signal_value_inr":  round(self._total_signal_val, 2),
            "slippage_pct_of_turnover": (
                round(self._total_slip_inr / self._total_signal_val * 100, 4)
                if self._total_signal_val > 0 else 0.0
            ),
            "config": {
                "base_slippage_pct":  self.config.base_slippage * 100,
                "extra_slippage_pct": self.config.extra_slippage * 100,
                "market_impact":      self.config.market_impact,
                "impact_factor":      self.config.impact_factor,
                "avg_daily_volume":   self.config.avg_daily_volume,
                "tick_size":          self.config.tick_size,
            },
        }

    def get_fill_history(self) -> List[Dict[str, Any]]:
        """Return all fills as a list of dicts (JSON-serialisable)."""
        return [f.to_dict() for f in self._fills]

    def reset_stats(self):
        """Clear fill history and reset counters."""
        self._fills.clear()
        self._total_fills      = 0
        self._total_slip_inr   = 0.0
        self._total_signal_val = 0.0
        logger.info("PaperFillEngine stats reset")


# ─── Convenience presets ───────────────────────────────────────────────────────

def tight_fill(seed: Optional[int] = None) -> PaperFillEngine:
    """
    Liquid large-cap preset (NIFTY50 / BANKNIFTY).

    slip = 0.03 % + Uniform(0, 0.01 %)
    """
    return PaperFillEngine(FillConfig(
        base_slippage    = 0.0003,
        extra_slippage   = 0.0001,
        market_impact    = True,
        impact_factor    = 0.0005,
        avg_daily_volume = 2_000_000,
        tick_size        = 0.05,
        seed             = seed,
    ))


def normal_fill(seed: Optional[int] = None) -> PaperFillEngine:
    """
    Default mid-cap NSE preset.

    slip = 0.05 % + Uniform(0, 0.03 %)
    """
    return PaperFillEngine(FillConfig(
        base_slippage    = 0.0005,
        extra_slippage   = 0.0003,
        market_impact    = True,
        impact_factor    = 0.001,
        avg_daily_volume = 500_000,
        tick_size        = 0.05,
        seed             = seed,
    ))


def wide_fill(seed: Optional[int] = None) -> PaperFillEngine:
    """
    Illiquid / small-cap preset (high spread, large impact).

    slip = 0.15 % + Uniform(0, 0.10 %)
    """
    return PaperFillEngine(FillConfig(
        base_slippage    = 0.0015,
        extra_slippage   = 0.0010,
        market_impact    = True,
        impact_factor    = 0.003,
        avg_daily_volume = 50_000,
        tick_size        = 0.05,
        seed             = seed,
    ))


# ─── PaperBroker: drop-in replacement for live broker in paper mode ───────────

class PaperBroker:
    """
    Lightweight paper-trading broker that wraps :class:`PaperFillEngine`.

    Acts as a **drop-in replacement** for a real broker in paper mode:
    - ``place_order()`` fills instantly with realistic slippage
    - ``get_positions()`` returns the current virtual book
    - ``get_account_balance()`` tracks virtual cash

    Usage::

        from trading.paper_fill_engine import PaperBroker, normal_fill

        paper = PaperBroker(
            initial_capital = 500_000,
            fill_engine     = normal_fill(seed=42),
        )

        # In your strategy loop:
        from trading.broker_interface import Order
        order = Order("RELIANCE", 100, "BUY")
        result = paper.place_order(order, signal_price=2960.50)
        print(result)
        # {'status': 'FILLED', 'order_id': '...', 'executed_price': 2962.10, ...}
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        fill_engine: Optional[PaperFillEngine] = None,
    ):
        self.capital      = initial_capital
        self.fill_engine  = fill_engine or normal_fill()
        self.positions:   Dict[str, Dict[str, Any]] = {}   # symbol → position dict
        self.order_book:  List[Dict[str, Any]] = []
        self._order_seq   = 0

        logger.info(
            f"PaperBroker initialised | capital=₹{initial_capital:,.2f}"
        )

    def place_order(
        self,
        order: Any,
        signal_price: Optional[float] = None,
        current_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fill an order in the paper book with realistic slippage.

        Parameters
        ----------
        order : Order
            ``trading.broker_interface.Order`` instance.
        signal_price : float | None
            Strategy signal price.  If not supplied, falls back to
            ``order.price`` or ``current_price`` (in that priority).

        Returns
        -------
        dict
            Result dict containing ``status``, ``order_id``,
            ``executed_price``, ``slippage_inr``, ``signal_price``.
        """
        # Resolve signal price
        sp = signal_price or order.price or current_price
        if sp is None or sp <= 0:
            return {
                "status": "REJECTED",
                "reason": "No valid signal_price available",
            }

        # Generate fill
        try:
            fill = self.fill_engine.fill_order(order=order, signal_price=sp)
        except Exception as exc:
            logger.error(f"Fill engine error: {exc}")
            return {"status": "REJECTED", "reason": str(exc)}

        # ── Capital check ─────────────────────────────────────────────────────
        trade_value = fill.executed_price * fill.quantity
        if order.side == "BUY" and trade_value > self.capital:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient capital: need ₹{trade_value:,.2f}, have ₹{self.capital:,.2f}",
            }

        # ── Update virtual book ────────────────────────────────────────────────
        self._update_position(order.symbol, order.side, fill.quantity, fill.executed_price)

        if order.side == "BUY":
            self.capital -= trade_value
        else:
            self.capital += trade_value

        # ── Assign order ID ────────────────────────────────────────────────────
        self._order_seq   += 1
        order_id = f"PAPER-{self._order_seq:06d}"
        order.order_id    = order_id
        order.status      = "COMPLETE"

        # ── Record in order book ───────────────────────────────────────────────
        record = {
            "order_id":       order_id,
            "symbol":         order.symbol,
            "side":           order.side,
            "quantity":       fill.quantity,
            "signal_price":   fill.signal_price,
            "executed_price": fill.executed_price,
            "slippage_pct":   round(fill.slippage_applied * 100, 4),
            "slippage_inr":   fill.slippage_inr,
            "slippage_bps":   fill.slippage_bps,
            "fill_id":        fill.fill_id,
            "timestamp":      fill.filled_at,
            "status":         "COMPLETE",
        }
        self.order_book.append(record)

        logger.info(
            f"PAPER ORDER FILLED [{order_id}] "
            f"{order.side} {fill.quantity}×{order.symbol} | "
            f"signal=₹{fill.signal_price:.2f}  exec=₹{fill.executed_price:.2f} | "
            f"slip=₹{fill.slippage_inr:.2f} ({fill.slippage_bps:.1f} bps) | "
            f"cash=₹{self.capital:,.2f}"
        )

        return {
            "status":         "FILLED",
            "order_id":       order_id,
            "executed_price": fill.executed_price,
            "signal_price":   fill.signal_price,
            "slippage_inr":   fill.slippage_inr,
            "slippage_bps":   fill.slippage_bps,
            "fill_id":        fill.fill_id,
        }

    def _update_position(
        self,
        symbol:    str,
        side:      str,
        quantity:  int,
        price:     float,
    ):
        """Update the virtual position book after a fill."""
        pos = self.positions.get(symbol, {
            "symbol":        symbol,
            "quantity":      0,
            "average_price": 0.0,
            "realized_pnl":  0.0,
        })

        if side == "BUY":
            # Increase long position (or reduce short)
            old_qty = pos["quantity"]
            old_avg = pos["average_price"]
            new_qty = old_qty + quantity
            if new_qty != 0:
                pos["average_price"] = (
                    (old_avg * max(old_qty, 0) + price * quantity) /
                    max(new_qty, quantity)
                )
            pos["quantity"] = new_qty
        else:
            # Reduce long (or increase short)
            old_qty = pos["quantity"]
            if old_qty > 0:
                closed = min(old_qty, quantity)
                pos["realized_pnl"] += (price - pos["average_price"]) * closed
            pos["quantity"] = old_qty - quantity

        self.positions[symbol] = pos

    def get_positions(self) -> List[Dict[str, Any]]:
        """Return current virtual positions."""
        return [p for p in self.positions.values() if p["quantity"] != 0]

    def get_account_balance(self) -> Dict[str, Any]:
        """Return virtual account balance."""
        return {
            "cash":           round(self.capital, 2),
            "positions_value": sum(
                p["quantity"] * p["average_price"]
                for p in self.positions.values()
                if p["quantity"] > 0
            ),
            "total_realized_pnl": round(
                sum(p.get("realized_pnl", 0) for p in self.positions.values()), 2
            ),
        }

    def get_order_book(self) -> List[Dict[str, Any]]:
        """Return all paper order records."""
        return list(self.order_book)

    def get_fill_stats(self) -> Dict[str, Any]:
        """Return fill-engine statistics."""
        return self.fill_engine.get_stats()


# ─── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("\n" + "=" * 70)
    print("  PaperFillEngine — Feature Verification")
    print("=" * 70)

    # ── 1. Basic fill test ────────────────────────────────────────────────────
    engine = normal_fill(seed=99)

    scenarios = [
        ("BUY",  "RELIANCE", 2960.50,  100),
        ("SELL", "RELIANCE", 2960.50,  100),
        ("BUY",  "NIFTY50",  22_150.0, 50),
        ("SELL", "TATASTEEL", 140.25,  500),  # large qty → market impact
        ("BUY",  "SBIN",      820.00,    1),  # min qty → tiny impact
    ]

    for side, sym, price, qty in scenarios:
        fill = engine.fill(side, price, qty, sym)
        assert fill.executed_price != price, "FAIL: exec == signal (no slippage!)"
        if side == "BUY":
            assert fill.executed_price > price, "FAIL: BUY exec should be HIGHER"
        else:
            assert fill.executed_price < price, "FAIL: SELL exec should be LOWER"

        print(
            f"  {side:4s} {qty:4d}×{sym:<12s} "
            f"signal=₹{price:>10,.2f}  "
            f"exec=₹{fill.executed_price:>10,.2f}  "
            f"slip={fill.slippage_bps:5.1f} bps  "
            f"₹{fill.slippage_inr:>8,.2f}"
        )

    stats = engine.get_stats()
    print(f"\n  Summary over {stats['total_fills']} fills:")
    print(f"    Avg slip  : {stats['avg_slippage_bps']:.2f} bps")
    print(f"    Total slip: ₹{stats['total_slippage_inr']:,.2f}")

    # ── 2. PaperBroker test ───────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("  PaperBroker — Order book test")
    print("-" * 70)

    # Simulate broker_interface.Order without importing it
    class _MockOrder:
        def __init__(self, symbol, quantity, side, price=None):
            self.symbol   = symbol
            self.quantity = quantity
            self.side     = side.upper()
            self.price    = price
            self.order_id = None
            self.status   = "PENDING"

    broker = PaperBroker(initial_capital=500_000, fill_engine=tight_fill(seed=0))

    trades = [
        ("RELIANCE", 50, "BUY",  2960.50),
        ("TCS",      10, "BUY",  4105.00),
        ("RELIANCE", 50, "SELL", 2990.00),
        ("NIFTY50",   2, "BUY", 22200.00),
    ]
    for sym, qty, side, sp in trades:
        o = _MockOrder(sym, qty, side, sp)
        r = broker.place_order(o, signal_price=sp)
        print(
            f"  {side:4s} {qty}×{sym:<10s}  "
            f"signal=₹{sp:>10,.2f}  "
            f"exec=₹{r['executed_price']:>10,.2f}  "
            f"slip={r['slippage_bps']:5.1f} bps  [{r['status']}]"
        )

    bal = broker.get_account_balance()
    print(f"\n  Cash remaining : ₹{bal['cash']:>12,.2f}")
    print(f"  Realised PnL   : ₹{bal['total_realized_pnl']:>12,.2f}")
    pos = broker.get_positions()
    print(f"  Open positions : {len(pos)}")

    # ── 3. Tick guarantee — no exact-price fills ──────────────────────────────
    print("\n" + "-" * 70)
    print("  Guarantee: executed_price != signal_price (1 000 fills)")
    eng2 = PaperFillEngine(FillConfig(base_slippage=0.0001, extra_slippage=0.0), seed=7)
    failures = 0
    for _ in range(1000):
        f = eng2.fill("BUY", 100.0, 1, "TEST")
        if f.executed_price == 100.0:
            failures += 1
    print(f"  Exact-price fills: {failures}/1000  (expected: 0)")
    assert failures == 0, "FAIL: some fills matched exact signal price!"

    print("\n" + "=" * 70)
    print("  All assertions passed ✓")
    print("=" * 70 + "\n")

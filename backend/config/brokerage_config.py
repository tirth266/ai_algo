"""
AngelOne Indian Brokerage Cost Model — Configuration & Calculator
=================================================================

Single source of truth for all transaction-cost rates used in backtesting.

Cost components per order leg (entry and exit are separate legs):

    ┌─────────────────────────────────────────────────────────────┐
    │  Component            Rate             Applied on           │
    ├─────────────────────────────────────────────────────────────┤
    │  Brokerage      min(0.25% × value, ₹20)   both legs        │
    │  STT            0.025% (intraday)           SELL leg only   │
    │                 0.100% (delivery)           SELL leg only   │
    │  NSE Txn Chgs   0.00325% × value            both legs      │
    │  SEBI Charges   0.0001% × value             both legs      │
    │  Stamp Duty     0.003% × value              BUY leg only   │
    │  GST            18% × (brokerage + txn)     both legs      │
    │  Slippage       configurable %              both legs       │
    └─────────────────────────────────────────────────────────────┘

Net PnL = Gross PnL − total_cost
total_cost = entry_cost + exit_cost
           = (brokerage + txn + sebi + stamp + gst + slippage) × 2 legs
             + STT on SELL leg

All rates can be overridden via environment variables so they stay
up to date without touching source code.

Usage::

    from config.brokerage_config import BrokerageCostModel, ANGELONE_INTRADAY

    cost_model = BrokerageCostModel()           # picks up env-var overrides
    entry = cost_model.calculate_entry_cost(
        price=500.0, quantity=100, action="BUY"
    )
    exit_ = cost_model.calculate_exit_cost(
        price=515.0, quantity=100, action="BUY"   # closing a long
    )
    breakdown = cost_model.full_trade_breakdown(entry, exit_)
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Literal

logger = logging.getLogger(__name__)

# ─── helpers ──────────────────────────────────────────────────────────────────

def _env_float(key: str, default: float) -> float:
    """Read a float from env, fall back to *default*."""
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        logger.warning(f"Invalid env value for {key!r}; using default {default}")
        return default


# ─── Rate constants (AngelOne, NSE segment, FY 2025–26) ───────────────────────

# Brokerage: flat 0.25 % or ₹ 20 — whichever is lower
ANGELONE_BROKERAGE_PCT   = _env_float("BROKERAGE_PCT",         0.0025)   # 0.25 %
ANGELONE_BROKERAGE_CAP   = _env_float("BROKERAGE_CAP_RS",      20.00)    # ₹ 20 max

# STT (Securities Transaction Tax) — SELL side only
STT_INTRADAY_PCT         = _env_float("STT_INTRADAY_PCT",       0.00025)  # 0.025 %
STT_DELIVERY_PCT         = _env_float("STT_DELIVERY_PCT",       0.001)    # 0.100 %

# NSE transaction charges
NSE_TXN_CHARGES_PCT      = _env_float("NSE_TXN_CHARGES_PCT",    0.0000325) # 0.00325 %

# SEBI charges (₹ 10 per crore → ~0.000010 %)
SEBI_CHARGES_PCT         = _env_float("SEBI_CHARGES_PCT",       0.0000001) # 0.00001 %

# Stamp duty — BUY side only (delivery: 0.015 %, intraday: 0.003 %)
STAMP_DUTY_INTRADAY_PCT  = _env_float("STAMP_DUTY_INTRADAY_PCT", 0.00003)  # 0.003 %
STAMP_DUTY_DELIVERY_PCT  = _env_float("STAMP_DUTY_DELIVERY_PCT", 0.00015)  # 0.015 %

# GST — 18 % on (brokerage + NSE txn charges)
GST_PCT                  = _env_float("GST_PCT",                0.18)     # 18 %

# Default slippage — configurable per strategy/session
DEFAULT_SLIPPAGE_PCT     = _env_float("DEFAULT_SLIPPAGE_PCT",   0.0005)   # 0.05 %


# ─── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class LegCost:
    """
    Cost breakdown for a single order leg (entry OR exit).

    All values are in ₹.
    """
    trade_value:         float = 0.0   # price × quantity
    slippage_cost:       float = 0.0   # slippage ₹ amount
    execution_price:     float = 0.0   # price after slippage
    brokerage:           float = 0.0
    stt:                 float = 0.0   # non-zero only on SELL leg
    nse_txn_charges:     float = 0.0
    sebi_charges:        float = 0.0
    stamp_duty:          float = 0.0   # non-zero only on BUY leg
    gst:                 float = 0.0   # 18 % on brokerage + nse_txn
    total:               float = 0.0   # sum of all cost components

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TradeCostBreakdown:
    """
    Full round-trip cost breakdown for one completed trade.

    Attributes:
        entry:       LegCost for the entry order.
        exit:        LegCost for the exit order.
        gross_pnl:   P&L before any costs.
        total_cost:  entry.total + exit.total  (₹).
        net_pnl:     gross_pnl − total_cost  (₹).
        cost_as_pct_of_gross: |total_cost / gross_pnl| × 100 if gross ≠ 0.
    """
    entry:                 LegCost = field(default_factory=LegCost)
    exit:                  LegCost = field(default_factory=LegCost)
    gross_pnl:             float = 0.0
    total_cost:            float = 0.0
    net_pnl:               float = 0.0
    cost_as_pct_of_gross:  float = 0.0   # % of gross eaten by costs

    def to_dict(self) -> dict:
        return {
            "entry":                 self.entry.to_dict(),
            "exit":                  self.exit.to_dict(),
            "gross_pnl":             round(self.gross_pnl, 4),
            "total_cost":            round(self.total_cost, 4),
            "net_pnl":               round(self.net_pnl, 4),
            "cost_as_pct_of_gross":  round(self.cost_as_pct_of_gross, 2),
        }


# ─── Core calculation engine ───────────────────────────────────────────────────

class BrokerageCostModel:
    """
    AngelOne (NSE) realistic cost model for backtesting.

    Calculates the full cost of every order leg — entry and exit —
    and produces a ``TradeCostBreakdown`` with:

    - ``gross_pnl``                 price move × quantity
    - ``total_cost`` (₹)           brokerage + STT + txn + sebi + stamp + gst + slippage
    - ``net_pnl``                   gross_pnl − total_cost

    Parameters
    ----------
    is_delivery : bool
        True → use delivery STT / stamp rates.
        False (default) → use intraday MIS rates.
    slippage_pct : float
        Market-impact slippage per leg as a fraction of price.
        Default: 0.05 % (``DEFAULT_SLIPPAGE_PCT``).
    brokerage_pct : float
        Brokerage percentage per order per leg.
    brokerage_cap : float
        Maximum brokerage per order per leg in ₹.
    nse_txn_charges_pct, sebi_charges_pct, gst_pct, …
        Override individual cost components if needed.
    """

    def __init__(
        self,
        is_delivery:           bool  = False,
        slippage_pct:          float = DEFAULT_SLIPPAGE_PCT,
        brokerage_pct:         float = ANGELONE_BROKERAGE_PCT,
        brokerage_cap:         float = ANGELONE_BROKERAGE_CAP,
        stt_intraday_pct:      float = STT_INTRADAY_PCT,
        stt_delivery_pct:      float = STT_DELIVERY_PCT,
        nse_txn_charges_pct:   float = NSE_TXN_CHARGES_PCT,
        sebi_charges_pct:      float = SEBI_CHARGES_PCT,
        stamp_duty_intraday_pct: float = STAMP_DUTY_INTRADAY_PCT,
        stamp_duty_delivery_pct: float = STAMP_DUTY_DELIVERY_PCT,
        gst_pct:               float = GST_PCT,
    ):
        self.is_delivery          = is_delivery
        self.slippage_pct         = slippage_pct
        self.brokerage_pct        = brokerage_pct
        self.brokerage_cap        = brokerage_cap
        self.stt_intraday_pct     = stt_intraday_pct
        self.stt_delivery_pct     = stt_delivery_pct
        self.nse_txn_charges_pct  = nse_txn_charges_pct
        self.sebi_charges_pct     = sebi_charges_pct
        self.stamp_duty_intraday_pct = stamp_duty_intraday_pct
        self.stamp_duty_delivery_pct = stamp_duty_delivery_pct
        self.gst_pct              = gst_pct

        logger.info(
            "BrokerageCostModel initialised | "
            f"mode={'DELIVERY' if is_delivery else 'INTRADAY'} | "
            f"slippage={slippage_pct*100:.3f}% | "
            f"brokerage=min({brokerage_pct*100:.2f}%, ₹{brokerage_cap})"
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _brokerage(self, trade_value: float) -> float:
        """0.25 % OR ₹ 20 — whichever is LOWER (AngelOne flat fee model)."""
        return min(trade_value * self.brokerage_pct, self.brokerage_cap)

    def _stt(self, trade_value: float, is_sell_leg: bool) -> float:
        """STT is charged only on the SELL leg."""
        if not is_sell_leg:
            return 0.0
        rate = self.stt_delivery_pct if self.is_delivery else self.stt_intraday_pct
        return trade_value * rate

    def _nse_txn(self, trade_value: float) -> float:
        return trade_value * self.nse_txn_charges_pct

    def _sebi(self, trade_value: float) -> float:
        return trade_value * self.sebi_charges_pct

    def _stamp(self, trade_value: float, is_buy_leg: bool) -> float:
        """Stamp duty is charged only on the BUY leg."""
        if not is_buy_leg:
            return 0.0
        rate = self.stamp_duty_delivery_pct if self.is_delivery else self.stamp_duty_intraday_pct
        return trade_value * rate

    def _gst(self, brokerage: float, nse_txn: float) -> float:
        """18 % GST on (brokerage + NSE txn charges)."""
        return (brokerage + nse_txn) * self.gst_pct

    def _apply_slippage(
        self,
        price: float,
        is_buy_action: bool,
    ) -> tuple[float, float]:
        """
        Return (execution_price, slippage_cost_per_unit).

        BUY  → fills slightly higher (adverse slippage).
        SELL → fills slightly lower  (adverse slippage).
        """
        slip = price * self.slippage_pct
        exec_price = (price + slip) if is_buy_action else (price - slip)
        return exec_price, slip

    # ── Public API ─────────────────────────────────────────────────────────────

    def calculate_entry_cost(
        self,
        price:    float,
        quantity: int,
        action:   Literal["BUY", "SELL"],
    ) -> LegCost:
        """
        Compute all costs for the entry order leg.

        Parameters
        ----------
        price :    Candle close price (or limit price).
        quantity : Number of shares / units.
        action :   ``"BUY"`` for long entry, ``"SELL"`` for short entry.

        Returns
        -------
        LegCost
            Full cost breakdown including slippage-adjusted execution price.
        """
        is_buy_action = (action == "BUY")
        exec_price, slip_per_unit = self._apply_slippage(price, is_buy_action)
        trade_value    = exec_price * quantity
        slippage_cost  = slip_per_unit * quantity

        brokerage      = self._brokerage(trade_value)
        # For entry: SELL action means this leg is a sell (short entry → sell side)
        stt            = self._stt(trade_value, is_sell_leg=not is_buy_action)
        nse_txn        = self._nse_txn(trade_value)
        sebi           = self._sebi(trade_value)
        stamp          = self._stamp(trade_value, is_buy_leg=is_buy_action)
        gst            = self._gst(brokerage, nse_txn)

        total = brokerage + stt + nse_txn + sebi + stamp + gst + slippage_cost

        return LegCost(
            trade_value=round(trade_value, 4),
            slippage_cost=round(slippage_cost, 4),
            execution_price=round(exec_price, 4),
            brokerage=round(brokerage, 4),
            stt=round(stt, 4),
            nse_txn_charges=round(nse_txn, 4),
            sebi_charges=round(sebi, 4),
            stamp_duty=round(stamp, 4),
            gst=round(gst, 4),
            total=round(total, 4),
        )

    def calculate_exit_cost(
        self,
        price:    float,
        quantity: int,
        action:   Literal["BUY", "SELL"],
    ) -> LegCost:
        """
        Compute all costs for the exit order leg.

        The *action* here is the ORIGINAL position direction, not the exit
        direction.  E.g. to close a long (BUY) position you sell, so the
        exit leg is a SELL action for STT purposes.

        Parameters
        ----------
        price :    Current candle close (or limit price).
        quantity : Number of shares / units.
        action :   Original position direction (``"BUY"`` = long, ``"SELL"`` = short).
        """
        # Closing a BUY position → exit is a SELL (adverse slippage = lower fill)
        # Closing a SELL position → exit is a BUY (adverse slippage = higher fill)
        is_closing_long = (action == "BUY")
        exec_price, slip_per_unit = self._apply_slippage(price, is_buy_action=not is_closing_long)
        trade_value   = exec_price * quantity
        slippage_cost = slip_per_unit * quantity

        brokerage   = self._brokerage(trade_value)
        # Exit of a long position = sell → STT applies
        stt         = self._stt(trade_value, is_sell_leg=is_closing_long)
        nse_txn     = self._nse_txn(trade_value)
        sebi        = self._sebi(trade_value)
        # Exit of a long position = sell → no stamp duty; short exit = buy → stamp duty
        stamp       = self._stamp(trade_value, is_buy_leg=not is_closing_long)
        gst         = self._gst(brokerage, nse_txn)

        total = brokerage + stt + nse_txn + sebi + stamp + gst + slippage_cost

        return LegCost(
            trade_value=round(trade_value, 4),
            slippage_cost=round(slippage_cost, 4),
            execution_price=round(exec_price, 4),
            brokerage=round(brokerage, 4),
            stt=round(stt, 4),
            nse_txn_charges=round(nse_txn, 4),
            sebi_charges=round(sebi, 4),
            stamp_duty=round(stamp, 4),
            gst=round(gst, 4),
            total=round(total, 4),
        )

    def full_trade_breakdown(
        self,
        entry_leg: LegCost,
        exit_leg:  LegCost,
        gross_pnl: float,
    ) -> TradeCostBreakdown:
        """
        Combine entry + exit legs into a complete round-trip breakdown.

        Parameters
        ----------
        entry_leg : LegCost returned by ``calculate_entry_cost``.
        exit_leg  : LegCost returned by ``calculate_exit_cost``.
        gross_pnl : Price-move P&L BEFORE costs
                    (exit_price − entry_price) × qty  for a long, etc.

        Returns
        -------
        TradeCostBreakdown
            With ``net_pnl = gross_pnl − total_cost``.
        """
        total_cost = entry_leg.total + exit_leg.total
        net_pnl    = gross_pnl - total_cost
        cost_pct   = abs(total_cost / gross_pnl) * 100 if gross_pnl != 0 else 0.0

        return TradeCostBreakdown(
            entry=entry_leg,
            exit=exit_leg,
            gross_pnl=round(gross_pnl, 4),
            total_cost=round(total_cost, 4),
            net_pnl=round(net_pnl, 4),
            cost_as_pct_of_gross=round(cost_pct, 2),
        )

    def to_dict(self) -> dict:
        """Return the current rate configuration as a dictionary."""
        return {
            "mode":                       "DELIVERY" if self.is_delivery else "INTRADAY",
            "brokerage_pct":              self.brokerage_pct,
            "brokerage_cap_rs":           self.brokerage_cap,
            "stt_pct":                    self.stt_delivery_pct if self.is_delivery else self.stt_intraday_pct,
            "nse_txn_charges_pct":        self.nse_txn_charges_pct,
            "sebi_charges_pct":           self.sebi_charges_pct,
            "stamp_duty_pct":             self.stamp_duty_delivery_pct if self.is_delivery else self.stamp_duty_intraday_pct,
            "gst_pct":                    self.gst_pct,
            "slippage_pct":               self.slippage_pct,
        }


# ─── Convenience presets ───────────────────────────────────────────────────────

def angelone_intraday(slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> BrokerageCostModel:
    """Return a cost model pre-configured for AngelOne intraday (MIS) trades."""
    return BrokerageCostModel(is_delivery=False, slippage_pct=slippage_pct)


def angelone_delivery(slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> BrokerageCostModel:
    """Return a cost model pre-configured for AngelOne CNC (delivery) trades."""
    return BrokerageCostModel(is_delivery=True, slippage_pct=slippage_pct)


# ─── Quick self-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # --- Example: 100 shares of RELIANCE @ ₹ 2 950 (intraday long) ------------
    model = angelone_intraday(slippage_pct=0.0005)

    price    = 2950.0
    qty      = 100
    buy_px   = price
    sell_px  = 3010.0   # target hit

    entry = model.calculate_entry_cost(price=buy_px,  quantity=qty, action="BUY")
    exit_ = model.calculate_exit_cost( price=sell_px, quantity=qty, action="BUY")

    gross = (exit_.execution_price - entry.execution_price) * qty
    breakdown = model.full_trade_breakdown(entry, exit_, gross_pnl=gross)

    print("\n" + "=" * 64)
    print("  AngelOne Brokerage Cost Model — Sample Trade")
    print("=" * 64)
    print(f"  Symbol  : RELIANCE-EQ  |  Qty: {qty}")
    print(f"  Entry   : ₹{entry.execution_price:>10,.2f}   (slippage ₹{entry.slippage_cost:,.2f})")
    print(f"  Exit    : ₹{exit_.execution_price:>10,.2f}   (slippage ₹{exit_.slippage_cost:,.2f})")
    print(f"  Gross PnL  : ₹{breakdown.gross_pnl:>10,.2f}")
    print("-" * 64)
    print(f"  Brokerage  : ₹{entry.brokerage + exit_.brokerage:>10,.4f}")
    print(f"  STT        : ₹{entry.stt        + exit_.stt:>10,.4f}  (SELL leg only)")
    print(f"  NSE Txn    : ₹{entry.nse_txn_charges + exit_.nse_txn_charges:>10,.4f}")
    print(f"  SEBI       : ₹{entry.sebi_charges    + exit_.sebi_charges:>10,.4f}")
    print(f"  Stamp Duty : ₹{entry.stamp_duty + exit_.stamp_duty:>10,.4f}  (BUY leg only)")
    print(f"  GST        : ₹{entry.gst        + exit_.gst:>10,.4f}")
    print(f"  Slippage   : ₹{entry.slippage_cost + exit_.slippage_cost:>10,.4f}")
    print("-" * 64)
    print(f"  Total Cost : ₹{breakdown.total_cost:>10,.4f}  ({breakdown.cost_as_pct_of_gross:.1f}% of gross)")
    print(f"  Net PnL    : ₹{breakdown.net_pnl:>10,.2f}")
    print("=" * 64)

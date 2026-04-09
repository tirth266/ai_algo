"""
Comprehensive Backtesting Performance Report
=============================================

Accepts engine result dicts (train and/or test) and produces:

1. Structured JSON report
   ─ Complete per-metric breakdown for train and test sets
   ─ Degradation ratios (train → test)
   ─ Overfitting warning flags
   ─ Execution quality stats
   ─ Cost breakdown

2. Human-readable ASCII report
   ─ Banner with symbol / period / run time
   ─ Capital & Returns section
   ─ Cost Breakdown section
   ─ Performance Metrics section (train vs test side-by-side)
   ─ Risk Metrics section
   ─ Execution Quality section
   ─ Overfitting Analysis section (with ⚠ / ✓ indicators)
   ─ Verdict / Recommendation

Overfitting rules used (configurable):
  • Win-rate degradation   > THRESHOLD_WIN_RATE         (default 10 pp)
  • Net PnL degradation    > THRESHOLD_NET_PNL           (default 30 %)
  • Sharpe degradation     > THRESHOLD_SHARPE            (default 0.5)
  • Profit factor degrade  > THRESHOLD_PROFIT_FACTOR     (default 0.5)
  • Max drawdown worsens   > THRESHOLD_MAX_DD            (default 5 pp)

Usage::

    from backtest.reports.performance_report import PerformanceReport

    report = PerformanceReport(
        symbol    = "RELIANCE",
        timeframe = "5minute",
        period    = "2024-01-01 → 2024-12-31",
        train_results = engine.run_backtest(..., preloaded_data=train_data),
        test_results  = engine.run_backtest(..., preloaded_data=test_data),
    )

    json_report = report.to_json()
    text_report = report.to_text()
    api_payload = report.to_api_response()
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ─── Overfitting thresholds ────────────────────────────────────────────────────
THRESHOLD_WIN_RATE      =  10.0   # pp drop from train→test
THRESHOLD_NET_PNL       =  30.0   # % drop in net PnL
THRESHOLD_SHARPE        =   0.5   # absolute Sharpe drop
THRESHOLD_PROFIT_FACTOR =   0.5   # absolute PF drop
THRESHOLD_MAX_DD        =   5.0   # pp worsening in max drawdown


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _g(d: dict, *keys, default=0.0):
    """Safe nested getter with a default value."""
    val = d
    for k in keys:
        if not isinstance(val, dict):
            return default
        val = val.get(k, default)
    return val if val is not None else default


def _pct_change(old: float, new: float) -> Optional[float]:
    """Return percentage change from old to new, or None if old is 0."""
    if old == 0:
        return None
    return (new - old) / abs(old) * 100


def _fmt_inr(v: float, sign: bool = False) -> str:
    """Format value as Indian Rupees."""
    prefix = "+" if sign and v > 0 else ""
    return f"{prefix}₹{v:>12,.2f}"


def _fmt_pct(v: float, sign: bool = False) -> str:
    prefix = "+" if sign and v > 0 else ""
    return f"{prefix}{v:>9.2f}%"


def _fmt_ratio(v: float) -> str:
    return f"{v:>9.2f}"


def _rating(v: float, thresholds=(0, 0.5, 1.0, 1.5, 2.0),
            labels=("Very Poor", "Poor", "Fair", "Good", "Excellent")) -> str:
    """Convert a Sharpe-like ratio to a qualitative label."""
    for i, t in enumerate(thresholds):
        if v < t:
            return labels[max(i - 1, 0)]
    return labels[-1]


# ─── Metric extractor ─────────────────────────────────────────────────────────

def _extract_metrics(result: dict) -> dict:
    """
    Normalise a raw engine result dict into a flat metrics dict.

    Works with both the new ``gross_pnl / net_pnl / total_cost`` schema
    and the legacy ``total_pnl`` schema.
    """
    gross    = _g(result, "gross_pnl")
    net      = _g(result, "net_pnl") or _g(result, "total_pnl")
    cost     = _g(result, "total_cost")
    init_cap = _g(result, "initial_capital") or 1.0
    fin_cap  = _g(result, "final_capital")

    if gross == 0 and net != 0:
        gross = net      # legacy compatibility

    return {
        # Capital
        "initial_capital":  init_cap,
        "final_capital":    fin_cap,

        # P&L
        "gross_pnl":        gross,
        "total_cost":       cost,
        "net_pnl":          net,
        "return_pct":       _g(result, "return_percent"),

        # Win / loss
        "total_trades":     int(_g(result, "total_trades")),
        "winning_trades":   int(_g(result, "winning_trades")),
        "losing_trades":    int(_g(result, "losing_trades")),
        "win_rate":         _g(result, "win_rate"),
        "loss_rate":        _g(result, "loss_rate", default=100 - _g(result, "win_rate")),
        "avg_win":          _g(result, "avg_win"),
        "avg_loss":         _g(result, "avg_loss"),
        "avg_pnl":          _g(result, "avg_pnl"),

        # Risk
        "max_drawdown":     _g(result, "max_drawdown"),
        "sharpe_ratio":     _g(result, "sharpe_ratio"),
        "profit_factor":    _g(result, "profit_factor"),
        "expectancy":       _g(result, "expectancy"),

        # Cost breakdown
        "cost_breakdown": result.get("cost_breakdown", {}),

        # Execution quality
        "execution_quality": result.get("execution_quality", {}),
    }


# ─── Overfitting analyser ─────────────────────────────────────────────────────

def _analyse_overfitting(train: dict, test: dict) -> dict:
    """
    Compare train vs test metrics and flag overfitting.

    Returns a structured dict with per-metric deltas, flag booleans,
    and an overall verdict.
    """
    flags: Dict[str, dict] = {}

    # ── Win rate ──────────────────────────────────────────────────────────────
    wr_delta = train["win_rate"] - test["win_rate"]
    flags["win_rate"] = {
        "train": train["win_rate"],
        "test":  test["win_rate"],
        "delta": round(-wr_delta, 2),          # positive = degradation
        "degradation_pp": round(wr_delta, 2),
        "overfit": wr_delta > THRESHOLD_WIN_RATE,
        "threshold": THRESHOLD_WIN_RATE,
    }

    # ── Net PnL ───────────────────────────────────────────────────────────────
    pnl_pct = _pct_change(train["net_pnl"], test["net_pnl"])
    pnl_overfit = (pnl_pct is not None) and (pnl_pct < -THRESHOLD_NET_PNL)
    flags["net_pnl"] = {
        "train": train["net_pnl"],
        "test":  test["net_pnl"],
        "change_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "overfit": pnl_overfit,
        "threshold_pct": THRESHOLD_NET_PNL,
    }

    # ── Sharpe ratio ──────────────────────────────────────────────────────────
    sharpe_delta = train["sharpe_ratio"] - test["sharpe_ratio"]
    flags["sharpe_ratio"] = {
        "train": train["sharpe_ratio"],
        "test":  test["sharpe_ratio"],
        "delta": round(-sharpe_delta, 2),
        "overfit": sharpe_delta > THRESHOLD_SHARPE,
        "threshold": THRESHOLD_SHARPE,
    }

    # ── Profit factor ─────────────────────────────────────────────────────────
    pf_delta = train["profit_factor"] - test["profit_factor"]
    flags["profit_factor"] = {
        "train": train["profit_factor"],
        "test":  test["profit_factor"],
        "delta": round(-pf_delta, 2),
        "overfit": pf_delta > THRESHOLD_PROFIT_FACTOR,
        "threshold": THRESHOLD_PROFIT_FACTOR,
    }

    # ── Max drawdown (lower/more negative = worse) ────────────────────────────
    dd_delta = test["max_drawdown"] - train["max_drawdown"]   # negative = worse
    flags["max_drawdown"] = {
        "train": train["max_drawdown"],
        "test":  test["max_drawdown"],
        "delta": round(dd_delta, 2),
        "overfit": dd_delta < -THRESHOLD_MAX_DD,
        "threshold": -THRESHOLD_MAX_DD,
    }

    # ── Overall verdicts ──────────────────────────────────────────────────────
    triggered = [k for k, v in flags.items() if v["overfit"]]
    n_triggered = len(triggered)

    if n_triggered == 0:
        severity = "NONE"
        verdict  = "✓ No overfitting detected. Strategy performance is consistent."
    elif n_triggered == 1:
        severity = "MILD"
        verdict  = f"⚠ Mild overfitting: {triggered[0]} deteriorated on test data."
    elif n_triggered == 2:
        severity = "MODERATE"
        verdict  = (
            f"⚠⚠ Moderate overfitting: {', '.join(triggered)} all deteriorated. "
            "Consider simpler parameters or more robust features."
        )
    else:
        severity = "SEVERE"
        verdict  = (
            f"🚨 SEVERE overfitting: {n_triggered}/5 metrics degraded significantly. "
            "Train » Test. Results are NOT reliable. Re-tune or discard strategy."
        )

    return {
        "severity":       severity,
        "verdict":        verdict,
        "triggered_count": n_triggered,
        "triggered_flags": triggered,
        "metrics":        flags,
        "thresholds_used": {
            "win_rate_pp":      THRESHOLD_WIN_RATE,
            "net_pnl_pct":      THRESHOLD_NET_PNL,
            "sharpe":           THRESHOLD_SHARPE,
            "profit_factor":    THRESHOLD_PROFIT_FACTOR,
            "max_drawdown_pp":  THRESHOLD_MAX_DD,
        },
    }


# ─── Main report class ─────────────────────────────────────────────────────────

class PerformanceReport:
    """
    Structured backtest performance report with train/test comparison.

    Parameters
    ----------
    symbol : str
        Instrument ticker.
    timeframe : str
        Candle width (e.g. ``'5minute'``).
    period : str
        Human-readable date range (e.g. ``'2024-01-01 → 2024-12-31'``).
    test_results : dict
        Output of ``InstitutionalBacktestEngine.run_backtest()`` on test data.
    train_results : dict | None
        Output of the same engine on train data (required for overfitting
        analysis).  If omitted, comparison section is skipped.
    split_info : dict | None
        Data-split metadata (rows, dates) as returned by
        ``prepare_data_for_backtesting()``.
    """

    def __init__(
        self,
        symbol:        str,
        timeframe:     str,
        period:        str,
        test_results:  Dict[str, Any],
        train_results: Optional[Dict[str, Any]] = None,
        split_info:    Optional[Dict[str, Any]] = None,
    ):
        self.symbol        = symbol
        self.timeframe     = timeframe
        self.period        = period
        self.generated_at  = datetime.now()
        self.split_info    = split_info or {}

        self.train_m: Optional[dict] = (
            _extract_metrics(train_results) if train_results else None
        )
        self.test_m  = _extract_metrics(test_results)

        self.overfit: Optional[dict] = (
            _analyse_overfitting(self.train_m, self.test_m)
            if self.train_m else None
        )

        logger.info(
            f"PerformanceReport built | {symbol} {timeframe} | "
            f"net_pnl=₹{self.test_m['net_pnl']:,.2f} | "
            f"overfit={self.overfit['severity'] if self.overfit else 'N/A'}"
        )

    # ── Public outputs ─────────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Return the full report as a pretty-printed JSON string."""
        return json.dumps(self._build_json(), indent=2, default=str)

    def to_dict(self) -> dict:
        """Return the full report as a Python dict."""
        return self._build_json()

    def to_text(self) -> str:
        """Return the full report as a human-readable ASCII string."""
        return self._build_text()

    def to_api_response(self) -> dict:
        """
        Return a slimmed-down dict suitable for direct use in a Flask
        ``jsonify()`` API response.
        """
        d = self._build_json()
        # Drop raw trade lists to keep payload lean
        d.pop("raw_trades", None)
        return d

    # ── JSON builder ───────────────────────────────────────────────────────────

    def _build_json(self) -> dict:
        report = {
            "metadata": {
                "symbol":       self.symbol,
                "timeframe":    self.timeframe,
                "period":       self.period,
                "generated_at": self.generated_at.isoformat(),
                "split_info":   self.split_info,
            },
            "test_performance":  self._metrics_section(self.test_m, "test"),
        }

        if self.train_m:
            report["train_performance"] = self._metrics_section(self.train_m, "train")

        if self.overfit:
            report["overfitting_analysis"] = self.overfit

        report["summary"] = self._build_summary_json()
        return report

    @staticmethod
    def _metrics_section(m: dict, label: str) -> dict:
        cb = m.get("cost_breakdown", {})
        eq = m.get("execution_quality", {})
        return {
            "label": label,
            "capital": {
                "initial":        m["initial_capital"],
                "final":          m["final_capital"],
                "return_pct":     m["return_pct"],
            },
            "pnl": {
                "gross_pnl":      m["gross_pnl"],
                "total_cost":     m["total_cost"],
                "net_pnl":        m["net_pnl"],
                "cost_pct_gross": (
                    round(m["total_cost"] / m["gross_pnl"] * 100, 2)
                    if m["gross_pnl"] != 0 else 0
                ),
            },
            "trade_stats": {
                "total_trades":   m["total_trades"],
                "winning_trades": m["winning_trades"],
                "losing_trades":  m["losing_trades"],
                "win_rate":       round(m["win_rate"],  2),
                "loss_rate":      round(m["loss_rate"], 2),
                "avg_win":        m["avg_win"],
                "avg_loss":       m["avg_loss"],
                "avg_pnl":        m["avg_pnl"],
            },
            "risk_metrics": {
                "max_drawdown":   round(m["max_drawdown"],  2),
                "sharpe_ratio":   round(m["sharpe_ratio"],  2),
                "profit_factor":  round(m["profit_factor"], 2),
                "expectancy":     round(m["expectancy"],    2),
                "sharpe_rating":  _rating(m["sharpe_ratio"]),
            },
            "cost_breakdown": {
                "brokerage":  _g(cb, "brokerage"),
                "stt":        _g(cb, "stt"),
                "nse_txn":    _g(cb, "nse_txn"),
                "sebi":       _g(cb, "sebi"),
                "stamp_duty": _g(cb, "stamp_duty"),
                "gst":        _g(cb, "gst"),
                "slippage":   _g(cb, "slippage"),
                "total":      _g(cb, "total") or m["total_cost"],
            },
            "execution_quality": eq if eq else {},
        }

    def _build_summary_json(self) -> dict:
        """Top-level quick-read summary for dashboards."""
        t = self.test_m
        s: Dict[str, Any] = {
            "net_pnl":        round(t["net_pnl"],        2),
            "gross_pnl":      round(t["gross_pnl"],      2),
            "total_cost":     round(t["total_cost"],     2),
            "win_rate":       round(t["win_rate"],       2),
            "max_drawdown":   round(t["max_drawdown"],   2),
            "sharpe_ratio":   round(t["sharpe_ratio"],   2),
            "profit_factor":  round(t["profit_factor"],  2),
            "total_trades":   t["total_trades"],
            "return_pct":     round(t["return_pct"],     2),
            "data_set":       "test_only",
        }
        if self.overfit:
            s["overfit_severity"] = self.overfit["severity"]
            s["overfit_verdict"]  = self.overfit["verdict"]
        return s

    # ── Text builder ───────────────────────────────────────────────────────────

    W = 72   # report width

    def _build_text(self) -> str:
        lines: List[str] = []
        sep  = "═" * self.W
        thin = "─" * self.W

        def banner(txt: str):
            lines.append(sep)
            lines.append(f"  {txt}")
            lines.append(sep)

        def section(txt: str):
            lines.append("")
            lines.append(thin)
            lines.append(f"  {txt}")
            lines.append(thin)

        def row(label: str, val: str, note: str = ""):
            pad = self.W - len(label) - len(val) - 4
            lines.append(f"  {label}{'·' * max(pad, 1)}{val}  {note}".rstrip())

        def compare_row(label: str, train_val: str, test_val: str, flag: str = ""):
            col1 = 28
            col2 = 20
            col3 = 20
            lbl  = f"  {label}"
            lbl  = lbl.ljust(col1)
            tv   = train_val.rjust(col2)
            tv2  = test_val.rjust(col3)
            lines.append(f"{lbl}{tv}{tv2}  {flag}".rstrip())

        # ── Banner ────────────────────────────────────────────────────────────
        banner(f"BACKTESTING PERFORMANCE REPORT  ·  {self.symbol} / {self.timeframe}")
        lines.append(f"  Period    : {self.period}")
        lines.append(f"  Generated : {self.generated_at.strftime('%Y-%m-%d %H:%M:%S IST')}")
        if self.split_info:
            tr = self.split_info.get("train_rows", "?")
            te = self.split_info.get("test_rows", "?")
            lines.append(f"  Data      : Train {tr} bars  |  Test {te} bars")

        # ── Capital & Returns ─────────────────────────────────────────────────
        t = self.test_m
        section("CAPITAL & RETURNS  (TEST SET)")
        row("Initial Capital",  _fmt_inr(t["initial_capital"]))
        row("Final Capital",    _fmt_inr(t["final_capital"]))
        row("Total Return",     _fmt_pct(t["return_pct"],   sign=True))
        row("Gross PnL",        _fmt_inr(t["gross_pnl"],    ),    "← price-move only")
        row("Total Costs",      _fmt_inr(-t["total_cost"],  ),    "← all charges + slip")
        row("Net PnL",          _fmt_inr(t["net_pnl"],      ),    "← TRUE profitability")

        # ── Cost breakdown ────────────────────────────────────────────────────
        cb = t.get("cost_breakdown", {})
        if any(_g(cb, k) for k in ("brokerage", "stt", "gst", "slippage")):
            section("COST BREAKDOWN  (TEST SET — ROUND TRIP TOTALS)")
            row("Brokerage",    _fmt_inr(_g(cb, "brokerage")))
            row("STT",          _fmt_inr(_g(cb, "stt")))
            row("NSE Txn",      _fmt_inr(_g(cb, "nse_txn")))
            row("SEBI",         _fmt_inr(_g(cb, "sebi")))
            row("Stamp Duty",   _fmt_inr(_g(cb, "stamp_duty")))
            row("GST",          _fmt_inr(_g(cb, "gst")))
            row("Slippage",     _fmt_inr(_g(cb, "slippage")))
            row("TOTAL",        _fmt_inr(_g(cb, "total") or t["total_cost"]))
            if t["gross_pnl"] != 0:
                cost_pct = t["total_cost"] / t["gross_pnl"] * 100
                row("Cost as % of Gross", _fmt_pct(cost_pct))

        # ── Comparison table ──────────────────────────────────────────────────
        if self.train_m:
            tr2 = self.train_m
            section("TRAIN vs TEST COMPARISON")

            # Header
            lines.append(
                f"  {'Metric':<28}{'TRAIN':>20}{'TEST':>20}  STATUS"
            )
            lines.append(thin)

            of = self.overfit["metrics"]

            def of_flag(key: str) -> str:
                return "⚠ OVERFIT" if of.get(key, {}).get("overfit") else "✓"

            compare_row("Win Rate",
                        _fmt_pct(tr2["win_rate"]),
                        _fmt_pct(t["win_rate"]),
                        of_flag("win_rate"))
            compare_row("Gross PnL",
                        _fmt_inr(tr2["gross_pnl"]),
                        _fmt_inr(t["gross_pnl"]))
            compare_row("Net PnL",
                        _fmt_inr(tr2["net_pnl"]),
                        _fmt_inr(t["net_pnl"]),
                        of_flag("net_pnl"))
            compare_row("Max Drawdown",
                        _fmt_pct(tr2["max_drawdown"]),
                        _fmt_pct(t["max_drawdown"]),
                        of_flag("max_drawdown"))
            compare_row("Sharpe Ratio",
                        _fmt_ratio(tr2["sharpe_ratio"]),
                        _fmt_ratio(t["sharpe_ratio"]),
                        of_flag("sharpe_ratio"))
            compare_row("Profit Factor",
                        _fmt_ratio(tr2["profit_factor"]),
                        _fmt_ratio(t["profit_factor"]),
                        of_flag("profit_factor"))
            compare_row("Total Trades",
                        str(tr2["total_trades"]).rjust(20),
                        str(t["total_trades"]).rjust(20))
            compare_row("Avg Win",
                        _fmt_inr(tr2["avg_win"]),
                        _fmt_inr(t["avg_win"]))
            compare_row("Avg Loss",
                        _fmt_inr(tr2["avg_loss"]),
                        _fmt_inr(t["avg_loss"]))

        # ── Performance metrics (test only) ───────────────────────────────────
        section("PERFORMANCE METRICS  (TEST SET)")
        row("Total Trades",     f"{t['total_trades']:>15d}")
        row("Winning Trades",   f"{t['winning_trades']:>15d}")
        row("Losing Trades",    f"{t['losing_trades']:>15d}")
        row("Win Rate",         _fmt_pct(t["win_rate"]))
        row("Avg Win",          _fmt_inr(t["avg_win"]))
        row("Avg Loss",         _fmt_inr(t["avg_loss"]))
        avg_rr = (
            round(t["avg_win"] / t["avg_loss"], 2)
            if t["avg_loss"] > 0 else float("inf")
        )
        row("Avg R:R",          f"{avg_rr:>15.2f} : 1")
        row("Expectancy",       _fmt_inr(t["expectancy"]),  "per trade")

        section("RISK METRICS  (TEST SET)")
        row("Max Drawdown",     _fmt_pct(t["max_drawdown"]))
        row("Sharpe Ratio",     f"{t['sharpe_ratio']:>15.2f}  [{_rating(t['sharpe_ratio'])}]")
        row("Profit Factor",    f"{t['profit_factor']:>15.2f}")

        # ── Execution quality ─────────────────────────────────────────────────
        eq = t.get("execution_quality", {})
        if eq:
            section("EXECUTION QUALITY  (TEST SET)")
            row("Orders Submitted",   f"{_g(eq, 'total_submitted'):>15.0f}")
            row("Orders Filled",      f"{_g(eq, 'total_filled'):>15.0f}")
            row("Partial Fills",      f"{_g(eq, 'total_partial'):>15.0f}")
            row("Rejected",           f"{_g(eq, 'total_rejected'):>15.0f}")
            row("Fill Rate",          _fmt_pct(_g(eq, "fill_rate_pct")))
            row("Rejection Rate",     _fmt_pct(_g(eq, "rejection_rate_pct")))
            row("Avg Slippage",       _fmt_pct(_g(eq, "avg_slippage_pct")))
            row("Total Slip Cost",    _fmt_inr(_g(eq, "total_slippage_cost")))
            row("Avg Fill Ratio",     _fmt_pct(_g(eq, "avg_fill_ratio") * 100))

        # ── Overfitting analysis ───────────────────────────────────────────────
        if self.overfit:
            section("OVERFITTING ANALYSIS")
            of = self.overfit
            severity_icon = {
                "NONE":     "✓  NONE",
                "MILD":     "⚠  MILD",
                "MODERATE": "⚠⚠ MODERATE",
                "SEVERE":   "🚨 SEVERE",
            }.get(of["severity"], of["severity"])

            lines.append(f"  Severity : {severity_icon}")
            lines.append(f"  Verdict  : {of['verdict']}")
            lines.append("")

            fm = of["metrics"]

            def of_detail(key: str, fmt_fn):
                d = fm.get(key, {})
                flag = "⚠ OVERFIT" if d.get("overfit") else "✓ OK"
                tv   = d.get("train", 0)
                te   = d.get("test",  0)
                delta = d.get("delta") or d.get("change_pct")
                delta_str = f"{delta:+.2f}" if delta is not None else "N/A"
                lines.append(
                    f"  {key:<24} train={fmt_fn(tv):>10}  test={fmt_fn(te):>10}"
                    f"  Δ={delta_str:>8}  {flag}"
                )

            of_detail("win_rate",      lambda v: f"{v:.2f}%")
            of_detail("net_pnl",       lambda v: f"₹{v:,.0f}")
            of_detail("sharpe_ratio",  lambda v: f"{v:.2f}")
            of_detail("profit_factor", lambda v: f"{v:.2f}")
            of_detail("max_drawdown",  lambda v: f"{v:.2f}%")

        # ── Recommendation ─────────────────────────────────────────────────────
        section("RECOMMENDATION")
        sr   = t["sharpe_ratio"]
        wr   = t["win_rate"]
        pf   = t["profit_factor"]
        dd   = abs(t["max_drawdown"])
        npnl = t["net_pnl"]

        recs: List[str] = []
        if npnl > 0:
            recs.append("✓ Strategy is profitable after all costs.")
        else:
            recs.append("✗ Strategy is NET LOSS after costs. Do NOT deploy.")

        if sr >= 1.5:
            recs.append("✓ Excellent Sharpe ratio — strong risk-adjusted returns.")
        elif sr >= 0.5:
            recs.append("⚠ Acceptable Sharpe. Monitor live for consistency.")
        else:
            recs.append("✗ Sharpe < 0.5 — risk-adjusted returns are poor.")

        if wr >= 55:
            recs.append(f"✓ Win rate {wr:.1f}% is healthy.")
        elif wr >= 45:
            recs.append(f"⚠ Win rate {wr:.1f}% is borderline — check avg R:R.")
        else:
            recs.append(f"✗ Win rate {wr:.1f}% is low. Strategy needs higher R:R.")

        if pf >= 1.5:
            recs.append(f"✓ Profit factor {pf:.2f} — winners dwarf losers.")
        elif pf >= 1.0:
            recs.append(f"⚠ Profit factor {pf:.2f} — marginal edge.")
        else:
            recs.append(f"✗ Profit factor {pf:.2f} < 1.0 — strategy loses money.")

        if dd <= 10:
            recs.append(f"✓ Drawdown {dd:.1f}% is well-controlled.")
        elif dd <= 20:
            recs.append(f"⚠ Drawdown {dd:.1f}% — acceptable but size positions carefully.")
        else:
            recs.append(f"✗ Drawdown {dd:.1f}% is high — reduce position size or add filters.")

        if self.overfit and self.overfit["severity"] in ("SEVERE", "MODERATE"):
            recs.append(
                "🚨 OVERFIT WARNING: re-parameterise or collect more data before live trading."
            )

        for rec in recs:
            lines.append(f"  {rec}")

        lines.append("")
        lines.append(sep)
        lines.append("")
        return "\n".join(lines)


# ─── Convenience function ──────────────────────────────────────────────────────

def build_performance_report(
    symbol:        str,
    timeframe:     str,
    period:        str,
    test_results:  Dict[str, Any],
    train_results: Optional[Dict[str, Any]] = None,
    split_info:    Optional[Dict[str, Any]] = None,
    print_report:  bool = False,
) -> PerformanceReport:
    """
    Build a :class:`PerformanceReport` and optionally print it.

    Returns the report object so callers can choose their output format.
    """
    report = PerformanceReport(
        symbol=symbol,
        timeframe=timeframe,
        period=period,
        test_results=test_results,
        train_results=train_results,
        split_info=split_info,
    )
    if print_report:
        print(report.to_text())
    return report


# ─── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # ── Synthetic results (mimic InstitutionalBacktestEngine output) ──────────
    _TRAIN = {
        "symbol":          "RELIANCE",
        "initial_capital": 100_000,
        "final_capital":   115_400,
        "gross_pnl":       17_250,
        "total_cost":       1_850,
        "net_pnl":         15_400,
        "total_pnl":       15_400,
        "return_percent":   15.4,
        "total_trades":     42,
        "winning_trades":   26,
        "losing_trades":    16,
        "win_rate":         61.9,
        "loss_rate":        38.1,
        "avg_win":          980,
        "avg_loss":         450,
        "avg_pnl":          366,
        "profit_factor":    2.31,
        "expectancy":       366,
        "max_drawdown":    -5.2,
        "sharpe_ratio":     1.82,
        "cost_breakdown": {
            "brokerage":  640, "stt":  280, "nse_txn": 180,
            "sebi":         4, "stamp_duty": 60, "gst": 150,
            "slippage":   536, "total": 1850,
        },
        "execution_quality": {
            "total_submitted": 45, "total_filled": 40, "total_partial": 3,
            "total_rejected": 2, "total_expired": 0,
            "fill_rate_pct": 95.6, "rejection_rate_pct": 4.4,
            "avg_slippage_pct": 0.0512, "total_slippage_cost": 536,
            "avg_fill_ratio": 0.94, "avg_delay_candles": 1.0,
        },
        "trades":      [],
        "equity_curve": [],
    }

    _TEST = {                           # degraded — moderate overfit scenario
        "symbol":          "RELIANCE",
        "initial_capital": 100_000,
        "final_capital":   104_800,
        "gross_pnl":        6_900,
        "total_cost":       2_100,
        "net_pnl":          4_800,
        "total_pnl":        4_800,
        "return_percent":    4.8,
        "total_trades":     18,
        "winning_trades":    9,
        "losing_trades":     9,
        "win_rate":         50.0,
        "loss_rate":        50.0,
        "avg_win":          890,
        "avg_loss":         540,
        "avg_pnl":          267,
        "profit_factor":    1.48,
        "expectancy":       267,
        "max_drawdown":   -12.4,
        "sharpe_ratio":     0.91,
        "cost_breakdown": {
            "brokerage":  360, "stt":  160, "nse_txn": 100,
            "sebi":         2, "stamp_duty": 38, "gst": 90,
            "slippage":  1350, "total": 2100,
        },
        "execution_quality": {
            "total_submitted": 20, "total_filled": 16, "total_partial": 2,
            "total_rejected": 2, "total_expired": 0,
            "fill_rate_pct": 90.0, "rejection_rate_pct": 10.0,
            "avg_slippage_pct": 0.0618, "total_slippage_cost": 1350,
            "avg_fill_ratio": 0.91, "avg_delay_candles": 1.0,
        },
        "trades":      [],
        "equity_curve": [],
    }

    _SPLIT = {
        "train_rows": 8_400,
        "test_rows":  3_600,
        "train_ratio": 0.70,
    }

    report = build_performance_report(
        symbol        = "RELIANCE",
        timeframe     = "5minute",
        period        = "2024-01-01 → 2024-12-31",
        train_results = _TRAIN,
        test_results  = _TEST,
        split_info    = _SPLIT,
        print_report  = True,
    )

    # Validate JSON
    j = report.to_json()
    d = json.loads(j)
    print(f"JSON keys: {list(d.keys())}")
    print(f"Overfitting severity : {d['overfitting_analysis']['severity']}")
    print(f"Test net PnL         : ₹{d['summary']['net_pnl']:,.2f}")

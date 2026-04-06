# t:/1311/algo-trading-platform/backend/engine/guardian.py
"""
Guardian – safety utilities for the LiveRunner.

Features implemented for Ironclad v2:

1. **Continuity Watchdog** with jitter‑buffer and 9:15 AM grace period.
2. **Position Mirror** with two‑strike mismatch rule.
3. **Fatal‑Error Logger** that writes a diagnostic dump to the user's Desktop.
4. Helper exception ``DataGapError``.
"""

import logging
import os
import json
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------
class DataGapError(RuntimeError):
    """Raised when a gap larger than the allowed interval is detected."""
    pass

# ----------------------------------------------------------------------
# Fatal‑error reporter
# ----------------------------------------------------------------------
FATAL_REPORT_PATH = os.path.expanduser(r"C:\Users\Dell\Desktop\FATAL_ERROR.txt")

def write_fatal_report(reason: str, details: str) -> None:
    """Write a comprehensive fatal‑error report.

    The file is overwritten each time a new fatal condition occurs.
    """
    try:
        with open(FATAL_REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(f"=== FATAL ERROR REPORT ===\n")
            f.write(f"Timestamp   : {datetime.now().isoformat()}\n")
            f.write(f"Reason      : {reason}\n")
            f.write("Details     :\n")
            f.write(details + "\n")
            f.write("--- End of Report ---\n")
        logger.error("Fatal error written to %s", FATAL_REPORT_PATH)
    except Exception as e:
        logger.exception("Failed to write fatal error report: %s", e)

# ----------------------------------------------------------------------
# Continuity Watchdog
# ----------------------------------------------------------------------
def check_continuity(
    df: pd.DataFrame,
    max_gap_minutes: int = 5,
    market_open_grace: int = 30,
) -> None:
    """Validate that candle timestamps are contiguous.

    * **Jitter buffer** – timestamps are rounded to the nearest 5 minutes
      to avoid false alarms caused by sub‑second clock drift.
    * **Grace period** – during the first 5 minutes after market open
      (09:15 IST) a smaller gap of ``market_open_grace`` seconds is allowed.
    """
    if df.empty:
        raise DataGapError("Empty dataframe – no market data available")

    # Expect a column named `timestamp` or `datetime`
    ts_col = "timestamp" if "timestamp" in df.columns else "datetime"
    series = pd.to_datetime(df[ts_col])
    # Jitter buffer – round to nearest 5‑minute bucket
    series = series.dt.round("5min")
    diffs = series.diff().dt.total_seconds().fillna(0)

    # Determine if we are within the first 5 minutes of the session
    now = datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    within_grace_window = (now - market_open) <= timedelta(minutes=5)

    allowed_gap = market_open_grace if within_grace_window else max_gap_minutes * 60
    if (diffs > allowed_gap).any():
        raise DataGapError(
            f"Gap larger than allowed ({allowed_gap}s) detected in market stream"
        )
    logger.debug("Continuity watchdog passed – no gaps beyond %s seconds", allowed_gap)

# ----------------------------------------------------------------------
# Position Mirror – two‑strike rule
# ----------------------------------------------------------------------
def verify_position_mirror(live_runner: any, kite_instance: any) -> None:
    """Compare internal positions with broker positions.

    A mismatch counter is stored on the ``live_runner`` instance. The kill‑
    switch is only triggered after **two consecutive** mismatches.
    """
    broker_positions = kite_instance.positions("net")
    broker_keys = {
        f"{p['tradingsymbol']}_{p['product']}"
        for p in broker_positions
        if p.get("quantity", 0) != 0
    }
    internal_keys = set(live_runner.open_positions.keys())

    if internal_keys != broker_keys:
        # Increment mismatch counter
        cnt = getattr(live_runner, "position_mismatch_counter", 0) + 1
        setattr(live_runner, "position_mismatch_counter", cnt)
        logger.warning(
            "Position mismatch detected (strike %d). Internal: %s | Broker: %s",
            cnt,
            internal_keys,
            broker_keys,
        )
        if cnt >= 2:
            # Two consecutive mismatches – kill the engine
            write_fatal_report(
                reason="External Position Manipulation",
                details=f"Internal positions {internal_keys} differ from broker {broker_keys}",
            )
            live_runner.kill_switch_active = True
            raise RuntimeError("External position manipulation – engine halted")
    else:
        # Reset counter on a clean heartbeat
        setattr(live_runner, "position_mismatch_counter", 0)

# ----------------------------------------------------------------------
# Helper to trigger kill‑switch from anywhere
# ----------------------------------------------------------------------
def trigger_kill_switch(live_runner: any, reason: str, details: str = "") -> None:
    """Centralised kill‑switch activation with fatal reporting."""
    write_fatal_report(reason=reason, details=details)
    live_runner.kill_switch_active = True
    logger.critical("Kill‑switch activated: %s", reason)

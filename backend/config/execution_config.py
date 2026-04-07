"""
Execution Configuration Module

Configures realistic market execution parameters.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ExecutionConfig:
    """Execution configuration for realistic trading."""

    # Slippage settings
    slippage_pct: float = 0.1  # 0.1% slippage

    # Fee settings
    fee_pct: float = 0.1  # 0.1% brokerage fee

    # Spread settings
    spread_pct: float = 0.02  # 0.02% bid-ask spread

    # Execution mode
    mode: str = "paper"  # "paper" or "live"

    # Priority settings
    sl_priority: bool = True  # Prioritize SL over TP in same candle

    # Logging
    log_adjustments: bool = True

    def __post_init__(self):
        """Load from environment if available."""
        self.slippage_pct = float(os.getenv("SLIPPAGE_PCT", self.slippage_pct))
        self.fee_pct = float(os.getenv("FEE_PCT", self.fee_pct))
        self.spread_pct = float(os.getenv("SPREAD_PCT", self.spread_pct))
        self.mode = os.getenv("EXECUTION_MODE", self.mode)
        self.sl_priority = os.getenv("SL_PRIORITY", "true").lower() == "true"
        self.log_adjustments = os.getenv("LOG_ADJUSTMENTS", "true").lower() == "true"

    def to_dict(self) -> dict:
        return {
            "slippage_pct": self.slippage_pct,
            "fee_pct": self.fee_pct,
            "spread_pct": self.spread_pct,
            "mode": self.mode,
            "sl_priority": self.sl_priority,
            "log_adjustments": self.log_adjustments,
        }


# Default configuration
default_config = ExecutionConfig()


def get_execution_config() -> ExecutionConfig:
    """Get execution configuration."""
    return default_config

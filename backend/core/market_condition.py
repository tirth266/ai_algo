"""
Market Condition Detection Module

Centralizes market condition detection logic.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def detect_ema_alignment(df: pd.DataFrame, ema_periods: list = None) -> str:
    """
    Detect EMA alignment.

    Returns:
        'trending_up': EMA20 > EMA50 > EMA100 > EMA200
        'trending_down': EMA20 < EMA50 < EMA100 < EMA200
        'tangled': No clear alignment
    """
    if ema_periods is None:
        ema_periods = [20, 50, 100, 200]

    if len(df) < max(ema_periods) + 1:
        return "unknown"

    ema20 = df[f"ema_{ema_periods[0]}"].iloc[-1]
    ema50 = df[f"ema_{ema_periods[1]}"].iloc[-1]
    ema100 = df[f"ema_{ema_periods[2]}"].iloc[-1]
    ema200 = df[f"ema_{ema_periods[3]}"].iloc[-1]

    if ema20 > ema50 > ema100 > ema200:
        return "trending_up"
    elif ema20 < ema50 < ema100 < ema200:
        return "trending_down"
    return "tangled"


def detect_market_structure(df: pd.DataFrame, lookback: int = 5) -> str:
    """
    Detect market structure (HH/HL or LH/LL).

    Returns:
        'hh_hl': Higher High + Higher Low
        'lh_ll': Lower High + Lower Low
        'neutral': No clear structure
    """
    if len(df) < lookback + 2:
        return "neutral"

    last_high = df["high"].iloc[-1]
    last_low = df["low"].iloc[-1]
    prev_high = df["high"].iloc[-2]
    prev_low = df["low"].iloc[-2]

    if last_high > prev_high and last_low > prev_low:
        return "hh_hl"
    elif last_high < prev_high and last_low < prev_low:
        return "lh_ll"
    return "neutral"


def is_trending_market(
    df: pd.DataFrame, ema_periods: list = None, threshold: float = 0.5
) -> bool:
    """
    Check if market is trending.

    Args:
        df: DataFrame with EMA columns
        ema_periods: EMA periods to check
        threshold: Minimum spread percentage
    """
    if ema_periods is None:
        ema_periods = [20, 50, 100, 200]

    if len(df) < max(ema_periods) + 1:
        return False

    ema20 = df[f"ema_{ema_periods[0]}"].iloc[-1]
    ema200 = df[f"ema_{ema_periods[3]}"].iloc[-1]

    spread_pct = abs(ema20 - ema200) / ema200 * 100 if ema200 != 0 else 0

    alignment = detect_ema_alignment(df, ema_periods)
    return alignment.startswith("trending") and spread_pct > threshold


def is_sideways_market(
    df: pd.DataFrame, ema_periods: list = None, threshold: float = 0.5
) -> bool:
    """
    Check if market is sideways.
    """
    if ema_periods is None:
        ema_periods = [20, 50, 100, 200]

    if len(df) < max(ema_periods) + 1:
        return True

    ema20 = df[f"ema_{ema_periods[0]}"].iloc[-1]
    ema100 = df[f"ema_{ema_periods[2]}"].iloc[-1]

    spread_pct = abs(ema20 - ema100) / ema100 * 100 if ema100 != 0 else 0

    return spread_pct < threshold


def detect_market_condition(df: pd.DataFrame) -> str:
    """
    Detect overall market condition.

    Returns:
        'trending_up', 'trending_down', 'sideways', 'weak_trend'
    """
    alignment = detect_ema_alignment(df)
    structure = detect_market_structure(df)

    if alignment == "trending_up":
        return "trending_up"
    elif alignment == "trending_down":
        return "trending_down"
    elif alignment == "tangled":
        return "sideways"

    return "weak_trend"


def get_trend_strength(df: pd.DataFrame) -> float:
    """
    Calculate trend strength (0-100).
    """
    alignment = detect_ema_alignment(df)
    structure = detect_market_structure(df)

    strength = 0.0

    if alignment == "trending_up":
        strength += 40
    elif alignment == "trending_down":
        strength += 40

    if structure in ["hh_hl", "lh_ll"]:
        strength += 30

    if "atr" in df.columns and len(df) > 0:
        atr = df["atr"].iloc[-1]
        close = df["close"].iloc[-1]
        if atr > 0:
            atr_pct = (atr / close) * 100
            strength += min(30, atr_pct * 10)

    return min(100, strength)

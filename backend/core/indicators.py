"""
Unified RSI Utilities Module

Centralizes RSI and divergence detection.

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def detect_rsi_divergence(
    prices: pd.Series, rsi: pd.Series, pivot_period: int = 5
) -> Dict[str, Any]:
    """
    Detect RSI divergence patterns.

    Returns:
        Dict with:
        - type: 'regular_bullish'|'regular_bearish'|'hidden_bullish'|'hidden_bearish'|'none'
        - bullish: bool
        - bearish: bool
        - strength: float
    """
    if len(prices) < pivot_period * 2 + 1:
        return {"type": "none", "bullish": False, "bearish": False, "strength": 0.0}

    price_highs = []
    price_lows = []
    rsi_highs = []
    rsi_lows = []

    for i in range(pivot_period, len(prices) - pivot_period):
        is_high = (
            prices.iloc[i] == prices.iloc[i - pivot_period : i + pivot_period].max()
        )
        is_low = (
            prices.iloc[i] == prices.iloc[i - pivot_period : i + pivot_period].min()
        )

        if is_high:
            price_highs.append(prices.iloc[i])
            rsi_highs.append(rsi.iloc[i])

        if is_low:
            price_lows.append(prices.iloc[i])
            rsi_lows.append(rsi.iloc[i])

    if len(price_highs) < 2 or len(price_lows) < 2:
        return {"type": "none", "bullish": False, "bearish": False, "strength": 0.0}

    regular_bullish = price_lows[-1] < price_lows[-2] and rsi_lows[-1] > rsi_lows[-2]
    regular_bearish = (
        price_highs[-1] > price_highs[-2] and rsi_highs[-1] < rsi_highs[-2]
    )
    hidden_bullish = price_lows[-1] > price_lows[-2] and rsi_lows[-1] < rsi_lows[-2]
    hidden_bearish = price_highs[-1] < price_highs[-2] and rsi_highs[-1] > rsi_highs[-2]

    div_type = "none"
    if regular_bullish:
        div_type = "regular_bullish"
    elif regular_bearish:
        div_type = "regular_bearish"
    elif hidden_bullish:
        div_type = "hidden_bullish"
    elif hidden_bearish:
        div_type = "hidden_bearish"

    strength = 0.0
    if div_type != "none":
        if "bullish" in div_type and len(rsi_lows) >= 2:
            strength = rsi_lows[-1] - rsi_lows[-2]
        elif "bearish" in div_type and len(rsi_highs) >= 2:
            strength = rsi_highs[-2] - rsi_highs[-1]

    return {
        "type": div_type,
        "bullish": regular_bullish or hidden_bullish,
        "bearish": regular_bearish or hidden_bearish,
        "regular_bullish": regular_bullish,
        "regular_bearish": regular_bearish,
        "hidden_bullish": hidden_bullish,
        "hidden_bearish": hidden_bearish,
        "strength": abs(strength),
    }


def calculate_vwap(data: pd.DataFrame, anchor: str = "Session") -> pd.Series:
    """Calculate VWAP."""
    df = data.copy()

    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    tpv = tp * df["volume"]

    index = df.index

    if anchor == "Session":
        groups = pd.Series(index.date, index=index)
    else:
        groups = pd.Series(index, index=index)

    vwap_values = pd.Series(index=df.index, dtype=float)

    for group_key in groups.unique():
        mask = groups == group_key
        indices = df.index[mask]

        if len(indices) == 0:
            continue

        cum_tpv = tpv.loc[indices].cumsum()
        cum_vol = df["volume"].loc[indices].cumsum()

        vwap_values.loc[indices] = cum_tpv / cum_vol

    vwap_values = vwap_values.ffill()
    return vwap_values


def calculate_vwap_bands(data: pd.DataFrame, multiplier: float = 2.0) -> pd.DataFrame:
    """Calculate VWAP with standard deviation bands."""
    df = data.copy()

    df["vwap"] = calculate_vwap(df)

    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    deviation = tp - df["vwap"]
    stdev = deviation.expanding(min_periods=2).std().ffill()

    df["vwap_upper_1"] = df["vwap"] + stdev * 1.0
    df["vwap_lower_1"] = df["vwap"] - stdev * 1.0
    df["vwap_upper_2"] = df["vwap"] + stdev * multiplier
    df["vwap_lower_2"] = df["vwap"] - stdev * multiplier

    return df


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ATR."""
    high = data["high"]
    low = data["low"]
    close = data["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate EMA."""
    return prices.ewm(span=period, adjust=False).mean()


def calculate_volume_ma(data: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate volume moving average."""
    return data["volume"].rolling(window=period).mean()


def is_volume_spike(
    data: pd.DataFrame, period: int = 20, threshold: float = 1.5
) -> bool:
    """Check if volume is above average."""
    volume_ma = calculate_volume_ma(data, period)
    current_volume = data["volume"].iloc[-1]
    return current_volume > (volume_ma.iloc[-1] * threshold)


def calculate_adx(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ADX (Average Directional Index)."""
    high = data["high"]
    low = data["low"]
    close = data["close"]

    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Calculate Directional Movement
    dm_plus = high - high.shift(1)
    dm_minus = low.shift(1) - low

    # Filter movements
    dm_plus[(dm_plus < 0) | (dm_plus < dm_minus)] = 0
    dm_minus[(dm_minus < 0) | (dm_minus < dm_plus)] = 0

    # Smoothed values
    atr = true_range.rolling(window=period).mean()
    dm_plus_smooth = dm_plus.rolling(window=period).mean()
    dm_minus_smooth = dm_minus.rolling(window=period).mean()

    # Directional Indicators
    di_plus = 100 * (dm_plus_smooth / atr)
    di_minus = 100 * (dm_minus_smooth / atr)

    # ADX
    dx = (abs(di_plus - di_minus) / (di_plus + di_minus)) * 100
    adx = dx.rolling(window=period).mean()

    return adx

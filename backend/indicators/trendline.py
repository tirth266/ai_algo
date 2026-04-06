"""
Trendline Detection Module

Implements dynamic trendline detection using pivot highs and lows.
Identifies swing points, builds linear regression trendlines, and detects breakouts.

Algorithm:
1. Identify swing highs (pivot highs) and swing lows (pivot lows)
2. Fit linear regression trendline through pivot points
3. Calculate upper and lower trendline boundaries
4. Detect breakouts when price crosses trendline boundaries
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from scipy import stats
import logging

logger = logging.getLogger(__name__)


def identify_pivots(
    data: pd.DataFrame,
    lookback: int = 5
) -> Tuple[pd.Series, pd.Series]:
    """
    Identify swing highs and swing lows using pivot point detection.
    
    A pivot high is a bar where the high is the highest in the lookback period.
    A pivot low is a bar where the low is the lowest in the lookback period.
    
    Args:
        data: DataFrame with 'high' and 'low' columns
        lookback: Number of bars to check on each side (default: 5)
    
    Returns:
        Tuple of (pivot_highs, pivot_lows) as boolean Series
    
    Example:
        >>> pivot_highs, pivot_lows = identify_pivots(candles, lookback=5)
        >>> print(f"Found {pivot_highs.sum()} swing highs")
    """
    high = data['high']
    low = data['low']
    
    # Initialize pivot arrays
    pivot_highs = pd.Series(False, index=data.index)
    pivot_lows = pd.Series(False, index=data.index)
    
    # Need at least 2*lookback + 1 bars
    min_bars = 2 * lookback + 1
    
    if len(data) < min_bars:
        logger.warning(f"Insufficient data for pivot detection (need {min_bars}, have {len(data)})")
        return pivot_highs, pivot_lows
    
    # Find pivot highs
    for i in range(lookback, len(data) - lookback):
        # Check if current high is highest in the window
        left_window = high.iloc[i-lookback:i]
        right_window = high.iloc[i+1:i+lookback+1]
        
        if high.iloc[i] > left_window.max() and high.iloc[i] > right_window.max():
            pivot_highs.iloc[i] = True
    
    # Find pivot lows
    for i in range(lookback, len(data) - lookback):
        # Check if current low is lowest in the window
        left_window = low.iloc[i-lookback:i]
        right_window = low.iloc[i+1:i+lookback+1]
        
        if low.iloc[i] < left_window.min() and low.iloc[i] < right_window.min():
            pivot_lows.iloc[i] = True
    
    logger.info(f"Identified {pivot_highs.sum()} swing highs and {pivot_lows.sum()} swing lows")
    
    return pivot_highs, pivot_lows


def fit_trendline(
    prices: pd.Series,
    indices: pd.Series
) -> Tuple[float, float]:
    """
    Fit a linear regression trendline through given points.
    
    Args:
        prices: Price values (highs or lows)
        indices: Time indices (bar numbers)
    
    Returns:
        Tuple of (slope, intercept) for the trendline equation: y = slope*x + intercept
    
    Example:
        >>> slope, intercept = fit_trendline(swing_highs, swing_high_indices)
        >>> future_value = slope * future_index + intercept
    """
    if len(prices) < 2:
        logger.warning("Need at least 2 points to fit trendline")
        return 0.0, prices.iloc[-1] if len(prices) > 0 else 0.0
    
    # Perform linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(indices, prices)
    
    logger.debug(f"Trendline fitted: slope={slope:.4f}, intercept={intercept:.2f}, r²={r_value**2:.3f}")
    
    return slope, intercept


def calculate_trendline_channels(
    data: pd.DataFrame,
    lookback: int = 5
) -> pd.DataFrame:
    """
    Calculate trendline channels based on pivot points.
    
    Creates both upper trendline (through swing highs) and lower trendline (through swing lows).
    
    Args:
        data: DataFrame with OHLC data
        lookback: Pivot detection lookback period
    
    Returns:
        DataFrame with added columns:
        - 'trendline_upper': Upper trendline value
        - 'trendline_lower': Lower trendline value
        - 'swing_high_price': Price at most recent swing high
        - 'swing_low_price': Price at most recent swing low
    
    Example:
        >>> result = calculate_trendline_channels(candles)
        >>> print(result[['close', 'trendline_upper', 'trendline_lower']].tail())
    """
    logger.info(f"Calculating trendline channels with lookback={lookback}")
    
    df = data.copy()
    
    # Identify pivots
    pivot_highs, pivot_lows = identify_pivots(df, lookback)
    
    # Get indices of pivot points
    high_indices = df.index[pivot_highs]
    low_indices = df.index[pivot_lows]
    
    # Get pivot prices
    high_prices = df.loc[high_indices, 'high'] if len(high_indices) > 0 else pd.Series()
    low_prices = df.loc[low_indices, 'low'] if len(low_indices) > 0 else pd.Series()
    
    # Initialize trendline columns
    df['trendline_upper'] = np.nan
    df['trendline_lower'] = np.nan
    df['swing_high_price'] = np.nan
    df['swing_low_price'] = np.nan
    
    # Calculate trendlines for each bar
    for i in range(len(df)):
        # Use only pivots up to current bar
        current_high_indices = high_indices[high_indices <= df.index[i]]
        current_low_indices = low_indices[low_indices <= df.index[i]]
        
        if len(current_high_indices) >= 2:
            # Get prices as numpy array
            prices = high_prices.loc[current_high_indices].values.astype(float)
            # Use simple indices 0, 1, 2, ...
            numeric_indices = np.arange(len(prices))
            
            try:
                slope, intercept = fit_trendline(prices, numeric_indices)
                # Project trendline to current bar
                df.iloc[i, df.columns.get_loc('trendline_upper')] = slope * i + intercept
            except Exception as e:
                logger.debug(f"Could not fit upper trendline at bar {i}: {e}")
        
        if len(current_low_indices) >= 2:
            # Get prices as numpy array
            prices = low_prices.loc[current_low_indices].values.astype(float)
            # Use simple indices 0, 1, 2, ...
            numeric_indices = np.arange(len(prices))
            
            try:
                slope, intercept = fit_trendline(prices, numeric_indices)
                # Project trendline to current bar
                df.iloc[i, df.columns.get_loc('trendline_lower')] = slope * i + intercept
            except Exception as e:
                logger.debug(f"Could not fit lower trendline at bar {i}: {e}")
    
    # Mark swing high/low prices
    df.loc[pivot_highs, 'swing_high_price'] = df.loc[pivot_highs, 'high']
    df.loc[pivot_lows, 'swing_low_price'] = df.loc[pivot_lows, 'low']
    
    # Forward fill swing prices (keep track of most recent)
    df['swing_high_price'] = df['swing_high_price'].ffill()
    df['swing_low_price'] = df['swing_low_price'].ffill()
    
    logger.info("Trendline channel calculation complete")
    
    return df


def detect_breakouts(
    data: pd.DataFrame,
    lookback: int = 5
) -> Dict[str, Any]:
    """
    Detect trendline breakouts.
    
    A breakout occurs when price closes above the upper trendline or below the lower trendline.
    
    Args:
        data: DataFrame with OHLC data
        lookback: Pivot detection lookback period
    
    Returns:
        Dict with structure:
        {
            'breakout_up': bool,
            'breakout_down': bool,
            'trendline_value': float,
            'strength': float (distance from trendline as percentage)
        }
    
    Example:
        >>> breakout = detect_breakouts(candles)
        >>> if breakout['breakout_up']:
        ...     print(f"Bullish breakout! Strength: {breakout['strength']:.2f}%")
    """
    logger.info("Detecting trendline breakouts")
    
    result_df = calculate_trendline_channels(data, lookback)
    
    if len(result_df) == 0 or result_df['trendline_upper'].isna().all():
        return {
            'breakout_up': False,
            'breakout_down': False,
            'trendline_value': None,
            'strength': 0.0
        }
    
    current_close = result_df['close'].iloc[-1]
    upper_trendline = result_df['trendline_upper'].iloc[-1]
    lower_trendline = result_df['trendline_lower'].iloc[-1]
    
    breakout_up = False
    breakout_down = False
    strength = 0.0
    trendline_value = None
    
    # Check for upper breakout
    if not pd.isna(upper_trendline):
        if current_close > upper_trendline:
            breakout_up = True
            strength = ((current_close - upper_trendline) / upper_trendline) * 100
            trendline_value = upper_trendline
            logger.info(f"Bullish breakout detected! Strength: {strength:.2f}%")
    
    # Check for lower breakout
    if not pd.isna(lower_trendline):
        if current_close < lower_trendline:
            breakout_down = True
            strength = ((lower_trendline - current_close) / lower_trendline) * 100
            trendline_value = lower_trendline
            logger.info(f"Bearish breakout detected! Strength: {strength:.2f}%")
    
    return {
        'breakout_up': bool(breakout_up),
        'breakout_down': bool(breakout_down),
        'trendline_value': float(trendline_value) if trendline_value else None,
        'strength': float(abs(strength))
    }


def get_trendline_signal(data: pd.DataFrame, lookback: int = 5) -> Dict[str, Any]:
    """
    Get comprehensive trendline signal for strategy consumption.
    
    Args:
        data: DataFrame with OHLC data
        lookback: Pivot detection lookback period
    
    Returns:
        Dict with structure:
        {
            'trendline_value': float,
            'breakout_up': bool,
            'breakout_down': bool,
            'swing_high': float,
            'swing_low': float,
            'channel_width': float (percentage)
        }
    
    Example:
        >>> signal = get_trendline_signal(candles)
        >>> print(signal)
    """
    logger.info("Getting trendline signal")
    
    result_df = calculate_trendline_channels(data, lookback)
    breakout_info = detect_breakouts(data, lookback)
    
    if len(result_df) == 0:
        return {
            'trendline_value': None,
            'breakout_up': False,
            'breakout_down': False,
            'swing_high': None,
            'swing_low': None,
            'channel_width': 0.0
        }
    
    upper = result_df['trendline_upper'].iloc[-1]
    lower = result_df['trendline_lower'].iloc[-1]
    swing_high = result_df['swing_high_price'].iloc[-1]
    swing_low = result_df['swing_low_price'].iloc[-1]
    
    # Calculate channel width
    if not pd.isna(upper) and not pd.isna(lower):
        channel_width = ((upper - lower) / lower) * 100
    else:
        channel_width = 0.0
    
    signal = {
        'trendline_value': breakout_info['trendline_value'],
        'breakout_up': breakout_info['breakout_up'],
        'breakout_down': breakout_info['breakout_down'],
        'swing_high': float(swing_high) if not pd.isna(swing_high) else None,
        'swing_low': float(swing_low) if not pd.isna(swing_low) else None,
        'channel_width': float(channel_width)
    }
    
    logger.info(f"Trendline signal: breakout_up={signal['breakout_up']}, breakout_down={signal['breakout_down']}")
    
    return signal

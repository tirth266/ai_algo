"""
Liquidity Detection Module

Implements liquidity level detection and sweep identification.
Identifies previous highs/lows where liquidity pools form and detects when they are swept.

Algorithm:
1. Identify significant swing highs and lows (liquidity pools)
2. Track these levels as price moves
3. Detect sweeps when price breaks a level and closes beyond it
4. Identify potential reversals after liquidity grabs

Key Concepts:
- Liquidity High: Previous swing high where stop losses cluster
- Liquidity Low: Previous swing low where stop losses cluster
- Sweep: When price breaks a level and closes beyond it (liquidity grab)
- Rejection: Price sweeps but fails to continue in breakout direction
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


def identify_liquidity_levels(
    data: pd.DataFrame,
    lookback: int = 10
) -> Tuple[List[float], List[float]]:
    """
    Identify significant liquidity levels from swing highs and lows.
    
    These are price levels where stop losses and pending orders tend to cluster.
    
    Args:
        data: DataFrame with 'high' and 'low' columns
        lookback: Lookback period for swing detection
    
    Returns:
        Tuple of (liquidity_highs, liquidity_lows) as lists of price levels
    
    Example:
        >>> liq_highs, liq_lows = identify_liquidity_levels(candles, lookback=10)
        >>> print(f"Liquidity highs: {liq_highs}")
        >>> print(f"Liquidity lows: {liq_lows}")
    """
    logger.info(f"Identifying liquidity levels with lookback={lookback}")
    
    high = data['high']
    low = data['low']
    
    liquidity_highs = []
    liquidity_lows = []
    
    # Need at least 2*lookback + 1 bars
    min_bars = 2 * lookback + 1
    
    if len(data) < min_bars:
        logger.warning(f"Insufficient data for liquidity level detection")
        return liquidity_highs, liquidity_lows
    
    # Find swing highs (potential liquidity highs)
    for i in range(lookback, len(data) - lookback):
        left_window = high.iloc[i-lookback:i]
        right_window = high.iloc[i+1:i+lookback+1]
        
        if high.iloc[i] > left_window.max() and high.iloc[i] > right_window.max():
            liquidity_highs.append(float(high.iloc[i]))
    
    # Find swing lows (potential liquidity lows)
    for i in range(lookback, len(data) - lookback):
        left_window = low.iloc[i-lookback:i]
        right_window = low.iloc[i+1:i+lookback+1]
        
        if low.iloc[i] < left_window.min() and low.iloc[i] < right_window.min():
            liquidity_lows.append(float(low.iloc[i]))
    
    logger.info(f"Found {len(liquidity_highs)} liquidity highs and {len(liquidity_lows)} liquidity lows")
    
    return liquidity_highs, liquidity_lows


def detect_sweeps(
    data: pd.DataFrame,
    liquidity_highs: List[float],
    liquidity_lows: List[float]
) -> Dict[str, Any]:
    """
    Detect liquidity sweeps.
    
    A sweep occurs when:
    1. Price breaks above a liquidity high and closes above it
    2. Price breaks below a liquidity low and closes below it
    
    Args:
        data: DataFrame with OHLC data
        liquidity_highs: List of identified liquidity high levels
        liquidity_lows: List of identified liquidity low levels
    
    Returns:
        Dict with structure:
        {
            'sweep_high': bool,
            'sweep_low': bool,
            'swept_level': float or None,
            'sweep_type': 'high' | 'low' | None
        }
    
    Example:
        >>> sweep = detect_sweeps(candles, [22500, 22600], [22300, 22200])
        >>> if sweep['sweep_high']:
        ...     print(f"Liquidity swept at {sweep['swept_level']}")
    """
    logger.info("Detecting liquidity sweeps")
    
    if len(data) == 0:
        return {
            'sweep_high': False,
            'sweep_low': False,
            'swept_level': None,
            'sweep_type': None
        }
    
    current_bar = data.iloc[-1]
    current_close = current_bar['close']
    current_high = current_bar['high']
    current_low = current_bar['low']
    
    sweep_high = False
    sweep_low = False
    swept_level = None
    sweep_type = None
    
    # Check for high sweeps
    for level in liquidity_highs:
        if current_high > level and current_close > level:
            # Price broke and closed above liquidity high
            sweep_high = True
            swept_level = level
            sweep_type = 'high'
            logger.info(f"Liquidity high swept at {level}")
            break  # Take the most recent sweep
    
    # Check for low sweeps
    for level in liquidity_lows:
        if current_low < level and current_close < level:
            # Price broke and closed below liquidity low
            sweep_low = True
            swept_level = level
            sweep_type = 'low'
            logger.info(f"Liquidity low swept at {level}")
            break  # Take the most recent sweep
    
    return {
        'sweep_high': bool(sweep_high),
        'sweep_low': bool(sweep_low),
        'swept_level': float(swept_level) if swept_level else None,
        'sweep_type': sweep_type
    }


def detect_rejection(
    data: pd.DataFrame,
    liquidity_highs: List[float],
    liquidity_lows: List[float]
) -> Dict[str, Any]:
    """
    Detect liquidity sweep rejections (failed breakouts).
    
    A rejection occurs when:
    1. Price breaks a level during the bar
    2. But closes back inside the range
    3. Indicates failed breakout and potential reversal
    
    Args:
        data: DataFrame with OHLC data
        liquidity_highs: List of liquidity high levels
        liquidity_lows: List of liquidity low levels
    
    Returns:
        Dict with structure:
        {
            'rejection_high': bool,
            'rejection_low': bool,
            'rejected_level': float or None,
            'wick_size': float (size of rejection wick)
        }
    
    Example:
        >>> rejection = detect_rejection(candles, [22500], [22300])
        >>> if rejection['rejection_high']:
        ...     print(f"Rejection at {rejection['rejected_level']}, wick: {rejection['wick_size']}%")
    """
    logger.info("Detecting liquidity rejections")
    
    if len(data) == 0:
        return {
            'rejection_high': False,
            'rejection_low': False,
            'rejected_level': None,
            'wick_size': 0.0
        }
    
    current_bar = data.iloc[-1]
    current_close = current_bar['close']
    current_high = current_bar['high']
    current_low = current_bar['low']
    current_open = current_bar['open']
    
    rejection_high = False
    rejection_low = False
    rejected_level = None
    wick_size = 0.0
    
    # Calculate body size for rejection confirmation
    body_size = abs(current_close - current_open)
    total_range = current_high - current_low
    
    if total_range == 0:
        return {
            'rejection_high': False,
            'rejection_low': False,
            'rejected_level': None,
            'wick_size': 0.0
        }
    
    # Check for high rejections
    for level in liquidity_highs:
        if current_high > level and current_close < level:
            # Price broke above but closed below - bearish rejection
            upper_wick = current_high - max(current_open, current_close)
            wick_pct = (upper_wick / total_range) * 100
            
            if wick_pct > 50:  # Significant rejection wick
                rejection_high = True
                rejected_level = level
                wick_size = wick_pct
                logger.info(f"Rejection at liquidity high {level}, wick: {wick_pct:.1f}%")
                break
    
    # Check for low rejections
    for level in liquidity_lows:
        if current_low < level and current_close > level:
            # Price broke below but closed above - bullish rejection
            lower_wick = min(current_open, current_close) - current_low
            wick_pct = (lower_wick / total_range) * 100
            
            if wick_pct > 50:  # Significant rejection wick
                rejection_low = True
                rejected_level = level
                wick_size = wick_pct
                logger.info(f"Rejection at liquidity low {level}, wick: {wick_pct:.1f}%")
                break
    
    return {
        'rejection_high': bool(rejection_high),
        'rejection_low': bool(rejection_low),
        'rejected_level': float(rejected_level) if rejected_level else None,
        'wick_size': float(wick_size)
    }


def get_liquidity_signal(
    data: pd.DataFrame,
    lookback: int = 10
) -> Dict[str, Any]:
    """
    Get comprehensive liquidity signal for strategy consumption.
    
    Combines sweep detection and rejection analysis into a single signal.
    
    Args:
        data: DataFrame with OHLC data
        lookback: Lookback period for liquidity level identification
    
    Returns:
        Dict with structure:
        {
            'liquidity_high_sweep': bool,
            'liquidity_low_sweep': bool,
            'level': float or None,
            'sweep_type': 'sweep' | 'rejection' | None,
            'signal_strength': float (0-100)
        }
    
    Example:
        >>> signal = get_liquidity_signal(candles, lookback=10)
        >>> print(signal)
        {
            'liquidity_high_sweep': True,
            'liquidity_low_sweep': False,
            'level': 22500.0,
            'sweep_type': 'sweep',
            'signal_strength': 75.5
        }
    """
    logger.info(f"Getting liquidity signal with lookback={lookback}")
    
    # Identify liquidity levels
    liquidity_highs, liquidity_lows = identify_liquidity_levels(data, lookback)
    
    if not liquidity_highs and not liquidity_lows:
        return {
            'liquidity_high_sweep': False,
            'liquidity_low_sweep': False,
            'level': None,
            'sweep_type': None,
            'signal_strength': 0.0
        }
    
    # Detect sweeps
    sweep_info = detect_sweeps(data, liquidity_highs, liquidity_lows)
    
    # Detect rejections
    rejection_info = detect_rejection(data, liquidity_highs, liquidity_lows)
    
    # Determine primary signal
    liquidity_high_sweep = False
    liquidity_low_sweep = False
    level = None
    sweep_type = None
    signal_strength = 0.0
    
    if sweep_info['sweep_high']:
        liquidity_high_sweep = True
        level = sweep_info['swept_level']
        sweep_type = 'sweep'
        signal_strength = 80.0  # Strong signal
    elif sweep_info['sweep_low']:
        liquidity_low_sweep = True
        level = sweep_info['swept_level']
        sweep_type = 'sweep'
        signal_strength = 80.0
    elif rejection_info['rejection_high']:
        liquidity_high_sweep = True  # Still consider it a "sweep" but with rejection
        level = rejection_info['rejected_level']
        sweep_type = 'rejection'
        signal_strength = min(100.0, rejection_info['wick_size'])  # Stronger wick = stronger signal
    elif rejection_info['rejection_low']:
        liquidity_low_sweep = True
        level = rejection_info['rejected_level']
        sweep_type = 'rejection'
        signal_strength = min(100.0, rejection_info['wick_size'])
    
    logger.info(f"Liquidity signal: sweep_type={sweep_type}, strength={signal_strength:.1f}%")
    
    return {
        'liquidity_high_sweep': bool(liquidity_high_sweep),
        'liquidity_low_sweep': bool(liquidity_low_sweep),
        'level': float(level) if level else None,
        'sweep_type': sweep_type,
        'signal_strength': float(signal_strength)
    }

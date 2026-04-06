"""
Supertrend Indicator Module

Implements the Supertrend technical indicator for trend detection.
The Supertrend indicator uses ATR (Average True Range) to calculate dynamic support/resistance levels.

Algorithm:
1. Calculate ATR using specified period
2. Calculate upper and lower bands using ATR multiplier
3. Determine trend direction based on price position relative to bands
4. Generate supertrend values that flip when trend changes
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_atr(data: pd.DataFrame, period: int = 10) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        data: DataFrame with 'high', 'low', 'close' columns
        period: ATR calculation period (default: 10)
    
    Returns:
        pd.Series: ATR values
    """
    high = data['high']
    low = data['low']
    close = data['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR as SMA of True Range
    atr = true_range.rolling(window=period).mean()
    
    return atr


def supertrend(
    data: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Calculate Supertrend indicator.
    
    The Supertrend indicator plots a line that switches between acting as support
    (in uptrend) and resistance (in downtrend).
    
    Args:
        data: DataFrame with OHLC data
              Required columns: ['open', 'high', 'low', 'close']
        period: ATR period (default: 10)
        multiplier: ATR multiplier for band calculation (default: 3.0)
    
    Returns:
        DataFrame with added columns:
        - 'supertrend': The supertrend line value
        - 'trend_direction': 1 for bullish, -1 for bearish
        - 'upper_band': Upper band value
        - 'lower_band': Lower band value
    
    Example:
        >>> result = supertrend(candles, period=10, multiplier=3.0)
        >>> print(result[['close', 'supertrend', 'trend_direction']].tail())
    """
    logger.info(f"Calculating Supertrend with period={period}, multiplier={multiplier}")
    
    if len(data) < period + 1:
        logger.warning("Insufficient data for Supertrend calculation")
        return pd.DataFrame()
    
    df = data.copy()
    
    # Calculate ATR
    df['atr'] = calculate_atr(df, period)
    
    # Calculate basic upper and lower bands
    hl2 = (df['high'] + df['low']) / 2
    
    df['upper_band'] = hl2 + (multiplier * df['atr'])
    df['lower_band'] = hl2 - (multiplier * df['atr'])
    
    # Initialize arrays for supertrend and trend direction
    supertrend_values = np.zeros(len(df))
    trend_direction = np.zeros(len(df))
    
    # First valid index (after ATR period)
    first_valid = period - 1
    
    # Initial values
    supertrend_values[first_valid] = df['upper_band'].iloc[first_valid]
    trend_direction[first_valid] = -1  # Start with bearish assumption
    
    # Calculate supertrend iteratively
    for i in range(first_valid + 1, len(df)):
        prev_trend = trend_direction[i - 1]
        prev_supertrend = supertrend_values[i - 1]
        
        current_close = df['close'].iloc[i]
        current_upper = df['upper_band'].iloc[i]
        current_lower = df['lower_band'].iloc[i]
        
        # Determine new supertrend value and trend direction
        if prev_trend == 1:  # Previous trend was bullish
            if current_close > prev_supertrend:
                # Trend continues bullish
                trend_direction[i] = 1
                supertrend_values[i] = max(current_lower, prev_supertrend)
            else:
                # Trend reverses to bearish
                trend_direction[i] = -1
                supertrend_values[i] = current_upper
        else:  # Previous trend was bearish
            if current_close < prev_supertrend:
                # Trend continues bearish
                trend_direction[i] = -1
                supertrend_values[i] = min(current_upper, prev_supertrend)
            else:
                # Trend reverses to bullish
                trend_direction[i] = 1
                supertrend_values[i] = current_lower
    
    # Assign to DataFrame
    df['supertrend'] = supertrend_values
    df['trend_direction'] = trend_direction.astype(int)
    
    # Clean up temporary columns
    df.drop(columns=['atr'], inplace=True)
    
    logger.info(f"Supertrend calculation complete. Latest trend: {'Bullish' if trend_direction[-1] == 1 else 'Bearish'}")
    
    return df


def get_supertrend_signal(data: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Dict[str, Any]:
    """
    Get Supertrend signal in dictionary format for strategy consumption.
    
    Args:
        data: DataFrame with OHLC data
        period: ATR period
        multiplier: ATR multiplier
    
    Returns:
        Dict with structure:
        {
            'trend': 'bullish' | 'bearish',
            'value': float (supertrend value),
            'direction': int (1 or -1),
            'change': bool (True if trend changed from previous bar)
        }
    
    Example:
        >>> signal = get_supertrend_signal(candles)
        >>> print(signal)
        {'trend': 'bullish', 'value': 22450.5, 'direction': 1, 'change': False}
    """
    logger.info("Getting Supertrend signal")
    
    result_df = supertrend(data, period, multiplier)
    
    if result_df.empty or len(result_df) < 2:
        return {
            'trend': 'unknown',
            'value': None,
            'direction': 0,
            'change': False
        }
    
    current_direction = result_df['trend_direction'].iloc[-1]
    previous_direction = result_df['trend_direction'].iloc[-2] if len(result_df) >= 2 else current_direction
    
    signal = {
        'trend': 'bullish' if current_direction == 1 else 'bearish',
        'value': float(result_df['supertrend'].iloc[-1]),
        'direction': int(current_direction),
        'change': bool(current_direction != previous_direction)
    }
    
    logger.info(f"Supertrend signal: {signal['trend']} (changed: {signal['change']})")
    
    return signal

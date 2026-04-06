"""
TradingView Supertrend Indicator Module

Implements the exact TradingView Pine Script Supertrend logic.
Uses ATR-based dynamic trailing stop with trend direction detection.

Algorithm (Pine Script reference):
1. Calculate ATR using True Range formula
2. Calculate basic upper/lower bands using hl2
3. Apply final band logic based on previous close conditions
4. Determine trend direction from price position relative to bands
5. Calculate supertrend line value

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TradingViewSupertrend:
    """
    TradingView Supertrend Indicator.
    
    Implements the exact logic from TradingView Pine Script.
    
    Parameters:
    - atr_length: ATR calculation period (default: 10)
    - factor: ATR multiplier for band width (default: 3.0)
    """
    
    def __init__(self, atr_length: int = 10, factor: float = 3.0):
        """
        Initialize TradingView Supertrend indicator.
        
        Args:
            atr_length: ATR period (default: 10)
            factor: ATR multiplier (default: 3.0)
        """
        self.atr_length = atr_length
        self.factor = factor
        
        logger.info(f"TradingViewSupertrend initialized: atr_length={atr_length}, factor={factor}")
    
    def calculate(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate TradingView Supertrend indicator.
        
        Args:
            data: DataFrame with OHLCV columns
        
        Returns:
            Dict with supertrend results
        """
        # Validate minimum data
        if len(data) < self.atr_length + 1:
            logger.debug(f"Insufficient data: {len(data)} bars (need {self.atr_length + 1})")
            return self._empty_result()
        
        try:
            df = data.copy()
            
            # Step 1: Calculate ATR
            atr = self._calculate_atr(df)
            
            # Step 2: Calculate hl2 and basic bands
            df['hl2'] = (df['high'] + df['low']) / 2
            
            # Basic bands (before adjustment)
            df['basic_upper'] = df['hl2'] + (self.factor * atr)
            df['basic_lower'] = df['hl2'] - (self.factor * atr)
            
            # Step 3: Calculate final bands with previous close logic
            final_upper, final_lower = self._calculate_final_bands(df)
            
            # Step 4 & 5: Determine trend direction and calculate supertrend
            trend_direction, supertrend_values, trend_changes = self._calculate_trend_and_supertrend(
                df, final_upper, final_lower
            )
            
            # Get latest values
            latest_idx = len(df) - 1
            latest_trend = 'bullish' if trend_direction[latest_idx] == -1 else 'bearish'
            latest_direction = trend_direction[latest_idx]
            latest_value = supertrend_values[latest_idx]
            latest_upper = final_upper.iloc[latest_idx]
            latest_lower = final_lower.iloc[latest_idx]
            latest_change = trend_changes[latest_idx]
            
            # Build result
            result = {
                'trend': latest_trend,
                'direction': int(latest_direction),
                'value': float(latest_value),
                'upper_band': float(latest_upper),
                'lower_band': float(latest_lower),
                'trend_change': bool(latest_change),
                'all_trends': trend_direction.tolist(),
                'all_supertrends': supertrend_values.tolist()
            }
            
            logger.info(f"Supertrend calculated: {latest_trend} (changed: {latest_change})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating TradingView Supertrend: {str(e)}", exc_info=True)
            return self._empty_result()
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        True Range formula:
        TR = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )
        
        ATR = SMA(TR, atr_length)
        
        Args:
            df: DataFrame with OHLC data
        
        Returns:
            pd.Series: ATR values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate True Range components
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR is SMA of True Range
        atr = true_range.rolling(window=self.atr_length).mean()
        
        logger.debug(f"ATR calculated: latest={atr.iloc[-1]:.2f}")
        
        return atr
    
    def _calculate_final_bands(self, df: pd.DataFrame) -> tuple:
        """
        Calculate final upper and lower bands with Pine Script logic.
        
        Upper Band Logic:
        If previous close > previous upper_band
            keep upper_band unchanged
        Else
            upper_band = min(current basic_upper, previous upper_band)
        
        Lower Band Logic:
        If previous close < previous lower_band
            keep lower_band unchanged
        Else
            lower_band = max(current basic_lower, previous basic_lower)
        
        Args:
            df: DataFrame with basic_upper and basic_lower columns
        
        Returns:
            Tuple of (final_upper, final_lower) as Series
        """
        n = len(df)
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        
        # Initialize with basic bands
        final_upper[0] = df['basic_upper'].iloc[0]
        final_lower[0] = df['basic_lower'].iloc[0]
        
        # Iterate through bars applying Pine Script logic
        for i in range(1, n):
            prev_close = df['close'].iloc[i - 1]
            prev_upper = final_upper[i - 1]
            prev_lower = final_lower[i - 1]
            
            current_basic_upper = df['basic_upper'].iloc[i]
            current_basic_lower = df['basic_lower'].iloc[i]
            
            # Upper band logic
            if prev_close > prev_upper:
                # Keep unchanged
                final_upper[i] = prev_upper
            else:
                # Min of current and previous
                final_upper[i] = min(current_basic_upper, prev_upper)
            
            # Lower band logic
            if prev_close < prev_lower:
                # Keep unchanged
                final_lower[i] = prev_lower
            else:
                # Max of current and previous
                final_lower[i] = max(current_basic_lower, prev_lower)
        
        logger.debug(f"Final bands calculated: upper={final_upper[-1]:.2f}, lower={final_lower[-1]:.2f}")
        
        return pd.Series(final_upper, index=df.index), pd.Series(final_lower, index=df.index)
    
    def _calculate_trend_and_supertrend(
        self,
        df: pd.DataFrame,
        final_upper: pd.Series,
        final_lower: pd.Series
    ) -> tuple:
        """
        Determine trend direction and calculate supertrend line.
        
        Trend Direction Logic:
        If close > previous upper_band
            trend = bullish (-1)
        If close < previous lower_band
            trend = bearish (1)
        
        Supertrend Line:
        If trend is bullish
            supertrend = lower_band
        If trend is bearish
            supertrend = upper_band
        
        Args:
            df: DataFrame with OHLC data
            final_upper: Final upper band Series
            final_lower: Final lower band Series
        
        Returns:
            Tuple of (trend_direction, supertrend_values, trend_changes)
        """
        n = len(df)
        trend_direction = np.zeros(n)  # -1 = bullish, 1 = bearish
        supertrend_values = np.zeros(n)
        trend_changes = np.zeros(n, dtype=bool)
        
        # Initialize first bar
        # Start with bearish assumption if no clear signal
        if df['close'].iloc[0] > final_upper.iloc[0]:
            trend_direction[0] = -1  # Bullish
        else:
            trend_direction[0] = 1   # Bearish
        
        # Set initial supertrend value
        if trend_direction[0] == -1:
            supertrend_values[0] = final_lower.iloc[0]
        else:
            supertrend_values[0] = final_upper.iloc[0]
        
        # Iterate through remaining bars
        for i in range(1, n):
            prev_trend = trend_direction[i - 1]
            current_close = df['close'].iloc[i]
            prev_upper = final_upper.iloc[i - 1]
            prev_lower = final_lower.iloc[i - 1]
            
            # Determine new trend based on Pine Script logic
            if prev_trend == -1:  # Previous was bullish
                if current_close < prev_lower:
                    # Trend reverses to bearish
                    trend_direction[i] = 1
                    trend_changes[i] = True
                else:
                    # Trend continues bullish
                    trend_direction[i] = -1
            else:  # Previous was bearish
                if current_close > prev_upper:
                    # Trend reverses to bullish
                    trend_direction[i] = -1
                    trend_changes[i] = True
                else:
                    # Trend continues bearish
                    trend_direction[i] = 1
            
            # Calculate supertrend value based on current trend
            if trend_direction[i] == -1:  # Bullish
                supertrend_values[i] = final_lower.iloc[i]
            else:  # Bearish
                supertrend_values[i] = final_upper.iloc[i]
        
        num_changes = trend_changes.sum()
        logger.debug(f"Trend direction calculated: {num_changes} changes detected")
        
        return trend_direction, supertrend_values, trend_changes
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when calculation fails."""
        return {
            'trend': 'unknown',
            'direction': 0,
            'value': None,
            'upper_band': None,
            'lower_band': None,
            'trend_change': False,
            'all_trends': [],
            'all_supertrends': []
        }

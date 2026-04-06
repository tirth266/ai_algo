"""
LuxAlgo Liquidity Swings Indicator Module

Detects swing highs/lows, creates liquidity zones, tracks price interactions,
and identifies liquidity sweeps with volume analysis.

Algorithm:
1. Detect pivot highs and lows using rolling windows
2. Create liquidity zones around pivots
3. Track price interactions (touches) with zones
4. Accumulate volume at liquidity zones
5. Detect liquidity sweeps (bullish/bearish)

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class LuxAlgoLiquiditySwings:
    """
    LuxAlgo Liquidity Swings Indicator.
    
    Detects liquidity zones from swing points and identifies sweeps.
    
    Parameters:
    - pivot_lookback: Pivot detection window (default: 14)
    - area_mode: Zone calculation method ('wick' or 'full_range')
    - filter_mode: Filtering method ('count' or 'volume')
    - filter_threshold: Minimum touches/volume to consider zone significant
    """
    
    def __init__(
        self,
        pivot_lookback: int = 14,
        area_mode: str = 'wick',
        filter_mode: str = 'count',
        filter_threshold: int = 0
    ):
        """
        Initialize LuxAlgo Liquidity Swings indicator.
        
        Args:
            pivot_lookback: Number of bars for pivot detection
            area_mode: 'wick' (uses wicks) or 'full_range' (uses full candle range)
            filter_mode: 'count' (filter by touch count) or 'volume' (filter by volume)
            filter_threshold: Minimum threshold for filtering
        """
        self.pivot_lookback = pivot_lookback
        self.area_mode = area_mode.lower()
        self.filter_mode = filter_mode.lower()
        self.filter_threshold = filter_threshold
        
        # Validate parameters
        if self.area_mode not in ['wick', 'full_range']:
            logger.warning(f"Invalid area_mode '{self.area_mode}', defaulting to 'wick'")
            self.area_mode = 'wick'
        
        if self.filter_mode not in ['count', 'volume']:
            logger.warning(f"Invalid filter_mode '{self.filter_mode}', defaulting to 'count'")
            self.filter_mode = 'count'
        
        # State tracking
        self.liquidity_zones: List[Dict[str, Any]] = []
        self.last_swing_high = None
        self.last_swing_low = None
        
        logger.info(
            f"LuxAlgoLiquiditySwings initialized: "
            f"lookback={pivot_lookback}, area={area_mode}, filter={filter_mode}"
        )
    
    def calculate(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Liquidity Swings indicator on market data.
        
        Args:
            data: DataFrame with OHLCV columns
        
        Returns:
            Dict with indicator results
        """
        # Validate minimum data
        min_bars = 2 * self.pivot_lookback + 1
        if len(data) < min_bars:
            logger.debug(f"Insufficient data: {len(data)} bars (need {min_bars})")
            return self._empty_result()
        
        try:
            # Step 1: Detect pivots
            pivot_highs, pivot_lows = self._detect_pivots(data)
            
            # Step 2: Create/update liquidity zones
            self._update_liquidity_zones(data, pivot_highs, pivot_lows)
            
            # Step 3: Track price interactions with zones
            self._track_zone_interactions(data)
            
            # Step 4: Detect liquidity sweeps
            sweep_detected, sweep_type = self._detect_sweeps(data)
            
            # Step 5: Build result
            result = self._build_result(data, pivot_highs, pivot_lows, sweep_detected, sweep_type)
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating Liquidity Swings: {str(e)}", exc_info=True)
            return self._empty_result()
    
    def _detect_pivots(self, data: pd.DataFrame) -> tuple:
        """
        Detect pivot highs and pivot lows.
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Tuple of (pivot_highs, pivot_lows) as boolean Series
        """
        high = data['high']
        low = data['low']
        
        pivot_highs = pd.Series(False, index=data.index)
        pivot_lows = pd.Series(False, index=data.index)
        
        min_bars = 2 * self.pivot_lookback + 1
        
        if len(data) < min_bars:
            return pivot_highs, pivot_lows
        
        # Detect pivot highs
        for i in range(self.pivot_lookback, len(data) - self.pivot_lookback):
            left_window = high.iloc[i-self.pivot_lookback:i]
            right_window = high.iloc[i+1:i+self.pivot_lookback+1]
            
            if high.iloc[i] > left_window.max() and high.iloc[i] >= right_window.max():
                pivot_highs.iloc[i] = True
                self.last_swing_high = {
                    'index': i,
                    'price': float(high.iloc[i]),
                    'time': data.index[i]
                }
                logger.debug(f"Swing high detected at {high.iloc[i]:.2f}")
        
        # Detect pivot lows
        for i in range(self.pivot_lookback, len(data) - self.pivot_lookback):
            left_window = low.iloc[i-self.pivot_lookback:i]
            right_window = low.iloc[i+1:i+self.pivot_lookback+1]
            
            if low.iloc[i] < left_window.min() and low.iloc[i] <= right_window.min():
                pivot_lows.iloc[i] = True
                self.last_swing_low = {
                    'index': i,
                    'price': float(low.iloc[i]),
                    'time': data.index[i]
                }
                logger.debug(f"Swing low detected at {low.iloc[i]:.2f}")
        
        num_highs = pivot_highs.sum()
        num_lows = pivot_lows.sum()
        logger.info(f"Pivot detection: {num_highs} highs, {num_lows} lows")
        
        return pivot_highs, pivot_lows
    
    def _update_liquidity_zones(self, data: pd.DataFrame, pivot_highs: pd.Series, pivot_lows: pd.Series):
        """
        Create and update liquidity zones from pivot points.
        
        Args:
            data: DataFrame with OHLCV data
            pivot_highs: Boolean Series marking pivot highs
            pivot_lows: Boolean Series marking pivot lows
        """
        current_index = len(data) - 1
        
        # Add new liquidity zones from pivot highs
        if pivot_highs.any():
            last_pivot_idx = pivot_highs[pivot_highs].index[-1]
            last_pivot_bar = data.loc[last_pivot_idx]
            
            # Create zone based on area mode
            if self.area_mode == 'wick':
                zone_top = float(last_pivot_bar['high'])
                zone_bottom = float(last_pivot_bar['close'])
            else:  # full_range
                zone_top = float(last_pivot_bar['high'])
                zone_bottom = float(last_pivot_bar['low'])
            
            # Check if we already have this zone
            zone_exists = any(
                abs(zone['top'] - zone_top) < 0.01 and 
                zone['type'] == 'high'
                for zone in self.liquidity_zones
            )
            
            if not zone_exists:
                zone = {
                    'type': 'high',
                    'top': zone_top,
                    'bottom': zone_bottom,
                    'created_at': last_pivot_idx,
                    'touch_count': 0,
                    'accumulated_volume': 0.0,
                    'last_touched': None
                }
                self.liquidity_zones.append(zone)
                logger.info(f"Liquidity zone created at high: {zone_top:.2f}")
        
        # Add new liquidity zones from pivot lows
        if pivot_lows.any():
            last_pivot_idx = pivot_lows[pivot_lows].index[-1]
            last_pivot_bar = data.loc[last_pivot_idx]
            
            # Create zone based on area mode
            if self.area_mode == 'wick':
                zone_top = float(last_pivot_bar['open'])
                zone_bottom = float(last_pivot_bar['low'])
            else:  # full_range
                zone_top = float(last_pivot_bar['high'])
                zone_bottom = float(last_pivot_bar['low'])
            
            # Check if we already have this zone
            zone_exists = any(
                abs(zone['bottom'] - zone_bottom) < 0.01 and 
                zone['type'] == 'low'
                for zone in self.liquidity_zones
            )
            
            if not zone_exists:
                zone = {
                    'type': 'low',
                    'top': zone_top,
                    'bottom': zone_bottom,
                    'created_at': last_pivot_idx,
                    'touch_count': 0,
                    'accumulated_volume': 0.0,
                    'last_touched': None
                }
                self.liquidity_zones.append(zone)
                logger.info(f"Liquidity zone created at low: {zone_bottom:.2f}")
    
    def _track_zone_interactions(self, data: pd.DataFrame):
        """
        Track price interactions with liquidity zones.
        
        Args:
            data: DataFrame with OHLCV data
        """
        if not self.liquidity_zones:
            return
        
        current_bar = data.iloc[-1]
        current_high = current_bar['high']
        current_low = current_bar['low']
        current_volume = current_bar['volume']
        
        # Check each zone for interactions
        for zone in self.liquidity_zones:
            touched = False
            
            if zone['type'] == 'high':
                # Check if price touched the high zone
                if current_low <= zone['top'] and current_high >= zone['bottom']:
                    touched = True
            elif zone['type'] == 'low':
                # Check if price touched the low zone
                if current_high >= zone['bottom'] and current_low <= zone['top']:
                    touched = True
            
            if touched:
                zone['touch_count'] += 1
                zone['accumulated_volume'] += float(current_volume)
                zone['last_touched'] = len(data) - 1
                logger.debug(f"Liquidity zone touched: {zone['type']} at {zone['top']:.2f}/{zone['bottom']:.2f}")
    
    def _detect_sweeps(self, data: pd.DataFrame) -> tuple:
        """
        Detect liquidity sweeps.
        
        Bullish sweep: Price dips below swing low, then closes back above
        Bearish sweep: Price breaks above swing high, then closes below
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Tuple of (sweep_detected: bool, sweep_type: str or None)
        """
        if len(data) < 2:
            return False, None
        
        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2]
        
        current_close = current_bar['close']
        current_high = current_bar['high']
        current_low = current_bar['low']
        
        prev_close = prev_bar['close']
        prev_high = prev_bar['high']
        prev_low = prev_bar['low']
        
        # Check for bullish sweep (sweep of swing low)
        if self.last_swing_low:
            swing_low_price = self.last_swing_low['price']
            
            # Price broke below swing low but closed back above
            if current_low < swing_low_price and current_close > swing_low_price:
                # Confirmation: previous bar was also below or near swing low
                if prev_low <= swing_low_price * 1.001:  # Within 0.1%
                    logger.info(f"Bullish liquidity sweep detected at {swing_low_price:.2f}")
                    return True, 'bullish'
        
        # Check for bearish sweep (sweep of swing high)
        if self.last_swing_high:
            swing_high_price = self.last_swing_high['price']
            
            # Price broke above swing high but closed back below
            if current_high > swing_high_price and current_close < swing_high_price:
                # Confirmation: previous bar was also above or near swing high
                if prev_high >= swing_high_price * 0.999:  # Within 0.1%
                    logger.info(f"Bearish liquidity sweep detected at {swing_high_price:.2f}")
                    return True, 'bearish'
        
        return False, None
    
    def _build_result(
        self,
        data: pd.DataFrame,
        pivot_highs: pd.Series,
        pivot_lows: pd.Series,
        sweep_detected: bool,
        sweep_type: Optional[str]
    ) -> Dict[str, Any]:
        """
        Build result dictionary.
        
        Args:
            data: DataFrame with OHLCV data
            pivot_highs: Boolean Series
            pivot_lows: Boolean Series
            sweep_detected: Whether sweep was detected
            sweep_type: Type of sweep ('bullish' or 'bearish')
        
        Returns:
            Dict with indicator results
        """
        current_index = len(data) - 1
        
        # Get most significant liquidity zone
        significant_zone = None
        if self.liquidity_zones:
            # Filter zones based on filter mode
            if self.filter_mode == 'count':
                filtered_zones = [
                    z for z in self.liquidity_zones 
                    if z['touch_count'] >= self.filter_threshold
                ]
            elif self.filter_mode == 'volume':
                filtered_zones = [
                    z for z in self.liquidity_zones 
                    if z['accumulated_volume'] >= self.filter_threshold
                ]
            else:
                filtered_zones = self.liquidity_zones
            
            if filtered_zones:
                # Get most recently touched zone
                significant_zone = max(
                    filtered_zones,
                    key=lambda z: z.get('last_touched', 0) or 0
                )
        
        # Build result
        result = {
            'swing_high_detected': bool(pivot_highs.iloc[-1]),
            'swing_low_detected': bool(pivot_lows.iloc[-1]),
            'liquidity_zone_top': float(significant_zone['top']) if significant_zone else None,
            'liquidity_zone_bottom': float(significant_zone['bottom']) if significant_zone else None,
            'touch_count': significant_zone['touch_count'] if significant_zone else 0,
            'volume_accumulated': significant_zone['accumulated_volume'] if significant_zone else 0.0,
            'sweep_detected': bool(sweep_detected),
            'sweep_type': sweep_type,
            'last_swing_high': self.last_swing_high['price'] if self.last_swing_high else None,
            'last_swing_low': self.last_swing_low['price'] if self.last_swing_low else None
        }
        
        logger.debug(
            f"Result built: swing_high={result['swing_high_detected']}, "
            f"swing_low={result['swing_low_detected']}, sweep={sweep_detected}"
        )
        
        return result
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when calculation fails."""
        return {
            'swing_high_detected': False,
            'swing_low_detected': False,
            'liquidity_zone_top': None,
            'liquidity_zone_bottom': None,
            'touch_count': 0,
            'volume_accumulated': 0.0,
            'sweep_detected': False,
            'sweep_type': None,
            'last_swing_high': None,
            'last_swing_low': None
        }
    
    def get_liquidity_zones(self) -> List[Dict[str, Any]]:
        """Get list of all liquidity zones."""
        return self.liquidity_zones.copy()
    
    def clear_state(self):
        """Clear indicator state."""
        self.liquidity_zones = []
        self.last_swing_high = None
        self.last_swing_low = None
        logger.info("LuxAlgoLiquiditySwings state cleared")

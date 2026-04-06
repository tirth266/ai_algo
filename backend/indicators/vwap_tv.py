"""
TradingView VWAP Indicator Module

Implements Volume Weighted Average Price (VWAP) with standard deviation bands.
Reproduces exact TradingView VWAP logic with session-based resets.

Features:
- Session-based VWAP calculation (Daily/Weekly/Monthly/Quarterly/Yearly)
- Standard deviation bands with customizable multipliers
- HLC3 typical price source
- Cumulative volume-weighted averaging

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TradingViewVWAP:
    """
    TradingView VWAP Indicator with Standard Deviation Bands.
    
    Implements Volume Weighted Average Price calculation with configurable
    anchor periods and standard deviation bands.
    
    Parameters:
        anchor_period: Reset period for VWAP calculation
                      Options: 'Session', 'Week', 'Month', 'Quarter', 'Year'
        source: Price source for calculation (default: 'hlc3')
        band_multiplier_1: First band multiplier (default: 1.0)
        band_multiplier_2: Second band multiplier (default: 2.0)
        band_multiplier_3: Third band multiplier (default: 3.0)
    
    Example:
        >>> vwap = TradingViewVWAP(anchor_period='Session')
        >>> result = vwap.calculate(candles)
        >>> print(f"VWAP: {result['vwap']:.2f}")
    """
    
    def __init__(
        self,
        anchor_period: str = "Session",
        source: str = "hlc3",
        band_multiplier_1: float = 1.0,
        band_multiplier_2: float = 2.0,
        band_multiplier_3: float = 3.0
    ):
        """
        Initialize VWAP indicator.
        
        Args:
            anchor_period: Reset period for cumulative calculation
            source: Price source (default: hlc3)
            band_multiplier_1: First standard deviation band multiplier
            band_multiplier_2: Second standard deviation band multiplier
            band_multiplier_3: Third standard deviation band multiplier
        """
        self.anchor_period = anchor_period
        self.source = source
        self.band_multiplier_1 = band_multiplier_1
        self.band_multiplier_2 = band_multiplier_2
        self.band_multiplier_3 = band_multiplier_3
        
        logger.info(
            f"TradingViewVWAP initialized: anchor={anchor_period}, "
            f"source={source}, bands=[{band_multiplier_1}, {band_multiplier_2}, {band_multiplier_3}]"
        )
    
    def calculate(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate VWAP and standard deviation bands.
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Dict with VWAP values and bands
        
        Example:
            >>> result = vwap.calculate(candles)
            >>> # result contains:
            >>> # - vwap: Current VWAP value
            >>> # - upper_band_1/2/3: Upper bands
            >>> # - lower_band_1/2/3: Lower bands
            >>> # - price_above_vwap: Boolean
        """
        if len(data) < 2:
            logger.warning("Insufficient data for VWAP calculation")
            return self._empty_result()
        
        try:
            # Step 1: Calculate typical price (TP)
            tp = self._calculate_typical_price(data)
            
            # Step 2: Calculate TP * Volume
            tpv = tp * data['volume']
            
            # Step 3 & 4: Calculate cumulative VWAP with resets
            vwap_values = self._calculate_vwap_with_resets(data, tp, tpv)
            
            # Calculate standard deviation bands
            stdev_values = self._calculate_standard_deviation(data, tp, vwap_values)
            
            # Calculate bands
            bands = self._calculate_bands(vwap_values, stdev_values)
            
            # Get latest values
            latest_idx = len(data) - 1
            latest_vwap = vwap_values.iloc[latest_idx]
            latest_price = tp.iloc[latest_idx]
            
            # Build result dictionary
            result = {
                'vwap': float(latest_vwap),
                'upper_band_1': float(bands['upper_1'].iloc[latest_idx]),
                'lower_band_1': float(bands['lower_1'].iloc[latest_idx]),
                'upper_band_2': float(bands['upper_2'].iloc[latest_idx]),
                'lower_band_2': float(bands['lower_2'].iloc[latest_idx]),
                'upper_band_3': float(bands['upper_3'].iloc[latest_idx]),
                'lower_band_3': float(bands['lower_3'].iloc[latest_idx]),
                'price_above_vwap': bool(latest_price > latest_vwap),
                'stdev': float(stdev_values.iloc[latest_idx])
            }
            
            # Log significant events
            self._log_events(data, tp, vwap_values, bands, latest_idx)
            
            logger.info(
                f"VWAP calculated: {latest_vwap:.2f}, "
                f"price={'above' if result['price_above_vwap'] else 'below'} VWAP, "
                f"stdev={result['stdev']:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating VWAP: {str(e)}", exc_info=True)
            return self._empty_result()
    
    def _calculate_typical_price(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate typical price based on configured source.
        
        Default: HLC3 = (high + low + close) / 3
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Series with typical price values
        """
        if self.source == 'hlc3':
            tp = (data['high'] + data['low'] + data['close']) / 3.0
        elif self.source == 'hl2':
            tp = (data['high'] + data['low']) / 2.0
        elif self.source == 'close':
            tp = data['close']
        else:
            # Default to HLC3
            tp = (data['high'] + data['low'] + data['close']) / 3.0
        
        logger.debug(f"Typical price calculated using source={self.source}")
        return tp
    
    def _calculate_vwap_with_resets(
        self,
        data: pd.DataFrame,
        tp: pd.Series,
        tpv: pd.Series
    ) -> pd.Series:
        """
        Calculate cumulative VWAP with periodic resets.
        
        Resets calculation when anchor period changes:
        - Session: New trading day
        - Week: New week
        - Month: New month
        - Quarter: New quarter
        - Year: New year
        
        Args:
            data: DataFrame with OHLCV data
            tp: Typical price series
            tpv: Typical price * volume series
        
        Returns:
            Series with VWAP values
        """
        # Create group keys based on anchor period
        group_keys = self._create_anchor_groups(data)
        
        # Calculate cumulative VWAP for each group
        vwap_values = pd.Series(index=data.index, dtype=float)
        
        for group_key in group_keys.unique():
            # Get indices for this group
            mask = group_keys == group_key
            group_indices = data.index[mask]
            
            if len(group_indices) == 0:
                continue
            
            # Get cumulative sums for this group
            group_tpv = tpv.loc[group_indices]
            group_volume = data['volume'].loc[group_indices]
            
            # Calculate cumulative sums
            cum_tpv = group_tpv.cumsum()
            cum_volume = group_volume.cumsum()
            
            # Calculate VWAP: cumulative_tpv / cumulative_volume
            group_vwap = cum_tpv / cum_volume
            
            # Assign to result
            vwap_values.loc[group_indices] = group_vwap
        
        # Handle any NaN values (first bar will be NaN)
        vwap_values = vwap_values.ffill()
        
        logger.debug(f"VWAP calculated with {len(group_keys.unique())} anchor periods")
        return vwap_values
    
    def _create_anchor_groups(self, data: pd.DataFrame) -> pd.Series:
        """
        Create grouping keys based on anchor period.
        
        Args:
            data: DataFrame with datetime index
        
        Returns:
            Series with group keys
        """
        index = data.index
        
        if self.anchor_period == "Session":
            # Group by date (daily reset)
            groups = index.date
        
        elif self.anchor_period == "Week":
            # Group by year-week
            groups = index.isocalendar().week.astype(str) + "_" + index.year.astype(str)
        
        elif self.anchor_period == "Month":
            # Group by year-month
            groups = index.to_period('M')
        
        elif self.anchor_period == "Quarter":
            # Group by year-quarter
            groups = index.to_period('Q')
        
        elif self.anchor_period == "Year":
            # Group by year
            groups = index.year
        
        else:
            # Default to daily session
            groups = index.date
        
        logger.debug(f"Anchor period grouping: {self.anchor_period}")
        return pd.Series(groups, index=index)
    
    def _calculate_standard_deviation(
        self,
        data: pd.DataFrame,
        tp: pd.Series,
        vwap: pd.Series
    ) -> pd.Series:
        """
        Calculate rolling standard deviation of typical price around VWAP.
        
        Uses the same anchor groups as VWAP for consistency.
        
        Args:
            data: DataFrame with OHLCV data
            tp: Typical price series
            vwap: VWAP series
        
        Returns:
            Series with standard deviation values
        """
        # Calculate deviation from VWAP
        deviation = tp - vwap
        
        # Create same anchor groups
        group_keys = self._create_anchor_groups(data)
        
        # Calculate standard deviation within each group
        stdev_values = pd.Series(index=data.index, dtype=float)
        
        for group_key in group_keys.unique():
            mask = group_keys == group_key
            group_indices = data.index[mask]
            
            if len(group_indices) < 2:
                # Need at least 2 samples for stdev
                stdev_values.loc[group_indices] = 0.0
                continue
            
            # Calculate expanding standard deviation
            group_tp = tp.loc[group_indices]
            group_stdev = group_tp.expanding(min_periods=2).std()
            
            stdev_values.loc[group_indices] = group_stdev
        
        # Fill NaN values
        stdev_values = stdev_values.ffill().fillna(0.0)
        
        logger.debug(f"Standard deviation calculated: mean={stdev_values.mean():.4f}")
        return stdev_values
    
    def _calculate_bands(
        self,
        vwap: pd.Series,
        stdev: pd.Series
    ) -> Dict[str, pd.Series]:
        """
        Calculate standard deviation bands.
        
        Band formula:
        upper_band_N = vwap + (stdev * multiplier_N)
        lower_band_N = vwap - (stdev * multiplier_N)
        
        Args:
            vwap: VWAP series
            stdev: Standard deviation series
        
        Returns:
            Dict with upper and lower band series
        """
        bands = {
            'upper_1': vwap + (stdev * self.band_multiplier_1),
            'lower_1': vwap - (stdev * self.band_multiplier_1),
            'upper_2': vwap + (stdev * self.band_multiplier_2),
            'lower_2': vwap - (stdev * self.band_multiplier_2),
            'upper_3': vwap + (stdev * self.band_multiplier_3),
            'lower_3': vwap - (stdev * self.band_multiplier_3)
        }
        
        logger.debug(
            f"Bands calculated: "
            f"Band1±{self.band_multiplier_1}, Band2±{self.band_multiplier_2}, Band3±{self.band_multiplier_3}"
        )
        return bands
    
    def _log_events(
        self,
        data: pd.DataFrame,
        tp: pd.Series,
        vwap: pd.Series,
        bands: Dict[str, pd.Series],
        latest_idx: int
    ):
        """
        Log significant VWAP events.
        
        Events logged:
        - VWAP reset (new anchor period)
        - Price crosses VWAP
        - Price touches bands
        
        Args:
            data: DataFrame with OHLCV data
            tp: Typical price series
            vwap: VWAP series
            bands: Dict of band series
            latest_idx: Index of latest bar
        """
        if latest_idx < 1:
            return
        
        current_tp = tp.iloc[latest_idx]
        current_vwap = vwap.iloc[latest_idx]
        prev_vwap = vwap.iloc[latest_idx - 1] if latest_idx > 0 else None
        
        # Check for VWAP reset (significant jump indicates new session)
        if prev_vwap is not None:
            vwap_change_pct = abs(current_vwap - prev_vwap) / prev_vwap * 100 if prev_vwap != 0 else 0
            if vwap_change_pct > 0.5:  # More than 0.5% change suggests reset
                logger.info(f"VWAP reset detected at bar {latest_idx}: {prev_vwap:.2f} to {current_vwap:.2f}")
        
        # Check for price crossing VWAP
        if latest_idx > 1:
            prev_tp = tp.iloc[latest_idx - 1]
            prev_above = prev_tp > vwap.iloc[latest_idx - 1]
            curr_above = current_tp > current_vwap
            
            if prev_above != curr_above:
                cross_type = "bullish" if curr_above else "bearish"
                logger.info(
                    f"Price {'crossed above' if curr_above else 'crossed below'} VWAP: "
                    f"{cross_type} cross at {current_vwap:.2f}"
                )
        
        # Check for band touches
        if current_tp >= bands['upper_1'].iloc[latest_idx]:
            logger.info(f"Price touched upper band 1 at {bands['upper_1'].iloc[latest_idx]:.2f}")
        elif current_tp <= bands['lower_1'].iloc[latest_idx]:
            logger.info(f"Price touched lower band 1 at {bands['lower_1'].iloc[latest_idx]:.2f}")
    
    def _empty_result(self) -> Dict[str, Any]:
        """
        Return empty result dict for error cases.
        
        Returns:
            Dict with None/False values
        """
        return {
            'vwap': None,
            'upper_band_1': None,
            'lower_band_1': None,
            'upper_band_2': None,
            'lower_band_2': None,
            'upper_band_3': None,
            'lower_band_3': None,
            'price_above_vwap': False,
            'stdev': None
        }


# Convenience function for quick access
def get_vwap_signal(
    data: pd.DataFrame,
    anchor_period: str = "Session",
    **kwargs
) -> Dict[str, Any]:
    """
    Get VWAP signal with specified parameters.
    
    Args:
        data: DataFrame with OHLCV data
        anchor_period: Reset period (default: Session)
        **kwargs: Additional parameters for TradingViewVWAP
    
    Returns:
        Dict with VWAP results
    
    Example:
        >>> signal = get_vwap_signal(candles, anchor_period='Month')
        >>> print(f"VWAP: {signal['vwap']:.2f}")
    """
    vwap = TradingViewVWAP(anchor_period=anchor_period, **kwargs)
    return vwap.calculate(data)

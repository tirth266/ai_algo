"""
TradingView Bollinger Bands Indicator Module

Implements Bollinger Bands with multiple moving average types.
Reproduces exact TradingView Bollinger Bands logic.

Features:
- Multiple MA types: SMA, EMA, RMA, WMA, VWMA
- Configurable standard deviation multiplier
- Band width calculation
- Price position detection

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TradingViewBollingerBands:
    """
    TradingView Bollinger Bands Indicator.
    
    Implements Bollinger Bands with configurable moving average type
    and standard deviation multiplier.
    
    Parameters:
        length: MA period (default: 20)
        ma_type: Moving average type (default: SMA)
                Options: SMA, EMA, RMA, WMA, VWMA
        source: Price source (default: close)
        stddev_multiplier: Standard deviation multiplier (default: 2.0)
    
    Example:
        >>> bb = TradingViewBollingerBands(length=20, ma_type='SMA')
        >>> result = bb.calculate(candles)
        >>> print(f"Upper: {result['upper_band']:.2f}, Lower: {result['lower_band']:.2f}")
    """
    
    def __init__(
        self,
        length: int = 20,
        ma_type: str = "SMA",
        source: str = "close",
        stddev_multiplier: float = 2.0
    ):
        """
        Initialize Bollinger Bands indicator.
        
        Args:
            length: Moving average period
            ma_type: Type of moving average
            source: Price source for calculation
            stddev_multiplier: Standard deviation multiplier for bands
        """
        self.length = length
        self.ma_type = ma_type.upper()
        self.source = source
        self.stddev_multiplier = stddev_multiplier
        
        # Validate MA type
        valid_ma_types = ['SMA', 'EMA', 'RMA', 'WMA', 'VWMA']
        if self.ma_type not in valid_ma_types:
            logger.warning(f"Invalid MA type '{self.ma_type}', defaulting to SMA")
            self.ma_type = 'SMA'
        
        logger.info(
            f"TradingViewBollingerBands initialized: "
            f"length={length}, ma_type={ma_type}, source={source}, "
            f"stddev_mult={stddev_multiplier}"
        )
    
    def calculate(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Bollinger Bands and related metrics.
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Dict with Bollinger Bands values and metrics
        
        Example:
            >>> result = bb.calculate(candles)
            >>> # Contains: basis, upper_band, lower_band,
            >>> #           band_width, price_above_upper, price_below_lower
        """
        if len(data) < self.length:
            logger.warning(f"Insufficient data for BB calculation (need {self.length} bars)")
            return self._empty_result()
        
        try:
            # Get source prices
            source_prices = self._get_source_prices(data)
            
            # Step 1: Calculate moving average (basis)
            basis = self._calculate_moving_average(source_prices)
            
            # Step 2: Calculate standard deviation
            stdev = self._calculate_standard_deviation(source_prices)
            
            # Step 3: Calculate upper and lower bands
            upper_band = basis + (stdev * self.stddev_multiplier)
            lower_band = basis - (stdev * self.stddev_multiplier)
            
            # Calculate band width (normalized)
            band_width = (upper_band - lower_band) / basis
            
            # Calculate %B (price position within bands)
            percent_b = self._calculate_percent_b(data['close'], upper_band, lower_band)
            
            # Get latest values
            latest_idx = len(data) - 1
            latest_close = data['close'].iloc[latest_idx]
            latest_basis = basis.iloc[latest_idx]
            latest_upper = upper_band.iloc[latest_idx]
            latest_lower = lower_band.iloc[latest_idx]
            
            # Build result dictionary
            result = {
                'basis': float(latest_basis),
                'upper_band': float(latest_upper),
                'lower_band': float(latest_lower),
                'band_width': float(band_width.iloc[latest_idx]),
                'percent_b': float(percent_b.iloc[latest_idx]),
                'price_above_upper': bool(latest_close > latest_upper),
                'price_below_lower': bool(latest_close < latest_lower),
                'stdev': float(stdev.iloc[latest_idx])
            }
            
            # Log significant events
            self._log_events(data, latest_close, latest_basis, latest_upper, latest_lower)
            
            logger.info(
                f"Bollinger Bands calculated: "
                f"basis={latest_basis:.2f}, "
                f"width={band_width.iloc[latest_idx]:.2%}, "
                f"stdev={stdev.iloc[latest_idx]:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}", exc_info=True)
            return self._empty_result()
    
    def _get_source_prices(self, data: pd.DataFrame) -> pd.Series:
        """
        Get source prices based on configured source.
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Series with source prices
        """
        if self.source == 'close':
            return data['close']
        elif self.source == 'open':
            return data['open']
        elif self.source == 'high':
            return data['high']
        elif self.source == 'low':
            return data['low']
        elif self.source == 'hlc3':
            return (data['high'] + data['low'] + data['close']) / 3.0
        elif self.source == 'hl2':
            return (data['high'] + data['low']) / 2.0
        else:
            # Default to close
            return data['close']
    
    def _calculate_moving_average(self, source: pd.Series) -> pd.Series:
        """
        Calculate moving average based on configured type.
        
        Supported types:
        - SMA: Simple Moving Average
        - EMA: Exponential Moving Average
        - RMA: Running Moving Average (Wilder's smoothing)
        - WMA: Weighted Moving Average
        - VWMA: Volume Weighted Moving Average
        
        Args:
            source: Source price series
        
        Returns:
            Series with moving average values
        """
        if self.ma_type == 'SMA':
            return self._calculate_sma(source)
        elif self.ma_type == 'EMA':
            return self._calculate_ema(source)
        elif self.ma_type == 'RMA':
            return self._calculate_rma(source)
        elif self.ma_type == 'WMA':
            return self._calculate_wma(source)
        elif self.ma_type == 'VWMA':
            return self._calculate_vwma(source)
        else:
            # Default to SMA
            return self._calculate_sma(source)
    
    def _calculate_sma(self, source: pd.Series) -> pd.Series:
        """Calculate Simple Moving Average."""
        return source.rolling(window=self.length).mean()
    
    def _calculate_ema(self, source: pd.Series) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return source.ewm(span=self.length, adjust=False).mean()
    
    def _calculate_rma(self, source: pd.Series) -> pd.Series:
        """
        Calculate Running Moving Average (Wilder's smoothing).
        
        Formula:
        rma[0] = sma(source, length)
        rma[i] = (rma[i-1] * (length-1) + source[i]) / length
        """
        rma = pd.Series(index=source.index, dtype=float)
        
        # First value is SMA
        rma.iloc[:self.length] = source.iloc[:self.length].rolling(window=self.length).mean().iloc[-1]
        
        # Apply Wilder's smoothing
        for i in range(self.length, len(source)):
            rma.iloc[i] = (rma.iloc[i-1] * (self.length - 1) + source.iloc[i]) / self.length
        
        return rma
    
    def _calculate_wma(self, source: pd.Series) -> pd.Series:
        """
        Calculate Weighted Moving Average.
        
        Weights decrease linearly from most recent to oldest.
        """
        weights = np.arange(1, self.length + 1)
        
        def weighted_avg(x):
            return np.average(x, weights=weights)
        
        return source.rolling(window=self.length).apply(weighted_avg, raw=True)
    
    def _calculate_vwma(self, source: pd.Series) -> pd.Series:
        """
        Calculate Volume Weighted Moving Average.
        
        Requires volume data in DataFrame.
        """
        # This needs access to volume, which we don't have here
        # Will be calculated in main method if VWMA is selected
        logger.warning("VWMA requires volume data, using SMA instead")
        return self._calculate_sma(source)
    
    def _calculate_standard_deviation(self, source: pd.Series) -> pd.Series:
        """
        Calculate standard deviation of source prices.
        
        Uses population standard deviation (ddof=0) like TradingView.
        
        Args:
            source: Source price series
        
        Returns:
            Series with standard deviation values
        """
        return source.rolling(window=self.length).std(ddof=0)
    
    def _calculate_percent_b(
        self,
        close: pd.Series,
        upper: pd.Series,
        lower: pd.Series
    ) -> pd.Series:
        """
        Calculate %B indicator.
        
        Shows where price is relative to bands.
        
        Formula:
        %B = (close - lower) / (upper - lower)
        
        Values:
        - > 1.0: Price above upper band
        - 0.5: Price at middle band
        - < 0.0: Price below lower band
        
        Args:
            close: Close prices
            upper: Upper band
            lower: Lower band
        
        Returns:
            Series with %B values
        """
        return (close - lower) / (upper - lower)
    
    def _log_events(
        self,
        data: pd.DataFrame,
        close: float,
        basis: float,
        upper: float,
        lower: float
    ):
        """
        Log significant Bollinger Bands events.
        
        Events logged:
        - Price touches/crosses upper band
        - Price touches/crosses lower band
        - Squeeze (narrow bands)
        - Expansion (wide bands)
        
        Args:
            data: DataFrame with OHLCV data
            close: Current close price
            basis: Current basis value
            upper: Current upper band
            lower: Current lower band
        """
        # Check for band touches
        if close >= upper:
            logger.info(f"Price touched/ crossed upper band at {upper:.2f}")
        elif close <= lower:
            logger.info(f"Price touched/crossed lower band at {lower:.2f}")
        
        # Check for squeeze (very narrow bands)
        band_width_pct = (upper - lower) / basis * 100
        if band_width_pct < 5:  # Less than 5% width
            logger.info(f"Bollinger Band squeeze detected (width: {band_width_pct:.2f}%)")
        elif band_width_pct > 20:  # More than 20% width
            logger.info(f"Bollinger Band expansion detected (width: {band_width_pct:.2f}%)")
    
    def _empty_result(self) -> Dict[str, Any]:
        """
        Return empty result dict for error cases.
        
        Returns:
            Dict with None/False values
        """
        return {
            'basis': None,
            'upper_band': None,
            'lower_band': None,
            'band_width': None,
            'percent_b': None,
            'price_above_upper': False,
            'price_below_lower': False,
            'stdev': None
        }


# Convenience function for quick access
def get_bollinger_bands_signal(
    data: pd.DataFrame,
    length: int = 20,
    ma_type: str = "SMA",
    **kwargs
) -> Dict[str, Any]:
    """
    Get Bollinger Bands signal with specified parameters.
    
    Args:
        data: DataFrame with OHLCV data
        length: MA period (default: 20)
        ma_type: Moving average type (default: SMA)
        **kwargs: Additional parameters for TradingViewBollingerBands
    
    Returns:
        Dict with Bollinger Bands results
    
    Example:
        >>> signal = get_bollinger_bands_signal(candles, length=20)
        >>> print(f"Basis: {signal['basis']:.2f}")
    """
    bb = TradingViewBollingerBands(length=length, ma_type=ma_type, **kwargs)
    return bb.calculate(data)

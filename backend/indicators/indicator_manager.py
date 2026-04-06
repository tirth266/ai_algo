"""
Indicator Manager Module

Central orchestrator for all technical indicators.
Provides a unified interface for strategies to access and compute indicators.

Features:
- Register indicators dynamically
- Compute indicators on demand
- Cache results for performance
- Return standardized output format
"""

import pandas as pd
from typing import Dict, Any, Optional, Callable
import logging

from .supertrend import supertrend, get_supertrend_signal
from .trendline import get_trendline_signal, calculate_trendline_channels
from .liquidity import get_liquidity_signal, identify_liquidity_levels
from .luxalgo_liquidity_swings import LuxAlgoLiquiditySwings
from .supertrend_tv import TradingViewSupertrend
from .vwap_tv import TradingViewVWAP
from .bollinger_bands_tv import TradingViewBollingerBands

logger = logging.getLogger(__name__)


class IndicatorManager:
    """
    Central manager for all technical indicators.
    
    Provides a clean API for strategies to compute and access indicators.
    
    Example Usage:
        >>> manager = IndicatorManager()
        >>> result = manager.calculate('supertrend', candles)
        >>> print(result)
        {'trend': 'bullish', 'value': 22450}
        
        >>> st = manager.supertrend(candles)
        >>> tl = manager.trendline(candles)
        >>> liq = manager.liquidity(candles)
    """
    
    def __init__(self):
        """Initialize the indicator manager."""
        self._indicators: Dict[str, Callable] = {}
        self._cache: Dict[str, Any] = {}
        
        # Register built-in indicators
        self._register_builtin_indicators()
        
        logger.info("IndicatorManager initialized")
    
    def _register_builtin_indicators(self):
        """Register all built-in indicators."""
        # Supertrend
        self.register('supertrend', self._compute_supertrend)
        
        # Trendline
        self.register('trendline', self._compute_trendline)
        
        # Liquidity
        self.register('liquidity', self._compute_liquidity)
        
        # LuxAlgo Liquidity Swings
        self.register('luxalgo_liquidity_swings', self._compute_luxalgo_liquidity_swings)
        
        # TradingView Supertrend
        self.register('tv_supertrend', self._compute_tv_supertrend)
        
        # TradingView VWAP
        self.register('tv_vwap', self._compute_tv_vwap)
        
        # TradingView Bollinger Bands
        self.register('tv_bollinger', self._compute_tv_bollinger)
        
        logger.info(f"Registered {len(self._indicators)} built-in indicators")
    
    def register(self, name: str, compute_func: Callable):
        """
        Register a new indicator.
        
        Args:
            name: Unique identifier for the indicator
            compute_func: Function that computes the indicator
        
        Example:
            >>> def my_indicator(data):
            ...     return {'value': data['close'].mean()}
            >>> manager.register('my_indicator', my_indicator)
        """
        self._indicators[name] = compute_func
        logger.debug(f"Registered indicator: {name}")
    
    def calculate(
        self,
        indicator: str,
        data: pd.DataFrame,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate an indicator by name.
        
        Args:
            indicator: Name of registered indicator
            data: DataFrame with OHLCV data
            **kwargs: Additional parameters for the indicator
        
        Returns:
            Dict with indicator results
        
        Raises:
            ValueError: If indicator is not registered
        
        Example:
            >>> result = manager.calculate('supertrend', candles, period=10, multiplier=3.0)
            >>> print(result)
            {'trend': 'bullish', 'value': 22450, 'direction': 1}
        """
        logger.info(f"Calculating indicator: {indicator}")
        
        if indicator not in self._indicators:
            raise ValueError(f"Indicator '{indicator}' not registered. Available: {list(self._indicators.keys())}")
        
        try:
            # Check cache first
            cache_key = f"{indicator}_{len(data)}_{str(kwargs)}"
            if cache_key in self._cache:
                logger.debug(f"Cache hit for {indicator}")
                return self._cache[cache_key]
            
            # Compute indicator
            compute_func = self._indicators[indicator]
            result = compute_func(data, **kwargs)
            
            # Cache result
            self._cache[cache_key] = result
            
            # Limit cache size
            if len(self._cache) > 100:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            logger.info(f"Indicator {indicator} calculated successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating {indicator}: {str(e)}", exc_info=True)
            return {'error': str(e)}
    
    def _compute_supertrend(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute Supertrend indicator."""
        period = kwargs.get('period', 10)
        multiplier = kwargs.get('multiplier', 3.0)
        
        return get_supertrend_signal(data, period, multiplier)
    
    def _compute_trendline(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute Trendline indicator."""
        lookback = kwargs.get('lookback', 5)
        
        return get_trendline_signal(data, lookback)
    
    def _compute_liquidity(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute Liquidity indicator."""
        lookback = kwargs.get('lookback', 10)
        
        return get_liquidity_signal(data, lookback)
    
    def _compute_luxalgo_liquidity_swings(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute LuxAlgo Liquidity Swings indicator."""
        pivot_lookback = kwargs.get('pivot_lookback', 14)
        area_mode = kwargs.get('area_mode', 'wick')
        filter_mode = kwargs.get('filter_mode', 'count')
        filter_threshold = kwargs.get('filter_threshold', 0)
        
        indicator = LuxAlgoLiquiditySwings(
            pivot_lookback=pivot_lookback,
            area_mode=area_mode,
            filter_mode=filter_mode,
            filter_threshold=filter_threshold
        )
        
        return indicator.calculate(data)
    
    def _compute_tv_supertrend(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute TradingView Supertrend indicator."""
        atr_length = kwargs.get('atr_length', 10)
        factor = kwargs.get('factor', 3.0)
        
        indicator = TradingViewSupertrend(
            atr_length=atr_length,
            factor=factor
        )
        
        return indicator.calculate(data)
    
    def _compute_tv_vwap(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute TradingView VWAP indicator."""
        anchor_period = kwargs.get('anchor_period', 'Session')
        source = kwargs.get('source', 'hlc3')
        band_multiplier_1 = kwargs.get('band_multiplier_1', 1.0)
        band_multiplier_2 = kwargs.get('band_multiplier_2', 2.0)
        band_multiplier_3 = kwargs.get('band_multiplier_3', 3.0)
        
        indicator = TradingViewVWAP(
            anchor_period=anchor_period,
            source=source,
            band_multiplier_1=band_multiplier_1,
            band_multiplier_2=band_multiplier_2,
            band_multiplier_3=band_multiplier_3
        )
        
        return indicator.calculate(data)
    
    def _compute_tv_bollinger(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Compute TradingView Bollinger Bands indicator."""
        length = kwargs.get('length', 20)
        ma_type = kwargs.get('ma_type', 'SMA')
        source = kwargs.get('source', 'close')
        stddev_multiplier = kwargs.get('stddev_multiplier', 2.0)
        
        indicator = TradingViewBollingerBands(
            length=length,
            ma_type=ma_type,
            source=source,
            stddev_multiplier=stddev_multiplier
        )
        
        return indicator.calculate(data)
    
    # Convenience methods for direct access
    
    def supertrend(self, data: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Dict[str, Any]:
        """
        Calculate Supertrend indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            period: ATR period (default: 10)
            multiplier: ATR multiplier (default: 3.0)
        
        Returns:
            Dict with supertrend signal
        
        Example:
            >>> st = manager.supertrend(candles)
            >>> print(f"Trend: {st['trend']}, Value: {st['value']}")
        """
        return self.calculate('supertrend', data, period=period, multiplier=multiplier)
    
    def trendline(self, data: pd.DataFrame, lookback: int = 5) -> Dict[str, Any]:
        """
        Calculate Trendline indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            lookback: Pivot lookback period (default: 5)
        
        Returns:
            Dict with trendline signal
        
        Example:
            >>> tl = manager.trendline(candles)
            >>> if tl['breakout_up']:
            ...     print(f"Bullish breakout! Strength: {tl['channel_width']:.2f}%")
        """
        return self.calculate('trendline', data, lookback=lookback)
    
    def liquidity(self, data: pd.DataFrame, lookback: int = 10) -> Dict[str, Any]:
        """
        Calculate Liquidity indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            lookback: Swing detection lookback (default: 10)
        
        Returns:
            Dict with liquidity signal
        
        Example:
            >>> liq = manager.liquidity(candles)
            >>> if liq['liquidity_high_sweep']:
            ...     print(f"Liquidity swept at {liq['level']}")
        """
        return self.calculate('liquidity', data, lookback=lookback)
    
    def luxalgo_liquidity_swings(
        self,
        data: pd.DataFrame,
        pivot_lookback: int = 14,
        area_mode: str = 'wick',
        filter_mode: str = 'count',
        filter_threshold: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate LuxAlgo Liquidity Swings indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            pivot_lookback: Pivot detection window (default: 14)
            area_mode: Zone calculation method ('wick' or 'full_range')
            filter_mode: Filtering method ('count' or 'volume')
            filter_threshold: Minimum threshold (default: 0)
        
        Returns:
            Dict with liquidity swings results
        
        Example:
            >>> liq = manager.luxalgo_liquidity_swings(candles)
            >>> if liq['sweep_detected']:
            ...     print(f"Liquidity sweep: {liq['sweep_type']}")
        """
        return self.calculate(
            'luxalgo_liquidity_swings',
            data,
            pivot_lookback=pivot_lookback,
            area_mode=area_mode,
            filter_mode=filter_mode,
            filter_threshold=filter_threshold
        )
    
    def tv_supertrend(
        self,
        data: pd.DataFrame,
        atr_length: int = 10,
        factor: float = 3.0
    ) -> Dict[str, Any]:
        """
        Calculate TradingView Supertrend indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            atr_length: ATR period (default: 10)
            factor: ATR multiplier (default: 3.0)
        
        Returns:
            Dict with TV supertrend signal
        
        Example:
            >>> tvst = manager.tv_supertrend(candles)
            >>> if tvst['trend'] == 'bullish':
            ...     print(f"TV Supertrend bullish at {tvst['value']}")
        """
        return self.calculate(
            'tv_supertrend',
            data,
            atr_length=atr_length,
            factor=factor
        )
    
    def tv_vwap(
        self,
        data: pd.DataFrame,
        anchor_period: str = "Session",
        source: str = "hlc3",
        band_multipliers: tuple = (1.0, 2.0, 3.0)
    ) -> Dict[str, Any]:
        """
        Calculate TradingView VWAP indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            anchor_period: Reset period (default: Session)
                          Options: Session, Week, Month, Quarter, Year
            source: Price source (default: hlc3)
            band_multipliers: Tuple of (mult1, mult2, mult3) for bands
        
        Returns:
            Dict with VWAP results
        
        Example:
            >>> vwap = manager.tv_vwap(candles)
            >>> if vwap['price_above_vwap']:
            ...     print(f"Price above VWAP at {vwap['vwap']:.2f}")
        """
        return self.calculate(
            'tv_vwap',
            data,
            anchor_period=anchor_period,
            source=source,
            band_multiplier_1=band_multipliers[0],
            band_multiplier_2=band_multipliers[1],
            band_multiplier_3=band_multipliers[2]
        )
    
    def tv_bollinger(
        self,
        data: pd.DataFrame,
        length: int = 20,
        ma_type: str = "SMA",
        source: str = "close",
        stddev_multiplier: float = 2.0
    ) -> Dict[str, Any]:
        """
        Calculate TradingView Bollinger Bands indicator directly.
        
        Args:
            data: DataFrame with OHLC data
            length: MA period (default: 20)
            ma_type: Moving average type (default: SMA)
            source: Price source (default: close)
            stddev_multiplier: Standard deviation multiplier (default: 2.0)
        
        Returns:
            Dict with Bollinger Bands results
        
        Example:
            >>> bb = manager.tv_bollinger(candles)
            >>> if bb['price_below_lower']:
            ...     print("Price below lower band - potential bounce")
        """
        return self.calculate(
            'tv_bollinger',
            data,
            length=length,
            ma_type=ma_type,
            source=source,
            stddev_multiplier=stddev_multiplier
        )
    
    def clear_cache(self):
        """Clear the indicator calculation cache."""
        self._cache.clear()
        logger.info("Indicator cache cleared")
    
    def list_indicators(self) -> list:
        """
        Get list of registered indicators.
        
        Returns:
            List of indicator names
        
        Example:
            >>> indicators = manager.list_indicators()
            >>> print(f"Available indicators: {indicators}")
        """
        return list(self._indicators.keys())
    
    def describe(self, indicator: str) -> Dict[str, Any]:
        """
        Get description of an indicator.
        
        Args:
            indicator: Name of the indicator
        
        Returns:
            Dict with indicator metadata
        
        Example:
            >>> desc = manager.describe('supertrend')
            >>> print(desc)
            {
                'name': 'supertrend',
                'type': 'trend',
                'parameters': ['period', 'multiplier'],
                'output': ['trend', 'value', 'direction']
            }
        """
        descriptions = {
            'supertrend': {
                'name': 'Supertrend',
                'type': 'trend',
                'parameters': ['period', 'multiplier'],
                'output': ['trend', 'value', 'direction', 'change'],
                'description': 'ATR-based trend following indicator'
            },
            'trendline': {
                'name': 'Dynamic Trendlines',
                'type': 'support_resistance',
                'parameters': ['lookback'],
                'output': ['breakout_up', 'breakout_down', 'trendline_value', 'swing_high', 'swing_low'],
                'description': 'Pivot-based linear regression trendlines'
            },
            'liquidity': {
                'name': 'Liquidity Detection',
                'type': 'market_structure',
                'parameters': ['lookback'],
                'output': ['liquidity_high_sweep', 'liquidity_low_sweep', 'level', 'sweep_type'],
                'description': 'Identifies liquidity pools and sweeps'
            }
        }
        
        return descriptions.get(indicator, {'error': 'Indicator not found'})


# Global instance for easy access
_manager_instance: Optional[IndicatorManager] = None


def get_indicator_manager() -> IndicatorManager:
    """
    Get or create the global indicator manager instance.
    
    Returns:
        IndicatorManager instance
    
    Example:
        >>> manager = get_indicator_manager()
        >>> result = manager.supertrend(candles)
    """
    global _manager_instance
    
    if _manager_instance is None:
        _manager_instance = IndicatorManager()
    
    return _manager_instance

"""
Indicator Pipeline Module

Processes indicator calculations on candle data.

Features:
- Runs multiple indicators in sequence
- Caches indicator results
- Error handling and recovery
- Performance monitoring
- Thread-safe operations

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class IndicatorPipeline:
    """
    Orchestrates indicator calculations on market data.
    
    Manages execution of multiple indicators and aggregates
    their outputs into a unified snapshot.
    
    Indicators run:
    - Bollinger Bands
    - VWAP
    - Supertrend
    - ATR
    
    Example:
        >>> pipeline = IndicatorPipeline()
        >>> snapshot = pipeline.run(candles_df)
        >>> print(f"BB Basis: {snapshot['bollinger']['basis']:.2f}")
    """
    
    def __init__(self):
        """
        Initialize indicator pipeline.
        
        Sets up indicator manager and caching.
        """
        self._indicator_manager = None
        
        # Caching
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'calculations_run': 0,
            'cache_hits': 0,
            'errors': 0
        }
        
        logger.info("IndicatorPipeline initialized")
    
    def _get_indicator_manager(self):
        """
        Lazy load indicator manager to avoid circular imports.
        
        Returns:
            IndicatorManager instance
        """
        if self._indicator_manager is None:
            from indicators.indicator_manager import get_indicator_manager
            self._indicator_manager = get_indicator_manager()
        
        return self._indicator_manager
    
    def run(
        self,
        candles: pd.DataFrame,
        symbol: str = None,
        force_recalc: bool = False
    ) -> Dict[str, Any]:
        """
        Run all indicators on candle data.
        
        Args:
            candles: DataFrame with OHLCV data
            symbol: Trading symbol (for caching)
            force_recalc: Force recalculation even if cached
        
        Returns:
            Dictionary with all indicator results
        
        Example:
            >>> snapshot = pipeline.run(candles_df)
            >>> # Contains: bollinger, vwap, supertrend, atr
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"{symbol}_{len(candles)}"
            if not force_recalc and self._is_cache_valid(cache_key):
                with self._lock:
                    self._stats['cache_hits'] += 1
                
                logger.debug(f"Using cached indicators for {symbol}")
                return self._cache.get(cache_key, {})
            
            # Validate input data
            if not self._validate_candles(candles):
                logger.error("Invalid candle data for indicators")
                return self._empty_snapshot()
            
            # Run indicators
            result = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'candle_count': len(candles),
                'bollinger': self._run_bollinger(candles),
                'vwap': self._run_vwap(candles),
                'supertrend': self._run_supertrend(candles),
                'atr': self._run_atr(candles)
            }
            
            # Cache result
            with self._lock:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = datetime.now()
                self._stats['calculations_run'] += 1
            
            # Log performance
            elapsed = time.time() - start_time
            logger.debug(
                f"Indicators calculated for {symbol} in {elapsed*1000:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Error running indicators: {str(e)}",
                exc_info=True
            )
            
            with self._lock:
                self._stats['errors'] += 1
            
            return self._empty_snapshot()
    
    def _run_bollinger(self, candles: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Bollinger Bands.
        
        Args:
            candles: OHLCV DataFrame
        
        Returns:
            Bollinger Bands result dict
        """
        try:
            manager = self._get_indicator_manager()
            
            result = manager.tv_bollinger(
                candles,
                length=20,
                ma_type='SMA',
                stddev_multiplier=2.0
            )
            
            logger.debug(
                f"Bollinger Bands: basis={result['basis']:.2f}, "
                f"width={result['band_width']:.2%}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Bollinger calculation failed: {str(e)}")
            return self._empty_indicator('bollinger')
    
    def _run_vwap(self, candles: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate VWAP indicator.
        
        Args:
            candles: OHLCV DataFrame
        
        Returns:
            VWAP result dict
        """
        try:
            manager = self._get_indicator_manager()
            
            result = manager.tv_vwap(
                candles,
                anchor_period='Session',
                source='hlc3'
            )
            
            logger.debug(
                f"VWAP: {result['vwap']:.2f}, "
                f"price={'above' if result['price_above_vwap'] else 'below'}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"VWAP calculation failed: {str(e)}")
            return self._empty_indicator('vwap')
    
    def _run_supertrend(self, candles: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Supertrend indicator.
        
        Args:
            candles: OHLCV DataFrame
        
        Returns:
            Supertrend result dict
        """
        try:
            manager = self._get_indicator_manager()
            
            result = manager.tv_supertrend(
                candles,
                atr_length=10,
                factor=3.0
            )
            
            logger.debug(
                f"Supertrend: {result['trend']}, "
                f"value={result['supertrend']:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Supertrend calculation failed: {str(e)}")
            return self._empty_indicator('supertrend')
    
    def _run_atr(self, candles: pd.DataFrame) -> float:
        """
        Calculate ATR (Average True Range).
        
        Args:
            candles: OHLCV DataFrame
        
        Returns:
            ATR value
        """
        try:
            from risk.risk_manager import get_risk_manager
            
            rm = get_risk_manager()
            atr_series = rm.calculate_atr(candles, period=14)
            
            atr_value = atr_series.iloc[-1] if len(atr_series) > 0 else 0.0
            
            logger.debug(f"ATR (14): {atr_value:.4f}")
            
            return float(atr_value)
            
        except Exception as e:
            logger.error(f"ATR calculation failed: {str(e)}")
            return 0.0
    
    def _validate_candles(self, candles: pd.DataFrame) -> bool:
        """
        Validate candle data has required columns.
        
        Args:
            candles: OHLCV DataFrame
        
        Returns:
            True if valid
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Check columns
        for col in required_columns:
            if col not in candles.columns:
                logger.error(f"Missing required column: {col}")
                return False
        
        # Check minimum data length
        if len(candles) < 20:
            logger.warning(f"Insufficient data for indicators: {len(candles)} bars")
            return False
        
        # Check for NaN values
        if candles[required_columns].isna().any().any():
            logger.warning("Candle data contains NaN values")
            return False
        
        return True
    
    def _is_cache_valid(self, cache_key: str, ttl_seconds: int = 60) -> bool:
        """
        Check if cached result is still valid.
        
        Args:
            cache_key: Cache key
            ttl_seconds: Time-to-live in seconds
        
        Returns:
            True if cache is valid
        """
        with self._lock:
            if cache_key not in self._cache:
                return False
            
            if cache_key not in self._cache_timestamps:
                return False
            
            age = (datetime.now() - self._cache_timestamps[cache_key]).total_seconds()
            
            return age < ttl_seconds
    
    def _empty_snapshot(self) -> Dict[str, Any]:
        """
        Return empty indicator snapshot for error cases.
        
        Returns:
            Empty snapshot dict
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'symbol': None,
            'candle_count': 0,
            'bollinger': self._empty_indicator('bollinger'),
            'vwap': self._empty_indicator('vwap'),
            'supertrend': self._empty_indicator('supertrend'),
            'atr': 0.0
        }
    
    def _empty_indicator(self, indicator_type: str) -> Dict[str, Any]:
        """
        Return empty result for specific indicator.
        
        Args:
            indicator_type: Type of indicator
        
        Returns:
            Empty result dict
        """
        if indicator_type == 'bollinger':
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
        elif indicator_type == 'vwap':
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
        elif indicator_type == 'supertrend':
            return {
                'trend': None,
                'supertrend': None,
                'trend_change': False,
                'direction': None
            }
        else:
            return {}
    
    def clear_cache(self):
        """Clear all cached indicator results."""
        with self._lock:
            self._cache.clear()
            self._cache_timestamps.clear()
        
        logger.info("Indicator cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.
        
        Returns:
            Stats dictionary
        """
        with self._lock:
            return {
                **self._stats,
                'cache_size': len(self._cache),
                'last_calculation': (
                    max(self._cache_timestamps.values())
                    if self._cache_timestamps else None
                )
            }


# Global pipeline instance
_indicator_pipeline: Optional[IndicatorPipeline] = None


def get_indicator_pipeline() -> IndicatorPipeline:
    """
    Get or create global indicator pipeline instance.
    
    Returns:
        IndicatorPipeline instance
    
    Example:
        >>> pipeline = get_indicator_pipeline()
        >>> snapshot = pipeline.run(candles_df)
    """
    global _indicator_pipeline
    
    if _indicator_pipeline is None:
        _indicator_pipeline = IndicatorPipeline()
    
    return _indicator_pipeline

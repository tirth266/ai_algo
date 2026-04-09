"""
Indicator Engine - Centralized indicator calculation layer.

RESPONSIBILITY:
- Calculate ALL technical indicators from market data
- Pre-compute indicators before passing to strategy
- Keep strategies PURE (only receive indicators, generate signals)

BENEFITS:
- Strategies stay simple and testable
- Easy to mock indicators for testing
- Centralized indicator logic (no duplication)
- Clear separation: Data → Indicators → Strategy → Signal
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

from ..core.indicators import (
    calculate_rsi,
    calculate_ema,
    calculate_atr,
    calculate_volume_ma,
    detect_rsi_divergence,
    calculate_vwap_bands,
)
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import calculate_trendline_channels, identify_pivots
from ..core.market_condition import (
    detect_market_condition,
    detect_market_structure,
    is_trending_market,
    is_sideways_market,
)

logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Centralized indicator calculation engine.
    
    Converts raw OHLCV candles into computed indicators.
    All strategies receive indicators from this engine (not computing themselves).
    """

    def __init__(
        self,
        ema_periods: List[int] = None,
        atr_period: int = 10,
        rsi_period: int = 14,
        volume_ma_period: int = 20,
        supertrend_period: int = 10,
        supertrend_multiplier: float = 3.0,
        vwap_std_dev: float = 2.0,
    ):
        """
        Initialize indicator engine with configuration.
        
        Args:
            ema_periods: List of EMA periods to calculate (default: [20, 50, 100, 200])
            atr_period: ATR calculation period
            rsi_period: RSI calculation period
            volume_ma_period: Volume moving average period
            supertrend_period: Supertrend ATR period
            supertrend_multiplier: Supertrend ATR multiplier
            vwap_std_dev: VWAP standard deviation bands
        """
        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.volume_ma_period = volume_ma_period
        self.supertrend_period = supertrend_period
        self.supertrend_multiplier = supertrend_multiplier
        self.vwap_std_dev = vwap_std_dev

    def calculate(self, candles: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate all indicators from candles.
        
        Args:
            candles: DataFrame with OHLCV data
        
        Returns:
            Dict with all calculated indicators
        """
        if candles is None or candles.empty:
            raise ValueError("Candles DataFrame cannot be empty")

        df = candles.copy()
        indicators = {}

        try:
            # === TREND INDICATORS ===
            # Calculate EMAs (trend direction)
            for period in self.ema_periods:
                col_name = f"ema_{period}"
                indicators[col_name] = self._calculate_ema(df["close"], period)

            # === VOLATILITY INDICATORS ===
            # Calculate ATR (volatility, stop loss sizing)
            indicators["atr"] = self._calculate_atr(df)

            # === MOMENTUM INDICATORS ===
            # Calculate RSI (overbought/oversold)
            indicators["rsi"] = self._calculate_rsi(df["close"])

            # Detect RSI divergence (momentum reversal)
            indicators["rsi_divergence"] = self._detect_rsi_divergence(df)

            # === VOLUME INDICATORS ===
            # Calculate volume moving average
            indicators["volume_ma"] = self._calculate_volume_ma(df)

            # Check for volume spike
            indicators["volume_spike"] = self._is_volume_spike(df)

            # === MEAN REVERSION INDICATORS ===
            # Calculate VWAP bands
            vwap_data = self._calculate_vwap_bands(df)
            indicators.update(vwap_data)

            # === TREND FOLLOWING INDICATORS ===
            # Calculate Supertrend (trend direction + reversal)
            supertrend_data = self._calculate_supertrend(df)
            indicators.update(supertrend_data)

            # === STRUCTURAL INDICATORS ===
            # Identify pivots (support/resistance)
            pivot_data = self._identify_pivots(df)
            indicators.update(pivot_data)

            # Calculate trendlines (structure)
            trendline_data = self._calculate_trendlines(df)
            indicators.update(trendline_data)

            # === MARKET CONDITION ===
            # Detect market condition
            indicators["market_condition"] = detect_market_condition(df)
            indicators["market_structure"] = detect_market_structure(df)
            indicators["is_trending"] = is_trending_market(df)
            indicators["is_sideways"] = is_sideways_market(df)

            # === CURRENT PRICE ===
            # Add current price for reference
            indicators["current_price"] = float(df["close"].iloc[-1])
            indicators["current_open"] = float(df["open"].iloc[-1])
            indicators["current_high"] = float(df["high"].iloc[-1])
            indicators["current_low"] = float(df["low"].iloc[-1])
            indicators["current_volume"] = float(df["volume"].iloc[-1])

            logger.debug(f"Indicators calculated: {list(indicators.keys())}")

            return indicators

        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}", exc_info=True)
            raise

    # ===== PRIVATE CALCULATION METHODS =====

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate EMA safely."""
        try:
            return series.ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"EMA calculation error (period {period}): {e}")
            return pd.Series([np.nan] * len(series), index=series.index)

    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range."""
        try:
            return calculate_atr(df, self.atr_period)
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            return pd.Series([np.nan] * len(df))

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate RSI."""
        try:
            return calculate_rsi(close, self.rsi_period)
        except Exception as e:
            logger.error(f"RSI calculation error: {e}")
            return pd.Series([np.nan] * len(close))

    def _detect_rsi_divergence(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect RSI divergence."""
        try:
            return detect_rsi_divergence(df, self.rsi_period)
        except Exception as e:
            logger.error(f"RSI divergence detection error: {e}")
            return None

    def _calculate_volume_ma(self, df: pd.DataFrame) -> pd.Series:
        """Calculate volume moving average."""
        try:
            return calculate_volume_ma(df, self.volume_ma_period)
        except Exception as e:
            logger.error(f"Volume MA calculation error: {e}")
            return pd.Series([np.nan] * len(df))

    def _is_volume_spike(self, df: pd.DataFrame) -> bool:
        """Check for volume spike."""
        try:
            volume_ma = df["volume"].rolling(self.volume_ma_period).mean()
            current_volume = df["volume"].iloc[-1]
            return current_volume > volume_ma.iloc[-1] * 1.5
        except Exception as e:
            logger.error(f"Volume spike check error: {e}")
            return False

    def _calculate_vwap_bands(self, df: pd.DataFrame) -> Dict:
        """Calculate VWAP and bands."""
        try:
            vwap_df = calculate_vwap_bands(df)
            return {
                "vwap": vwap_df["vwap"],
                "vwap_upper": vwap_df.get("vwap_upper_2", vwap_df["vwap"]),
                "vwap_lower": vwap_df.get("vwap_lower_2", vwap_df["vwap"]),
            }
        except Exception as e:
            logger.error(f"VWAP calculation error: {e}")
            return {
                "vwap": pd.Series([np.nan] * len(df)),
                "vwap_upper": pd.Series([np.nan] * len(df)),
                "vwap_lower": pd.Series([np.nan] * len(df)),
            }

    def _calculate_supertrend(self, df: pd.DataFrame) -> Dict:
        """Calculate Supertrend."""
        try:
            supertrend_df = calculate_supertrend(
                df[["open", "high", "low", "close"]].copy(),
                period=self.supertrend_period,
                multiplier=self.supertrend_multiplier,
            )
            if supertrend_df.empty:
                return {
                    "supertrend": pd.Series([np.nan] * len(df)),
                    "trend_direction": pd.Series([0] * len(df)),
                }
            return {
                "supertrend": supertrend_df["supertrend"],
                "trend_direction": supertrend_df["trend_direction"],
            }
        except Exception as e:
            logger.error(f"Supertrend calculation error: {e}")
            return {
                "supertrend": pd.Series([np.nan] * len(df)),
                "trend_direction": pd.Series([0] * len(df)),
            }

    def _identify_pivots(self, df: pd.DataFrame) -> Dict:
        """Identify pivot highs and lows."""
        try:
            pivot_highs, pivot_lows = identify_pivots(df, 5)
            return {
                "is_pivot_high": pivot_highs,
                "is_pivot_low": pivot_lows,
            }
        except Exception as e:
            logger.error(f"Pivot identification error: {e}")
            return {
                "is_pivot_high": pd.Series([False] * len(df)),
                "is_pivot_low": pd.Series([False] * len(df)),
            }

    def _calculate_trendlines(self, df: pd.DataFrame) -> Dict:
        """Calculate trendline channels."""
        try:
            trendline_df = calculate_trendline_channels(df, 14)
            return {
                "trendline_upper": trendline_df["trendline_upper"],
                "trendline_lower": trendline_df["trendline_lower"],
            }
        except Exception as e:
            logger.error(f"Trendline calculation error: {e}")
            return {
                "trendline_upper": pd.Series([np.nan] * len(df)),
                "trendline_lower": pd.Series([np.nan] * len(df)),
            }

    def get_latest_indicators(self, candles: pd.DataFrame) -> Dict:
        """
        Get latest indicator values (current bar only).
        
        Useful for real-time trading.
        
        Args:
            candles: DataFrame with OHLCV data
        
        Returns:
            Dict with latest indicator values
        """
        all_indicators = self.calculate(candles)

        latest = {}
        for key, value in all_indicators.items():
            if isinstance(value, pd.Series):
                latest[key] = float(value.iloc[-1]) if not pd.isna(value.iloc[-1]) else None
            elif isinstance(value, (int, float)):
                latest[key] = value
            else:
                latest[key] = value

        return latest


# Singleton instance for system-wide use
_indicator_engine = None


def get_indicator_engine() -> IndicatorEngine:
    """Get or create singleton IndicatorEngine."""
    global _indicator_engine
    if _indicator_engine is None:
        _indicator_engine = IndicatorEngine()
    return _indicator_engine


def reset_indicator_engine() -> None:
    """Reset indicator engine singleton (for testing)."""
    global _indicator_engine
    _indicator_engine = None

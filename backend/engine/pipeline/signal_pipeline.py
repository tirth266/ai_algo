"""
Signal Pipeline Module

Processes trading signals from strategy engine.

Features:
- Integrates with LuxAlgoTrendlineStrategy
- Signal validation and filtering
- Signal enrichment with metadata
- Thread-safe operations
- Error handling

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class SignalPipeline:
    """
    Orchestrates signal generation from strategy.
    
    Takes indicator snapshots and candle data,
    runs strategy, and outputs validated signals.
    
    Example:
        >>> pipeline = SignalPipeline()
        >>> signal = pipeline.run(candles_df, indicator_snapshot)
        >>> if signal:
        ...     print(f"Signal: {signal['type']}")
    """
    
    def __init__(self, symbol: str = None):
        """
        Initialize signal pipeline.
        
        Args:
            symbol: Default trading symbol
        
        Example:
            >>> pipeline = SignalPipeline('RELIANCE')
        """
        self.symbol = symbol
        self._strategy = None
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            'signals_generated': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'no_signal': 0,
            'errors': 0
        }
        
        logger.info(f"SignalPipeline initialized: symbol={symbol}")
    
    def _get_strategy(self):
        """
        Lazy load strategy to avoid circular imports.
        
        Returns:
            LuxAlgoTrendlineStrategy instance
        """
        if self._strategy is None:
            from strategies.luxalgo_trendline_strategy import LuxAlgoTrendlineStrategy
            
            # Strategy configuration
            config = {
                'swing_length': 14,
                'slope_multiplier': 0.01,
                'slope_method': 'ATR',
                'use_liquidity': True,
                'pivot_lookback': 14,
                'use_vwap': True,
                'vwap_anchor': 'Session',
                'use_bollinger': True,
                'bb_length': 20,
                'bb_stddev_mult': 2.0,
                'account_balance': 100000,
                'risk_per_trade': 1.0,
                'atr_multiplier': 2.0,
                'symbol': self.symbol or 'RELIANCE'
            }
            
            self._strategy = LuxAlgoTrendlineStrategy(config)
            logger.info("LuxAlgoTrendlineStrategy initialized")
        
        return self._strategy
    
    def run(
        self,
        candles: any,
        indicators: Dict[str, Any],
        symbol: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal from indicator data.
        
        Args:
            candles: DataFrame with OHLCV data or dict with candle info
            indicators: Indicator snapshot from IndicatorPipeline
            symbol: Trading symbol (overrides default)
        
        Returns:
            Signal dict if generated, None otherwise
        
        Example:
            >>> signal = pipeline.run(candles_df, snapshot)
            >>> if signal and signal['type'] == 'BUY':
            ...     print("Buy signal detected!")
        """
        try:
            # Get symbol
            trade_symbol = symbol or self.symbol or 'RELIANCE'
            
            # Validate inputs
            if not self._validate_inputs(candles, indicators):
                logger.warning("Invalid inputs for signal generation")
                return None
            
            # Run strategy
            strategy = self._get_strategy()
            signal = strategy.generate_signal(candles)
            
            # Update statistics
            with self._lock:
                if signal:
                    self._stats['signals_generated'] += 1
                    
                    if signal.get('type') == 'BUY':
                        self._stats['buy_signals'] += 1
                    elif signal.get('type') == 'SELL':
                        self._stats['sell_signals'] += 1
                else:
                    self._stats['no_signal'] += 1
            
            # Enrich signal if present
            if signal:
                signal = self._enrich_signal(signal, indicators, trade_symbol)
                
                logger.info(
                    f"Signal generated: {signal['type']} "
                    f"confidence={signal['confidence']:.2%} "
                    f"symbol={trade_symbol}"
                )
            else:
                logger.debug(f"No signal for {trade_symbol}")
            
            return signal
            
        except Exception as e:
            logger.error(
                f"Error generating signal: {str(e)}",
                exc_info=True
            )
            
            with self._lock:
                self._stats['errors'] += 1
            
            return None
    
    def _validate_inputs(
        self,
        candles: any,
        indicators: Dict[str, Any]
    ) -> bool:
        """
        Validate input data for signal generation.
        
        Args:
            candles: Candle data
            indicators: Indicator snapshot
        
        Returns:
            True if valid
        """
        # Check indicators exist
        if not indicators:
            logger.warning("Empty indicator snapshot")
            return False
        
        # Check required indicators
        required = ['bollinger', 'vwap', 'supertrend']
        for key in required:
            if key not in indicators:
                logger.warning(f"Missing indicator: {key}")
                return False
        
        # Check candles exist
        if candles is None or (hasattr(candles, '__len__') and len(candles) == 0):
            logger.warning("No candle data provided")
            return False
        
        return True
    
    def _enrich_signal(
        self,
        signal: Dict[str, Any],
        indicators: Dict[str, Any],
        symbol: str
    ) -> Dict[str, Any]:
        """
        Add metadata and context to signal.
        
        Args:
            signal: Raw signal from strategy
            indicators: Indicator snapshot
            symbol: Trading symbol
        
        Returns:
            Enriched signal dict
        """
        # Add timestamp if not present
        if 'timestamp' not in signal:
            signal['timestamp'] = datetime.now().isoformat()
        
        # Add symbol if not present
        if 'symbol' not in signal:
            signal['symbol'] = symbol
        
        # Add indicator summary
        signal['indicator_summary'] = {
            'bollinger': {
                'basis': indicators['bollinger'].get('basis'),
                'percent_b': indicators['bollinger'].get('percent_b'),
                'band_width': indicators['bollinger'].get('band_width')
            },
            'vwap': {
                'vwap': indicators['vwap'].get('vwap'),
                'price_above_vwap': indicators['vwap'].get('price_above_vwap')
            },
            'supertrend': {
                'trend': indicators['supertrend'].get('trend'),
                'trend_change': indicators['supertrend'].get('trend_change')
            },
            'atr': indicators.get('atr')
        }
        
        # Add signal strength classification
        signal['signal_strength'] = self._classify_signal_strength(signal)
        
        # Add risk metrics
        if signal.get('entry_price') and signal.get('stop_loss'):
            risk_distance = abs(signal['entry_price'] - signal['stop_loss'])
            risk_percent = (risk_distance / signal['entry_price']) * 100
            
            signal['risk_metrics'] = {
                'risk_distance': risk_distance,
                'risk_percent': round(risk_percent, 2),
                'reward_risk_ratio': None  # To be calculated by execution layer
            }
        
        logger.debug(
            f"Signal enriched: {signal['type']} "
            f"strength={signal['signal_strength']}"
        )
        
        return signal
    
    def _classify_signal_strength(self, signal: Dict[str, Any]) -> str:
        """
        Classify signal strength based on confidence and factors.
        
        Args:
            signal: Signal dict
        
        Returns:
            Strength string: 'weak', 'moderate', 'strong', 'very_strong'
        """
        confidence = signal.get('confidence', 0)
        reason_count = len(signal.get('reason', []))
        
        # Classification logic
        if confidence >= 0.80 and reason_count >= 4:
            return 'very_strong'
        elif confidence >= 0.70 and reason_count >= 3:
            return 'strong'
        elif confidence >= 0.60 and reason_count >= 2:
            return 'moderate'
        else:
            return 'weak'
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.
        
        Returns:
            Stats dictionary
        """
        with self._lock:
            return dict(self._stats)
    
    def reset_strategy(self):
        """Reset the strategy instance (clears internal state)."""
        self._strategy = None
        logger.info("Strategy reset")


# Global signal pipeline instance
_signal_pipeline: Optional[SignalPipeline] = None


def get_signal_pipeline(symbol: str = None) -> SignalPipeline:
    """
    Get or create global signal pipeline instance.
    
    Args:
        symbol: Default trading symbol
    
    Returns:
        SignalPipeline instance
    
    Example:
        >>> pipeline = get_signal_pipeline('RELIANCE')
        >>> signal = pipeline.run(candles_df, snapshot)
    """
    global _signal_pipeline
    
    if _signal_pipeline is None or (symbol and _signal_pipeline.symbol != symbol):
        _signal_pipeline = SignalPipeline(symbol=symbol)
    
    return _signal_pipeline

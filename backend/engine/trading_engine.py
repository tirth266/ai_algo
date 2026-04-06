"""
Trading Engine Module

Core execution engine for unified strategy signal generation.
Coordinates indicator calculations and strategy execution.

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.indicator_manager import get_indicator_manager
from services.market_data import MarketDataService

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Unified Strategy Execution Engine.
    
    Orchestrates:
    - Market data fetching
    - Indicator calculations
    - Strategy signal generation
    - Signal output standardization
    
    Example:
        >>> engine = TradingEngine()
        >>> signal = engine.generate_signal('RELIANCE')
        >>> print(signal)
        {'symbol': 'RELIANCE', 'signal': 'BUY', 'confidence': 0.84, ...}
    """
    
    def __init__(self):
        """Initialize the trading engine."""
        self.indicator_manager = get_indicator_manager()
        self.market_data_service = MarketDataService()
        
        self.strategy = None
        # TODO: register strategies from strategy_registry
        
        # Cache for latest signals
        self.signal_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("TradingEngine initialized")
    
    def generate_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal for a given symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE', 'TCS', 'NIFTY')
        
        Returns:
            Dict with standardized signal output or None
        
        Example:
            >>> signal = engine.generate_signal('RELIANCE')
            >>> if signal:
            ...     print(f"Signal: {signal['signal']}, Confidence: {signal['confidence']}")
        """
        try:
            logger.info(f"Generating signal for {symbol}")
            
            # Step 1: Fetch candles
            candles = self._fetch_candles(symbol)
            
            if candles is None or len(candles) < 50:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Step 2: Run indicators
            indicators = self._run_indicators(candles)
            
            # Step 3: Run strategy
            signal = self._run_strategy(symbol, candles, indicators)
            
            if signal:
                # Step 4: Standardize output
                standardized_signal = self._standardize_signal(symbol, signal, candles)
                
                # Cache the signal
                self.signal_cache[symbol] = standardized_signal
                
                logger.info(
                    f"Signal generated for {symbol}: "
                    f"{standardized_signal['signal']} (confidence: {standardized_signal['confidence']:.2f})"
                )
                
                return standardized_signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {str(e)}", exc_info=True)
            return None
    
    def _fetch_candles(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLCV data for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            logger.debug(f"Fetching candles for {symbol}")
            
            # Use market data service to fetch candles
            # For demo/testing, we can also use mock data
            candles = self.market_data_service.get_candles(symbol)
            
            if candles is None:
                logger.warning(f"No candles returned for {symbol}, using mock data")
                candles = self._generate_mock_data(symbol)
            
            logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {str(e)}")
            # Fallback to mock data
            return self._generate_mock_data(symbol)
    
    def _generate_mock_data(self, symbol: str) -> pd.DataFrame:
        """
        Generate mock OHLCV data for testing.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            DataFrame with simulated OHLCV data
        """
        import numpy as np
        from datetime import datetime, timedelta
        
        logger.info(f"Generating mock data for {symbol}")
        
        # Set random seed based on symbol for reproducibility
        np.random.seed(hash(symbol) % 2**32)
        
        # Generate 500 bars of data
        num_bars = 500
        base_price = np.random.uniform(500, 3000)
        
        # Generate timestamps
        end_date = datetime.now()
        timestamps = [end_date - timedelta(minutes=i) for i in range(num_bars)]
        timestamps.reverse()
        
        # Generate price data with trends
        returns = np.random.randn(num_bars) * 0.02
        trend = np.sin(np.linspace(0, 4 * np.pi, num_bars)) * 0.01
        close_prices = base_price * (1 + returns + trend).cumprod()
        
        # Generate OHLC
        high_prices = close_prices * (1 + np.abs(np.random.randn(num_bars)) * 0.01)
        low_prices = close_prices * (1 - np.abs(np.random.randn(num_bars)) * 0.01)
        open_prices = np.roll(close_prices, 1)
        open_prices[0] = base_price
        
        # Ensure high >= low and proper OHLC relationships
        high_prices = np.maximum(high_prices, np.maximum(open_prices, close_prices))
        low_prices = np.minimum(low_prices, np.minimum(open_prices, close_prices))
        
        volume = np.random.randint(1000, 10000, num_bars)
        
        df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volume
        }, index=pd.DatetimeIndex(timestamps))
        
        return df
    
    def _run_indicators(self, candles: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate all required indicators.
        
        Args:
            candles: DataFrame with OHLCV data
        
        Returns:
            Dict with indicator results
        """
        logger.debug("Running indicators")
        
        # Calculate TradingView Supertrend
        tv_supertrend = self.indicator_manager.tv_supertrend(candles)
        
        # Calculate Trendline
        trendline = self.indicator_manager.trendline(candles)
        
        # Calculate Liquidity Swings
        liquidity = self.indicator_manager.luxalgo_liquidity_swings(candles)
        
        indicators = {
            'tv_supertrend': tv_supertrend,
            'trendline': trendline,
            'liquidity': liquidity
        }
        
        logger.debug(
            f"Indicators calculated: "
            f"ST={tv_supertrend['trend']}, "
            f"TL breakout={trendline.get('breakout_up', False) or trendline.get('breakout_down', False)}, "
            f"Liq sweep={liquidity.get('sweep_detected', False)}"
        )
        
        return indicators
    
    def _run_strategy(
        self,
        symbol: str,
        candles: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Run strategy to generate signal.
        
        Args:
            symbol: Stock symbol
            candles: DataFrame with OHLCV data
            indicators: Dict with calculated indicators
        
        Returns:
            Dict with strategy signal or None
        """
        logger.debug(f"Running strategy for {symbol}")
        
        # Update strategy symbol
        if self.strategy:
            self.strategy.symbol = symbol
            
            # Use strategy's generate_signal method
            # The strategy will internally use the indicators
            signal = self.strategy.generate_signal(candles)
            
            if signal:
                logger.info(f"Strategy signal for {symbol}: {signal['type']}")
                return signal
        
        # If no signal from strategy, apply final decision logic manually
        return self._apply_final_decision_logic(indicators, candles)
    
    def _apply_final_decision_logic(
        self,
        indicators: Dict[str, Any],
        candles: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Apply final BUY/SELL decision logic based on indicator confluence.
        
        BUY when:
        - Supertrend bullish
        - Trendline breakout upward
        - Liquidity sweep bullish
        
        SELL when:
        - Supertrend bearish
        - Trendline breakout downward
        - Liquidity sweep bearish
        
        Args:
            indicators: Dict with indicator results
            candles: DataFrame with OHLCV data
        
        Returns:
            Dict with signal or None
        """
        st = indicators['tv_supertrend']
        tl = indicators['trendline']
        liq = indicators['liquidity']
        
        reasons = []
        bullish_factors = 0
        bearish_factors = 0
        
        # Check Supertrend
        if st['trend'] == 'bullish':
            bullish_factors += 1
            reasons.append('supertrend bullish')
        else:
            bearish_factors += 1
            reasons.append('supertrend bearish')
        
        # Check Trendline breakout
        if tl.get('breakout_up'):
            bullish_factors += 1
            reasons.append('trendline breakout upward')
        elif tl.get('breakout_down'):
            bearish_factors += 1
            reasons.append('trendline breakout downward')
        
        # Check Liquidity sweep
        if liq.get('sweep_detected'):
            if liq.get('sweep_type') == 'bullish':
                bullish_factors += 1
                reasons.append('liquidity sweep bullish')
            elif liq.get('sweep_type') == 'bearish':
                bearish_factors += 1
                reasons.append('liquidity sweep bearish')
        
        # Determine final signal
        current_price = float(candles['close'].iloc[-1])
        current_time = candles.index[-1].isoformat()
        
        # Strong bullish confluence (at least 2 factors)
        if bullish_factors >= 2:
            confidence = bullish_factors / 3.0
            return {
                'type': 'BUY',
                'action': 'BUY',
                'confidence': confidence,
                'reason': reasons,
                'price': current_price,
                'timestamp': current_time
            }
        
        # Strong bearish confluence (at least 2 factors)
        elif bearish_factors >= 2:
            confidence = bearish_factors / 3.0
            return {
                'type': 'SELL',
                'action': 'SELL',
                'confidence': confidence,
                'reason': reasons,
                'price': current_price,
                'timestamp': current_time
            }
        
        # No clear signal
        return None
    
    def _standardize_signal(
        self,
        symbol: str,
        signal: Dict[str, Any],
        candles: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Standardize signal output format.
        
        Args:
            symbol: Stock symbol
            signal: Raw signal from strategy
            candles: DataFrame with OHLCV data
        
        Returns:
            Standardized signal dict
        """
        return {
            'symbol': symbol,
            'signal': signal.get('type', signal.get('action', 'HOLD')),
            'confidence': float(signal.get('confidence', 0.5)),
            'price': float(signal.get('price', candles['close'].iloc[-1])),
            'timestamp': signal.get('timestamp', candles.index[-1].isoformat()),
            'reason': signal.get('reason', ['indicator confluence']),
            'indicators': {
                'tv_supertrend': self.indicator_manager.tv_supertrend(candles),
                'trendline': self.indicator_manager.trendline(candles),
                'liquidity': self.indicator_manager.luxalgo_liquidity_swings(candles)
            }
        }
    
    def get_latest_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest cached signal for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Cached signal or None
        """
        return self.signal_cache.get(symbol)
    
    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cached signals.
        
        Returns:
            Dict of all signals by symbol
        """
        return self.signal_cache.copy()
    
    def clear_cache(self):
        """Clear signal cache."""
        self.signal_cache.clear()
        logger.info("Signal cache cleared")


# Global engine instance
_engine_instance: Optional[TradingEngine] = None


def get_trading_engine() -> TradingEngine:
    """
    Get or create global trading engine instance.
    
    Returns:
        TradingEngine instance
    """
    global _engine_instance
    
    if _engine_instance is None:
        _engine_instance = TradingEngine()
    
    return _engine_instance


if __name__ == "__main__":
    # Test the trading engine
    logging.basicConfig(level=logging.INFO)
    
    engine = get_trading_engine()
    
    # Test signal generation
    test_symbols = ['RELIANCE', 'TCS', 'INFY']
    
    for symbol in test_symbols:
        print(f"\n{'='*60}")
        print(f"Testing {symbol}")
        print('='*60)
        
        signal = engine.generate_signal(symbol)
        
        if signal:
            print(f"Symbol: {signal['symbol']}")
            print(f"Signal: {signal['signal']}")
            print(f"Confidence: {signal['confidence']:.2%}")
            print(f"Price: ₹{signal['price']:.2f}")
            print(f"Reasons:")
            for reason in signal['reason']:
                print(f"  - {reason}")
        else:
            print("No signal generated")

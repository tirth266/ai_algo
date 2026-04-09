"""
Execution Flow - Refactored Strategy Architecture

ARCHITECTURE:
Data Layer (Market Data Service)
         ↓
Indicator Engine (Pre-compute all indicators)
         ↓
Strategy (Pure logic: market_data + indicators → signal)
         ↓
Trading System (Execute signal, manage risk, place orders)

BENEFITS:
✅ Strategies are pure functions (testable, predictable)
✅ Easy to mock indicators for unit testing
✅ Clear separation of concerns
✅ Centralized indicator logic (no duplication across strategies)
✅ Data fetching is decoupled from strategy logic
"""

import pandas as pd
import logging
from typing import Dict, Optional, Any

from ..services.market_data import get_market_data_service
from ..indicators.indicator_engine import get_indicator_engine
from ..strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class RefactoredTradingExecutor:
    """
    Refactored execution flow with pure strategy architecture.
    
    Responsibility:
    1. Fetch data (Market Data Service)
    2. Calculate indicators (Indicator Engine)
    3. Call strategy with processed inputs (Pure Function)
    4. Execute signal (Trading System)
    """

    def __init__(self, strategy: BaseStrategy):
        """
        Initialize executor with strategy.
        
        Args:
            strategy: BaseStrategy subclass (pure logic only)
        """
        self.strategy = strategy
        self.market_data_service = get_market_data_service()
        self.indicator_engine = get_indicator_engine()

    def execute_trading_cycle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Execute single trading cycle: Fetch → Calculate → Signal → Execute.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
        
        Returns:
            Signal dict if generated, None otherwise
        """
        logger.info(f"Starting trading cycle for {symbol}")

        try:
            # ===== STEP 1: FETCH MARKET DATA =====
            logger.debug(f"Step 1: Fetching market data for {symbol}...")
            market_data = self._fetch_market_data(symbol)
            if market_data is None:
                logger.warning(f"Could not fetch market data for {symbol}")
                return None

            candles = market_data['candles']
            logger.debug(f"  Got {len(candles)} candles")

            # ===== STEP 2: CALCULATE INDICATORS =====
            logger.debug("Step 2: Calculating indicators...")
            indicators = self.indicator_engine.calculate(candles)
            logger.debug(f"  Calculated {len(indicators)} indicators")

            # ===== STEP 3: CALL PURE STRATEGY =====
            logger.debug("Step 3: Generating signal from strategy...")
            signal = self._generate_signal(
                market_data=market_data['current'],
                indicators=indicators
            )

            if signal is None:
                logger.debug(f"  No signal generated for {symbol}")
                return None

            logger.info(f"✅ Signal: {signal['action']} (confidence: {signal['confidence']:.2f})")

            # ===== STEP 4: VALIDATE & EXECUTE SIGNAL =====
            logger.debug("Step 4: Validating and executing signal...")
            # (This would be handled by TradingSystem)

            return signal

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
            return None

    def _fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data for symbol.
        
        Returns:
            Dict with 'candles' (DataFrame) and 'current' (current bar dict)
        """
        try:
            # Get from market data service (with caching)
            candles = self.market_data_service.get_candles(
                symbol=symbol,
                timeframe=self.strategy.timeframe,
                limit=200  # Fetch 200 candles for indicators
            )

            if candles is None or candles.empty:
                logger.warning(f"No candles for {symbol}")
                return None

            # Check for stale data
            if self.market_data_service.is_data_stale(symbol, self.strategy.timeframe):
                cache_age = self.market_data_service.get_cache_age(symbol, self.strategy.timeframe)
                logger.warning(f"Data for {symbol} is stale ({cache_age}s old)")
                # Optionally return None to skip this cycle
                # return None

            # Extract current bar
            current = {
                "symbol": symbol,
                "price": float(candles["close"].iloc[-1]),
                "open": float(candles["open"].iloc[-1]),
                "high": float(candles["high"].iloc[-1]),
                "low": float(candles["low"].iloc[-1]),
                "volume": float(candles["volume"].iloc[-1]),
                "timestamp": str(candles.index[-1])
            }

            return {
                "candles": candles,
                "current": current
            }

        except Exception as e:
            logger.error(f"Error fetching market data: {e}", exc_info=True)
            return None

    def _generate_signal(self, market_data: Dict, indicators: Dict) -> Optional[Dict]:
        """
        Call pure strategy to generate signal.
        
        Args:
            market_data: Current market data dict
            indicators: Pre-computed indicators dict
        
        Returns:
            Signal dict or None
        """
        try:
            # Call strategy with both inputs
            signal = self.strategy.generate_signal(
                market_data=market_data,
                indicators=indicators
            )

            if signal is None:
                return None

            # Validate signal structure
            self.strategy._validate_signal_output(signal)

            return signal

        except Exception as e:
            logger.error(f"Error generating signal: {e}", exc_info=True)
            return None


# ===================================================================
# EXAMPLE USAGE
# ===================================================================

if __name__ == "__main__":
    """
    Example: How to use refactored architecture
    """

    # 1. Import pure strategy
    from backend.strategies.example_rsi_strategy import RSIStrategy

    # 2. Initialize strategy (pure logic only)
    strategy = RSIStrategy(capital=50000.0)

    # 3. Initialize executor
    executor = RefactoredTradingExecutor(strategy)

    # 4. Execute trading cycle
    signal = executor.execute_trading_cycle(symbol="RELIANCE")

    if signal:
        print(f"Signal: {signal['action']}")
        print(f"Confidence: {signal['confidence']:.2f}")
        print(f"Stop Loss: ${signal['stop_loss']:.2f}")

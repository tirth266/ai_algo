"""
Pure RSI Strategy - Example Implementation

DEMONSTRATES:
✅ Proper inheritance from BaseStrategy
✅ Pure logic only (no data fetching, no API calls)
✅ Receives pre-computed indicators from IndicatorEngine
✅ Returns properly structured signal
✅ Easily testable with mock data

ARCHITECTURE:
- IndicatorEngine: calculates RSI
- Strategy: receives RSI value, applies logic, returns signal
- Trading System: receives signal, executes trade

This strategy does NOT:
❌ Fetch data
❌ Calculate indicators
❌ Call APIs
❌ Execute trades
"""

from typing import Dict
from .base_strategy import BaseStrategy


class RSIStrategy(BaseStrategy):
    """
    Simple RSI (Relative Strength Index) trading strategy.
    
    PURE LOGIC:
    - Receives RSI indicator from IndicatorEngine
    - Uses simple rules to generate signal
    - No calculations, no data fetching
    
    Rules:
    - BUY when RSI < 30 (oversold)
    - SELL when RSI > 70 (overbought)
    - HOLD otherwise
    
    Confidence: Based on how extreme RSI is
    Stop Loss: 2% below current price
    """

    def __init__(self, name: str = "RSI_Strategy", capital: float = 25000.0, timeframe: str = '5m'):
        """
        Initialize pure RSI strategy.
        
        Args:
            name: Strategy identifier
            capital: Capital allocation
            timeframe: Indicator timeframe (e.g., '5m', '15m')
        """
        super().__init__(name, capital, timeframe)
        
        # Strategy parameters
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.stop_loss_pct = 0.02  # 2% below entry

    def generate_signal(self, market_data: Dict, indicators: Dict) -> Dict:
        """
        Pure function: market_data + indicators → signal.
        
        NO CALCULATIONS - only uses received data.
        
        Args:
            market_data: {"price": 2850.50, ...}
            indicators: {"rsi": 28.5, ...} (pre-calculated by IndicatorEngine)
        
        Returns:
            {
                "action": "BUY" | "SELL" | "HOLD",
                "confidence": 0.0-1.0,
                "stop_loss": float
            }
        """
        
        # ===== EXTRACT DATA (no calculations) =====
        # Get RSI (pre-calculated by IndicatorEngine)
        rsi = indicators.get('rsi', 50.0)
        current_price = market_data.get('price', 0.0)
        
        # Validate required data
        if current_price <= 0:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "stop_loss": 0.0
            }
        
        # ===== CALCULATE STOP LOSS =====
        stop_loss = current_price * (1 - self.stop_loss_pct)
        
        # ===== APPLY PURE LOGIC =====
        
        if rsi < self.rsi_oversold:
            # RSI indicates oversold - BUY signal
            # Confidence increases as RSI goes deeper into oversold territory
            # At RSI=20: confidence = (30-20)/30 = 0.33
            # At RSI=5: confidence = (30-5)/30 = 0.83
            confidence = min(1.0, (self.rsi_oversold - rsi) / self.rsi_oversold)
            
            return {
                "action": "BUY",
                "confidence": confidence,
                "stop_loss": stop_loss
            }
        
        elif rsi > self.rsi_overbought:
            # RSI indicates overbought - SELL signal
            # Confidence increases as RSI goes higher above overbought
            # At RSI=80: confidence = (80-70)/30 = 0.33
            # At RSI=95: confidence = (95-70)/30 = 0.83
            confidence = min(1.0, (rsi - self.rsi_overbought) / (100 - self.rsi_overbought))
            
            return {
                "action": "SELL",
                "confidence": confidence,
                "stop_loss": stop_loss
            }
        
        else:
            # RSI in neutral zone - HOLD
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "stop_loss": stop_loss
            }


# ===================================================================
# TESTING WITH MOCK DATA
# ===================================================================

if __name__ == "__main__":
    """
    Unit test example: Test strategy with mock indicators.
    
    BENEFIT: No need for real market data, broker connection, or API calls.
    Strategy is pure function - same inputs always produce same output.
    """
    
    # Initialize strategy (pure logic)
    strategy = RSIStrategy(capital=25000.0)
    
    # Define mock data
    market_data = {
        "symbol": "RELIANCE",
        "price": 2850.50,
        "open": 2845.00,
        "high": 2855.00,
        "low": 2840.00,
        "volume": 1000000
    }
    
    # Test 1: Oversold (BUY signal)
    print("Test 1: RSI = 25 (Oversold)")
    indicators_oversold = {"rsi": 25.0}
    signal = strategy.generate_signal(market_data, indicators_oversold)
    assert signal["action"] == "BUY"
    assert signal["confidence"] > 0
    print(f"  ✓ {signal}")
    
    # Test 2: Overbought (SELL signal)
    print("\nTest 2: RSI = 85 (Overbought)")
    indicators_overbought = {"rsi": 85.0}
    signal = strategy.generate_signal(market_data, indicators_overbought)
    assert signal["action"] == "SELL"
    assert signal["confidence"] > 0
    print(f"  ✓ {signal}")
    
    # Test 3: Neutral (HOLD)
    print("\nTest 3: RSI = 50 (Neutral)")
    indicators_neutral = {"rsi": 50.0}
    signal = strategy.generate_signal(market_data, indicators_neutral)
    assert signal["action"] == "HOLD"
    assert signal["confidence"] == 0.0
    print(f"  ✓ {signal}")
    
    print("\n✅ All tests passed - Strategy is pure and testable!")


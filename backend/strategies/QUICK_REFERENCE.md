# Strategy Quick Reference Card

**Status:** ✅ COMPLETE | **Syntax:** ✅ VERIFIED

---

## One-Minute Overview

**BaseStrategy** = Strict interface for all strategies

**Requirements:**
1. Inherit from `BaseStrategy`
2. Implement `generate_signal(market_data, indicators)`
3. Return exactly: `{"action": "BUY"|"SELL"|"HOLD", "confidence": 0-1, "stop_loss": float}`
4. No API calls, no execution logic

**Enforcement:**
- ✅ Abstract method check at init
- ✅ Forbidden pattern scan at init
- ✅ Signal validation at return

---

## Template

```python
from backend.strategies.base_strategy import BaseStrategy
from typing import Dict

class MyStrategy(BaseStrategy):
    """Your strategy description."""
    
    def __init__(self, capital=25000.0):
        super().__init__("MyStrategy", capital)
        # Strategy-specific setup here
    
    def generate_signal(self, market_data: Dict, indicators: Dict) -> Dict:
        """
        Analyze market_data + indicators
        Return signal dict with action, confidence, stop_loss
        """
        
        # Read-only: Extract data
        price = market_data['price']
        indicator_value = indicators['your_indicator']
        
        # Calculate signal
        if indicator_value > threshold:
            action = "BUY"
            confidence = 0.8
        elif indicator_value < threshold:
            action = "SELL"
            confidence = 0.7
        else:
            action = "HOLD"
            confidence = 0.0
        
        # Calculate stop loss
        stop_loss = price * 0.98
        
        # Return required structure
        return {
            "action": action,
            "confidence": confidence,
            "stop_loss": stop_loss
        }
```

---

## Input Arguments

### market_data (Dict)
```python
{
    "symbol": str,       # e.g., "RELIANCE"
    "price": float,      # Current price
    "open": float,       # Open price
    "high": float,       # Day high
    "low": float,        # Day low
    "volume": int,       # Trading volume
    "timestamp": str     # ISO format time
}
```

### indicators (Dict)
```python
{
    "rsi": float,        # Relative Strength Index
    "sma_20": float,     # 20-period SMA
    "sma_50": float,     # 50-period SMA
    "ema_12": float,     # 12-period EMA
    "macd": float,       # MACD value
    "bb_upper": float,   # Bollinger Band upper
    "bb_lower": float,   # Bollinger Band lower
    # ... add as needed
}
```

---

## Output Structure

```python
{
    "action": str,          # REQUIRED: "BUY", "SELL", or "HOLD"
    "confidence": float,    # REQUIRED: 0.0 to 1.0
    "stop_loss": float      # REQUIRED: numeric value >= 0
}
```

**Validation:**
- ❌ Missing any key → ValueError
- ❌ action not in {BUY, SELL, HOLD} → ValueError
- ❌ confidence not 0.0-1.0 → ValueError
- ❌ stop_loss not numeric → ValueError

---

## Examples

### Example 1: RSI Strategy
```python
def generate_signal(self, market_data, indicators) -> Dict:
    rsi = indicators['rsi']
    price = market_data['price']
    
    if rsi < 30:
        return {
            "action": "BUY",
            "confidence": (30 - rsi) / 30,
            "stop_loss": price * 0.98
        }
    elif rsi > 70:
        return {
            "action": "SELL",
            "confidence": (rsi - 70) / 30,
            "stop_loss": price * 1.02
        }
    else:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "stop_loss": price * 0.98
        }
```

### Example 2: Moving Average Crossover
```python
def generate_signal(self, market_data, indicators) -> Dict:
    sma_20 = indicators['sma_20']
    sma_50 = indicators['sma_50']
    price = market_data['price']
    
    if sma_20 > sma_50:
        return {
            "action": "BUY",
            "confidence": min(1.0, (sma_20 - sma_50) / sma_50),
            "stop_loss": price * 0.95
        }
    elif sma_20 < sma_50:
        return {
            "action": "SELL",
            "confidence": min(1.0, (sma_50 - sma_20) / sma_50),
            "stop_loss": price * 1.05
        }
    else:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "stop_loss": price * 0.98
        }
```

### Example 3: Multi-Indicator Strategy
```python
def generate_signal(self, market_data, indicators) -> Dict:
    rsi = indicators['rsi']
    macd = indicators['macd']
    price = market_data['price']
    
    bullish_signals = 0
    if rsi < 30:
        bullish_signals += 1
    if macd > 0:
        bullish_signals += 1
    
    if bullish_signals == 2:
        confidence = 0.9
        action = "BUY"
    elif bullish_signals == 0:
        confidence = 0.7
        action = "SELL"
    else:
        confidence = 0.3
        action = "HOLD"
    
    return {
        "action": action,
        "confidence": confidence,
        "stop_loss": price * 0.97
    }
```

---

## Helpers

### get_quantity(price)
```python
# Calculate position size from capital
quantity = self.get_quantity(price)

# Example: capital=25000, price=2850.50
# quantity = int(25000 / 2850.50) = 8

# Then use:
order_size = self.get_quantity(market_data['price'])
```

---

## DO ✅

```python
✅ Read market_data and indicators
✅ Perform calculations on data
✅ Use technical analysis
✅ Return structured signal
✅ Apply stop_loss logic
✅ Validate confidence levels
```

---

## DON'T ❌

```python
❌ from backend.broker_api import ...
❌ from backend.database import ...
❌ place_order(...)
❌ execute_trade(...)
❌ log_to_database(...)
❌ make_http_request(...)
❌ Modify self.capital directly
❌ Return non-dict signal
```

---

## Error Messages & Solutions

### Error: "Strategy 'X' must implement generate_signal()"
**Solution:** Add `generate_signal()` method to your strategy class

### Error: "not allowed to import/use 'broker'"
**Solution:** Remove broker imports from your strategy code

### Error: "Signal must be dict..."
**Solution:** Return `{"action": ..., "confidence": ..., "stop_loss": ...}`

### Error: "Signal action must be BUY/SELL/HOLD..."
**Solution:** Ensure action is exactly one of: "BUY", "SELL", "HOLD"

### Error: "Signal confidence must be 0.0-1.0..."
**Solution:** Keep confidence between 0.0 and 1.0

### Error: "Signal stop_loss must be >= 0..."
**Solution:** Ensure stop_loss is numeric and non-negative

---

## Testing Your Strategy

```python
# Test 1: Initialize (validates constraints)
strategy = MyStrategy()
print("✓ Strategy initialized successfully")

# Test 2: Generate signal
signal = strategy.generate_signal(
    market_data={"price": 100.0},
    indicators={"rsi": 25.0}
)

# Test 3: Validate return
assert 'action' in signal
assert 'confidence' in signal
assert 'stop_loss' in signal
assert signal['action'] in ["BUY", "SELL", "HOLD"]
assert 0.0 <= signal['confidence'] <= 1.0
assert signal['stop_loss'] >= 0.0
print("✓ Signal validation passed")
```

---

## File Locations

```
backend/strategies/
├── base_strategy.py                    (Strict interface)
├── example_rsi_strategy.py            (Example implementation)
├── STRATEGY_ARCHITECTURE.md           (Full documentation)
├── IMPLEMENTATION_SUMMARY.md          (Summary)
└── QUICK_REFERENCE.md                 (This file)
```

---

## One-Line Philosophy

> **Strategy = Signal Generator ONLY. No API calls. No execution. Pure analysis.**

---

**Version:** 1.0  
**Date:** April 8, 2026  
**Status:** ✅ COMPLETE

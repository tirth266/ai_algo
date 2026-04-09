"""
STRATEGY ARCHITECTURE - Quick Implementation Guide

STATUS: ✅ STRICT INTERFACE ENFORCED

===================================================================
ARCHITECTURE OVERVIEW
===================================================================

BaseStrategy (abc.ABC):
├── REQUIRED: generate_signal(market_data, indicators) → Dict
├── VALIDATION: Forbidden pattern checks at __init__
├── CONSTRAINT: No API calls, no execution logic
└── HELPER: get_quantity(price) → int

===================================================================
IMPLEMENTING A STRATEGY
===================================================================

1. INHERIT from BaseStrategy:

    from backend.strategies.base_strategy import BaseStrategy
    
    class MyStrategy(BaseStrategy):
        def __init__(self, name="MyStrategy", capital=25000.0):
            super().__init__(name, capital)

2. IMPLEMENT generate_signal():

    def generate_signal(self, market_data: Dict, indicators: Dict) -> Dict:
        # Read-only: Analyze market data
        price = market_data['price']
        rsi = indicators['rsi']
        
        # Calculate signal
        if rsi < 30:
            action = "BUY"
        elif rsi > 70:
            action = "SELL"
        else:
            action = "HOLD"
        
        # Return EXACT structure:
        return {
            "action": action,              # "BUY" | "SELL" | "HOLD"
            "confidence": 0.75,            # 0.0 to 1.0
            "stop_loss": price * 0.98      # Numeric value
        }

3. USE ONLY IN SIGNAL GENERATION:
   ✅ Read market data
   ✅ Calculate technical indicators
   ✅ Analyze patterns
   ✅ Return signal

4. NEVER DO:
   ❌ Import broker/api modules
   ❌ Place orders
   ❌ Query database directly
   ❌ Make HTTP requests
   ❌ Modify state

===================================================================
SIGNAL STRUCTURE
===================================================================

REQUIRED Return Format:
{
    "action": str,          # "BUY", "SELL", or "HOLD"
    "confidence": float,    # Range: 0.0 to 1.0
    "stop_loss": float      # Price level (>= 0.0)
}

VALIDATION:
- Action: Must be exactly "BUY", "SELL", or "HOLD"
- Confidence: Must be between 0.0 and 1.0
- Stop Loss: Must be >= 0.0

EXAMPLE SIGNALS:

Signal 1 - Strong BUY:
{
    "action": "BUY",
    "confidence": 0.95,
    "stop_loss": 2840.25
}

Signal 2 - Weak SELL:
{
    "action": "SELL",
    "confidence": 0.45,
    "stop_loss": 2860.50
}

Signal 3 - Hold:
{
    "action": "HOLD",
    "confidence": 0.0,
    "stop_loss": 2850.00
}

===================================================================
ENFORCEMENT MECHANISMS
===================================================================

1. ABSTRACT METHOD ENFORCEMENT:
   - generate_signal() MUST be implemented
   - Missing method → NotImplementedError at __init__

2. FORBIDDEN PATTERN DETECTION:
   - Scans generate_signal() source code
   - Rejects: broker, api, database, execute, order, requests, conn
   - Pattern found → ValueError at __init__

3. SIGNAL VALIDATION:
   - Every signal checked at return time
   - Invalid structure → ValueError at runtime
   - Validated automatically by _validate_signal_output()

===================================================================
EXAMPLE: RSI STRATEGY
===================================================================

from backend.strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("RSI_Strategy")
        self.oversold = 30
        self.overbought = 70
    
    def generate_signal(self, market_data, indicators):
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

# Usage:
strategy = RSIStrategy()
signal = strategy.generate_signal(
    market_data={"symbol": "RELIANCE", "price": 2850.50},
    indicators={"rsi": 25.5}
)
# Returns: {"action": "BUY", "confidence": 0.15, "stop_loss": 2793.49}

===================================================================
ANTI-PATTERNS (DO NOT DO)
===================================================================

❌ Pattern 1 - API Calls in Strategy:

    def generate_signal(self, market_data, indicators):
        # FORBIDDEN!
        from backend.broker_api import get_account
        account = get_account()  # ERROR!
        return {"action": "BUY", ...}

❌ Pattern 2 - Order Execution:

    def generate_signal(self, market_data, indicators):
        # FORBIDDEN!
        from backend.core.execution import place_order
        place_order("RELIANCE", 100, "BUY")  # ERROR!
        return {"action": "BUY", ...}

❌ Pattern 3 - Database Operations:

    def generate_signal(self, market_data, indicators):
        # FORBIDDEN!
        from backend.database import log_trade
        log_trade("RELIANCE", "BUY")  # ERROR!
        return {"action": "BUY", ...}

❌ Pattern 4 - Invalid Signal Structure:

    def generate_signal(self, market_data, indicators):
        # Wrong structure - will fail validation!
        return "BUY"  # ERROR - should be Dict
        # or
        return {"action": "BUY"}  # ERROR - missing confidence, stop_loss
        # or
        return {
            "action": "INVALID",  # ERROR - not BUY/SELL/HOLD
            "confidence": 1.5,    # ERROR - not 0.0-1.0
            "stop_loss": "high"   # ERROR - not numeric
        }

===================================================================
HELPER METHODS
===================================================================

get_quantity(price) → int:
    Calculate position size based on capital.
    
    Example:
        quantity = self.get_quantity(2850.50)
        # quantity = int(25000 / 2850.50) = 8

===================================================================
TESTING YOUR STRATEGY
===================================================================

Test 1: Strategy Initialization
    from backend.strategies.my_strategy import MyStrategy
    strategy = MyStrategy()  # Should not raise error

Test 2: Signal Generation
    signal = strategy.generate_signal(
        market_data={"price": 100.0},
        indicators={"rsi": 25.0}
    )
    assert signal['action'] in ["BUY", "SELL", "HOLD"]
    assert 0.0 <= signal['confidence'] <= 1.0
    assert signal['stop_loss'] >= 0.0

Test 3: Forbidden Patterns Detected
    # If strategy imports broker/api:
    try:
        BadStrategy()  # Raises ValueError
    except ValueError as e:
        print(e)  # "not allowed to import/use ..."

Test 4: Signal Validation
    signal = strategy.generate_signal(...)
    strategy._validate_signal_output(signal)  # Raises if invalid

===================================================================
MIGRATION GUIDE
===================================================================

If you have existing strategies:

OLD:
    class OldStrategy(SomeBase):
        def analyze(self, df):
            return "BUY"

NEW:
    class NewStrategy(BaseStrategy):
        def generate_signal(self, market_data, indicators):
            return {
                "action": "BUY",
                "confidence": 0.8,
                "stop_loss": 100.0
            }

Changes:
1. Inherit from BaseStrategy
2. Rename analyze() → generate_signal()
3. Add parameters: market_data, indicators
4. Return structured dict (not string)
5. Remove any API/execution code
6. Add confidence and stop_loss calculation

===================================================================
KEY PRINCIPLES
===================================================================

1. SINGLE RESPONSIBILITY
   Strategy = Signal generation only
   Trading System = Signal execution

2. SEPARATION OF CONCERNS
   Strategy: What to trade?
   Execution: How/When to trade?
   Risk Engine: Position sizing

3. PURITY
   Same inputs → Same output
   No side effects
   No external state modification

4. TESTABILITY
   Easy to unit test
   No external dependencies
   Deterministic behavior

===================================================================
BENEFITS
===================================================================

✅ Consistent interface across all strategies
✅ Prevents accidental API/execution code
✅ Clear signal structure for downstream systems
✅ Easy validation and testing
✅ Scalability for adding new strategies
✅ Safety: Strategies can't break execution layer
✅ Debugging: Clear separation of concerns

===================================================================
"""

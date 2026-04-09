from abc import ABC, abstractmethod
from typing import Dict, Optional
import inspect
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    PURE STRATEGY INTERFACE - Signal generation only.
    
    KEY PRINCIPLE:
    Strategy receives market_data + pre-computed indicators.
    Strategy returns signal only (no calculations, no API calls).
    
    ARCHITECTURE:
    Data Layer → Indicator Engine → Strategy → Signal
    
    REQUIREMENTS:
    - All strategies MUST inherit BaseStrategy
    - All strategies MUST implement generate_signal(market_data, indicators) → Dict
    - Strategies MUST NOT calculate indicators (pre-computed by IndicatorEngine)
    - Strategies MUST NOT fetch data
    - Strategies MUST NOT call APIs or databases
    - Strategies MUST NOT execute trades
    - Strategies are PURE FUNCTIONS: same inputs → same outputs
    
    ENFORCEMENT:
    - Abstract method enforcement via ABC
    - Forbidden pattern detection at init (data fetching, API calls)
    - Signal validation enforced at runtime
    
    BENEFITS:
    - Strategies are easily testable with mock indicators
    - Strategies are simple and focused
    - No tight coupling to data sources
    - Easy to swap strategies
    - Easy to mock/unit test
    """

    def __init__(self, name: str, capital: float = 25000.0, timeframe: str = '5m'):
        """
        Initialize pure strategy.
        
        Args:
            name: Unique strategy identifier (e.g., "RSI_Strategy")
            capital: Capital allocated to this strategy (for position sizing)
            timeframe: Timeframe for indicator calculations (e.g., '5m', '15m')
        
        Raises:
            NotImplementedError: If generate_signal not implemented
            ValueError: If forbidden patterns (data fetching, API calls) detected
        """
        self.name = name
        self.capital = capital
        self.timeframe = timeframe
        
        # Validate at initialization
        self._validate_required_methods()
        self._validate_no_data_coupling()

    @abstractmethod
    def generate_signal(self, market_data: Dict, indicators: Dict) -> Dict:
        """
        PURE FUNCTION: Generate trading signal from market data + indicators.
        
        This method MUST:
        ✅ Read market_data and indicators (read-only)
        ✅ Apply decision logic based on values
        ✅ Return signal dict with exact structure
        ✅ Produce same output for same inputs (pure function)
        
        This method MUST NOT:
        ❌ Calculate indicators (use pre-computed from 'indicators' param)
        ❌ Fetch data from anywhere (use 'market_data' param)
        ❌ Call APIs or brokers
        ❌ Access databases
        ❌ Execute trades
        ❌ Have side effects
        
        Args:
            market_data: Dict with current market state
                {
                    "symbol": "RELIANCE",
                    "price": 2850.50,
                    "open": 2845.00,
                    "high": 2855.00,
                    "low": 2840.00,
                    "volume": 1000000,
                    "timestamp": "2026-04-08 14:30:00"
                }
            
            indicators: Dict with pre-calculated technical indicators
                {
                    "ema_20": 2848.30,
                    "ema_50": 2840.00,
                    "rsi": 65.5,
                    "atr": 15.20,
                    "supertrend": 2835.00,
                    "trend_direction": 1,
                    "volume_ma": 950000,
                    "vwap": 2846.50,
                    ...
                }
        
        Returns:
            Signal dict with EXACT structure:
            {
                "action": str,          # MUST be: "BUY", "SELL", or "HOLD"
                "confidence": float,    # MUST be: 0.0 <= confidence <= 1.0
                "stop_loss": float      # MUST be: numeric value >= 0.0
            }
        
        Example Implementation:
            def generate_signal(self, market_data, indicators):
                # Read pre-computed RSI
                rsi = indicators.get('rsi', 50)
                price = market_data['price']
                
                # Pure logic: no calculations, no API calls
                if rsi < 30:
                    return {
                        "action": "BUY",
                        "confidence": (30 - rsi) / 30,  # Higher confidence when more oversold
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
        """
        pass

    def _validate_required_methods(self) -> None:
        """
        Validate that generate_signal is implemented by subclass.
        
        Raises:
            NotImplementedError: If generate_signal not implemented
        """
        method = getattr(self.__class__, 'generate_signal', None)
        
        if method is None:
            raise NotImplementedError(
                f"Strategy '{self.name}' MUST implement generate_signal(market_data, indicators)"
            )
        
        if method.__isabstractmethod__:
            raise NotImplementedError(
                f"Strategy '{self.name}' MUST implement generate_signal(market_data, indicators)"
            )

    def _validate_no_data_coupling(self) -> None:
        """
        Validate that strategy doesn't contain data-fetching patterns.
        
        Prevents accidental coupling to data sources, APIs, or databases.
        
        Raises:
            ValueError: If data-coupling patterns detected
        """
        forbidden_patterns = [
            ('broker', 'Broker API calls not allowed in strategies'),
            ('api', 'API calls not allowed in strategies'),
            ('database', 'Database operations not allowed in strategies'),
            ('db.query', 'Database queries not allowed in strategies'),
            ('http', 'HTTP requests not allowed in strategies'),
            ('requests', 'External requests not allowed in strategies'),
            ('execute_trade', 'Trade execution not allowed in strategies'),
            ('place_order', 'Order placement not allowed in strategies'),
            ('get_candles', 'Data fetching not allowed in strategies'),
            ('fetch_data', 'Data fetching not allowed in strategies'),
        ]
        
        try:
            source = inspect.getsource(self.generate_signal)
            source_lower = source.lower()
            
            for pattern, error_msg in forbidden_patterns:
                if pattern in source_lower:
                    raise ValueError(
                        f"❌ VIOLATION in '{self.name}': {error_msg}. "
                        f"Found: '{pattern}'. "
                        f"Strategies must ONLY use 'market_data' and 'indicators' parameters "
                        f"to generate signals. Data fetching is responsibility of execution layer."
                    )
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Could not validate strategy '{self.name}': {e}")

    def _validate_signal_output(self, signal: Dict) -> None:
        """
        Validate signal structure and values (called by TradingSystem).
        
        Args:
            signal: Signal dict to validate
        
        Raises:
            ValueError: If signal structure/values invalid
        """
        if not isinstance(signal, dict):
            raise ValueError(
                f"❌ Signal must be dict, got {type(signal)}. "
                f"Required: {{'action': 'BUY'|'SELL'|'HOLD', 'confidence': 0-1, 'stop_loss': float}}"
            )
        
        # Check required keys
        required_keys = {'action', 'confidence', 'stop_loss'}
        missing_keys = required_keys - set(signal.keys())
        
        if missing_keys:
            raise ValueError(
                f"❌ Signal missing keys: {missing_keys}. "
                f"Required: action, confidence, stop_loss"
            )
        
        # Validate action
        if signal['action'] not in {'BUY', 'SELL', 'HOLD'}:
            raise ValueError(
                f"❌ action must be BUY/SELL/HOLD, got '{signal['action']}'"
            )
        
        # Validate confidence
        if not isinstance(signal['confidence'], (int, float)):
            raise ValueError(
                f"❌ confidence must be numeric, got {type(signal['confidence'])}"
            )
        if not 0.0 <= signal['confidence'] <= 1.0:
            raise ValueError(
                f"❌ confidence must be 0.0-1.0, got {signal['confidence']}"
            )
        
        # Validate stop_loss
        if not isinstance(signal['stop_loss'], (int, float)):
            raise ValueError(
                f"❌ stop_loss must be numeric, got {type(signal['stop_loss'])}"
            )
        if signal['stop_loss'] < 0:
            raise ValueError(
                f"❌ stop_loss must be >= 0, got {signal['stop_loss']}"
            )

    def get_quantity(self, price: float) -> int:
        """
        SAFE HELPER: Calculate position size based on capital.
        
        Use this helper in generate_signal() for consistent position sizing.
        
        Args:
            price: Current price (numeric > 0)
        
        Returns:
            Position size (quantity of shares)
        
        Example:
            qty = self.get_quantity(market_data['price'])
        """
        if not isinstance(price, (int, float)):
            raise ValueError(f"Price must be numeric, got {type(price)}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        return max(1, int(self.capital / price))

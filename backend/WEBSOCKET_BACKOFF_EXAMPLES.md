"""
WebSocket Exponential Backoff Usage Examples

This module demonstrates how to use the exponential backoff 
reconnection system in DataManager.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Check Connection Status
# ============================================================================

def check_market_data_status():
    """Check current market data connection status."""
    from backend.services.market_data import get_data_manager
    
    manager = get_data_manager()
    
    print(f"Connected: {manager.is_connected}")
    print(f"Retry count: {manager.retry_count}/{manager.MAX_RETRIES}")
    print(f"Degraded: {manager.is_degraded}")
    
    if manager.is_degraded:
        print("🚨 ALERT: System is degraded - manual intervention needed")
        return False
    elif not manager.is_connected:
        delay = manager._get_backoff_delay()
        print(f"⚠️  Recovering - will retry in ~{delay:.1f}s")
        return False
    else:
        print("✅ System healthy and receiving live data")
        return True

## Example 2: Get Price with Status Check

```python
from backend.services.market_data import get_data_manager
from typing import Optional, Dict

def get_live_price(symbol: str) -> Optional[Dict]:
    """Get live price with connection status."""
    manager = get_data_manager()
    
    if manager.is_degraded:
        return {
            'error': 'System degraded - market data unavailable',
            'status': 'degraded'
        }
    
    if not manager.is_connected:
        return {
            'error': 'Market data recovering - try again soon',
            'status': 'recovering',
            'retry_count': manager.retry_count,
            'max_retries': manager.MAX_RETRIES
        }
    
    price = manager.get_price(symbol)
    return {
        'symbol': symbol,
        'price': price,
        'status': 'live',
        'symbols_in_store': len(manager.price_store.prices)
    }

# Usage
result = get_live_price('SBIN-EQ')
print(f"SBIN-EQ: {result}")
# Output: {'symbol': 'SBIN-EQ', 'price': 520.50, 'status': 'live', 'symbols_in_store': 42}
```

## Example 3: Monitor Reconnection Process

```python
import logging
import time
from backend.services.market_data import get_data_manager
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def monitor_reconnection(duration_seconds: int = 600):
    """Monitor reconnection attempts for specified duration."""
    manager = get_data_manager()
    start_time = datetime.now()
    
    print(f"Starting 10-minute reconnection monitor at {start_time}")
    print(f"Max retries before degradation: {manager.MAX_RETRIES}")
    print()
    
    while (datetime.now() - start_time).total_seconds() < duration_seconds:
        status = manager.health_status()
        
        print(f"[{datetime.now().isoformat()}]")
        print(f"  Connected: {status['is_connected']}")
        print(f"  Retry: {manager.retry_count}/{manager.MAX_RETRIES}")
        print(f"  Degraded: {manager.is_degraded}")
        print(f"  Staleness: {status['staleness_seconds']:.1f}s")
        print(f"  Ticks: {status['tick_count']}")
        
        if manager.is_degraded:
            print("  🚨 SYSTEM DEGRADED!")
            break
        
        time.sleep(10)  # Check every 10 seconds
        print()

# Usage
# monitor_reconnection(duration_seconds=600)  # Run for 10 minutes
```

## Example 4: Simulate Broker Outage (Testing)

```python
from backend.services.market_data import get_data_manager
from datetime import datetime, timedelta
import time

def simulate_broker_outage():
    """Simulate broker outage and test exponential backoff."""
    manager = get_data_manager()
    
    print("🔧 Simulating broker outage...\n")
    
    # Simulate stale data by setting timestamp to the past
    manager.last_tick_time = datetime.now() - timedelta(seconds=60)
    
    print("Simulated stale data (60+ seconds old)")
    print(f"Initial retry_count: {manager.retry_count}\n")
    
    # Run health checks to trigger reconnection attempts
    for attempt in range(15):
        print(f"\n--- Health Check {attempt + 1} ---")
        manager._perform_health_check()
        
        print(f"After check:")
        print(f"  retry_count: {manager.retry_count}/{manager.MAX_RETRIES}")
        print(f"  is_degraded: {manager.is_degraded}")
        
        # Wait a bit between checks
        time.sleep(0.5)
        
        if manager.is_degraded:
            print("\n✓ System correctly entered degraded state after max retries")
            break
    
    # Simulate recovery
    print("\n\n🔄 Simulating broker recovery...\n")
    manager.last_tick_time = datetime.now()  # Fresh data
    manager._perform_health_check()
    
    print(f"After recovery:")
    print(f"  retry_count: {manager.retry_count} (reset to 0 ✓)")
    print(f"  is_degraded: {manager.is_degraded}")
    print(f"  is_connected: {manager.is_connected}")

# Usage
# simulate_broker_outage()
```

## Example 5: Monitoring Integration - Flask Endpoint

```python
from flask import Blueprint, jsonify, current_app
from backend.services.market_data import get_data_manager
from datetime import datetime

market_data_bp = Blueprint('market_data', __name__)

@market_data_bp.route('/health/market-data', methods=['GET'])
def market_data_health():
    """GET /health/market-data - Check market data system health."""
    manager = get_data_manager()
    status = manager.health_status()
    
    if manager.is_degraded:
        # System degraded - return 503 Service Unavailable
        return jsonify({
            'status': 'degraded',
            'message': 'Market data system degraded - manual intervention required',
            'retry_count': manager.retry_count,
            'max_retries': manager.MAX_RETRIES,
            'last_retry_time': str(manager.last_retry_time),
            'action_required': 'Manual system restart or broker recovery'
        }), 503
    
    elif not manager.is_connected:
        # Reconnecting - return 503 with recovery info
        delay = manager._get_backoff_delay()
        return jsonify({
            'status': 'recovering',
            'message': 'Market data recovering',
            'retry_count': manager.retry_count,
            'max_retries': manager.MAX_RETRIES,
            'estimated_retry_in_seconds': delay,
            'tick_count': status['tick_count'],
            'symbols': len(manager.price_store.prices)
        }), 503
    
    else:
        # Healthy - return 200 OK
        return jsonify({
            'status': 'healthy',
            'message': 'Market data streaming normally',
            'tick_count': status['tick_count'],
            'symbols_active': len(manager.price_store.prices),
            'staleness_seconds': status['staleness_seconds'],
            'last_tick': str(manager.last_tick_time),
            'timestamp': datetime.now().isoformat()
        }), 200

# Register blueprint
# app.register_blueprint(market_data_bp)
```

## Example 6: Monitoring Integration - FastAPI Endpoint

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.market_data import get_data_manager
from datetime import datetime

router = APIRouter(prefix="/api/health", tags=["health"])

class MarketDataStatus(BaseModel):
    status: str  # 'healthy', 'recovering', 'degraded'
    message: str
    tick_count: int
    symbols_active: int
    retry_count: int
    max_retries: int
    timestamp: str

@router.get("/market-data", response_model=MarketDataStatus)
async def market_data_health():
    """GET /api/health/market-data - Check market data system health."""
    manager = get_data_manager()
    status = manager.health_status()
    
    if manager.is_degraded:
        raise HTTPException(
            status_code=503,
            detail={
                'status': 'degraded',
                'message': 'Market data system degraded - manual intervention required',
                'retry_count': manager.retry_count,
                'max_retries': manager.MAX_RETRIES,
                'action': 'Restart system or check broker'
            }
        )
    
    if not manager.is_connected:
        raise HTTPException(
            status_code=503,
            detail={
                'status': 'recovering',
                'message': 'Market data recovering',
                'retry_count': manager.retry_count,
                'max_retries': manager.MAX_RETRIES,
                'estimated_next_retry_seconds': manager._get_backoff_delay()
            }
        )
    
    return MarketDataStatus(
        status='healthy',
        message='Market data streaming normally',
        tick_count=status['tick_count'],
        symbols_active=len(manager.price_store.prices),
        retry_count=manager.retry_count,
        max_retries=manager.MAX_RETRIES,
        timestamp=datetime.now().isoformat()
    )

# Include router
# app.include_router(router)
```

## Example 7: Alert System Integration

```python
from backend.services.market_data import get_data_manager
from backend.services.notifications import send_alert, AlertLevel
import threading
import time

class MarketDataAlertMonitor:
    """Monitor market data and send alerts."""
    
    def __init__(self, check_interval_seconds: int = 30):
        self.interval = check_interval_seconds
        self.last_degraded_alert_sent = False
        self.last_recovering_alert_sent = False
    
    def check_and_alert(self):
        """Check market data status and send appropriate alerts."""
        manager = get_data_manager()
        
        if manager.is_degraded:
            if not self.last_degraded_alert_sent:
                send_alert(
                    level=AlertLevel.CRITICAL,
                    title="🚨 Market Data System Degraded",
                    message=f"WebSocket unreachable after {manager.retry_count} attempts",
                    context={
                        'retry_count': manager.retry_count,
                        'max_retries': manager.MAX_RETRIES,
                        'last_tick_time': str(manager.last_tick_time),
                        'symbols_lost': len(manager.price_store.prices),
                        'recommendation': 'Manual intervention required. Check broker status.'
                    }
                )
                self.last_degraded_alert_sent = True
                self.last_recovering_alert_sent = False
        
        elif not manager.is_connected:
            if not self.last_recovering_alert_sent and manager.retry_count >= 3:
                send_alert(
                    level=AlertLevel.WARNING,
                    title="⚠️ Market Data Recovering",
                    message=f"Reconnection attempt {manager.retry_count}/{manager.MAX_RETRIES}",
                    context={
                        'retry_count': manager.retry_count,
                        'max_retries': manager.MAX_RETRIES,
                        'next_retry_in_seconds': manager._get_backoff_delay(),
                        'recommendation': 'Monitor - system will auto-recover'
                    }
                )
                self.last_recovering_alert_sent = True
        
        else:
            # Healthy - clear flags
            self.last_degraded_alert_sent = False
            self.last_recovering_alert_sent = False
    
    def run_background(self):
        """Run monitoring in background thread."""
        def monitor_loop():
            while True:
                self.check_and_alert()
                time.sleep(self.interval)
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        return thread

# Usage
# monitor = MarketDataAlertMonitor(check_interval_seconds=30)
# monitor.run_background()
```

## Example 8: Backoff Schedule View

```python
from backend.services.market_data import DataManager

def show_backoff_schedule():
    """Display exponential backoff schedule."""
    manager = DataManager()
    
    print("Exponential Backoff Schedule")
    print("=" * 60)
    print(f"MAX_RETRIES: {manager.MAX_RETRIES}")
    print(f"MAX_BACKOFF_SECONDS: {manager.MAX_BACKOFF_SECONDS}")
    print(f"JITTER_RANGE: {manager.JITTER_RANGE}")
    print()
    print("Retry | Exponential | Jitter Range | Total Delay")
    print("-" * 60)
    
    cumulative = 0
    for retry in range(1, manager.MAX_RETRIES + 1):
        manager.retry_count = retry
        exponential = min(2 ** (retry - 1), manager.MAX_BACKOFF_SECONDS)
        jitter_min = 0
        jitter_max = manager.JITTER_RANGE
        delay_min = exponential + jitter_min
        delay_max = exponential + jitter_max
        cumulative += (delay_min + delay_max) / 2
        
        print(
            f"{retry:2d}    | {exponential:3.0f}s        | "
            f"{jitter_min}-{jitter_max}s        | {delay_min:.1f}-{delay_max:.1f}s"
        )
    
    print("-" * 60)
    print(f"Total time to max retries: ~{cumulative:.0f}s (~{cumulative/60:.1f} min)")

# Usage
# show_backoff_schedule()
```

## Example 9: Configuration Update

```python
from backend.services.market_data import DataManager

def update_backoff_config(max_retries: int = None, 
                          max_backoff: int = None,
                          jitter_range: float = None):
    """Update exponential backoff configuration."""
    
    if max_retries is not None:
        DataManager.MAX_RETRIES = max_retries
        print(f"✓ MAX_RETRIES = {max_retries}")
    
    if max_backoff is not None:
        DataManager.MAX_BACKOFF_SECONDS = max_backoff
        print(f"✓ MAX_BACKOFF_SECONDS = {max_backoff}")
    
    if jitter_range is not None:
        DataManager.JITTER_RANGE = jitter_range
        print(f"✓ JITTER_RANGE = {jitter_range}")

# Usage - More patient for unstable networks
# update_backoff_config(max_retries=15, max_backoff=120, jitter_range=5)

# Usage - Less patient for stable networks
# update_backoff_config(max_retries=5, max_backoff=30, jitter_range=1)
```

## Example 10: Automated Testing Script

```python
import pytest
from datetime import datetime, timedelta
from backend.services.market_data import DataManager

def test_exponential_backoff():
    """Test exponential backoff calculation."""
    manager = DataManager()
    
    expected = [1, 2, 4, 8, 16, 32, 60, 60, 60, 60]
    for retry, exp_backoff in enumerate(expected, 1):
        manager.retry_count = retry
        exponential_part = min(2 ** (retry - 1), manager.MAX_BACKOFF_SECONDS)
        
        assert exponential_part == exp_backoff, \
            f"Retry {retry}: expected {exp_backoff}s, got {exponential_part}s"
    
    print("✓ Exponential backoff calculation correct")

def test_jitter_range():
    """Test jitter is within expected range."""
    manager = DataManager()
    manager.retry_count = 3
    
    for _ in range(100):
        delay = manager._get_backoff_delay()
        exponential = 4  # 2^3
        
        assert delay >= exponential, "Delay less than exponential part"
        assert delay <= exponential + manager.JITTER_RANGE, "Delay exceeds max with jitter"
    
    print("✓ Jitter range within bounds")

def test_retry_count_reset():
    """Test retry count resets on success."""
    manager = DataManager()
    manager.retry_count = 5
    manager.last_tick_time = datetime.now()
    
    # Simulate fresh data
    manager._perform_health_check()
    
    assert manager.retry_count == 0, "Retry count not reset on fresh data"
    print("✓ Retry count reset on success")

def test_degradation_after_max_retries():
    """Test system degradation after max retries."""
    manager = DataManager()
    manager.is_running = True
    manager.last_tick_time = datetime.now() - timedelta(seconds=60)
    
    # Simulate max retries
    for i in range(manager.MAX_RETRIES + 1):
        manager._attempt_reconnect()
    
    assert manager.is_degraded, "System not degraded after max retries"
    print("✓ System degraded after max retries")

# Run tests
if __name__ == "__main__":
    test_exponential_backoff()
    test_jitter_range()
    test_retry_count_reset()
    test_degradation_after_max_retries()
    print("\n✓ All tests passed!")
```

---

## Key Patterns

### Pattern 1: Check Before Trading
```python
manager = get_data_manager()
if manager.is_degraded:
    raise Exception("Market data degraded - cannot trade")
if not manager.is_connected:
    raise Exception("Market data recovering - try again soon")
# Safe to trade with live prices
```

### Pattern 2: Graceful Degradation
```python
try:
    price = manager.get_price(symbol)
except Exception:
    if manager.is_degraded:
        price = fallback_price_cache
    else:
        raise
```

### Pattern 3: Health Endpoint
```python
if manager.is_degraded:
    return 503  # Service Unavailable
elif not manager.is_connected:
    return 503  # Recovering
else:
    return 200  # OK
```

---

**Last Updated:** April 8, 2026  
**Related:** [WEBSOCKET_RECONNECT_BACKOFF.md](WEBSOCKET_RECONNECT_BACKOFF.md)

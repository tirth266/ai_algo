"""
ANGELSERVICE USAGE EXAMPLES

This file contains production-ready code examples for using the AngelService
broker integration layer.

Run these examples to verify your setup and understand the API.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
from backend.services.angel_service import (
    get_angel_service, OrderRequest, ApiStatus,
)

logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: AUTHENTICATION
# ============================================================================

def example_authentication():
    """Authenticate with Angel One broker."""
    
    print("\n" + "="*70)
    print("EXAMPLE 1: AUTHENTICATION")
    print("="*70)
    
    service = get_angel_service()
    
    # Auto-login using environment variables
    response = service.login()
    
    print(f"Status: {response.status.value}")
    print(f"Message: {response.message}")
    
    if response.is_success():
        print("✓ Authentication successful!")
        print(f"  Token: {response.data['jwt_token']}")
    else:
        print("✗ Authentication failed!")
        print(f"  Error Code: {response.error_code}")


# ============================================================================
# EXAMPLE 2: PLACE A MARKET ORDER
# ============================================================================

def example_place_market_order():
    """Place a market order for BUY."""
    
    print("\n" + "="*70)
    print("EXAMPLE 2: PLACE MARKET ORDER")
    print("="*70)
    
    service = get_angel_service()
    
    # Create order request
    order_request = OrderRequest(
        symbol="SBIN-EQ",
        direction="BUY",
        quantity=10,
        price=0.0,  # Market order (price ignored)
        order_type="MARKET",
        product="INTRADAY",
    )
    
    print(f"Sending order: {order_request.direction} {order_request.quantity} "
          f"{order_request.symbol} @ {order_request.order_type}")
    
    # Place order
    response = service.place_order(order_request)
    
    print(f"Status: {response.status.value}")
    print(f"Message: {response.message}")
    
    if response.is_success():
        order_id = response.data["order_id"]
        print(f"✓ Order placed successfully!")
        print(f"  Order ID: {order_id}")
        print(f"  Symbol: {response.data['symbol']}")
        print(f"  Quantity: {response.data['quantity']}")
    else:
        print(f"✗ Order placement failed!")
        print(f"  Error Code: {response.error_code}")
        if response.retry_count > 0:
            print(f"  Retries: {response.retry_count}")


# ============================================================================
# EXAMPLE 3: PLACE A LIMIT ORDER WITH STOP LOSS
# ============================================================================

def example_place_limit_order_with_sl():
    """Place a limit order with stop loss."""
    
    print("\n" + "="*70)
    print("EXAMPLE 3: LIMIT ORDER WITH STOP LOSS")
    print("="*70)
    
    service = get_angel_service()
    
    # Create limit order with stop loss
    order_request = OrderRequest(
        symbol="RELIANCE-EQ",
        direction="BUY",
        quantity=5,
        price=2960.00,  # Limit price
        order_type="SL",  # Stop Loss order
        stop_loss=2950.00,  # Trigger price
        product="INTRADAY",
    )
    
    print(f"Sending order: {order_request.direction} {order_request.quantity} "
          f"{order_request.symbol} @ {order_request.price}")
    print(f"  Stop Loss: {order_request.stop_loss}")
    
    # Place order
    response = service.place_order(order_request)
    
    if response.is_success():
        print(f"✓ Stop loss order placed!")
        print(f"  Order ID: {response.data['order_id']}")
    else:
        print(f"✗ Order failed: {response.message}")


# ============================================================================
# EXAMPLE 4: GET OPEN ORDERS
# ============================================================================

def example_get_orders():
    """Retrieve all open orders."""
    
    print("\n" + "="*70)
    print("EXAMPLE 4: GET OPEN ORDERS")
    print("="*70)
    
    service = get_angel_service()
    
    print("Retrieving open orders...")
    response = service.get_orders()
    
    print(f"Status: {response.status.value}")
    print(f"Message: {response.message}")
    
    if response.is_success():
        orders = response.data["orders"]
        print(f"✓ Retrieved {len(orders)} orders:")
        
        for order in orders:
            print(f"\n  Order ID: {order['order_id']}")
            print(f"    Symbol: {order['symbol']}")
            print(f"    Direction: {order['direction']}")
            print(f"    Quantity: {order['quantity']}")
            print(f"    Price: {order['price']}")
            print(f"    Status: {order['status']}")
            print(f"    Type: {order['order_type']}")
    else:
        print(f"✗ Failed to retrieve orders!")
        print(f"  Error: {response.message}")


# ============================================================================
# EXAMPLE 5: GET POSITIONS
# ============================================================================

def example_get_positions():
    """Retrieve all open positions."""
    
    print("\n" + "="*70)
    print("EXAMPLE 5: GET POSITIONS")
    print("="*70)
    
    service = get_angel_service()
    
    print("Retrieving positions...")
    response = service.get_positions()
    
    print(f"Status: {response.status.value}")
    print(f"Message: {response.message}")
    
    if response.is_success():
        positions = response.data["positions"]
        print(f"✓ Retrieved {len(positions)} positions:")
        
        for pos in positions:
            print(f"\n  Symbol: {pos['symbol']}")
            print(f"    Direction: {pos['direction']}")
            print(f"    Quantity: {pos['quantity']}")
            print(f"    Entry Price: ₹{pos['entry_price']:.2f}")
            print(f"    Current Price: ₹{pos['current_price']:.2f}")
            print(f"    PnL: ₹{pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
            print(f"    Product: {pos['product']}")
    else:
        print(f"✗ Failed to retrieve positions!")
        print(f"  Error: {response.message}")


# ============================================================================
# EXAMPLE 6: ERROR HANDLING - RATE LIMIT
# ============================================================================

def example_handle_rate_limit():
    """Handle rate limit errors."""
    
    print("\n" + "="*70)
    print("EXAMPLE 6: HANDLE RATE LIMIT")
    print("="*70)
    
    service = get_angel_service()
    
    # Send many orders quickly to demonstrate rate limiting
    print("Sending multiple orders rapidly...")
    
    for i in range(5):
        order_request = OrderRequest(
            symbol=f"TEST-EQ",
            direction="BUY",
            quantity=1,
            price=0.0,
            order_type="MARKET",
        )
        
        response = service.place_order(order_request)
        
        print(f"\nOrder {i+1}:")
        print(f"  Status: {response.status.value}")
        
        if response.status == ApiStatus.RATE_LIMIT:
            print(f"  ✗ Rate limited!")
            print(f"  Message: {response.message}")
            print(f"  Retries: {response.retry_count}")
            print(f"  ⏳ AngelService will auto-retry with backoff")
            break
        elif response.is_success():
            print(f"  ✓ Success: {response.data['order_id']}")
        else:
            print(f"  ✗ Failed: {response.message}")


# ============================================================================
# EXAMPLE 7: ERROR HANDLING - AUTHENTICATION FAILURE
# ============================================================================

def example_handle_auth_error():
    """Handle authentication errors."""
    
    print("\n" + "="*70)
    print("EXAMPLE 7: HANDLE AUTHENTICATION ERROR")
    print("="*70)
    
    service = get_angel_service()
    
    # Try with invalid credentials
    print("Attempting login with invalid credentials...")
    response = service.login(
        client_id="INVALID_ID",
        password="INVALID_PASSWORD",
        totp="000000",
        retries=1  # Single retry for demo
    )
    
    print(f"Status: {response.status.value}")
    
    if response.status == ApiStatus.UNAUTHORIZED:
        print(f"✗ Authentication failed!")
        print(f"  Error Code: {response.error_code}")
        print(f"  Message: {response.message}")
        print(f"\nRecovery steps:")
        print(f"  1. Verify credentials in .env")
        print(f"  2. Check TOTP is correct")
        print(f"  3. Verify client ID")
        print(f"  4. Check broker account status")
    else:
        print(f"Unexpected status: {response.status.value}")


# ============================================================================
# EXAMPLE 8: MULTI-LEG TRADING STRATEGY
# ============================================================================

def example_multi_leg_strategy():
    """Example of multi-leg trading strategy."""
    
    print("\n" + "="*70)
    print("EXAMPLE 8: MULTI-LEG TRADING")
    print("="*70)
    
    service = get_angel_service()
    
    # Strategy: Buy SBIN, Sell RELIANCE for spread
    trades = [
        {
            "name": "Buy SBIN",
            "order": OrderRequest(
                symbol="SBIN-EQ",
                direction="BUY",
                quantity=10,
                price=0.0,
                order_type="MARKET",
            )
        },
        {
            "name": "Sell RELIANCE",
            "order": OrderRequest(
                symbol="RELIANCE-EQ",
                direction="SELL",
                quantity=5,
                price=0.0,
                order_type="MARKET",
            )
        },
    ]
    
    results = []
    
    for trade in trades:
        print(f"\n{trade['name']}...")
        response = service.place_order(trade['order'])
        
        results.append({
            "name": trade["name"],
            "response": response
        })
        
        if response.is_success():
            print(f"  ✓ Order placed: {response.data['order_id']}")
        else:
            print(f"  ✗ Order failed: {response.message}")
    
    # Summary
    print(f"\n{'─'*70}")
    print("STRATEGY EXECUTION SUMMARY")
    print(f"{'─'*70}")
    
    success_count = sum(1 for r in results if r["response"].is_success())
    total_count = len(results)
    
    print(f"Successful: {success_count}/{total_count}")
    
    for result in results:
        status = "✓" if result["response"].is_success() else "✗"
        print(f"  {status} {result['name']}: {result['response'].status.value}")


# ============================================================================
# EXAMPLE 9: POSITION RECONCILIATION
# ============================================================================

def example_position_reconciliation():
    """Reconcile local positions with broker."""
    
    print("\n" + "="*70)
    print("EXAMPLE 9: POSITION RECONCILIATION")
    print("="*70)
    
    from backend.core.execution import TradingSystem
    
    # Initialize system with live trading
    system = TradingSystem(
        capital=100000.0,
        enable_live_trading=True
    )
    
    print("Starting position reconciliation...")
    report = system.reconcile_with_broker()
    
    print(f"\nReconciliation Status: {report['status']}")
    print(f"Broker Positions: {report['broker_positions_count']}")
    print(f"Local Positions: {report['local_positions_count']}")
    
    if report.get('discrepancies_found', 0) > 0:
        print(f"\nDiscrepancies Found: {report['discrepancies_found']}")
        for disc in report.get('discrepancies', []):
            print(f"  ⚠ {disc}")
    else:
        print(f"✓ All positions reconciled successfully!")
    
    if report.get('corrections'):
        print(f"\nCorrections Applied: {len(report['corrections'])}")
        for correction in report['corrections']:
            print(f"  - {correction['action']}: {correction['symbol']}")


# ============================================================================
# EXAMPLE 10: MONITORING & LOGGING
# ============================================================================

def example_monitoring():
    """Example of monitoring service health."""
    
    print("\n" + "="*70)
    print("EXAMPLE 10: MONITORING & LOGGING")
    print("="*70)
    
    service = get_angel_service()
    
    # Check token state
    token_state = service.token_manager.get_token_state()
    
    print(f"Token State:")
    print(f"  Authenticated: {token_state['is_authenticated']}")
    print(f"  Expires At: {token_state.get('expires_at', 'Unknown')}")
    
    # Test basic operations
    operations = [
        ("Get Orders", lambda: service.get_orders()),
        ("Get Positions", lambda: service.get_positions()),
    ]
    
    print(f"\nOperation Health Check:")
    for op_name, op_func in operations:
        try:
            response = op_func()
            status = "✓" if response.is_success() else "✗"
            print(f"  {status} {op_name}: {response.status.value}")
        except Exception as e:
            print(f"  ✗ {op_name}: EXCEPTION - {str(e)}")


# ============================================================================
# MAIN - RUN EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  ANGEL SERVICE USAGE EXAMPLES" + " "*37 + "█")
    print("█" + " "*68 + "█")
    print("█"*70 + "\n")
    
    # Uncomment examples to run:
    
    # example_authentication()
    # example_place_market_order()
    # example_place_limit_order_with_sl()
    # example_get_orders()
    # example_get_positions()
    # example_handle_rate_limit()
    # example_handle_auth_error()
    # example_multi_leg_strategy()
    # example_position_reconciliation()
    # example_monitoring()
    
    print("\n" + "█"*70)
    print("█  To run an example, uncomment it in the __main__ section" + " "*11 + "█")
    print("█"*70)

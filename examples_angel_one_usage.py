"""
Angel One SmartAPI - Example Usage Scripts

This file contains practical examples of using the Angel One broker integration
for common trading scenarios.

Author: Quantitative Trading Systems Engineer
Date: March 28, 2026
"""

from backend.trading.angel_one_broker import AngelOneBroker, create_angelone_broker
from backend.trading.broker_interface import Order
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Basic Setup and Connection
# ============================================================================

def example_1_basic_connection():
    """Example 1: Connect to Angel One with auto-authentication."""
    
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Connection")
    print("="*70)
    
    # Method 1: Using convenience function (recommended)
    broker = create_angelone_broker()
    
    # Check connection
    if broker.is_connected():
        print(f"✅ Connected! User ID: {broker.user_id}")
        
        # Get profile
        profile = broker.smart_api.getProfile()
        print(f"   Name: {profile.get('name')}")
    
    return broker


# ============================================================================
# Example 2: Placing Market Orders
# ============================================================================

def example_2_market_order(broker):
    """Example 2: Place a market order."""
    
    print("\n" + "="*70)
    print("EXAMPLE 2: Market Order Placement")
    print("="*70)
    
    # Create a market order
    order = Order(
        symbol="SBIN-EQ",      # Trading symbol
        quantity=10,           # Number of shares
        side="BUY",            # BUY or SELL
        order_type="MARKET",   # Market order
        product="MIS"          # Intraday (MIS -> INTRADAY)
    )
    
    print(f"\nOrder Details:")
    print(f"  Symbol: {order.symbol}")
    print(f"  Quantity: {order.quantity}")
    print(f"  Side: {order.side}")
    print(f"  Type: {order.order_type}")
    
    # Place the order
    try:
        response = broker.place_order(order)
        
        print(f"\n✅ Order placed successfully!")
        print(f"   Order ID: {response['order_id']}")
        print(f"   Status: {response['status']}")
        
        return response['order_id']
    
    except Exception as e:
        print(f"\n❌ Order failed: {str(e)}")
        return None


# ============================================================================
# Example 3: Placing Limit Orders
# ============================================================================

def example_3_limit_order(broker):
    """Example 3: Place a limit order."""
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Limit Order Placement")
    print("="*70)
    
    # Get current LTP first
    ltp = broker.get_ltp("RELIANCE-EQ")
    print(f"\nRELIANCE-EQ LTP: ₹{ltp:.2f}")
    
    # Place limit order slightly below LTP
    limit_price = ltp * 0.995  # 0.5% below LTP
    
    order = Order(
        symbol="RELIANCE-EQ",
        quantity=5,
        side="BUY",
        order_type="LIMIT",
        price=limit_price,     # Limit price
        product="CNC"          # Delivery (CNC -> DELIVERY)
    )
    
    print(f"\nLimit Order Details:")
    print(f"  Symbol: {order.symbol}")
    print(f"  Quantity: {order.quantity}")
    print(f"  Limit Price: ₹{limit_price:.2f}")
    print(f"  Product: {order.product}")
    
    try:
        response = broker.place_order(order)
        
        print(f"\n✅ Limit order placed!")
        print(f"   Order ID: {response['order_id']}")
        
        return response['order_id']
    
    except Exception as e:
        print(f"\n❌ Order failed: {str(e)}")
        return None


# ============================================================================
# Example 4: Stop Loss Orders
# ============================================================================

def example_4_stop_loss_order(broker):
    """Example 4: Place a stop-loss limit order."""
    
    print("\n" + "="*70)
    print("EXAMPLE 4: Stop-Loss Limit Order")
    print("="*70)
    
    # Get current LTP
    ltp = broker.get_ltp("TATAMOTORS-EQ")
    print(f"\nTATAMOTORS-EQ LTP: ₹{ltp:.2f}")
    
    # For a BUY order with SL:
    # - Entry price: Current LTP
    # - Trigger price: Below LTP (for protection)
    trigger_price = ltp * 0.98  # 2% below LTP
    
    order = Order(
        symbol="TATAMOTORS-EQ",
        quantity=20,
        side="BUY",
        order_type="SL",         # Stop-loss limit
        price=ltp,               # Entry price
        stop_loss=trigger_price, # Stop-loss trigger
        product="MIS"
    )
    
    print(f"\nStop-Loss Order Details:")
    print(f"  Symbol: {order.symbol}")
    print(f"  Quantity: {order.quantity}")
    print(f"  Entry Price: ₹{ltp:.2f}")
    print(f"  Stop-Loss Trigger: ₹{trigger_price:.2f}")
    
    try:
        response = broker.place_order(order)
        
        print(f"\n✅ SL order placed!")
        print(f"   Order ID: {response['order_id']}")
        
        return response['order_id']
    
    except Exception as e:
        print(f"\n❌ Order failed: {str(e)}")
        return None


# ============================================================================
# Example 5: Managing Positions
# ============================================================================

def example_5_manage_positions(broker):
    """Example 5: View and manage positions."""
    
    print("\n" + "="*70)
    print("EXAMPLE 5: Position Management")
    print("="*70)
    
    # Get all positions
    positions = broker.get_positions()
    
    if not positions:
        print("\nℹ️  No open positions")
        return
    
    print(f"\n📊 Open Positions ({len(positions)} total):\n")
    
    for pos in positions:
        print(f"  {pos.symbol}")
        print(f"    Quantity: {pos.quantity}")
        print(f"    Avg Price: ₹{pos.average_price:.2f}")
        print(f"    LTP: ₹{pos.last_price:.2f}")
        print(f"    PnL: ₹{pos.pnl:.2f}")
        print(f"    Value: ₹{pos.value:.2f}")
        print()
    
    # Calculate total PnL
    total_pnl = sum(pos.pnl for pos in positions)
    total_value = sum(pos.value for pos in positions)
    
    print(f"{'='*50}")
    print(f"Total Portfolio Value: ₹{total_value:.2f}")
    print(f"Total PnL: ₹{total_pnl:.2f}")
    print(f"{'='*50}")


# ============================================================================
# Example 6: Order Management
# ============================================================================

def example_6_order_management(broker, order_id):
    """Example 6: Cancel or modify orders."""
    
    print("\n" + "="*70)
    print("EXAMPLE 6: Order Management")
    print("="*70)
    
    # Get open orders
    orders = broker.get_open_orders()
    
    if not orders:
        print("\nℹ️  No open orders")
        return
    
    print(f"\n📋 Open Orders ({len(orders)} total):\n")
    
    for order in orders:
        print(f"  Order ID: {order.order_id}")
        print(f"    Symbol: {order.symbol}")
        print(f"    Side: {order.side}")
        print(f"    Qty: {order.quantity}")
        print(f"    Filled: {order.filled_quantity}")
        print(f"    Pending: {order.pending_quantity}")
        print(f"    Price: ₹{order.price}")
        print(f"    Type: {order.order_type}")
        print(f"    Status: {order.status}")
        print()
    
    # Example: Modify an order
    if order_id and orders:
        print(f"\nModifying order {order_id}...")
        
        try:
            response = broker.modify_order(
                order_id=order_id,
                quantity=15  # Increase quantity
            )
            
            print(f"✅ Order modified!")
            print(f"   Response: {response['status']}")
        
        except Exception as e:
            print(f"❌ Modification failed: {str(e)}")
    
    # Example: Cancel an order
    if order_id and orders:
        print(f"\nCancelling order {order_id}...")
        
        try:
            response = broker.cancel_order(order_id=order_id)
            
            print(f"✅ Order cancelled!")
            print(f"   Response: {response['status']}")
        
        except Exception as e:
            print(f"❌ Cancellation failed: {str(e)}")


# ============================================================================
# Example 7: Account Balance and Margins
# ============================================================================

def example_7_account_balance(broker):
    """Example 7: Check account balance and margins."""
    
    print("\n" + "="*70)
    print("EXAMPLE 7: Account Balance & Margins")
    print("="*70)
    
    balance = broker.get_account_balance()
    
    print(f"\n💰 Account Summary:\n")
    print(f"  Total Net Value: ₹{balance['total_net_value']:.2f}")
    print(f"  Available Cash: ₹{balance['available_cash']:.2f}")
    print(f"  Available Intraday: ₹{balance['available_intraday']:.2f}")
    
    print(f"\n📊 Utilization:\n")
    print(f"  Used Debits: ₹{balance['utilized_debits']:.2f}")
    print(f"  Exposure Margin: ₹{balance['utilized_exposure']:.2f}")
    print(f"  Turnover: ₹{balance['utilized_turnover']:.2f}")
    
    # Calculate utilization percentage
    if balance['total_net_value'] > 0:
        utilization = (balance['utilized_debits'] / balance['total_net_value']) * 100
        print(f"\n  Margin Utilized: {utilization:.2f}%")


# ============================================================================
# Example 8: Market Data and Historical Charts
# ============================================================================

def example_8_market_data(broker):
    """Example 8: Get market data and historical candles."""
    
    print("\n" + "="*70)
    print("EXAMPLE 8: Market Data & Historical Charts")
    print("="*70)
    
    symbols = ["SBIN-EQ", "INFY-EQ", "HDFCBANK-EQ"]
    
    # Get LTP for multiple symbols
    print("\n📈 Last Traded Prices:\n")
    
    for symbol in symbols:
        try:
            ltp = broker.get_ltp(symbol)
            print(f"  {symbol}: ₹{ltp:.2f}")
        except Exception as e:
            print(f"  {symbol}: Not available")
    
    # Get historical data
    print(f"\n📊 Historical Candle Data (SBIN-EQ, 15m):\n")
    
    try:
        data = broker.get_historical_data(
            symbol="SBIN-EQ",
            interval="15m",
            from_date=datetime.now().replace(hour=9, minute=15),  # Today 9:15 AM
            to_date=datetime.now()
        )
        
        print(f"  Retrieved {data['count']} candles\n")
        
        # Show last 5 candles
        for candle in data['candles'][-5:]:
            timestamp = candle[0]
            open_price = candle[1]
            high = candle[2]
            low = candle[3]
            close = candle[4]
            volume = candle[5]
            
            print(f"  {timestamp}")
            print(f"    O: {open_price:.2f}, H: {high:.2f}, L: {low:.2f}, C: {close:.2f}, V: {volume}")
    
    except Exception as e:
        print(f"  Failed to get historical data: {str(e)}")


# ============================================================================
# Example 9: Complete Trading Workflow
# ============================================================================

def example_9_complete_workflow():
    """Example 9: Complete trading workflow from start to finish."""
    
    print("\n" + "="*70)
    print("EXAMPLE 9: COMPLETE TRADING WORKFLOW")
    print("="*70)
    
    # Step 1: Connect
    print("\n[Step 1] Connecting to Angel One...")
    broker = create_angelone_broker()
    
    if not broker.is_connected():
        print("❌ Connection failed!")
        return
    
    print(f"✅ Connected as: {broker.user_id}")
    
    # Step 2: Check balance
    print("\n[Step 2] Checking account balance...")
    balance = broker.get_account_balance()
    print(f"   Available: ₹{balance['available_cash']:.2f}")
    
    # Step 3: Check existing positions
    print("\n[Step 3] Checking existing positions...")
    positions = broker.get_positions()
    print(f"   Open positions: {len(positions)}")
    
    # Step 4: Get market data
    print("\n[Step 4] Getting market data...")
    ltp = broker.get_ltp("SBIN-EQ")
    print(f"   SBIN-EQ LTP: ₹{ltp:.2f}")
    
    # Step 5: Place order
    print("\n[Step 5] Placing test order...")
    order = Order(
        symbol="SBIN-EQ",
        quantity=1,
        side="BUY",
        order_type="MARKET",
        product="MIS"
    )
    
    print("   ⚠️  This is a demo - actual order placement commented out")
    # response = broker.place_order(order)
    # print(f"   Order ID: {response['order_id']}")
    
    # Step 6: Verify position
    print("\n[Step 6] Verifying position...")
    positions = broker.get_positions()
    print(f"   Total positions: {len(positions)}")
    
    # Step 7: Disconnect
    print("\n[Step 7] Disconnecting...")
    broker.disconnect()
    print("   Disconnected")
    
    print("\n✅ Workflow complete!")


# ============================================================================
# Main Execution
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  ANGEL ONE SMARTAPI - EXAMPLE USAGE GUIDE")
    print("="*70)
    print("\nSelect an example to run:")
    print("\n  1. Basic Connection")
    print("  2. Market Order")
    print("  3. Limit Order")
    print("  4. Stop-Loss Order")
    print("  5. Manage Positions")
    print("  6. Order Management")
    print("  7. Account Balance")
    print("  8. Market Data")
    print("  9. Complete Workflow")
    print("  0. Exit")
    
    choice = input("\nEnter choice (0-9): ").strip()
    
    if choice == '1':
        example_1_basic_connection()
    
    elif choice == '2':
        broker = create_angelone_broker()
        example_2_market_order(broker)
    
    elif choice == '3':
        broker = create_angelone_broker()
        example_3_limit_order(broker)
    
    elif choice == '4':
        broker = create_angelone_broker()
        example_4_stop_loss_order(broker)
    
    elif choice == '5':
        broker = create_angelone_broker()
        example_5_manage_positions(broker)
    
    elif choice == '6':
        broker = create_angelone_broker()
        # Get first open order for demo
        orders = broker.get_open_orders()
        order_id = orders[0].order_id if orders else None
        example_6_order_management(broker, order_id)
    
    elif choice == '7':
        broker = create_angelone_broker()
        example_7_account_balance(broker)
    
    elif choice == '8':
        broker = create_angelone_broker()
        example_8_market_data(broker)
    
    elif choice == '9':
        example_9_complete_workflow()
    
    elif choice == '0':
        print("\nExiting...")
    
    else:
        print("\n❌ Invalid choice!")
    
    print("\n" + "="*70 + "\n")

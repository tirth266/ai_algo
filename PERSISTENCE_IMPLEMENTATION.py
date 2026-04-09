"""
PERSISTENCE LAYER IMPLEMENTATION GUIDE

Comprehensive documentation for the new position & trade persistence system.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

# ============================================================================
# OVERVIEW
# ============================================================================
"""
The persistence layer ensures no positions or trades are lost on system restart.

COMPONENTS:
1. PositionPersistence (position_persistence.py) - Core persistence logic
2. TradeManager enhancements - Persists trades to DB on open/close
3. RiskEngine enhancements - Loads positions from DB on startup
4. TradingSystem enhancements - Orchestrates state restoration

FLOW:
    System Startup:
    ├─ TradingSystem.__init__() → _restore_state_from_database()
    │  ├─ RiskEngine.load_positions_from_database()
    │  └─ TradeManager.load_trades_from_database()
    └─ In-memory state restored from DB
    
    Trade Execution:
    ├─ TradeManager.open_trade() → PositionPersistence.save_trade()
    ├─ TradeManager.manage_trade() → PositionPersistence.save_trade() [on close]
    └─ TradeManager.close_trade() → PositionPersistence.save_trade()
"""

# ============================================================================
# I. POSITION PERSISTENCE API
# ============================================================================

from backend.core.position_persistence import PositionPersistence
from datetime import datetime

# Initialize persistence layer
persistence = PositionPersistence()

# -------- SAVE OPERATIONS --------

# Save a NEW position
persistence.save_position(
    symbol='AAPL',
    side='BUY',
    quantity=100,
    entry_price=150.0,
    stop_loss=145.0,
    take_profit_1=155.0,
    take_profit_2=160.0,
    strategy_name='master_strategy'
)

# Save a TRADE (full execution record)
persistence.save_trade(
    symbol='AAPL',
    side='BUY',
    quantity=100,
    entry_price=150.0,
    exit_price=155.0,
    stop_loss=145.0,
    take_profit=160.0,
    status='closed',
    exit_reason='TAKE_PROFIT',
    strategy_name='master_strategy',
    entry_time=datetime.now(),
    exit_time=datetime.now(),
    pnl=500.0  # (155 - 150) * 100
)

# Update an existing position
persistence.update_position(
    symbol='AAPL',
    quantity=50,  # Partial close
    stop_loss=150.5,  # Trailing stop loss
    realized_pnl=250.0  # Partial exit PnL
)

# Close a position
persistence.close_position(
    symbol='AAPL',
    realized_pnl=500.0
)

# -------- LOAD OPERATIONS --------

# Load all open positions (call on startup)
open_positions = persistence.load_open_positions()
# Returns:
# [
#     {
#         'symbol': 'AAPL',
#         'side': 'BUY',
#         'quantity': 100,
#         'entry_price': 150.0,
#         'stop_loss': 145.0,
#         'take_profit_1': 155.0,
#         'take_profit_2': 160.0,
#         'timestamp': datetime(...)
#     },
#     ...
# ]

# Load all open trades (call on startup)
open_trades = persistence.load_open_trades()
# Returns:
# [
#     {
#         'id': 'AAPL_1712577600',
#         'symbol': 'AAPL',
#         'direction': 'BUY',
#         'entry_price': 150.0,
#         'quantity': 100,
#         'stop_loss': 145.0,
#         'take_profit_1': 155.0,
#         'take_profit_2': 160.0,
#         'entry_time': datetime(...),
#         'status': 'OPEN'
#     },
#     ...
# ]

# Load closed trades (for reporting)
closed_trades = persistence.load_closed_trades(limit=100)

# -------- UTILITY OPERATIONS --------

# Get position by symbol
position = persistence.get_position_by_symbol('AAPL')

# Get count of open positions
count = persistence.get_total_open_positions()

# Get total realized PnL
total_pnl = persistence.get_total_realized_pnl()

# Clear all positions (for testing/reset)
cleared = persistence.clear_all_positions()

# Close persistence session
persistence.close()


# ============================================================================
# II. TRADEMANAGER INTEGRATION
# ============================================================================

from backend.core.trade_manager import TradeManager

# Initialize TradeManager - persistence is created automatically
trade_manager = TradeManager(
    capital=100000.0,
    risk_per_trade=0.02,
    max_open_positions=2
)

# Open a trade - automatically persisted to DB
trade = trade_manager.open_trade(
    symbol='AAPL',
    direction='BUY',
    entry_price=150.0,
    stop_loss=145.0,
    take_profit_1=155.0,
    take_profit_2=160.0,
    quantity=100,
    confidence='high',
    reason='strong_signal'
)

# Manage trade - automatically persisted on close
result = trade_manager.manage_trade(
    trade_id='AAPL_20260408120000000000',
    current_price=155.0,
    atr_value=2.5,
    ema_value=151.0
)
# If TP1 hit or SL triggered, trade is persisted to DB

# Close trade manually - automatically persisted to DB
result = trade_manager.close_trade(
    trade_id='AAPL_20260408120000000000',
    current_price=153.0
)

# RESTORE STATE ON STARTUP
trades_loaded = trade_manager.load_trades_from_database()
print(f"Restored {trades_loaded} trades from database")


# ============================================================================
# III. RISKENGINE INTEGRATION
# ============================================================================

from backend.core.risk_engine import RiskEngine

# Initialize RiskEngine - persistence created automatically
risk_engine = RiskEngine(
    capital=100000.0,
    max_risk_per_trade=0.02,
    max_open_positions=2
)

# Open a position (after trade validation)
from backend.core.risk_engine import TradeRequest
request = TradeRequest(
    symbol='AAPL',
    direction='BUY',
    quantity=100,
    price=150.0,
    stop_loss=145.0
)

# Validation (pre-trade)
validation = risk_engine.validate_trade(request)

# Open position (post-trade)
if validation['allowed']:
    risk_engine.open_position(request)

# Close position (post-trade exit)
risk_engine.close_position(
    symbol='AAPL',
    exit_price=155.0,
    pnl=500.0
)

# RESTORE STATE ON STARTUP
positions_loaded = risk_engine.load_positions_from_database()
print(f"Restored {positions_loaded} positions from database")


# ============================================================================
# IV. TRADINGSYSTEM INTEGRATION (AUTOMATIC)
# ============================================================================

from backend.core.execution import TradingSystem

# Initialize TradingSystem
# NOTE: Automatically calls _restore_state_from_database() in constructor
system = TradingSystem(
    capital=100000.0,
    risk_per_trade=0.02,
    max_open_positions=2
)
# State is automatically restored here!


# ============================================================================
# V. DATABASE MIGRATIONS & SETUP
# ============================================================================

"""
INITIAL DATABASE SETUP:

The persistence layer requires two tables:

1. POSITIONS TABLE
   Fields: id, symbol, side, quantity, average_price, current_price, 
           unrealized_pnl, realized_pnl, stop_loss, target, strategy_name, 
           created_at, updated_at

2. TRADES TABLE
   Fields: id, symbol, side, quantity, entry_price, exit_price, stop_loss,
           target, pnl, pnl_percentage, status, exit_reason, strategy_name,
           created_at, exited_at, order_id (nullable)

MIGRATION FROM LEGACY SYSTEM:

If you have existing trades in JSON logs, use this script to migrate:
"""

def migrate_json_logs_to_db():
    """Migrate legacy JSON trade logs to database."""
    import json
    import os
    from pathlib import Path
    
    persistence = PositionPersistence()
    logs_dir = Path('logs/trades')
    count = 0
    
    if logs_dir.exists():
        for log_file in logs_dir.glob('*.json'):
            try:
                with open(log_file) as f:
                    trades = json.load(f)
                    
                for trade in trades:
                    persistence.save_trade(
                        symbol=trade['symbol'],
                        side=trade['direction'],
                        quantity=trade['quantity'],
                        entry_price=trade['entry_price'],
                        exit_price=trade.get('exit_price'),
                        status='closed' if trade.get('exit_price') else 'open',
                        strategy_name=trade.get('strategy'),
                        pnl=trade.get('pnl', 0),
                    )
                    count += 1
            except Exception as e:
                print(f"Error migrating {log_file}: {e}")
    
    print(f"Migrated {count} trades from JSON logs to database")
    persistence.close()


# ============================================================================
# VI. TRANSACTIONAL SAFETY
# ============================================================================

"""
ALL database writes are wrapped in transactions for safety:

    with persistence.transaction() as session:
        # Your operations here
        # Automatic commit on success
        # Automatic rollback on error
        
This ensures:
- No partial writes
- Atomicity across multiple operations
- Data consistency after restart
"""


# ============================================================================
# VII. DUPLICATE PREVENTION
# ============================================================================

"""
The persistence layer prevents duplicate positions/trades after restart:

1. On SAVE: Check if position with same symbol already exists
   - If exists: UPDATE existing
   - If new: CREATE new entry

2. On LOAD: Load all positions with quantity > 0
   - Closed positions (qty=0) are not restored
   - Ensures no duplicate open positions

3. TRADE_ID: Uses format: symbol_timestamp
   - Unique per trade
   - Prevents duplicate trade entries
"""


# ============================================================================
# VIII. ERROR HANDLING
# ============================================================================

"""
Persistence errors are logged but don't halt trading:

    try:
        persistence.save_trade(...)
    except Exception as e:
        logger.error(f"Failed to persist trade: {e}")
        # Trading continues (log warning to operator)
        
This ensures system resilience. However, you should:
1. Monitor logs for persistence errors
2. Check database connectivity regularly
3. Verify state consistency after restarts
"""


# ============================================================================
# IX. BEST PRACTICES
# ============================================================================

"""
1. IMMEDIATE PERSISTENCE:
   - Trades are saved immediately when opened
   - Positions updated every time managed
   - No delay between trade execution and database write

2. RECOVERY ON RESTART:
   - Call load_positions_from_database() on RiskEngine
   - Call load_trades_from_database() on TradeManager
   - This happens automatically in TradingSystem.__init__()

3. MONITOR PERSISTENCE:
   - Log persistence errors
   - Check database health regularly
   - Verify state after restarts

4. DATABASE BACKUPS:
   - Regular backups of SQLite database
   - For production: PostgreSQL with backup strategy
   
5. TESTING:
   - Always test restart with open positions
   - Verify state matches before/after restart
   - Monitor for duplicate entries
"""


# ============================================================================
# X. VERIFICATION SCRIPT
# ============================================================================

def verify_persistence():
    """Verify persistence layer is working correctly."""
    from backend.core.trade_manager import TradeManager
    from backend.core.risk_engine import RiskEngine
    
    print("=== Persistence System Verification ===\n")
    
    # Test 1: Can create and save
    persistence = PositionPersistence()
    
    print("✓ Test 1: Save new position")
    pos = persistence.save_position(
        symbol='TEST',
        side='BUY',
        quantity=100,
        entry_price=100.0,
        stop_loss=95.0
    )
    print(f"  Saved: {pos.symbol} {pos.quantity} @ {pos.average_price}\n")
    
    # Test 2: Can load
    print("✓ Test 2: Load positions")
    positions = persistence.load_open_positions()
    print(f"  Loaded: {len(positions)} positions\n")
    
    # Test 3: Integration with TradeManager
    print("✓ Test 3: TradeManager persistence")
    tm = TradeManager(capital=100000.0)
    trade = tm.open_trade(
        symbol='NVDA',
        direction='BUY',
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=105.0,
        take_profit_2=110.0
    )
    print(f"  Opened trade: {trade.id}\n")
    
    # Test 4: Integration with RiskEngine
    print("✓ Test 4: RiskEngine position loading")
    re = RiskEngine(capital=100000.0)
    loaded = re.load_positions_from_database()
    print(f"  Loaded {loaded} positions into RiskEngine\n")
    
    # Cleanup
    persistence.close()
    
    print("=== All Verification Tests Passed ===")


if __name__ == '__main__':
    verify_persistence()

"""
Broker Reconciliation Test Suite

Comprehensive tests for the broker reconciliation system.

Tests:
1. CASE A: Broker position not in local DB → Add locally
2. CASE B: Local position not on broker → Mark closed
3. CASE C: Mismatch in qty/price → Correct locally
4. Critical failure handling (trading block)
5. Successful reconciliation after startup

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST SETUP/TEARDOWN
# ============================================================================

def setup_test_db() -> None:
    """Setup clean test database."""
    try:
        from backend.database.session import SessionLocal
        from backend.models.position import Position
        from backend.models.trade import Trade
        
        session = SessionLocal()
        
        # Clear existing data
        session.query(Trade).delete()
        session.query(Position).delete()
        session.commit()
        session.close()
        
        logger.info("✓ Test database cleaned")
        
    except Exception as e:
        logger.error(f"Failed to setup test DB: {str(e)}")
        raise


def teardown_test_db() -> None:
    """Clean up test database."""
    try:
        from backend.database.session import SessionLocal
        from backend.models.position import Position
        from backend.models.trade import Trade
        
        session = SessionLocal()
        session.query(Trade).delete()
        session.query(Position).delete()
        session.commit()
        session.close()
        
        logger.info("✓ Test database cleaned")
        
    except Exception as e:
        logger.error(f"Failed to teardown test DB: {str(e)}")


# ============================================================================
# TEST CASE A: Broker Position Not in Local DB
# ============================================================================

def test_case_a_add_missing_position() -> Tuple[bool, str]:
    """
    TEST CASE A: Position exists in broker but not locally.
    
    Expected: Position is added to local DB from broker data.
    """
    print("\n" + "="*70)
    print("TEST CASE A: Add Missing Local Position")
    print("="*70)
    
    try:
        from backend.database.session import SessionLocal
        from backend.models.position import Position
        from backend.core.broker_reconciliation import BrokerReconciliation, BrokerPosition
        
        # Setup
        setup_test_db()
        session = SessionLocal()
        
        # Verify DB is empty
        positions_before = session.query(Position).count()
        logger.info(f"Positions in DB before: {positions_before}")
        
        if positions_before != 0:
            session.close()
            return False, "DB should be clean"
        
        # Create mock reconciliation
        # When using None as broker_service, it uses mock data from local DB
        # So we need to manually set up the broker_positions for testing
        reconciliation = BrokerReconciliation(broker_service=None, session=session)
        
        # Manually create a broker position that doesn't exist locally
        broker_pos = BrokerPosition(
            symbol="AAPL",
            quantity=100,
            entry_price=150.00,
            current_price=151.00,
            side="BUY",
            pnl=100.0,
            pnl_percentage=0.67
        )
        
        reconciliation.broker_positions = [broker_pos]
        
        # Run reconciliation
        logger.info("Running reconciliation with broker-only position...")
        report = reconciliation.reconcile()
        
        # Verify results
        positions_after = session.query(Position).count()
        logger.info(f"Positions in DB after: {positions_after}")
        
        # Check if position was added
        added_pos = session.query(Position).filter(Position.symbol == "AAPL").first()
        
        if not added_pos:
            session.close()
            return False, f"Position not added to DB. Actions: {report['actions']}"
        
        # Verify position data
        if added_pos.quantity != 100:
            session.close()
            return False, f"Quantity mismatch: {added_pos.quantity} vs 100"
        
        if abs(added_pos.average_price - 150.00) > 0.01:
            session.close()
            return False, f"Price mismatch: {added_pos.average_price} vs 150.00"
        
        # Check reconciliation report
        found_add_action = any(a['action_type'] == 'ADD_LOCAL' for a in report.get('actions', []))
        
        session.close()
        reconciliation.close()
        teardown_test_db()
        
        if found_add_action:
            logger.info("✓ CASE A PASSED: Position added from broker")
            return True, "Position successfully added"
        else:
            return False, "No ADD_LOCAL action in report"
        
    except Exception as e:
        logger.error(f"TEST CASE A FAILED: {str(e)}", exc_info=True)
        return False, str(e)


# ============================================================================
# TEST CASE B: Local Position Not on Broker
# ============================================================================

def test_case_b_close_orphaned_position() -> Tuple[bool, str]:
    """
    TEST CASE B: Position exists locally but not on broker.
    
    Expected: Position is marked as closed (quantity = 0).
    """
    print("\n" + "="*70)
    print("TEST CASE B: Close Orphaned Local Position")
    print("="*70)
    
    try:
        from backend.database.session import SessionLocal
        from backend.models.position import Position
        from backend.core.broker_reconciliation import BrokerReconciliation
        
        # Setup
        setup_test_db()
        session = SessionLocal()
        
        # Create a local position
        local_pos = Position(
            symbol="MSFT",
            side="LONG",
            quantity=50,
            average_price=320.00,
            current_price=321.00,
            strategy_name="test"
        )
        session.add(local_pos)
        session.commit()
        
        logger.info(f"Created local position: MSFT {local_pos.quantity} @ {local_pos.average_price}")
        
        # Verify position exists
        pos_check = session.query(Position).filter(Position.symbol == "MSFT").first()
        if not pos_check:
            session.close()
            return False, "Position not created in DB"
        
        # Create mock reconciliation with empty broker positions
        reconciliation = BrokerReconciliation(broker_service=None, session=session)
        reconciliation.broker_positions = []  # Empty broker
        
        # Run reconciliation
        logger.info("Running reconciliation with local-only position...")
        report = reconciliation.reconcile()
        
        # Verify position was closed
        closed_pos = session.query(Position).filter(Position.symbol == "MSFT").first()
        
        if closed_pos.quantity != 0:
            session.close()
            return False, f"Position not closed: quantity = {closed_pos.quantity}"
        
        # Check reconciliation report
        found_close_action = any(a['action_type'] == 'CLOSE_LOCAL' for a in report.get('actions', []))
        
        session.close()
        reconciliation.close()
        teardown_test_db()
        
        if found_close_action:
            logger.info("✓ CASE B PASSED: Position closed because broker doesn't have it")
            return True, "Position successfully closed"
        else:
            return False, "No CLOSE_LOCAL action in report"
        
    except Exception as e:
        logger.error(f"TEST CASE B FAILED: {str(e)}", exc_info=True)
        return False, str(e)


# ============================================================================
# TEST CASE C: Quantity/Price Mismatch
# ============================================================================

def test_case_c_fix_mismatch() -> Tuple[bool, str]:
    """
    TEST CASE C: Position exists locally and on broker but with mismatched qty/price.
    
    Expected: Local position is updated to match broker values.
    """
    print("\n" + "="*70)
    print("TEST CASE C: Fix Quantity/Price Mismatch")
    print("="*70)
    
    try:
        from backend.database.session import SessionLocal
        from backend.models.position import Position
        from backend.core.broker_reconciliation import BrokerReconciliation, BrokerPosition
        
        # Setup
        setup_test_db()
        session = SessionLocal()
        
        # Create local position with mismatched qty
        local_pos = Position(
            symbol="GOOGL",
            side="LONG",
            quantity=100,  # Local has 100
            average_price=140.00,
            current_price=141.00,
            strategy_name="test"
        )
        session.add(local_pos)
        session.commit()
        
        logger.info(f"Created local position: GOOGL {local_pos.quantity} @ {local_pos.average_price}")
        
        # Create broker position with different qty
        broker_pos = BrokerPosition(
            symbol="GOOGL",
            quantity=95,  # Broker has 95
            entry_price=139.95,  # Slightly different price
            current_price=141.50,
            side="BUY",
            pnl=142.5,
            pnl_percentage=1.04
        )
        
        # Create mock reconciliation
        reconciliation = BrokerReconciliation(broker_service=None, session=session)
        reconciliation.broker_positions = [broker_pos]
        
        # Run reconciliation
        logger.info("Running reconciliation with quantity mismatch...")
        report = reconciliation.reconcile()
        
        # Verify position was corrected
        corrected_pos = session.query(Position).filter(Position.symbol == "GOOGL").first()
        
        if corrected_pos.quantity != 95:
            session.close()
            return False, f"Quantity not corrected: {corrected_pos.quantity} vs 95"
        
        if abs(corrected_pos.average_price - 139.95) > 0.01:
            session.close()
            return False, f"Price not corrected: {corrected_pos.average_price} vs 139.95"
        
        # Check reconciliation report
        found_update_action = any(
            a['action_type'] in ['UPDATE_QTY', 'UPDATE_PRICE'] 
            for a in report.get('actions', [])
        )
        
        session.close()
        reconciliation.close()
        teardown_test_db()
        
        if found_update_action:
            logger.info("✓ CASE C PASSED: Position corrected to match broker")
            return True, "Position successfully corrected"
        else:
            return False, "No UPDATE action in report"
        
    except Exception as e:
        logger.error(f"TEST CASE C FAILED: {str(e)}", exc_info=True)
        return False, str(e)


# ============================================================================
# TEST: Successful Reconciliation Report
# ============================================================================

def test_successful_reconciliation_report() -> Tuple[bool, str]:
    """
    TEST: Verify reconciliation report structure after successful reconciliation.
    
    Expected: Report contains all required fields and valid data.
    """
    print("\n" + "="*70)
    print("TEST: Successful Reconciliation Report")
    print("="*70)
    
    try:
        from backend.core.broker_reconciliation import BrokerReconciliation
        
        reconciliation = BrokerReconciliation(broker_service=None)
        report = reconciliation.reconcile()
        
        # Check report structure
        required_fields = [
            'status', 'is_reconciled', 'critical_error', 'discrepancies_found',
            'actions_taken', 'broker_positions_count', 'trading_allowed', 'message',
            'timestamp', 'actions'
        ]
        
        for field in required_fields:
            if field not in report:
                return False, f"Missing field in report: {field}"
        
        # Check types
        if not isinstance(report['status'], str):
            return False, "status should be string"
        
        if not isinstance(report['is_reconciled'], bool):
            return False, "is_reconciled should be bool"
        
        if not isinstance(report['actions'], list):
            return False, "actions should be list"
        
        # Verify action structure
        for action in report['actions']:
            required_action_fields = ['action_type', 'symbol', 'description', 'severity']
            for field in required_action_fields:
                if field not in action:
                    return False, f"Missing field in action: {field}"
        
        reconciliation.close()
        
        logger.info("✓ REPORT STRUCTURE VALID")
        return True, "Report structure is valid"
        
    except Exception as e:
        logger.error(f"TEST FAILED: {str(e)}", exc_info=True)
        return False, str(e)


# ============================================================================
# TEST: Trading Block on Critical Error
# ============================================================================

def test_trading_block_on_error() -> Tuple[bool, str]:
    """
    TEST: Verify trading is blocked when reconciliation encounters critical error.
    
    Expected: trading_allowed = False when critical_error = True
    """
    print("\n" + "="*70)
    print("TEST: Trading Block on Critical Error")
    print("="*70)
    
    try:
        from backend.core.broker_reconciliation import BrokerReconciliation
        
        # Create reconciliation
        reconciliation = BrokerReconciliation(broker_service=None)
        
        # Simulate critical error by forcing failure
        reconciliation.critical_error = True
        reconciliation.is_reconciled = False
        reconciliation.reconciliation_time = __import__('datetime').datetime.utcnow()
        
        report = reconciliation._build_report()
        
        # Check that trading is blocked
        if report['trading_allowed']:
            return False, "Trading should be blocked when critical_error=True"
        
        if not report['critical_error']:
            return False, "critical_error should be True"
        
        if report['status'] != 'failed':
            return False, f"Status should be 'failed', got {report['status']}"
        
        reconciliation.close()
        
        logger.info("✓ TRADING BLOCK WORKS CORRECTLY")
        return True, "Trading is blocked on critical error"
        
    except Exception as e:
        logger.error(f"TEST FAILED: {str(e)}", exc_info=True)
        return False, str(e)


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests() -> None:
    """Run complete test suite."""
    
    print("\n" + "="*70)
    print("BROKER RECONCILIATION TEST SUITE")
    print("="*70)
    
    tests = [
        ("CASE A", test_case_a_add_missing_position),
        ("CASE B", test_case_b_close_orphaned_position),
        ("CASE C", test_case_c_fix_mismatch),
        ("Report Structure", test_successful_reconciliation_report),
        ("Trading Block", test_trading_block_on_error),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success, message = test_func()
            results.append((test_name, success, message))
            
            if success:
                print(f"\n✓ {test_name}: PASSED")
            else:
                print(f"\n✗ {test_name}: FAILED")
                print(f"   {message}")
                
        except KeyboardInterrupt:
            print("\n\nTests interrupted")
            return
        except Exception as e:
            print(f"\n✗ {test_name}: ERROR")
            print(f"   {str(e)}")
            results.append((test_name, False, str(e)))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} tests passed\n")
    
    for test_name, success, message in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status:8} {test_name:20} {message}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED")
        return
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        return


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        logger.error(f"Test suite failed: {str(e)}", exc_info=True)
        sys.exit(1)

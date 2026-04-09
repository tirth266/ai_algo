"""
Broker Reconciliation Examples

Demonstrates typical usage patterns for the broker reconciliation system.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import sys
import json
from typing import Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: Automatic Reconciliation on Startup
# ============================================================================

def example_1_automatic_reconciliation():
    """
    Example 1: Automatic reconciliation on TradingSystem startup.
    
    This is the normal use case - reconciliation happens automatically
    when the system initializes.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Automatic Reconciliation on Startup")
    print("="*70 + "\n")
    
    try:
        from backend.core.execution import TradingSystem
        
        logger.info("Initializing TradingSystem...")
        
        system = TradingSystem(
            capital=100000.0,
            risk_per_trade=0.02,
            max_open_positions=5
        )
        
        # After initialization, reconciliation has run
        logger.info(f"Trading allowed: {system.trading_allowed}")
        logger.info(f"Reconciliation status: {system.reconciliation_status}")
        
        if system.trading_allowed:
            print("✓ Trading is enabled - reconciliation successful")
        else:
            print("✗ Trading is blocked - reconciliation failed")
            print(f"  Reason: {system.reconciliation_status.get('message')}")
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 2: Manual Reconciliation via REST API
# ============================================================================

def example_2_manual_reconciliation_via_api():
    """
    Example 2: Trigger reconciliation manually via REST API.
    
    Useful for:
    - Testing reconciliation on demand
    - Re-syncing after broker connection issues
    - Scheduled reconciliation
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Manual Reconciliation via REST API")
    print("="*70 + "\n")
    
    try:
        import requests
        
        api_base = "http://localhost:7000"
        
        # Trigger reconciliation
        logger.info("Sending POST /api/reconcile...")
        response = requests.post(f"{api_base}/api/reconcile", timeout=30)
        
        if response.status_code == 200:
            report = response.json()
            
            print_reconciliation_report(report)
            
            # Check if trading is allowed
            if report.get('trading_allowed'):
                print("\n✓ Trading is ALLOWED")
            else:
                print("\n✗ Trading is BLOCKED")
                
        else:
            logger.error(f"API error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 3: Check Reconciliation Status
# ============================================================================

def example_3_check_status():
    """
    Example 3: Query current reconciliation status.
    
    Useful for:
    - Monitoring system health
    - Checking if trading is allowed
    - Getting reconciliation statistics
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Check Reconciliation Status")
    print("="*70 + "\n")
    
    try:
        import requests
        
        api_base = "http://localhost:7000"
        
        logger.info("Sending GET /api/reconcile/status...")
        response = requests.get(f"{api_base}/api/reconcile/status", timeout=10)
        
        if response.status_code == 200:
            status = response.json()
            
            print("\nReconciliation Status:")
            print(f"  Reconciled: {status['is_reconciled']}")
            print(f"  Critical Error: {status['critical_error']}")
            print(f"  Discrepancies Found: {status['discrepancies_found']}")
            print(f"  Trading Allowed: {status['trading_allowed']}")
            print(f"  Actions Count: {status['actions_count']}")
            
            if status.get('reconciliation_time'):
                print(f"  Last Reconciliation: {status['reconciliation_time']}")
        else:
            logger.error(f"API error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 4: Review Reconciliation Actions
# ============================================================================

def example_4_review_actions():
    """
    Example 4: Review reconciliation actions with filtering.
    
    Useful for:
    - Understanding what corrections were made
    - Debugging reconciliation issues
    - Auditing position changes
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Review Reconciliation Actions")
    print("="*70 + "\n")
    
    try:
        import requests
        
        api_base = "http://localhost:7000"
        
        # Get all actions
        logger.info("Fetching all reconciliation actions...")
        response = requests.get(
            f"{api_base}/api/reconcile/actions",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\nTotal Actions: {data['total_count']}")
            print("\nRecent Actions:")
            
            for i, action in enumerate(data['actions'], 1):
                print(f"\n  {i}. {action['action_type']}: {action['symbol']}")
                print(f"     Description: {action['description']}")
                print(f"     Severity: {action['severity']}")
        
        # Get filtered actions (warnings only)
        logger.info("Fetching warning-level actions...")
        response = requests.get(
            f"{api_base}/api/reconcile/actions?severity=warning",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nWarning Actions: {data['filtered_count']}")
            
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 5: Handle Trading Block
# ============================================================================

def example_5_handle_trading_block():
    """
    Example 5: Handle and recover from trading block.
    
    Useful for:
    - Operations responding to trading blocks
    - Implementing retry logic
    - Manual intervention procedures
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Handle Trading Block (Fail-Safe)")
    print("="*70 + "\n")
    
    try:
        import requests
        
        api_base = "http://localhost:7000"
        
        # Check status
        logger.info("Checking reconciliation status...")
        response = requests.get(
            f"{api_base}/api/reconcile/status",
            timeout=10
        )
        
        if response.status_code == 200:
            status = response.json()
            
            if not status['trading_allowed']:
                print("\n⚠️  TRADING IS BLOCKED\n")
                
                # Get error details
                logger.info("Fetching error details...")
                response = requests.get(
                    f"{api_base}/api/reconcile/actions?severity=error",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    print("Error Actions:")
                    for action in data['actions']:
                        print(f"  - {action['symbol']}: {action['description']}")
                
                # Suggest recovery
                print("\n📋 Recovery Steps:")
                print("  1. Review error details above")
                print("  2. Fix the underlying issue (e.g., broker connection)")
                print("  3. Retry reconciliation: curl -X POST /api/reconcile")
                print("  4. Verify: curl -X GET /api/reconcile/status")
                
            else:
                print("\n✓ Trading is ALLOWED")
                
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 6: Programmatic Reconciliation
# ============================================================================

def example_6_programmatic_reconciliation():
    """
    Example 6: Direct Python usage of BrokerReconciliation class.
    
    Useful for:
    - Custom integration
    - Scheduled reconciliation scripts
    - Batch operations
    """
    print("\n" + "="*70)
    print("EXAMPLE 6: Programmatic Reconciliation (Direct Class Usage)")
    print("="*70 + "\n")
    
    try:
        from backend.core.broker_reconciliation import BrokerReconciliation
        from backend.services.angelone_service import AngelOneService
        
        logger.info("Initializing broker service...")
        broker_service = AngelOneService()
        
        logger.info("Creating BrokerReconciliation instance...")
        with BrokerReconciliation(broker_service=broker_service) as reconciliation:
            
            logger.info("Running reconciliation...")
            report = reconciliation.reconcile()
            
            print("\nReconciliation Report:")
            print(f"  Status: {report['status']}")
            print(f"  Trading Allowed: {report['trading_allowed']}")
            print(f"  Actions Taken: {report['actions_taken']}")
            print(f"  Discrepancies Found: {report['discrepancies_found']}")
            
            # Print actions
            print("\nActions:")
            for action in report.get('actions', []):
                symbol = action['symbol']
                action_type = action['action_type']
                desc = action['description']
                severity = action['severity']
                
                print(f"  [{severity.upper():7}] {action_type:15} {symbol:6} {desc}")
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# EXAMPLE 7: Mock Broker Reconciliation (Testing)
# ============================================================================

def example_7_mock_reconciliation():
    """
    Example 7: Reconciliation with mock broker (no real broker needed).
    
    Useful for:
    - Testing + demo environments
    - CI/CD pipelines
    - Development without broker connection
    """
    print("\n" + "="*70)
    print("EXAMPLE 7: Mock Broker Reconciliation (Testing)")
    print("="*70 + "\n")
    
    try:
        from backend.core.broker_reconciliation import BrokerReconciliation
        
        logger.info("Creating mock reconciliation (no broker service)...")
        
        # Initialize without broker service → uses mock data
        with BrokerReconciliation(broker_service=None) as reconciliation:
            
            logger.info("Running mock reconciliation...")
            report = reconciliation.reconcile()
            
            print("\nMock Reconciliation Report:")
            print(f"  Status: {report['status']}")
            print(f"  Message: {report['message']}")
            print(f"  Broker Positions: {report['broker_positions_count']}")
            print(f"  Actions: {report['actions_taken']}")
            
            if report.get('discrepancies_found'):
                print("\nDiscrepancies Found:")
                for action in report.get('actions', []):
                    if action['severity'] in ['warning', 'error']:
                        print(f"  - {action['symbol']}: {action['description']}")
            
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_reconciliation_report(report: Dict[str, Any]) -> None:
    """Pretty-print a reconciliation report."""
    
    print("\n" + "="*70)
    print("RECONCILIATION REPORT")
    print("="*70 + "\n")
    
    print("Summary:")
    print(f"  Status: {report['status']}")
    print(f"  Trading Allowed: {report['trading_allowed']}")
    print(f"  Timestamp: {report.get('timestamp', 'N/A')}")
    print(f"  Reconciled: {report['is_reconciled']}")
    print(f"  Critical Error: {report['critical_error']}")
    print(f"  Discrepancies Found: {report['discrepancies_found']}")
    
    print(f"\nCounts:")
    print(f"  Broker Positions: {report['broker_positions_count']}")
    print(f"  Actions Taken: {report['actions_taken']}")
    
    print(f"\nMessage: {report['message']}")
    
    if report.get('actions'):
        print(f"\nActions Performed ({len(report['actions'])}):")
        
        for i, action in enumerate(report['actions'], 1):
            action_type = action['action_type']
            symbol = action['symbol']
            severity = action['severity']
            description = action['description']
            
            severity_symbol = {
                'info': 'ℹ️ ',
                'warning': '⚠️ ',
                'error': '✗ '
            }.get(severity, '• ')
            
            print(f"  {i}. {severity_symbol} [{action_type:15}] {symbol:6} {description}")
            
            if action.get('before_state'):
                print(f"     Before: {action['before_state']}")
            if action.get('after_state'):
                print(f"     After:  {action['after_state']}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("BROKER RECONCILIATION EXAMPLES")
    print("="*70)
    print("\nSelect example to run:")
    print("  1. Automatic reconciliation on startup")
    print("  2. Manual reconciliation via REST API")
    print("  3. Check reconciliation status")
    print("  4. Review reconciliation actions")
    print("  5. Handle trading block (fail-safe)")
    print("  6. Programmatic reconciliation (direct class)")
    print("  7. Mock broker reconciliation (testing)")
    print("  9. Run all examples")
    
    try:
        choice = input("\nEnter choice (1-9): ").strip()
        
        if choice == "1":
            example_1_automatic_reconciliation()
        elif choice == "2":
            example_2_manual_reconciliation_via_api()
        elif choice == "3":
            example_3_check_status()
        elif choice == "4":
            example_4_review_actions()
        elif choice == "5":
            example_5_handle_trading_block()
        elif choice == "6":
            example_6_programmatic_reconciliation()
        elif choice == "7":
            example_7_mock_reconciliation()
        elif choice == "9":
            example_1_automatic_reconciliation()
            example_6_programmatic_reconciliation()
            example_7_mock_reconciliation()
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\n\nExamples interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        sys.exit(1)

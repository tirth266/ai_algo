"""
Broker Reconciliation Routes

Endpoints for reconciling system state with broker positions.

Endpoints:
- POST /api/reconcile - Trigger broker reconciliation
- GET /api/reconcile/status - Get current reconciliation status
- GET /api/reconcile/actions - Get recent reconciliation actions

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

logger = logging.getLogger(__name__)

reconciliation_router = APIRouter(prefix='/api/reconcile')

# Global reconciliation state
_reconciliation = None


async def get_reconciliation(request: Request):
    """Get or initialize global reconciliation instance."""
    global _reconciliation
    if _reconciliation is None:
        try:
            from .core.broker_reconciliation import BrokerReconciliation
            from .services.angelone_service import AngelOneService
            
            broker_service = AngelOneService()
            _reconciliation = BrokerReconciliation(broker_service=broker_service)
            logger.info("BrokerReconciliation initialized")
        except Exception as e:
            logger.error(f"Failed to initialize BrokerReconciliation: {str(e)}")
            return None
    
    return _reconciliation


@reconciliation_router.post('')
async def start_reconciliation(request: Request):
    """
    Trigger broker reconciliation.
    
    Performs full reconciliation:
    1. Fetch positions from broker
    2. Load local positions
    3. Compare and sync discrepancies
    4. Return detailed report
    
    Returns:
        JSON with reconciliation status and actions
        
    Response:
        {
            "status": "success|failed",
            "is_reconciled": bool,
            "critical_error": bool,
            "discrepancies_found": bool,
            "actions_taken": int,
            "trading_allowed": bool,
            "message": str,
            "actions": [
                {
                    "action_type": "ADD_LOCAL|CLOSE_LOCAL|UPDATE_PRICE|UPDATE_QTY|ERROR|INFO",
                    "symbol": str,
                    "description": str,
                    "severity": "info|warning|error",
                    "before_state": dict or null,
                    "after_state": dict or null
                }
            ]
        }
    """
    try:
        logger.info("Received POST /api/reconcile request")
        
        reconciliation = get_reconciliation()
        if not reconciliation:
            return {
                'status': 'error',
                'message': 'Reconciliation service not available',
                'trading_allowed': False
            }
        # Run reconciliation
        logger.info("Starting reconciliation process...")
        report = reconciliation.reconcile()
        
        logger.info(f"Reconciliation complete: {report['status']}")
        logger.info(f"Trading allowed: {report['trading_allowed']}")
        
        return report
        
    except Exception as e:
        logger.error(f"Reconciliation error: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Reconciliation failed: {str(e)}',
            'trading_allowed': False,
            'error_details': str(e)
        }


@reconciliation_router.get('/status')
async def get_status(request: Request):
    """
    Get current reconciliation status.
    
    Returns:
        JSON with reconciliation status
        
    Response:
        {
            "is_reconciled": bool,
            "critical_error": bool,
            "discrepancies_found": bool,
            "reconciliation_time": str (ISO format) or null,
            "trading_allowed": bool,
            "actions_count": int
        }
    """
    try:
        logger.info("Received GET /api/reconcile/status request")
        
        reconciliation = get_reconciliation()
        if not reconciliation:
            return {
                'is_reconciled': False,
                'critical_error': True,
                'trading_allowed': False,
                'message': 'Reconciliation service not available'
            }
        status = reconciliation.get_reconciliation_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting reconciliation status: {str(e)}")
        return {
            'is_reconciled': False,
            'critical_error': True,
            'trading_allowed': False,
            'message': str(e)
        }


@reconciliation_router.get('/actions')
async def get_actions(request: Request):
    """
    Get recent reconciliation actions.
    
    Query Parameters:
        action_type: Filter by action type (optional)
        symbol: Filter by symbol (optional)
        severity: Filter by severity - info|warning|error (optional)
    
    Returns:
        JSON with list of recent reconciliation actions
        
    Response:
        {
            "actions": [
                {
                    "action_type": str,
                    "symbol": str,
                    "description": str,
                    "severity": str,
                    "before_state": dict or null,
                    "after_state": dict or null
                }
            ],
            "total_count": int,
            "filtered_count": int
        }
    """
    try:
        logger.info("Received GET /api/reconcile/actions request")
        
        reconciliation = get_reconciliation()
        if not reconciliation:
            return {
                'actions': [],
                'total_count': 0,
                'filtered_count': 0,
                'message': 'Reconciliation service not available'
            }
        # Get filter parameters
        action_type = request.query_params.get('action_type', None)
        symbol = request.query_params.get('symbol', None)
        severity = request.query_params.get('severity', None)
        
        # Filter actions
        filtered_actions = reconciliation.actions
        
        if action_type:
            filtered_actions = [a for a in filtered_actions if a.action_type == action_type]
        
        if symbol:
            filtered_actions = [a for a in filtered_actions if a.symbol == symbol]
        
        if severity:
            filtered_actions = [a for a in filtered_actions if a.severity == severity]
        
        # Convert to dict format
        from dataclasses import asdict
        actions_dict = [asdict(action) for action in filtered_actions]
        
        return {
            'actions': actions_dict,
            'total_count': len(reconciliation.actions),
            'filtered_count': len(filtered_actions)
        }
        
    except Exception as e:
        logger.error(f"Error getting reconciliation actions: {str(e)}")
        return {
            'actions': [],
            'total_count': 0,
            'filtered_count': 0,
            'message': str(e)
        }


@reconciliation_router.get('/health')
async def health(request: Request):
    """
    Check reconciliation service health.
    
    Returns:
        JSON with health status
    """
    try:
        reconciliation = get_reconciliation()
        
        return {
            'status': 'healthy' if reconciliation else 'unavailable',
            'trading_allowed': reconciliation.is_reconciled if reconciliation else False
        }
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

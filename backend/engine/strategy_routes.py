"""
Strategy Routes Module

Flask API endpoints for strategy management.
Allows frontend to register, start, stop, and monitor strategies.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging

from .strategy_manager import StrategyManager
from .market_data_service import MarketDataService

logger = logging.getLogger(__name__)

# Create blueprint for strategy routes
strategy_bp = Blueprint('strategy', __name__, url_prefix='/api')

# Global references to engine components (set during app initialization)
_strategy_manager: StrategyManager = None
_market_data_service: MarketDataService = None
_execution_loop = None


def initialize_strategy_engine():
    """
    Initialize the strategy execution engine.
    
    Called once during Flask app startup.
    Creates instances of all engine components.
    """
    global _strategy_manager, _market_data_service, _execution_loop
    
    # Create market data service
    _market_data_service = MarketDataService()
    
    # Create strategy manager
    _strategy_manager = StrategyManager(_market_data_service)
    
    # Initialize strategy registry (ensures default strategies are available)
    from services.strategy_registry import initialize_registry
    initialize_registry()
    
    logger.info("Strategy engine initialized")


def get_strategy_manager() -> StrategyManager:
    """Get the strategy manager instance."""
    return _strategy_manager


def get_market_data_service() -> MarketDataService:
    """Get the market data service instance."""
    return _market_data_service


@strategy_bp.route('/strategy/register', methods=['POST'])
def register_strategy():
    """
    Register a new strategy.
    
    Request Body:
        {
            "name": "My Strategy",
            "symbol": "NIFTY50",
            "timeframe": "5minute",
            "strategy_key": "rsi_macd"  (optional — picks class from STRATEGY_CLASS_MAP)
        }
    
    Response:
        {
            "strategy_id": "STRAT-XXXXXXXX",
            "status": "registered"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'symbol']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get strategy parameters
        name = data['name']
        symbol = data['symbol']
        timeframe = data.get('timeframe', '5minute')
        strategy_key = data.get('strategy_key', '')
        
        # Create configuration
        config = {
            'name': name,
            'symbol': symbol.upper(),
            'timeframe': timeframe
        }
        
        # Resolve strategy class dynamically
        strategy_class = None
        
        if strategy_key:
            from services.strategy_registry import get_strategy_class
            strategy_class = get_strategy_class(strategy_key)
        
        if strategy_class is None:
            return jsonify({'error': 'Strategy class not found'}), 400
        
        # Register the strategy
        strategy_id = _strategy_manager.register_strategy(
            strategy_class,
            config
        )
        
        # Also register in the strategy registry (for the /api/strategies list)
        from services.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        registry.register_strategy({
            'strategy_id': strategy_id,
            'name': name,
            'symbol': symbol.upper(),
            'timeframe': timeframe,
            'status': 'registered',
            'strategy_key': strategy_key or 'example',
        })
        
        logger.info(f"Strategy registered: {strategy_id} - {name} (class: {strategy_class.__name__})")
        
        return jsonify({
            'strategy_id': strategy_id,
            'status': 'registered',
            'message': f'Strategy "{name}" registered successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error registering strategy: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategy/start', methods=['POST'])
def start_strategy():
    """
    Start a registered strategy with broker connection check.
    
    Request Body:
        {
            "strategy_id": "STRAT-XXXXXXXX",
            "symbol": "RELIANCE",
            "timeframe": "5minute"
        }
    
    Response:
        {
            "status": "running",
            "message": "Strategy started successfully"
        }
    """
    try:
        data = request.get_json()
        
        # DEBUG: Log everything coming in
        print("\n" + "="*70)
        print("DEBUG: Received Strategy Start Request")
        print("="*70)
        print(f"DEBUG: Full payload: {data}")
        print(f"DEBUG: strategy_id: {data.get('strategy_id') if data else 'NO DATA'}")
        print(f"DEBUG: symbol: {data.get('symbol') if data else 'NOT PROVIDED'}")
        print(f"DEBUG: timeframe: {data.get('timeframe') if data else 'NOT PROVIDED'}")
        print("="*70 + "\n")
        
        if not data:
            logger.error("No JSON data received in request")
            return jsonify({
                'error': 'No data provided',
                'received': None,
                'help': 'Request body must be JSON with strategy_id, symbol, and timeframe'
            }), 400
        
        # Validate required fields
        strategy_id = data.get('strategy_id')
        symbol = data.get('symbol')
        timeframe = data.get('timeframe', '5minute')
        
        missing_fields = []
        if not strategy_id:
            missing_fields.append('strategy_id')
        if not symbol:
            missing_fields.append('symbol')
        
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({
                'error': 'Missing Required Fields',
                'received': data,
                'missing_fields': missing_fields,
                'help': f'Request must include: strategy_id, symbol (and optionally timeframe)'
            }), 400
        
        # CRITICAL: Check broker connection first
        from flask import current_app
        broker_connection = getattr(current_app, 'broker_connection', {})
        
        if not broker_connection.get('connected'):
            logger.warning(f"Broker not connected when trying to start strategy {strategy_id}")
            return jsonify({
                'error': 'Broker not connected',
                'message': 'Zerodha broker is disconnected. Please connect broker first.',
                'status': 'disconnected',
                'help': 'Navigate to Settings → Broker Connection and login to Zerodha'
            }), 400
        
        # Check warm-up data availability
        try:
            from engine.market_data_service import MarketDataService
            market_data = MarketDataService()
            
            # Try to fetch minimum required bars (100 for warm-up)
            min_bars_required = 100
            candles = market_data.get_historical_data(symbol, timeframe, count=min_bars_required)
            
            if not candles or len(candles) < min_bars_required:
                logger.warning(f"Insufficient data for {symbol}: only {len(candles) if candles else 0} bars available")
                return jsonify({
                    'error': 'Insufficient data',
                    'message': f'Need {min_bars_required} bars for warm-up, but only {len(candles) if candles else 0} available',
                    'status': 'insufficient_data'
                }), 400
                
        except Exception as e:
            logger.error(f"Data validation failed: {str(e)}")
            return jsonify({
                'error': 'Data validation failed',
                'message': f'Cannot fetch historical data: {str(e)}'
            }), 400
        
        # All validations passed - start the strategy
        success = _strategy_manager.start_strategy(strategy_id)
        
        if success:
            logger.info(f"✅ Strategy started: {strategy_id} on {symbol} ({timeframe})")
            return jsonify({
                'status': 'running',
                'message': f'Strategy {strategy_id} started successfully',
                'broker_connected': broker_connection.get('connected'),
                'data_ready': True
            }), 200
        else:
            return jsonify({
                'error': 'Failed to start strategy',
                'message': 'Strategy may not exist or is already running',
                'status': 'failed'
            }), 400
        
    except Exception as e:
        logger.error(f"Error starting strategy: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'message': str(e)}), 500


@strategy_bp.route('/strategy/stop', methods=['POST'])
def stop_strategy():
    """
    Stop a running strategy.
    
    Request Body:
        {
            "strategy_id": "STRAT-XXXXXXXX"
        }
    
    Response:
        {
            "status": "stopped"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        strategy_id = data.get('strategy_id')
        
        if not strategy_id:
            return jsonify({'error': 'strategy_id is required'}), 400
        
        # Stop the strategy
        success = _strategy_manager.stop_strategy(strategy_id)
        
        if success:
            logger.info(f"Strategy stopped: {strategy_id}")
            return jsonify({
                'status': 'stopped',
                'message': f'Strategy {strategy_id} stopped successfully'
            }), 200
        else:
            return jsonify({
                'error': 'Failed to stop strategy',
                'details': 'Strategy may not exist or is already stopped'
            }), 400
        
    except Exception as e:
        logger.error(f"Error stopping strategy: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategy/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id: str):
    """
    Get details of a specific strategy.
    
    Path Parameters:
        strategy_id: Unique strategy identifier
    
    Response:
        {
            "strategy_id": "STRAT-XXXXXXXX",
            "name": "My Strategy",
            "symbol": "NIFTY",
            "timeframe": "5minute",
            "status": "running",
            "created_at": "...",
            "started_at": "..."
        }
    """
    try:
        metadata = _strategy_manager.get_strategy_metadata(strategy_id)
        
        if not metadata:
            return jsonify({'error': 'Strategy not found'}), 404
        
        return jsonify({
            'strategy_id': strategy_id,
            **metadata
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting strategy: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategy/unregister', methods=['POST'])
def unregister_strategy():
    """
    Unregister (remove) a strategy.
    
    Request Body:
        {
            "strategy_id": "STRAT-XXXXXXXX"
        }
    
    Response:
        {
            "status": "unregistered"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        strategy_id = data.get('strategy_id')
        
        if not strategy_id:
            return jsonify({'error': 'strategy_id is required'}), 400
        
        # Unregister the strategy
        success = _strategy_manager.unregister_strategy(strategy_id)
        
        if success:
            logger.info(f"Strategy unregistered: {strategy_id}")
            return jsonify({
                'status': 'unregistered',
                'message': f'Strategy {strategy_id} removed successfully'
            }), 200
        else:
            return jsonify({
                'error': 'Failed to unregister strategy',
                'details': 'Strategy may not exist'
            }), 400
        
    except Exception as e:
        logger.error(f"Error unregistering strategy: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategy/stats', methods=['GET'])
def get_strategy_statistics():
    """
    Get strategy statistics.
    
    Response:
        {
            "total": 5,
            "running": 2,
            "registered": 1,
            "stopped": 2
        }
    """
    try:
        stats = _strategy_manager.get_statistics()
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error getting strategy stats: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategies', methods=['GET'])
def list_all_strategies():
    """
    Get list of all registered strategies.
    
    Returns an empty array if no strategies are manually registered.
    
    Query params:
        status: Filter by status (optional: running, registered, stopped)
    
    Response:
        {
            "strategies": [...],
            "total": 0
        }
    """
    try:
        # Import strategy registry
        from services.strategy_registry import get_strategy_registry
        
        registry = get_strategy_registry()
        status_filter = request.args.get('status')
        
        # Get strategies from registry (empty if none registered)
        strategies_list = registry.get_available_strategies()
        
        # Filter by status if provided
        if status_filter:
            strategies_list = [s for s in strategies_list if s.get('status') == status_filter]
        
        logger.info(f"Returning {len(strategies_list)} strategies")
        
        return jsonify({
            'strategies': strategies_list,
            'total': len(strategies_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing strategies: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@strategy_bp.route('/strategies/clear', methods=['POST'])
def clear_all_strategies():
    """
    Clear all strategies from the registry.
    
    Allows wiping the registered list without restarting the server.
    
    Response:
        {
            "status": "cleared",
            "removed_count": 1,
            "message": "All strategies cleared"
        }
    """
    try:
        from services.strategy_registry import get_strategy_registry
        
        registry = get_strategy_registry()
        removed = registry.clear_all()
        
        logger.info(f"✓ Registry cleared: {removed} strategies removed")
        
        return jsonify({
            'status': 'cleared',
            'removed_count': removed,
            'message': f'All strategies cleared ({removed} removed)'
        }), 200
        
    except Exception as e:
        logger.error(f"Error clearing strategies: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500



@strategy_bp.route('/trading/kill-switch', methods=['POST'])
async def trigger_kill_switch():
    """
    Emergency kill-switch: Close all positions immediately.
    
    Request Body:
        {
            "reason": "manual" | "daily_loss_limit" | "system_error",
            "message": "Optional description"
        }
    
    Response:
        {
            "success": true,
            "positions_closed": 5,
            "orders_cancelled": 3,
            "total_pnl": -12500.00,
            "timestamp": "2024-03-22T14:30:00"
        }
    """
    try:
        data = request.get_json() or {}
        
        reason = data.get('reason', 'manual')
        message = data.get('message', '')
        
        logger.critical(f"KILL-SWITCH TRIGGERED: {reason} - {message}")
        
        # Import live runner
        from .runner.live_runner import get_live_runner
        
        runner = get_live_runner()
        
        # Trigger kill-switch
        success = await runner.trigger_kill_switch(reason=reason)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Kill-switch execution failed'
            }), 500
        
        # Get final status
        status = runner.get_status()
        
        logger.critical(
            f"Kill-switch executed. "
            f"Positions closed: {status['open_positions']}, "
            f"Total PnL: {status['daily_pnl']:.2f}"
        )
        
        return jsonify({
            'success': True,
            'positions_closed': status['open_positions'],
            'orders_cancelled': status['pending_orders'],
            'total_pnl': status['daily_pnl'],
            'realized_pnl': status['realized_pnl'],
            'unrealized_pnl': status['unrealized_pnl'],
            'timestamp': datetime.now().isoformat(),
            'reason': reason
        }), 200
        
    except Exception as e:
        logger.critical(f"Kill-switch endpoint error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/trading/status', methods=['GET'])
def get_trading_status():
    """
    Get current live trading status.
    
    Response:
        {
            "paper_trading": true,
            "kill_switch_active": false,
            "active_strategies": 2,
            "open_positions": 3,
            "pending_orders": 1,
            "daily_pnl": 5250.00,
            "win_rate_today": 62.5,
            "avg_slippage_bps": 2.3
        }
    """
    try:
        from .runner.live_runner import get_live_runner
        
        runner = get_live_runner()
        status = runner.get_status()
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Error getting trading status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/trading/reset-kill-switch', methods=['POST'])
async def reset_kill_switch():
    """Reset kill-switch to allow new trades"""
    try:
        from .runner.live_runner import get_live_runner
        
        runner = get_live_runner()
        success = await runner.reset_kill_switch()
        
        return jsonify({
            'success': success,
            'message': 'Kill-switch reset successfully' if success else 'Reset failed'
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting kill-switch: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/trading/start-full-workflow', methods=['POST'])
async def start_full_workflow():
    """
    Start complete validation pipeline: Optimize → Validate → Paper Trade.
    
    This endpoint orchestrates the entire lifecycle:
    1. Parameter Optimization (find robust parameters)
    2. Monte Carlo Validation (verify sequence independence)
    3. Walk-Forward Analysis (validate on unseen data)
    4. Live Runner Initialization (start paper trading)
    
    Request Body:
        {
            "symbol": "RELIANCE",
            "param_grid": {
                "supertrend_factor": [2.0, 3.0, 4.0],
                "min_votes": [3, 4]
            },
            "timeframe": "5minute",
            "days": 90
        }
    
    Response:
        {
            "success": true,
            "results": {
                "status": "Active",
                "best_params": {...},
                "risk_profile": {...},
                "walk_forward": {...},
                "live_runner": {...}
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        symbol = data.get('symbol')
        param_grid = data.get('param_grid')
        
        if not symbol or not param_grid:
            return jsonify({'error': 'symbol and param_grid are required'}), 400
        
        logger.info(f"Starting full workflow for {symbol}")
        logger.info(f"Param grid: {param_grid}")
        
        # Get orchestrator
        from .orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        
        # Run full workflow
        result = await orchestrator.full_workflow_init(symbol, data)
        
        if result['status'] == 'Active':
            logger.info(f"✅ Full workflow completed successfully for {symbol}")
            return jsonify({
                'success': True,
                'results': result,
                'message': result.get('message', 'Strategy validated and activated')
            }), 200
        else:
            logger.warning(f"Workflow failed for {symbol}: {result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Workflow failed'),
                'message': result.get('message', 'Validation pipeline failed')
            }), 400
        
    except Exception as e:
        logger.error(f"Error in full workflow: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/trading/quick-start', methods=['POST'])
async def quick_start_workflow():
    """
    Simplified workflow with predefined parameters.
    
    For users who want to skip optimization and use known-good parameters.
    
    Request Body:
        {
            "symbol": "RELIANCE",
            "supertrend_factor": 3.0,
            "min_votes": 3
        }
    
    Response:
        Same as /start-full-workflow
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        symbol = data.get('symbol')
        supertrend_factor = data.get('supertrend_factor', 3.0)
        min_votes = data.get('min_votes', 3)
        
        if not symbol:
            return jsonify({'error': 'symbol is required'}), 400
        
        logger.info(f"Quick starting workflow for {symbol} with factor={supertrend_factor}, votes={min_votes}")
        
        # Get orchestrator
        from .orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        
        # Run quick start
        result = await orchestrator.quick_start(symbol, supertrend_factor, min_votes)
        
        if result['status'] == 'Active':
            logger.info(f"✅ Quick start completed successfully for {symbol}")
            return jsonify({
                'success': True,
                'results': result,
                'message': result.get('message', 'Strategy activated with predefined parameters')
            }), 200
        else:
            logger.warning(f"Quick start failed for {symbol}: {result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Quick start failed'),
                'message': result.get('message', 'Strategy activation failed')
            }), 400
        
    except Exception as e:
        logger.error(f"Error in quick start: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

"""
Trading Control API Routes

Web-based control for the trading engine.
Start/stop trading from frontend UI.
"""

from flask import Blueprint, jsonify, request
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
trading_bp = Blueprint('trading', __name__, url_prefix='/api/trading')

# Trading engine state
trading_state = {
    'running': False,
    'thread': None,
    'start_time': None,
    'active_strategies': 0,
    'broker_connected': False,
    'symbols_monitored': [],
    'signals_generated': 0,
    'orders_placed': 0
}


@trading_bp.route('/start', methods=['POST'])
def start_trading():
    """
    Start the trading engine from web UI.
    
    This will:
    1. Authenticate with Zerodha
    2. Load strategies
    3. Start market monitoring
    4. Execute trades automatically
    
    Returns:
        JSON status response
    """
    try:
        logger.info("Web UI requested to start trading...")
        
        # Check if already running
        if trading_state['running']:
            return jsonify({
                'success': False,
                'message': 'Trading engine already running',
                'status': get_trading_status()
            }), 400
        
        # Import trading runner
        try:
            from trading.web_trading_controller import WebTradingController
        except ImportError as e:
            logger.error(f"Failed to import WebTradingController: {e}")
            return jsonify({
                'success': False,
                'message': f'Trading controller not found: {str(e)}'
            }), 500
        
        # Create controller instance
        controller = WebTradingController()
        
        # Start trading in background thread
        def run_trading():
            try:
                logger.info("Starting trading engine in background thread...")
                trading_state['running'] = True
                trading_state['start_time'] = datetime.now().isoformat()
                
                # Run the trading engine
                controller.run_trading_loop()
                
            except Exception as e:
                logger.error(f"Trading loop error: {str(e)}")
                trading_state['running'] = False
                raise
        
        # Start thread
        trading_state['thread'] = threading.Thread(target=run_trading, daemon=True)
        trading_state['thread'].start()
        
        logger.info("✓ Trading engine started successfully")
        
        return jsonify({
            'success': True,
            'message': 'Trading engine started successfully',
            'status': get_trading_status()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to start trading: {str(e)}")
        trading_state['running'] = False
        return jsonify({
            'success': False,
            'message': f'Failed to start trading: {str(e)}'
        }), 500


@trading_bp.route('/stop', methods=['POST'])
def stop_trading():
    """
    Stop the trading engine from web UI.
    
    This will:
    1. Stop the trading loop
    2. Close broker connections
    3. Update system status
    
    Returns:
        JSON status response
    """
    try:
        logger.info("Web UI requested to stop trading...")
        
        # Check if running
        if not trading_state['running']:
            return jsonify({
                'success': False,
                'message': 'Trading engine not running',
                'status': get_trading_status()
            }), 400
        
        # Signal to stop
        trading_state['running'] = False
        
        # Wait for thread to finish (with timeout)
        if trading_state['thread']:
            trading_state['thread'].join(timeout=5.0)
        
        logger.info("✓ Trading engine stopped successfully")
        
        return jsonify({
            'success': True,
            'message': 'Trading engine stopped successfully',
            'status': get_trading_status()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to stop trading: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to stop trading: {str(e)}'
        }), 500


@trading_bp.route('/status', methods=['GET'])
def get_trading_status():
    """
    Get current trading engine status.
    
    Returns:
        JSON with trading state
    """
    try:
        status = {
            'running': trading_state['running'],
            'active_strategies': trading_state['active_strategies'],
            'broker_connected': trading_state['broker_connected'],
            'symbols_monitored': trading_state['symbols_monitored'],
            'signals_generated': trading_state['signals_generated'],
            'orders_placed': trading_state['orders_placed'],
            'start_time': trading_state['start_time'],
            'uptime': calculate_uptime(trading_state['start_time']) if trading_state['start_time'] else None
        }
        
        return jsonify({
            'success': True,
            'status': status
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get trading status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get status: {str(e)}'
        }), 500


def calculate_uptime(start_time_str: str) -> str:
    """Calculate uptime from start time."""
    try:
        start_time = datetime.fromisoformat(start_time_str)
        now = datetime.now()
        delta = now - start_time
        
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except:
        return "Unknown"


def update_trading_stats(active_strategies: int, broker_connected: bool, 
                         symbols: list, signals: int, orders: int):
    """
    Update trading state statistics.
    
    Called by trading controller to update UI.
    """
    trading_state['active_strategies'] = active_strategies
    trading_state['broker_connected'] = broker_connected
    trading_state['symbols_monitored'] = symbols
    trading_state['signals_generated'] = signals
    trading_state['orders_placed'] = orders

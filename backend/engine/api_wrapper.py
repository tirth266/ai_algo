"""
API Wrapper for Node.js Integration

Provides a simple CLI interface for Node.js server to call Python trading engine.

Usage:
    python api_wrapper.py generate_signal '{"symbol": "RELIANCE"}'
    python api_wrapper.py get_status '{}'

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import sys
import json
import logging
import os
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def generate_signal(params: dict) -> dict:
    """Generate trading signal for symbol."""
    from engine.trading_engine import get_trading_engine
    
    symbol = params.get('symbol')
    
    if not symbol:
        return {'error': 'Symbol parameter required'}
    
    engine = get_trading_engine()
    signal = engine.generate_signal(symbol)
    
    if signal is None:
        return {
            'symbol': symbol,
            'signal': 'HOLD',
            'confidence': 0.5,
            'reason': ['No clear signal detected']
        }
    
    return signal


def start_trading_loop(params: dict) -> dict:
    """Start continuous trading loop."""
    from engine.execution_loop import get_execution_loop
    
    symbols = params.get('symbols', ['RELIANCE', 'TCS', 'INFY'])
    interval = params.get('interval', 60)
    
    loop = get_execution_loop(symbols=symbols, interval=interval)
    loop.start()
    
    return {
        'status': 'running',
        'symbols': symbols,
        'interval': interval
    }


def stop_trading_loop(params: dict) -> dict:
    """Stop continuous trading loop."""
    from engine.execution_loop import get_execution_loop
    
    # Get existing loop
    loop = get_execution_loop(symbols=[], interval=60)
    loop.stop()
    
    return {
        'status': 'stopped'
    }


def get_status(params: dict) -> dict:
    """Get trading engine status."""
    from engine.trading_engine import get_trading_engine
    from engine.execution_loop import get_execution_loop
    
    try:
        engine = get_trading_engine()
        loop = get_execution_loop(symbols=[], interval=60)
        
        return {
            'engine_ready': True,
            'signals_cached': len(engine.get_all_signals()),
            'loop_status': loop.get_status() if loop else None
        }
    except Exception as e:
        return {
            'engine_ready': False,
            'error': str(e)
        }


def get_all_signals(params: dict) -> dict:
    """Get all cached signals."""
    from engine.trading_engine import get_trading_engine
    
    engine = get_trading_engine()
    return engine.get_all_signals()


def add_symbol(params: dict) -> dict:
    """Add symbol to monitoring list."""
    from engine.execution_loop import get_execution_loop
    
    symbol = params.get('symbol')
    
    if not symbol:
        return {'error': 'Symbol parameter required'}
    
    loop = get_execution_loop(symbols=[], interval=60)
    loop.add_symbol(symbol)
    
    return {
        'status': 'added',
        'symbol': symbol
    }


def refresh_signal(params: dict) -> dict:
    """Refresh signal for symbol."""
    return generate_signal(params)


# Function mapping
FUNCTIONS = {
    'generate_signal': generate_signal,
    'start_trading_loop': start_trading_loop,
    'stop_trading_loop': stop_trading_loop,
    'get_status': get_status,
    'get_all_signals': get_all_signals,
    'add_symbol': add_symbol,
    'refresh_signal': refresh_signal
}


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: api_wrapper.py <function> <params_json>'}))
        sys.exit(1)
    
    function_name = sys.argv[1]
    params_json = sys.argv[2]
    
    # Add backend directory to path
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, backend_dir)
    
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        print(json.dumps({'error': 'Invalid JSON parameters'}))
        sys.exit(1)
    
    if function_name not in FUNCTIONS:
        print(json.dumps({
            'error': f'Unknown function: {function_name}',
            'available': list(FUNCTIONS.keys())
        }))
        sys.exit(1)
    
    try:
        result = FUNCTIONS[function_name](params)
        print(json.dumps(result, default=str))
    except Exception as e:
        logger.error(f"Error executing {function_name}: {str(e)}", exc_info=True)
        print(json.dumps({
            'error': str(e),
            'function': function_name
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()

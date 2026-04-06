"""
Trading Server - Standalone Python Server

Optional standalone server that keeps the trading engine in memory.
Used for faster response times (avoids subprocess startup overhead).

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import logging
import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.trading_engine import get_trading_engine
from engine.execution_loop import get_execution_loop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TradingAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for trading API."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.startswith('/api/'):
            self.handle_api_request(parsed_path)
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.startswith('/api/'):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            self.handle_api_request(parsed_path, post_data)
        else:
            self.send_error(404)
    
    def handle_api_request(self, parsed_path, data=None):
        """Process API requests."""
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        try:
            # Get trading engine instance
            engine = get_trading_engine()
            
            if path == '/api/signal':
                symbol = query_params.get('symbol', [None])[0]
                
                if not symbol:
                    self.send_json({'error': 'Symbol parameter required'}, 400)
                    return
                
                signal = engine.generate_signal(symbol)
                self.send_json(signal or {'signal': 'HOLD'})
                
            elif path == '/api/status':
                status = {
                    'engine_ready': True,
                    'signals_cached': len(engine.get_all_signals())
                }
                self.send_json(status)
                
            elif path == '/api/signals':
                signals = engine.get_all_signals()
                self.send_json(signals)
                
            else:
                self.send_json({'error': 'Unknown endpoint'}, 404)
                
        except Exception as e:
            logger.error(f"API error: {str(e)}", exc_info=True)
            self.send_json({'error': str(e)}, 500)
    
    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"{self.address_string()} - {format % args}")


def run_server(port=5001):
    """Run the HTTP server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, TradingAPIHandler)
    
    print(f"\n{'='*70}")
    print(f"🚀 Python Trading Server Running")
    print(f"{'='*70}")
    print(f"Server: http://localhost:{port}")
    print(f"Engine ready: ✓")
    print(f"{'='*70}\n")
    
    logger.info("Python trading server started")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        logger.info("Python trading server stopped")


if __name__ == "__main__":
    run_server(port=5001)

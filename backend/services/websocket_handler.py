"""
WebSocket Handler for Real-time Data Streaming
Provides real-time updates for prices, P&L, orders, and positions using Flask-SocketIO
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Set
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import logging

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections and real-time data streaming"""

    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.is_streaming = False
        self.stream_thread = None
        self.subscribed_symbols: Set[str] = set()
        self.client_rooms: Dict[str, Set[str]] = {}  # client_id -> set of symbols

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register SocketIO event handlers"""

        @self.socketio.on("connect")
        def handle_connect():
            client_id = request.sid
            logger.info(f"Client {client_id} connected")
            self.client_rooms[client_id] = set()
            emit("connection_status", {"status": "connected", "client_id": client_id})

        @self.socketio.on("disconnect")
        def handle_disconnect():
            client_id = request.sid
            logger.info(f"Client {client_id} disconnected")
            if client_id in self.client_rooms:
                del self.client_rooms[client_id]

        @self.socketio.on("subscribe_symbols")
        def handle_subscribe_symbols(data):
            client_id = request.sid
            symbols = data.get("symbols", [])
            logger.info(f"Client {client_id} subscribing to symbols: {symbols}")

            # Join rooms for each symbol
            for symbol in symbols:
                join_room(symbol)
                if client_id in self.client_rooms:
                    self.client_rooms[client_id].add(symbol)

            self.subscribed_symbols.update(symbols)

        @self.socketio.on("unsubscribe_symbols")
        def handle_unsubscribe_symbols(data):
            client_id = request.sid
            symbols = data.get("symbols", [])
            logger.info(f"Client {client_id} unsubscribing from symbols: {symbols}")

            # Leave rooms for each symbol
            for symbol in symbols:
                leave_room(symbol)
                if client_id in self.client_rooms:
                    self.client_rooms[client_id].discard(symbol)

    def start_streaming(self):
        """Start the background data streaming thread"""
        if not self.is_streaming:
            self.is_streaming = True
            self.stream_thread = threading.Thread(
                target=self._data_stream_loop, daemon=True
            )
            self.stream_thread.start()
            logger.info("WebSocket data streaming started")

    def stop_streaming(self):
        """Stop the background data streaming thread"""
        self.is_streaming = False
        if self.stream_thread:
            self.stream_thread.join(timeout=5)
        logger.info("WebSocket data streaming stopped")

    def _data_stream_loop(self):
        """Main loop for streaming real-time data"""
        while self.is_streaming:
            try:
                # Stream price updates
                self._stream_price_updates()

                # Stream P&L updates
                self._stream_pnl_updates()

                # Stream order updates
                self._stream_order_updates()

                # Stream position updates
                self._stream_position_updates()

                # Sleep for 1 second before next update
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in data stream loop: {e}")
                time.sleep(5)  # Wait longer on error

    def _stream_price_updates(self):
        """Stream price updates to subscribed clients"""
        if not self.subscribed_symbols:
            return

        try:
            # Import here to avoid circular imports
            from services.market_data import MarketDataService

            market_data = MarketDataService()

            for symbol in self.subscribed_symbols:
                try:
                    # Get real-time price data
                    ltp_data = market_data.get_ltp(symbol)
                    if ltp_data:
                        # Calculate change (simplified - in real implementation, compare with previous price)
                        change = 0.0  # Placeholder
                        change_pct = 0.0  # Placeholder

                        price_data = {
                            "symbol": symbol,
                            "ltp": ltp_data,
                            "change": change,
                            "change_pct": change_pct,
                            "timestamp": datetime.now().isoformat(),
                        }

                        # Emit to symbol-specific room
                        self.socketio.emit("price_update", price_data, room=symbol)

                except Exception as e:
                    logger.debug(f"Could not get price for {symbol}: {e}")

        except ImportError:
            # MarketDataService not available, emit mock data for development
            for symbol in self.subscribed_symbols:
                price_data = {
                    "symbol": symbol,
                    "ltp": 100.0 + (hash(symbol) % 50),  # Mock price based on symbol
                    "change": 0.5,
                    "change_pct": 0.5,
                    "timestamp": datetime.now().isoformat(),
                }
                self.socketio.emit("price_update", price_data, room=symbol)

    def _stream_pnl_updates(self):
        """Stream P&L updates to all connected clients"""
        try:
            # In a real implementation, this would come from the trading engine
            pnl_data = {
                "total_pnl": 1250.50,
                "realized": 800.25,
                "unrealized": 450.25,
                "timestamp": datetime.now().isoformat(),
            }
            self.socketio.emit("pnl_update", pnl_data)

        except Exception as e:
            logger.debug(f"Could not stream P&L updates: {e}")

    def _stream_order_updates(self):
        """Stream order updates to all connected clients"""
        try:
            # In a real implementation, this would come from the order management system
            # For now, we'll emit empty array or mock data
            order_data = []  # No order updates in mock
            self.socketio.emit("order_update", order_data)

        except Exception as e:
            logger.debug(f"Could not stream order updates: {e}")

    def _stream_position_updates(self):
        """Stream position updates to all connected clients"""
        try:
            # In a real implementation, this would come from the position management system
            position_data = []  # No position updates in mock
            self.socketio.emit("position_update", position_data)

        except Exception as e:
            logger.debug(f"Could not stream position updates: {e}")


def init_websocket_handler(app, socketio: SocketIO) -> WebSocketHandler:
    """
    Initialize and return WebSocket handler instance

    Args:
        app: Flask application instance
        socketio: SocketIO instance

    Returns:
        WebSocketHandler instance
    """
    handler = WebSocketHandler(socketio)

    # Start streaming when first client connects
    @socketio.on("connect")
    def start_stream_on_connect():
        handler.start_streaming()

    # Stop streaming when last client disconnects
    @socketio.on("disconnect")
    def stop_stream_on_disconnect():
        # Check if any clients remain connected
        # In a production app, you'd track connected clients properly
        pass

    return handler

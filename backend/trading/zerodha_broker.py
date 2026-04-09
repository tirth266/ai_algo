"""
Zerodha Broker Module

Integration with Kite Connect API from Zerodha.

Features:
- Authentication with API key
- Session management
- Market order execution
- Limit order execution
- Position retrieval
- Order status tracking

Example usage:
    from trading.zerodha_broker import ZerodhaBroker
    
    broker = ZerodhaBroker(api_key, access_token)
    broker.place_order(
        symbol="RELIANCE",
        quantity=10,
        order_type="MARKET",
        side="BUY"
    )

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import time

from ..utils.alert_manager import get_alert_manager

try:
    from kiteconnect import KiteConnect
    from kiteconnect.exceptions import TokenException, NetworkException
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("kiteconnect not installed. Install with: pip install kiteconnect")

from .broker_interface import (
    BrokerInterface, Order, Position, 
    OrderError, APIError, ConnectionError
)

logger = logging.getLogger(__name__)


class ZerodhaBroker(BrokerInterface):
    """
    Zerodha Kite Connect broker implementation.
    
    Provides live trading integration with Zerodha's Kite Connect API.
    
    Usage:
        >>> broker = ZerodhaBroker(
        ...     api_key='your_api_key',
        ...     api_secret='your_api_secret'
        ... )
        >>> broker.connect(access_token='your_access_token')
        >>> positions = broker.get_positions()
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str = None,
        access_token: str = None,
        pool_size: int = 10,
        timeout: int = 7
    ):
        """
        Initialize Zerodha broker.
        
        Args:
            api_key: Kite Connect API key
            api_secret: Kite Connect API secret (optional)
            access_token: Access token for authentication
            pool_size: Connection pool size
            timeout: Request timeout in seconds
        
        Example:
            >>> broker = ZerodhaBroker(
            ...     api_key='abc123',
            ...     access_token='xyz789'
            ... )
        """
        if not KITE_AVAILABLE:
            raise ImportError(
                "kiteconnect package not installed. "
                "Install with: pip install kiteconnect"
            )
        
        super().__init__()
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        
        # Kite Connect instance
        self.kite: Optional[KiteConnect] = None
        
        # Configuration
        self.pool_size = pool_size
        self.timeout = timeout
        
        # Session management
        self.last_request_time: Optional[datetime] = None
        self.request_count: int = 0
        
        # Symbol to instrument ID mapping
        self.symbol_map: Dict[str, str] = {}
        
        logger.info(f"ZerodhaBroker initialized: api_key={api_key[:4]}***")
    
    def connect(self, access_token: str = None, **kwargs) -> bool:
        """
        Connect to Kite Connect API.
        
        Args:
            access_token: Access token (optional, can be set in __init__)
            **kwargs: Additional Kite Connect parameters
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        
        Example:
            >>> broker.connect(access_token='your_token')
            >>> print(f"Connected: {broker.is_connected()}")
        """
        try:
            # Use provided token or fallback to init token
            token = access_token or self.access_token
            
            if not token:
                raise ConnectionError("Access token required")
            
            # Initialize Kite Connect
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(token)
            self.kite.set_session_timeout(self.timeout)
            
            # Test connection by getting profile
            try:
                profile = self.kite.profile()
                self.user_id = profile.get('user_id')
                self.connected = True
                
                logger.info(f"Connected to Zerodha: user_id={self.user_id}")
                
                # Load instrument list for symbol mapping
                self._load_instruments()
                
                return True
                
            except TokenException as e:
                raise ConnectionError(f"Invalid access token: {str(e)}")
            except NetworkException as e:
                raise ConnectionError(f"Network error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self.connected = False
            raise ConnectionError(f"Failed to connect: {str(e)}")
    
    def disconnect(self):
        """Disconnect from Kite Connect API."""
        try:
            if self.kite:
                self.kite = None
            self.connected = False
            logger.info("Disconnected from Zerodha")
            alert_message = (
                "Broker disconnect\n"
                "Broker: Zerodha\n"
                "Status: disconnected"
            )
            get_alert_manager().send(alert_message, level='WARNING')
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if connected to Kite Connect."""
        return self.connected and self.kite is not None
    
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order through Zerodha.
        
        Args:
            order: Order object to place
        
        Returns:
            Dictionary with order response including order_id
        
        Raises:
            OrderError: If order placement fails
        
        Example:
            >>> order = Order(symbol="RELIANCE", quantity=10, side="BUY")
            >>> response = broker.place_order(order)
            >>> print(f"Order ID: {response['order_id']}")
        """
        try:
            # Validate order
            self._validate_order(order)
            
            # Get instrument ID
            instrument = self._get_instrument_id(order.symbol)
            
            # Map order type to Kite constants
            variety = 'regular'
            product = self._map_product(order.product)
            order_type = self._map_order_type(order.order_type)
            
            # Prepare order parameters
            params = {
                'variety': variety,
                'exchange': 'NSE',  # Default to NSE
                'tradingsymbol': order.symbol,
                'transaction_type': order.side.lower(),
                'quantity': order.quantity,
                'product': product,
                'order_type': order_type,
                'disclosed_quantity': 0
            }
            
            # Add price for limit orders
            if order.order_type in ['LIMIT', 'SL']:
                params['price'] = order.price
            
            # Add trigger price for stop orders
            if order.order_type in ['SL', 'SL-M']:
                params['trigger_price'] = order.stop_loss or order.price
            
            # Place order
            response = self.kite.place_order(**params)
            order_id = response.get('order_id')
            
            # Update order object
            order.order_id = order_id
            order.status = 'OPEN'
            
            logger.info(f"Order placed: {order.symbol} {order.side} {order.quantity} @ {order.order_type}, order_id={order_id}")
            
            return {
                'order_id': order_id,
                'status': 'SUCCESS',
                'message': 'Order placed successfully',
                'symbol': order.symbol,
                'quantity': order.quantity,
                'side': order.side
            }
        
        except Exception as e:
            logger.error(f"Order placement failed: {str(e)}")
            order.status = 'REJECTED'
            raise OrderError(f"Failed to place order: {str(e)}")
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            order_id: Broker order ID to cancel
        
        Returns:
            Dictionary with cancellation response
        
        Raises:
            OrderError: If cancellation fails
        
        Example:
            >>> response = broker.cancel_order('order_123')
        """
        try:
            response = self.kite.cancel_order(variety='regular', order_id=order_id)
            
            logger.info(f"Order cancelled: order_id={order_id}")
            
            return {
                'order_id': order_id,
                'status': 'CANCELLED',
                'message': 'Order cancelled successfully'
            }
        
        except Exception as e:
            logger.error(f"Order cancellation failed: {str(e)}")
            raise OrderError(f"Failed to cancel order: {str(e)}")
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Modify an existing order.
        
        Args:
            order_id: Broker order ID
            quantity: New quantity (optional)
            price: New price (optional)
            order_type: New order type (optional)
            stop_loss: New stop loss (optional)
            target: New target (optional)
        
        Returns:
            Dictionary with modification response
        
        Raises:
            OrderError: If modification fails
        """
        try:
            # Prepare modification parameters
            params = {
                'variety': 'regular',
                'order_id': order_id
            }
            
            if quantity is not None:
                params['quantity'] = quantity
            
            if price is not None:
                params['price'] = price
            
            if order_type is not None:
                params['order_type'] = self._map_order_type(order_type)
            
            if stop_loss is not None:
                params['trigger_price'] = stop_loss
            
            response = self.kite.modify_order(**params)
            
            logger.info(f"Order modified: order_id={order_id}")
            
            return {
                'order_id': order_id,
                'status': 'MODIFIED',
                'message': 'Order modified successfully'
            }
        
        except Exception as e:
            logger.error(f"Order modification failed: {str(e)}")
            raise OrderError(f"Failed to modify order: {str(e)}")
    
    def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects
        
        Raises:
            APIError: If API call fails
        
        Example:
            >>> positions = broker.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos.symbol}: {pos.quantity} @ {pos.average_price:.2f}")
        """
        try:
            # Get net positions
            positions_data = self.kite.positions('net')
            
            positions = []
            for pos_data in positions_data:
                position = Position(
                    symbol=pos_data['tradingsymbol'],
                    quantity=pos_data['quantity'],
                    average_price=pos_data['average_price'],
                    last_price=pos_data['last_price']
                )
                
                # Update PnL
                position.unrealized_pnl = pos_data.get('unrealised', 0.0)
                position.realized_pnl = pos_data.get('realised', 0.0)
                
                positions.append(position)
            
            logger.info(f"Retrieved {len(positions)} positions")
            return positions
        
        except Exception as e:
            logger.error(f"Failed to get positions: {str(e)}")
            raise APIError(f"Failed to retrieve positions: {str(e)}")
    
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get account balance and margins.
        
        Returns:
            Dictionary with balance information
        
        Raises:
            APIError: If API call fails
        
        Example:
            >>> balance = broker.get_account_balance()
            >>> print(f"Available cash: {balance['available']['cash']:.2f}")
        """
        try:
            margins = self.kite.margins()
            
            balance = {
                'equity': margins.get('equity', {}),
                'commodity': margins.get('commodity', {}),
                'total_net_value': margins.get('net', 0.0),
                'available_cash': margins.get('available', {}).get('cash', 0.0),
                'available_intraday': margins.get('available', {}).get('intraday_payin', 0.0),
                'utilized_debits': margins.get('utilised', {}).get('debits', 0.0),
                'utilized_exposure': margins.get('utilised', {}).get('exposure', 0.0),
                'utilized_turnover': margins.get('utilised', {}).get('turnover', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.debug(f"Balance retrieved: net={balance['total_net_value']:.2f}")
            return balance
        
        except Exception as e:
            logger.error(f"Failed to get balance: {str(e)}")
            raise APIError(f"Failed to retrieve balance: {str(e)}")
    
    def get_open_orders(self) -> List[Order]:
        """
        Get all open/pending orders.
        
        Returns:
            List of Order objects
        
        Raises:
            APIError: If API call fails
        
        Example:
            >>> orders = broker.get_open_orders()
            >>> for order in orders:
            ...     print(f"{order.symbol} {order.side} {order.quantity}")
        """
        try:
            orders_data = self.kite.orders()
            
            orders = []
            for order_data in orders_data:
                # Only include open/pending orders
                if order_data['status'] in ['OPEN', 'TRIGGER PENDING', 'PENDING']:
                    order = Order(
                        symbol=order_data['tradingsymbol'],
                        quantity=order_data['quantity'],
                        side=order_data['transaction_type'].upper(),
                        order_type=order_data['order_type'].upper(),
                        price=order_data.get('price'),
                        product=order_data['product']
                    )
                    
                    order.order_id = order_data['order_id']
                    order.status = order_data['status']
                    order.filled_quantity = order_data.get('filled_quantity', 0)
                    order.pending_quantity = order_data.get('pending_quantity', 0)
                    order.average_price = order_data.get('average_price', 0.0)
                    
                    orders.append(order)
            
            logger.info(f"Retrieved {len(orders)} open orders")
            return orders
        
        except Exception as e:
            logger.error(f"Failed to get open orders: {str(e)}")
            raise APIError(f"Failed to retrieve open orders: {str(e)}")
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get order history/status.
        
        Args:
            order_id: Broker order ID
        
        Returns:
            List of order status updates
        
        Raises:
            APIError: If API call fails
        """
        try:
            # Get all orders and filter by order_id
            all_orders = self.kite.orders()
            order_history = [o for o in all_orders if o['order_id'] == order_id]
            
            if not order_history:
                raise APIError(f"Order not found: {order_id}")
            
            logger.debug(f"Retrieved history for order: {order_id}")
            return order_history
        
        except Exception as e:
            logger.error(f"Failed to get order history: {str(e)}")
            raise APIError(f"Failed to retrieve order history: {str(e)}")
    
    def get_historical_data(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Any]:
        """
        Get historical candle data.
        
        Args:
            symbol: Trading symbol
            interval: Candle interval (e.g., '5m', '15m', '1h')
            from_date: Start date
            to_date: End date
        
        Returns:
            Dictionary with OHLCV data
        
        Raises:
            APIError: If API call fails
        
        Example:
            >>> data = broker.get_historical_data(
            ...     symbol="RELIANCE",
            ...     interval="15m",
            ...     from_date=datetime(2024, 1, 1),
            ...     to_date=datetime(2024, 1, 31)
            ... )
        """
        try:
            # Get instrument token
            instrument_token = self._get_instrument_token(symbol)
            
            # Fetch historical data
            candles = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            logger.debug(
                f"Retrieved {len(candles)} candles for {symbol} "
                f"interval={interval}"
            )
            
            return {
                'symbol': symbol,
                'interval': interval,
                'candles': candles,
                'count': len(candles)
            }
        
        except Exception as e:
            logger.error(f"Failed to get historical data: {str(e)}")
            raise APIError(f"Failed to retrieve historical data: {str(e)}")
    
    def get_ltp(self, symbol: str) -> float:
        """
        Get last traded price.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Last traded price
        
        Raises:
            APIError: If API call fails
        
        Example:
            >>> ltp = broker.get_ltp("RELIANCE")
            >>> print(f"LTP: {ltp:.2f}")
        """
        try:
            # Get instrument token
            instrument_token = self._get_instrument_token(symbol)
            
            # Fetch quote
            quote = self.kite.quote(instrument_token)
            ltp = quote[instrument_token]['last_price']
            
            return ltp
        
        except Exception as e:
            logger.error(f"Failed to get LTP: {str(e)}")
            raise APIError(f"Failed to retrieve LTP: {str(e)}")
    
    def _load_instruments(self):
        """Load instrument list for symbol mapping."""
        try:
            instruments = self.kite.instruments()
            
            for inst in instruments:
                # Store mapping for NSE stocks
                if inst['exchange'] == 'NSE':
                    self.symbol_map[inst['tradingsymbol']] = inst['instrument_token']
            
            logger.info(f"Loaded {len(self.symbol_map)} instruments")
        
        except Exception as e:
            logger.error(f"Failed to load instruments: {str(e)}")
    
    def _get_instrument_id(self, symbol: str) -> str:
        """Get instrument token for symbol."""
        if symbol not in self.symbol_map:
            raise ValueError(f"Symbol not found: {symbol}")
        return self.symbol_map[symbol]
    
    def _get_instrument_token(self, symbol: str) -> str:
        """Get instrument token for symbol."""
        return self._get_instrument_id(symbol)
    
    def _map_product(self, product: str) -> str:
        """Map product type to Kite constants."""
        product_map = {
            'MIS': 'MIS',
            'CNC': 'CNC',
            'NRML': 'NRML',
            'CO': 'CO',
            'BO': 'BO'
        }
        return product_map.get(product.upper(), 'MIS')
    
    def _map_order_type(self, order_type: str) -> str:
        """Map order type to Kite constants."""
        order_type_map = {
            'MARKET': 'MARKET',
            'LIMIT': 'LIMIT',
            'SL': 'SL',
            'SL-M': 'SL-M'
        }
        return order_type_map.get(order_type.upper(), 'MARKET')
    
    def _rate_limit_check(self):
        """Implement rate limiting."""
        current_time = datetime.now()
        
        if self.last_request_time:
            time_diff = (current_time - self.last_request_time).total_seconds()
            
            # Kite has ~3 requests/second limit
            if time_diff < 0.33:
                time.sleep(0.33 - time_diff)
        
        self.last_request_time = current_time
        self.request_count += 1


def create_zerodha_broker(
    api_key: str,
    access_token: str,
    api_secret: str = None
) -> ZerodhaBroker:
    """
    Convenience function to create Zerodha broker instance.
    
    Args:
        api_key: Kite Connect API key
        access_token: Access token
        api_secret: API secret (optional)
    
    Returns:
        Connected ZerodhaBroker instance
    
    Example:
        >>> broker = create_zerodha_broker('key', 'token')
        >>> positions = broker.get_positions()
    """
    broker = ZerodhaBroker(
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token
    )
    
    broker.connect()
    return broker

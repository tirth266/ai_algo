"""
Angel One SmartAPI Broker Module

Integration with Angel One SmartAPI for live trading.

Features:
- TOTP-based authentication
- Session management
- Market/Limit/SL/SL-M order execution
- Position retrieval
- Order status tracking
- Instrument token lookup from master list
- Product type mapping (INTRADAY, DELIVERY, CARRYFORWARD)

Example usage:
    from trading.angel_one_broker import AngelOneBroker
    
    broker = AngelOneBroker()
    broker.connect()
    broker.place_order(
        symbol="SBIN-EQ",
        quantity=10,
        order_type="MARKET",
        side="BUY"
    )

Author: Quantitative Trading Systems Engineer
Date: March 28, 2026
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import time
import json
import requests
from pathlib import Path

from backend.services.angelone_service import get_angel_one_service

try:
    from smartapi import SmartConnect
    from smartapi.exceptions import SmartApiException
    SMARTAPI_AVAILABLE = True
except ImportError:
    SMARTAPI_AVAILABLE = False
    SmartApiException = None
    logger = logging.getLogger(__name__)
    logger.warning("smartapi package not installed. Install with: pip install smartapi-python")

from .broker_interface import (
    BrokerInterface, Order, Position, 
    OrderError, APIError, ConnectionError
)
from backend.utils.alert_manager import get_alert_manager

logger = logging.getLogger(__name__)


class AngelOneBroker(BrokerInterface):
    """
    Angel One SmartAPI broker implementation.
    
    Provides live trading integration with Angel One's SmartAPI.
    
    Usage:
        >>> broker = AngelOneBroker()
        >>> broker.connect()
        >>> positions = broker.get_positions()
    """
    
    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        client_id: str = None,
        totp_seed: str = None,
        auto_login: bool = True
    ):
        """
        Initialize Angel One broker.
        
        Args:
            api_key: SmartAPI API key (optional, can use env)
            secret_key: SmartAPI API secret (optional, can use env)
            client_id: Angel One Client ID (optional, can use env)
            totp_seed: TOTP seed for automated login (optional, can use env)
            auto_login: Automatically authenticate on connect
        
        Example:
            >>> broker = AngelOneBroker()
        """
        if not SMARTAPI_AVAILABLE:
            raise ImportError(
                "smartapi-python package not installed. "
                "Install with: pip install smartapi-python"
            )
        
        super().__init__()
        
        # Get credentials from parameters or environment
        import os
        self.api_key = api_key or os.getenv('ANGEL_ONE_API_KEY')
        self.secret_key = secret_key or os.getenv('ANGEL_ONE_SECRET_KEY')
        self.client_id = client_id or os.getenv('ANGEL_ONE_CLIENT_ID')
        self.totp_seed = totp_seed or os.getenv('ANGEL_ONE_TOTP_SEED')
        
        # Validate credentials
        if not self.api_key or not self.secret_key or not self.client_id:
            raise ValueError(
                "API credentials not provided. "
                "Set ANGEL_ONE_API_KEY, ANGEL_ONE_SECRET_KEY, and ANGEL_ONE_CLIENT_ID in .env"
            )
        
        # SmartConnect instance
        self.smart_api: Optional[SmartConnect] = None
        
        # Instrument mapping
        self.symbol_to_token_map: Dict[str, str] = {}
        self.token_to_symbol_map: Dict[str, str] = {}
        self.instrument_master: List[Dict] = []
        
        # Configuration
        self.config_dir = Path(__file__).parent.parent / 'config'
        self.instrument_file = self.config_dir / 'angelone_instruments.json'
        
        logger.info(f"AngelOneBroker initialized: api_key={self.api_key[:4]}***")
    
    def connect(self, access_token: str = None, **kwargs) -> bool:
        """
        Connect to Angel One SmartAPI.
        
        Args:
            access_token: Access token (optional, will auto-generate if not provided)
            **kwargs: Additional SmartAPI parameters
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        
        Example:
            >>> broker.connect()
            >>> print(f"Connected: {broker.is_connected()}")
        """
        try:
            logger.info("Connecting to Angel One SmartAPI...")
            
            # Initialize SmartConnect
            self.smart_api = SmartConnect(api_key=self.api_key)
            
            # Use provided token or obtain a valid token from TokenManager
            if access_token:
                self.smart_api.setAccessToken(access_token)
                self.connected = True
            else:
                service = get_angel_one_service()
                jwt_token = service.get_valid_token()
                self.smart_api.setAccessToken(jwt_token)
                self.connected = True
            
            # Test connection by getting profile
            try:
                profile = self.smart_api.getProfile()
                self.user_id = profile.get('clientcode', self.client_id)
                
                logger.info(f"Connected to Angel One: user_id={self.user_id}")
                
                # Load instrument list for symbol mapping
                self._load_instruments()
                
                return True
                
            except SmartApiException as e:
                raise ConnectionError(f"Invalid access token: {str(e)}")
        
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self.connected = False
            raise ConnectionError(f"Failed to connect: {str(e)}")
    
    def disconnect(self):
        """Disconnect from Angel One SmartAPI."""
        try:
            if self.smart_api:
                self.smart_api = None
            self.connected = False
            logger.info("Disconnected from Angel One")
            get_alert_manager().send(
                'Broker disconnected from Angel One',
                level='WARNING',
                extra={
                    'broker': 'Angel One',
                    'status': 'disconnected',
                },
            )
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if connected to Angel One."""
        return self.connected and self.smart_api is not None
    
    def _authenticate_with_totp(self) -> bool:
        """
        Authenticate using TOTP.
        
        Returns:
            True if authentication successful
        """
        try:
            import pyotp
            
            if not self.totp_seed:
                logger.error("TOTP seed not configured")
                return False
            
            # Generate TOTP
            totp = pyotp.TOTP(self.totp_seed).now()
            logger.info(f"Generated TOTP: {totp}")
            
            # Generate session
            session_data = self.smart_api.generateSession(
                self.client_id,
                self.secret_key,
                totp
            )
            
            access_token = session_data.get('token')
            
            if not access_token:
                logger.error("No access token received")
                return False
            
            # Set access token
            self.smart_api.setAccessToken(access_token)
            
            # Save token for future use
            self._save_access_token(access_token)
            
            logger.info("Authentication successful")
            return True
        
        except Exception as e:
            logger.error(f"TOTP authentication failed: {str(e)}")
            return False
    
    def _save_access_token(self, access_token: str):
        """Save access token to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            token_data = {
                'access_token': access_token,
                'client_id': self.client_id,
                'api_key': self.api_key,
                'timestamp': datetime.now().isoformat(),
                'expiry_date': (datetime.now() + timedelta(days=1)).isoformat()
            }
            
            token_file = self.config_dir / 'angelone_token.json'
            
            with open(token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"Access token saved to {token_file}")
        
        except Exception as e:
            logger.error(f"Failed to save access token: {str(e)}")
    
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order through Angel One.
        
        Args:
            order: Order object to place
        
        Returns:
            Dictionary with order response including order_id
        
        Raises:
            OrderError: If order placement fails
        
        Example:
            >>> order = Order(symbol="SBIN-EQ", quantity=10, side="BUY")
            >>> response = broker.place_order(order)
            >>> print(f"Order ID: {response['order_id']}")
        """
        try:
            # Validate order
            self._validate_order(order)
            
            # Get instrument token
            instrument_token = self._get_instrument_token(order.symbol)
            
            # Map order parameters to Angel One format
            variety = self._map_variety(order.product)
            product_type = self._map_product(order.product)
            order_type = self._map_order_type(order.order_type)
            transaction_type = self._map_transaction_type(order.side)
            
            # Determine exchange and symbol
            exchange = self._get_exchange(order.symbol)
            trading_symbol = self._get_trading_symbol(order.symbol)
            
            # Prepare order parameters
            params = {
                "variety": variety,
                "tradingsymbol": trading_symbol,
                "symboltoken": instrument_token,
                "exchange": exchange,
                "transactiontype": transaction_type,
                "quantity": str(order.quantity),
                "producttype": product_type,
                "ordertype": order_type,
                "price": "0",
                "triggerprice": "0",
                "disclosedquantity": "0"
            }
            
            # Add price for limit orders
            if order.order_type in ['LIMIT', 'SL']:
                params["price"] = str(order.price)
            
            # Add trigger price for stop orders
            if order.order_type in ['SL', 'SL-M']:
                params["triggerprice"] = str(order.stop_loss or order.price)
            
            # Place order
            response = self.smart_api.placeOrder(**params)
            
            # Extract order ID
            order_id = response.get('data', {}).get('orderid')
            
            if not order_id:
                raise OrderError("No order ID in response")
            
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
                'side': order.side,
                'data': response.get('data', {})
            }
        
        except SmartApiException as e:
            logger.error(f"Order placement failed: {str(e)}")
            order.status = 'REJECTED'
            raise OrderError(f"Failed to place order: {str(e)}")
        
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
            response = self.smart_api.cancelOrder(variety="NORMAL", orderid=order_id)
            
            logger.info(f"Order cancelled: order_id={order_id}")
            
            return {
                'order_id': order_id,
                'status': 'CANCELLED',
                'message': 'Order cancelled successfully',
                'data': response.get('data', {})
            }
        
        except SmartApiException as e:
            logger.error(f"Order cancellation failed: {str(e)}")
            raise OrderError(f"Failed to cancel order: {str(e)}")
        
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
                "variety": "NORMAL",
                "orderid": order_id
            }
            
            if quantity is not None:
                params["quantity"] = str(quantity)
            
            if price is not None:
                params["price"] = str(price)
            
            if order_type is not None:
                params["ordertype"] = self._map_order_type(order_type)
            
            if stop_loss is not None:
                params["triggerprice"] = str(stop_loss)
            
            response = self.smart_api.modifyOrder(**params)
            
            logger.info(f"Order modified: order_id={order_id}")
            
            return {
                'order_id': order_id,
                'status': 'MODIFIED',
                'message': 'Order modified successfully',
                'data': response.get('data', {})
            }
        
        except SmartApiException as e:
            logger.error(f"Order modification failed: {str(e)}")
            raise OrderError(f"Failed to modify order: {str(e)}")
        
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
            positions_data = self.smart_api.PositionAll()
            
            positions = []
            for pos_data in positions_data.get('data', []):
                # Skip if no quantity
                qty = int(pos_data.get('netqty', 0))
                if qty == 0:
                    continue
                
                symbol = pos_data.get('tradingsymbol', '')
                avg_price = float(pos_data.get('netavgprice', 0.0))
                last_price = float(pos_data.get('lp', 0.0))
                
                position = Position(
                    symbol=symbol,
                    quantity=qty,
                    average_price=avg_price,
                    last_price=last_price
                )
                
                # Calculate PnL
                position.unrealized_pnl = float(pos_data.get('calculatedprofloss', 0.0))
                
                positions.append(position)
            
            logger.info(f"Retrieved {len(positions)} positions")
            return positions
        
        except SmartApiException as e:
            logger.error(f"Failed to get positions: {str(e)}")
            raise APIError(f"Failed to retrieve positions: {str(e)}")
        
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
            >>> print(f"Available cash: {balance['available_cash']:.2f}")
        """
        try:
            # Get margin details
            margin_data = self.smart_api.getMargin()
            
            balance = {
                'total_net_value': float(margin_data.get('data', {}).get('net', 0.0)),
                'available_cash': float(margin_data.get('data', {}).get('availablecash', 0.0)),
                'available_intraday': float(margin_data.get('data', {}).get('availableintraday', 0.0)),
                'utilized_debits': float(margin_data.get('data', {}).get('utiliseddebits', 0.0)),
                'utilized_exposure': float(margin_data.get('data', {}).get('utilisedexposure', 0.0)),
                'utilized_turnover': float(margin_data.get('data', {}).get('utilisedturnover', 0.0)),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.debug(f"Balance retrieved: net={balance['total_net_value']:.2f}")
            return balance
        
        except SmartApiException as e:
            logger.error(f"Failed to get balance: {str(e)}")
            raise APIError(f"Failed to retrieve balance: {str(e)}")
        
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
            orders_data = self.smart_api.orderBook()
            
            orders = []
            for order_data in orders_data.get('data', []):
                # Only include open/pending orders
                status = order_data.get('status', '')
                if status in ['open', 'pending', 'TRIGGER PENDING', 'PENDING']:
                    order = Order(
                        symbol=order_data.get('tradingsymbol', ''),
                        quantity=int(order_data.get('quantity', 0)),
                        side='BUY' if order_data.get('transactiontype') == 'B' else 'SELL',
                        order_type=self._reverse_map_order_type(order_data.get('ordertype', 'MARKET')),
                        price=float(order_data.get('price', 0)),
                        product=self._reverse_map_product(order_data.get('producttype', 'MIS'))
                    )
                    
                    order.order_id = order_data.get('orderid')
                    order.status = status.upper()
                    order.filled_quantity = int(order_data.get('fillsize', 0))
                    order.pending_quantity = int(order_data.get('quantity', 0)) - int(order_data.get('fillsize', 0))
                    order.average_price = float(order_data.get('averageprice', 0.0))
                    
                    orders.append(order)
            
            logger.info(f"Retrieved {len(orders)} open orders")
            return orders
        
        except SmartApiException as e:
            logger.error(f"Failed to get open orders: {str(e)}")
            raise APIError(f"Failed to retrieve open orders: {str(e)}")
        
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
            all_orders = self.smart_api.orderBook()
            order_history = [o for o in all_orders.get('data', []) if o.get('orderid') == order_id]
            
            if not order_history:
                raise APIError(f"Order not found: {order_id}")
            
            logger.debug(f"Retrieved history for order: {order_id}")
            return order_history
        
        except SmartApiException as e:
            logger.error(f"Failed to get order history: {str(e)}")
            raise APIError(f"Failed to retrieve order history: {str(e)}")
        
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
            ...     symbol="SBIN-EQ",
            ...     interval="15m",
            ...     from_date=datetime(2024, 1, 1),
            ...     to_date=datetime(2024, 1, 31)
            ... )
        """
        try:
            # Get instrument token
            instrument_token = self._get_instrument_token(symbol)
            
            # Map interval to Angel One format
            angel_interval = self._map_interval(interval)
            
            # Fetch historical data
            candles = self.smart_api.getCandleData({
                "exchange": self._get_exchange(symbol),
                "symboltoken": instrument_token,
                "interval": angel_interval,
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            })
            
            candle_data = candles.get('data', [])
            
            logger.debug(
                f"Retrieved {len(candle_data)} candles for {symbol} "
                f"interval={interval}"
            )
            
            return {
                'symbol': symbol,
                'interval': interval,
                'candles': candle_data,
                'count': len(candle_data)
            }
        
        except SmartApiException as e:
            logger.error(f"Failed to get historical data: {str(e)}")
            raise APIError(f"Failed to retrieve historical data: {str(e)}")
        
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
            >>> ltp = broker.get_ltp("SBIN-EQ")
            >>> print(f"LTP: {ltp:.2f}")
        """
        try:
            # Get instrument token
            instrument_token = self._get_instrument_token(symbol)
            
            # Fetch quote
            quote = self.smart_api.quote(
                exchange=self._get_exchange(symbol),
                tradingsymbol=self._get_trading_symbol(symbol),
                symboltoken=instrument_token
            )
            
            ltp = float(quote.get('data', {}).get('lastprice', 0.0))
            
            return ltp
        
        except SmartApiException as e:
            logger.error(f"Failed to get LTP: {str(e)}")
            raise APIError(f"Failed to retrieve LTP: {str(e)}")
        
        except Exception as e:
            logger.error(f"Failed to get LTP: {str(e)}")
            raise APIError(f"Failed to retrieve LTP: {str(e)}")
    
    def _load_instruments(self):
        """Load instrument list for symbol mapping."""
        try:
            # Check if cached instrument file exists
            if self.instrument_file.exists():
                with open(self.instrument_file, 'r', encoding='utf-8') as f:
                    self.instrument_master = json.load(f)
                logger.info(f"Loaded {len(self.instrument_master)} instruments from cache")
            else:
                # Download from Angel One API
                logger.info("Downloading instrument list from Angel One...")
                
                # Angel One provides instrument list via CSV
                csv_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                response = requests.get(csv_url, timeout=10)
                response.raise_for_status()
                
                self.instrument_master = response.json()
                
                # Save to cache
                self.config_dir.mkdir(parents=True, exist_ok=True)
                with open(self.instrument_file, 'w', encoding='utf-8') as f:
                    json.dump(self.instrument_master, f, indent=2)
                
                logger.info(f"Downloaded and cached {len(self.instrument_master)} instruments")
            
            # Build symbol-to-token mapping
            for inst in self.instrument_master:
                symbol = inst.get('symbol', '')
                token = inst.get('symboltoken', '')
                exchange = inst.get('exch_seg', '')
                
                if symbol and token:
                    # Create unique symbol (exchange:symbol format)
                    full_symbol = f"{exchange}:{symbol}" if exchange else symbol
                    
                    self.symbol_to_token_map[full_symbol] = token
                    self.symbol_to_token_map[symbol] = token  # Also map without exchange
                    self.token_to_symbol_map[token] = symbol
            
            logger.info(f"Built mapping for {len(self.symbol_to_token_map)} symbols")
        
        except Exception as e:
            logger.error(f"Failed to load instruments: {str(e)}")
    
    def _get_instrument_token(self, symbol: str) -> str:
        """Get instrument token for symbol."""
        # Try direct lookup first
        if symbol in self.symbol_to_token_map:
            return self.symbol_to_token_map[symbol]
        
        # Try without exchange prefix
        symbol_clean = symbol.split(':')[-1]
        if symbol_clean in self.symbol_to_token_map:
            return self.symbol_to_token_map[symbol_clean]
        
        raise ValueError(f"Symbol not found: {symbol}. Ensure instrument list is loaded.")
    
    def _get_exchange(self, symbol: str) -> str:
        """Extract exchange from symbol."""
        if ':' in symbol:
            return symbol.split(':')[0]
        
        # Default to NSE for EQ symbols
        if '-EQ' in symbol:
            return 'NSE'
        
        # Default to NFO for futures/options
        if any(x in symbol for x in ['FUT', 'CE', 'PE']):
            return 'NFO'
        
        return 'NSE'  # Default exchange
    
    def _get_trading_symbol(self, symbol: str) -> str:
        """Extract trading symbol (without exchange prefix)."""
        if ':' in symbol:
            return symbol.split(':')[1]
        return symbol
    
    def _map_variety(self, product: str) -> str:
        """Map product type to Angel One variety."""
        # Angel One varieties: NORMAL, AMO, BO, CO
        return "NORMAL"  # Default to regular orders
    
    def _map_product(self, product: str) -> str:
        """Map product type to Angel One constants."""
        # Map Zerodha products to Angel One
        product_map = {
            'MIS': 'INTRADAY',      # MIS -> Intraday
            'CNC': 'DELIVERY',      # CNC -> Delivery
            'NRML': 'CARRYFORWARD', # NRML -> Carry Forward
            'CO': 'CARRYFORWARD',   # CO -> Carry Forward
            'BO': 'CARRYFORWARD'    # BO -> Carry Forward
        }
        return product_map.get(product.upper(), 'INTRADAY')
    
    def _map_order_type(self, order_type: str) -> str:
        """Map order type to Angel One constants."""
        order_type_map = {
            'MARKET': 'MARKET',
            'LIMIT': 'LIMIT',
            'SL': 'STOPLOSS_LIMIT',
            'SL-M': 'STOPLOSS_MARKET'
        }
        return order_type_map.get(order_type.upper(), 'MARKET')
    
    def _map_transaction_type(self, side: str) -> str:
        """Map transaction type to Angel One format."""
        return 'B' if side.upper() == 'BUY' else 'S'
    
    def _map_interval(self, interval: str) -> str:
        """Map interval to Angel One format."""
        interval_map = {
            '1m': 'ONE_MINUTE',
            '5m': 'FIVE_MINUTE',
            '15m': 'FIFTEEN_MINUTE',
            '30m': 'THIRTY_MINUTE',
            '1h': 'ONE_HOUR',
            'D': 'ONE_DAY'
        }
        return interval_map.get(interval, 'FIVE_MINUTE')
    
    def _reverse_map_order_type(self, angel_order_type: str) -> str:
        """Reverse map Angel One order type to standard format."""
        reverse_map = {
            'MARKET': 'MARKET',
            'LIMIT': 'LIMIT',
            'STOPLOSS_LIMIT': 'SL',
            'STOPLOSS_MARKET': 'SL-M'
        }
        return reverse_map.get(angel_order_type, 'MARKET')
    
    def _reverse_map_product(self, angel_product: str) -> str:
        """Reverse map Angel One product to standard format."""
        reverse_map = {
            'INTRADAY': 'MIS',
            'DELIVERY': 'CNC',
            'CARRYFORWARD': 'NRML'
        }
        return reverse_map.get(angel_product, 'MIS')


def create_angelone_broker(
    api_key: str = None,
    secret_key: str = None,
    client_id: str = None,
    totp_seed: str = None
) -> AngelOneBroker:
    """
    Convenience function to create Angel One broker instance.
    
    Args:
        api_key: SmartAPI API key (optional, uses env if not provided)
        secret_key: SmartAPI API secret (optional, uses env if not provided)
        client_id: Angel One Client ID (optional, uses env if not provided)
        totp_seed: TOTP seed for automated login (optional, uses env if not provided)
    
    Returns:
        Connected AngelOneBroker instance
    
    Example:
        >>> broker = create_angelone_broker()
        >>> positions = broker.get_positions()
    """
    broker = AngelOneBroker(
        api_key=api_key,
        secret_key=secret_key,
        client_id=client_id,
        totp_seed=totp_seed
    )
    
    broker.connect()
    return broker

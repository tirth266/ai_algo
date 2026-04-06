"""
Broker Interface Module

Abstract interface for broker connections.

Methods:
- connect()
- place_order()
- cancel_order()
- get_positions()
- get_account_balance()
- get_open_orders()

Designed for easy extension to multiple brokers.

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Order:
    """
    Represent a trading order.
    
    Attributes:
        symbol: Trading symbol (e.g., 'RELIANCE')
        quantity: Number of shares/units
        side: 'BUY' or 'SELL'
        order_type: 'MARKET', 'LIMIT', 'SL', 'SL-M'
        price: Limit/stop price (optional)
        product: Product type ('MIS', 'CNC', 'NRML')
        status: Order status
        order_id: Broker order ID
        timestamp: Order creation time
    """
    
    def __init__(
        self,
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = 'MARKET',
        price: Optional[float] = None,
        product: str = 'MIS',
        stop_loss: Optional[float] = None,
        target: Optional[float] = None
    ):
        """
        Initialize order object.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            side: 'BUY' or 'SELL'
            order_type: Order type
            price: Limit/stop price
            product: Product type
            stop_loss: Stop loss price
            target: Target price
        """
        self.symbol = symbol
        self.quantity = quantity
        self.side = side.upper()
        self.order_type = order_type.upper()
        self.price = price
        self.product = product.upper()
        self.stop_loss = stop_loss
        self.target = target
        
        # Runtime attributes
        self.order_id: Optional[str] = None
        self.status: str = 'PENDING'
        self.average_price: float = 0.0
        self.filled_quantity: int = 0
        self.pending_quantity: int = quantity
        self.timestamp: datetime = datetime.now()
        self.exchange_order_id: Optional[str] = None
        
        logger.debug(f"Order created: {self}")
    
    def __repr__(self):
        return f"Order({self.symbol}, {self.side}, {self.quantity}, {self.order_type})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side,
            'order_type': self.order_type,
            'price': self.price,
            'product': self.product,
            'stop_loss': self.stop_loss,
            'target': self.target,
            'order_id': self.order_id,
            'status': self.status,
            'average_price': self.average_price,
            'filled_quantity': self.filled_quantity,
            'pending_quantity': self.pending_quantity,
            'timestamp': self.timestamp.isoformat(),
            'exchange_order_id': self.exchange_order_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Create order from dictionary."""
        order = cls(
            symbol=data['symbol'],
            quantity=data['quantity'],
            side=data['side'],
            order_type=data.get('order_type', 'MARKET'),
            price=data.get('price'),
            product=data.get('product', 'MIS'),
            stop_loss=data.get('stop_loss'),
            target=data.get('target')
        )
        order.order_id = data.get('order_id')
        order.status = data.get('status', 'PENDING')
        order.average_price = data.get('average_price', 0.0)
        order.filled_quantity = data.get('filled_quantity', 0)
        order.pending_quantity = data.get('pending_quantity', order.quantity)
        order.timestamp = datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
        order.exchange_order_id = data.get('exchange_order_id')
        return order


class Position:
    """
    Represent a trading position.
    
    Attributes:
        symbol: Trading symbol
        quantity: Net quantity (positive=long, negative=short)
        average_price: Average entry price
        last_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss
    """
    
    def __init__(
        self,
        symbol: str,
        quantity: int = 0,
        average_price: float = 0.0,
        last_price: float = 0.0
    ):
        """
        Initialize position object.
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity
            average_price: Average entry price
            last_price: Current market price
        """
        self.symbol = symbol
        self.quantity = quantity
        self.average_price = average_price
        self.last_price = last_price
        self.unrealized_pnl: float = 0.0
        self.realized_pnl: float = 0.0
    
    @property
    def value(self) -> float:
        """Calculate position value."""
        return abs(self.quantity) * self.last_price
    
    @property
    def pnl(self) -> float:
        """Calculate total PnL (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    def update_pnl(self, last_price: float):
        """Update unrealized PnL based on current price."""
        self.last_price = last_price
        
        if self.quantity != 0:
            if self.quantity > 0:  # Long
                self.unrealized_pnl = (last_price - self.average_price) * self.quantity
            else:  # Short
                self.unrealized_pnl = (self.average_price - last_price) * abs(self.quantity)
    
    def __repr__(self):
        return f"Position({self.symbol}, qty={self.quantity}, avg={self.average_price:.2f})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'average_price': self.average_price,
            'last_price': self.last_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'value': self.value,
            'pnl': self.pnl
        }


class BrokerInterface(ABC):
    """
    Abstract base class for broker implementations.
    
    All broker implementations must inherit from this class
    and implement all abstract methods.
    
    Usage:
        class ZerodhaBroker(BrokerInterface):
            def connect(self): ...
            def place_order(self, order): ...
            # etc.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize broker interface.
        
        Args:
            config: Broker configuration dictionary
        """
        self.config = config or {}
        self.connected: bool = False
        self.user_id: Optional[str] = None
        
        logger.info(f"Broker interface initialized: {self.__class__.__name__}")
    
    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """
        Connect to broker API.
        
        Args:
            **kwargs: Broker-specific connection parameters
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from broker API."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        pass
    
    @abstractmethod
    def place_order(self, order: Order) -> Dict[str, Any]:
        """
        Place an order through the broker.
        
        Args:
            order: Order object to place
        
        Returns:
            Dictionary with order response including order_id
        
        Raises:
            OrderError: If order placement fails
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            order_id: Broker order ID to cancel
        
        Returns:
            Dictionary with cancellation response
        
        Raises:
            OrderError: If cancellation fails
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects
        
        Raises:
            APIError: If API call fails
        """
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get account balance and margins.
        
        Returns:
            Dictionary with balance information
        
        Raises:
            APIError: If API call fails
        """
        pass
    
    @abstractmethod
    def get_open_orders(self) -> List[Order]:
        """
        Get all open/pending orders.
        
        Returns:
            List of Order objects
        
        Raises:
            APIError: If API call fails
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        """
        pass
    
    @abstractmethod
    def get_ltp(self, symbol: str) -> float:
        """
        Get last traded price.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Last traded price
        
        Raises:
            APIError: If API call fails
        """
        pass
    
    def _validate_order(self, order: Order):
        """Validate order before placement."""
        if order.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if order.side not in ['BUY', 'SELL']:
            raise ValueError("Side must be 'BUY' or 'SELL'")
        
        if order.order_type not in ['MARKET', 'LIMIT', 'SL', 'SL-M']:
            raise ValueError("Invalid order type")
        
        if order.order_type == 'LIMIT' and order.price is None:
            raise ValueError("Price required for LIMIT order")
        
        logger.debug(f"Order validated: {order.symbol}")


class OrderError(Exception):
    """Exception raised for order-related errors."""
    pass


class APIError(Exception):
    """Exception raised for API-related errors."""
    pass


class ConnectionError(Exception):
    """Exception raised for connection-related errors."""
    pass

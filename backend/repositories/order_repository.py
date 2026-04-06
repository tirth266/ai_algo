"""
Order Repository

Database operations for Order model.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.order import Order, OrderStatus, OrderType


class OrderRepository:
    """
    Repository for order database operations.
    
    Provides CRUD operations and queries for orders.
    """
    
    def __init__(self, session: Session):
        """
        Initialize order repository.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = 'market',
        strategy_name: str = None,
        exchange: str = 'NSE'
    ) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            quantity: Number of shares
            price: Order price
            order_type: Type of order (market, limit, etc.)
            strategy_name: Name of strategy
            exchange: Exchange (default: 'NSE')
        
        Returns:
            Created Order instance
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            order_type=OrderType[order_type.upper()] if isinstance(order_type, str) else order_type,
            strategy_name=strategy_name,
            exchange=exchange
        )
        
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        
        return order
    
    def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order instance or None
        """
        return self.session.query(Order).filter(Order.id == order_id).first()
    
    def get_order_by_broker_id(self, broker_order_id: str) -> Optional[Order]:
        """
        Get order by broker order ID.
        
        Args:
            broker_order_id: Broker order ID
        
        Returns:
            Order instance or None
        """
        return self.session.query(Order).filter(
            Order.broker_order_id == broker_order_id
        ).first()
    
    def get_orders(
        self,
        symbol: str = None,
        status: OrderStatus = None,
        strategy_name: str = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders with optional filters.
        
        Args:
            symbol: Filter by symbol
            status: Filter by status
            strategy_name: Filter by strategy name
            limit: Maximum number of orders to return
        
        Returns:
            List of Order instances
        """
        query = self.session.query(Order)
        
        if symbol:
            query = query.filter(Order.symbol == symbol)
        
        if status:
            query = query.filter(Order.status == status)
        
        if strategy_name:
            query = query.filter(Order.strategy_name == strategy_name)
        
        query = query.order_by(desc(Order.created_at)).limit(limit)
        
        return query.all()
    
    def update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
        broker_order_id: str = None
    ) -> Optional[Order]:
        """
        Update order status.
        
        Args:
            order_id: Order ID
            status: New status
            broker_order_id: Broker order ID (optional)
        
        Returns:
            Updated Order instance or None
        """
        order = self.get_order_by_id(order_id)
        
        if order:
            order.status = status
            if broker_order_id:
                order.broker_order_id = broker_order_id
            
            self.session.commit()
            self.session.refresh(order)
        
        return order
    
    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
        
        Returns:
            True if cancelled, False otherwise
        """
        order = self.get_order_by_id(order_id)
        
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            self.session.commit()
            return True
        
        return False
    
    def get_pending_orders(self, symbol: str = None) -> List[Order]:
        """
        Get pending orders.
        
        Args:
            symbol: Filter by symbol (optional)
        
        Returns:
            List of pending Order instances
        """
        query = self.session.query(Order).filter(
            Order.status == OrderStatus.PENDING
        )
        
        if symbol:
            query = query.filter(Order.symbol == symbol)
        
        return query.all()
    
    def count_orders(
        self,
        symbol: str = None,
        status: OrderStatus = None
    ) -> int:
        """
        Count orders with optional filters.
        
        Args:
            symbol: Filter by symbol
            status: Filter by status
        
        Returns:
            Number of orders
        """
        query = self.session.query(Order)
        
        if symbol:
            query = query.filter(Order.symbol == symbol)
        
        if status:
            query = query.filter(Order.status == status)
        
        return query.count()
    
    def delete_order(self, order_id: int) -> bool:
        """
        Delete an order.
        
        Args:
            order_id: Order ID
        
        Returns:
            True if deleted, False otherwise
        """
        order = self.get_order_by_id(order_id)
        
        if order:
            self.session.delete(order)
            self.session.commit()
            return True
        
        return False

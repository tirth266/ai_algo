"""
Order Manager Module

Manage live orders with:
- Order submission queue
- Retry logic
- Partial fill handling
- Order cancellation
- Order tracking

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque
import time

from .broker_interface import BrokerInterface, Order, OrderError, APIError

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manage live order execution and tracking.
    
    Features:
    - Asynchronous order submission
    - Automatic retry on failures
    - Partial fill monitoring
    - Order state tracking
    - Queue management
    
    Usage:
        >>> manager = OrderManager(broker)
        >>> order = Order(symbol="RELIANCE", quantity=10, side="BUY")
        >>> result = await manager.submit_order(order)
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_pending_orders: int = 100
    ):
        """
        Initialize order manager.
        
        Args:
            broker: Broker instance for order execution
            max_retries: Maximum retry attempts for failed orders
            retry_delay: Delay between retries in seconds
            max_pending_orders: Maximum pending orders in queue
        """
        self.broker = broker
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_pending_orders = max_pending_orders
        
        # Order queues
        self.pending_queue: deque = deque(maxlen=max_pending_orders)
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: Dict[str, Order] = {}
        self.failed_orders: deque = deque(maxlen=100)
        
        # Statistics
        self.total_submitted = 0
        self.total_executed = 0
        self.total_failed = 0
        self.total_cancelled = 0
        
        logger.info("OrderManager initialized")
    
    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """
        Submit order for execution with retry logic.
        
        Args:
            order: Order to submit
        
        Returns:
            Execution result dictionary
        
        Example:
            >>> order = Order(symbol="TCS", quantity=5, side="BUY")
            >>> result = await manager.submit_order(order)
        """
        self.total_submitted += 1
        
        # Add to pending queue
        self.pending_queue.append(order)
        logger.info(f"Order submitted to queue: {order}")
        
        # Attempt execution with retries
        for attempt in range(self.max_retries):
            try:
                # Place order through broker
                response = self.broker.place_order(order)
                
                # Update order status
                order.order_id = response.get('order_id')
                order.status = 'OPEN'
                
                # Move to active orders
                if order.order_id:
                    self.active_orders[order.order_id] = order
                
                # Remove from pending queue
                if order in self.pending_queue:
                    self.pending_queue.remove(order)
                
                logger.info(f"Order executed successfully: {order.order_id}")
                return {
                    'status': 'SUCCESS',
                    'order_id': order.order_id,
                    'message': 'Order placed successfully'
                }
            
            except (OrderError, APIError) as e:
                logger.warning(
                    f"Order execution failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{str(e)}"
                )
                
                if attempt < self.max_retries - 1:
                    # Wait before retry
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final failure
                    order.status = 'REJECTED'
                    self.failed_orders.append(order)
                    self.total_failed += 1
                    
                    logger.error(f"Order failed after {self.max_retries} attempts: {order.symbol}")
                    return {
                        'status': 'FAILED',
                        'error': str(e),
                        'attempts': self.max_retries
                    }
        
        return {'status': 'FAILED', 'error': 'Max retries exceeded'}
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation result
        
        Example:
            >>> result = await manager.cancel_order('order_123')
        """
        try:
            # Check if order exists
            if order_id not in self.active_orders:
                return {
                    'status': 'NOT_FOUND',
                    'message': f'Order {order_id} not found'
                }
            
            order = self.active_orders[order_id]
            
            # Cancel through broker
            response = self.broker.cancel_order(order_id)
            
            # Update order status
            order.status = 'CANCELLED'
            
            # Move to completed
            self.completed_orders[order_id] = order
            del self.active_orders[order_id]
            self.total_cancelled += 1
            
            logger.info(f"Order cancelled: {order_id}")
            return {
                'status': 'CANCELLED',
                'order_id': order_id
            }
        
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {str(e)}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def monitor_order(self, order_id: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Monitor order status until completion or timeout.
        
        Args:
            order_id: Order ID to monitor
            timeout: Monitoring timeout in seconds
        
        Returns:
            Final order status
        
        Example:
            >>> result = await manager.monitor_order('order_123', timeout=60)
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Get order history
                history = self.broker.get_order_history(order_id)
                
                if not history:
                    logger.warning(f"No history found for order: {order_id}")
                    await asyncio.sleep(2)
                    continue
                
                latest_status = history[-1]['status']
                
                # Update local order
                if order_id in self.active_orders:
                    order = self.active_orders[order_id]
                    order.status = latest_status
                    order.filled_quantity = history[-1].get('filled_quantity', 0)
                    order.average_price = history[-1].get('average_price', 0.0)
                
                # Check if complete
                if latest_status in ['COMPLETE', 'CANCELLED', 'REJECTED']:
                    logger.info(f"Order {order_id} reached terminal state: {latest_status}")
                    
                    if order_id in self.active_orders:
                        order = self.active_orders.pop(order_id)
                        self.completed_orders[order_id] = order
                    
                    return {
                        'order_id': order_id,
                        'status': latest_status,
                        'history': history
                    }
                
                # Wait before next check
                await asyncio.sleep(2)
            
            except Exception as e:
                logger.error(f"Error monitoring order {order_id}: {str(e)}")
                await asyncio.sleep(5)
        
        logger.warning(f"Order monitoring timeout: {order_id}")
        return {
            'order_id': order_id,
            'status': 'TIMEOUT',
            'message': 'Monitoring timeout exceeded'
        }
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return list(self.active_orders.values())
    
    def get_pending_count(self) -> int:
        """Get count of pending orders in queue."""
        return len(self.pending_queue)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get order execution statistics."""
        return {
            'total_submitted': self.total_submitted,
            'total_executed': self.total_executed,
            'total_failed': self.total_failed,
            'total_cancelled': self.total_cancelled,
            'active_orders': len(self.active_orders),
            'pending_queue': len(self.pending_queue),
            'success_rate': (
                self.total_executed / self.total_submitted * 100
                if self.total_submitted > 0 else 0
            )
        }
    
    def clear_completed(self, older_than_seconds: int = 3600):
        """Clear completed orders older than specified time."""
        cutoff = datetime.now().timestamp() - older_than_seconds
        
        to_remove = []
        for order_id, order in self.completed_orders.items():
            if order.timestamp.timestamp() < cutoff:
                to_remove.append(order_id)
        
        for order_id in to_remove:
            del self.completed_orders[order_id]
        
        logger.info(f"Cleared {len(to_remove)} completed orders")

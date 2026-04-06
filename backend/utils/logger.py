"""
Centralized Logging System

Configures application-wide logging with multiple handlers.
Supports console, file, and rotating file handlers.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import sys

# Create logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


def setup_logging(log_level: str = 'INFO', log_format: str = None) -> None:
    """
    Setup application-wide logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
    """
    
    # Get log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Default log format
    if not log_format:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    
    # Create formatter
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Main log file handler (rotating)
    main_log_file = os.path.join(LOGS_DIR, 'trading.log')
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error log file (separate)
    error_log_file = os.path.join(LOGS_DIR, 'errors.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Orders log file (trading-specific)
    orders_log_file = os.path.join(LOGS_DIR, 'orders.log')
    orders_handler = TimedRotatingFileHandler(
        orders_log_file,
        when='D',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    orders_handler.setLevel(logging.INFO)
    orders_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    orders_handler.setFormatter(orders_formatter)
    
    # Create orders logger
    orders_logger = logging.getLogger('orders')
    orders_logger.addHandler(orders_handler)
    orders_logger.propagate = False
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"Logging initialized - Level: {log_level}")
    logger.info(f"Log directory: {LOGS_DIR}")
    logger.info(f"Main log: {main_log_file}")
    logger.info(f"Error log: {error_log_file}")
    logger.info(f"Orders log: {orders_log_file}")
    logger.info("=" * 80)


def get_trading_logger(name: str = 'trading') -> logging.Logger:
    """
    Get a trading-specific logger.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_trade(logger: logging.Logger, action: str, symbol: str, 
              quantity: int, price: float, pnl: float = None, 
              order_id: str = None, strategy: str = None):
    """
    Log a trading action in structured format.
    
    Args:
        logger: Logger instance
        action: Action type (BUY, SELL, CLOSE, etc.)
        symbol: Stock symbol
        quantity: Trade quantity
        price: Trade price
        pnl: Profit/Loss (if applicable)
        order_id: Order ID
        strategy: Strategy name
    """
    log_data = {
        'action': action,
        'symbol': symbol,
        'quantity': quantity,
        'price': f"₹{price:.2f}",
    }
    
    if pnl is not None:
        log_data['pnl'] = f"₹{pnl:.2f} ({(pnl/price)*100:.2f}%)"
    
    if order_id:
        log_data['order_id'] = order_id
    
    if strategy:
        log_data['strategy'] = strategy
    
    # Format as key=value pairs
    log_message = ' | '.join([f"{k}={v}" for k, v in log_data.items()])
    
    logger.info(f"TRADE: {log_message}")


if __name__ == "__main__":
    # Test logging system
    setup_logging(log_level='DEBUG')
    
    logger = get_trading_logger('test')
    
    print("Testing logging system...")
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    
    # Test trade logging
    log_trade(
        logger,
        action='BUY',
        symbol='RELIANCE',
        quantity=100,
        price=2500.00,
        order_id='ORD123',
        strategy='TestStrategy'
    )
    
    print(f"\n✓ Logging test complete!")
    print(f"Check logs in: {LOGS_DIR}")

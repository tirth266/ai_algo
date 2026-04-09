"""
Centralized JSON logging setup with rotating file handlers.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from .alert_manager import TelegramAlertHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

SENSITIVE_FIELDS = {
    'password',
    'token',
    'auth_token',
    'api_key',
    'access_token',
    'refresh_token',
    'secret',
    'credentials',
    'ssn',
    'card_number',
    'cvv',
}

STANDARD_RECORD_KEYS = {
    'name',
    'msg',
    'args',
    'levelname',
    'levelno',
    'pathname',
    'filename',
    'module',
    'exc_info',
    'exc_text',
    'stack_info',
    'lineno',
    'funcName',
    'created',
    'msecs',
    'relativeCreated',
    'thread',
    'threadName',
    'processName',
    'process',
    'message',
    'asctime',
}


class JsonLogFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'module': record.name.split('.')[-1],
            'logger': record.name,
            'message': record.getMessage(),
            'extra': self._extract_extra(record),
        }

        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)

    def _extract_extra(self, record: logging.LogRecord) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in STANDARD_RECORD_KEYS or key.startswith('_'):
                continue
            extra[key] = self._redact_sensitive(key, value)
        return extra

    def _redact_sensitive(self, key: str, value: Any) -> Any:
        lowered = key.lower()
        if lowered in SENSITIVE_FIELDS:
            return 'REDACTED'
        if isinstance(value, str) and any(field in lowered for field in SENSITIVE_FIELDS):
            return 'REDACTED'
        return value


class TradeEventFilter(logging.Filter):
    """Allow only trade-specific logger records to pass."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == 'trade'


def setup_logging(log_level: str = 'INFO', logs_dir: str = None) -> None:
    """Initialize structured logging with rotating JSON files."""
    if logs_dir:
        logs_dir = os.path.abspath(logs_dir)
    else:
        logs_dir = LOGS_DIR

    os.makedirs(logs_dir, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = JsonLogFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    app_log_file = os.path.join(logs_dir, 'app.log')
    app_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    error_log_file = os.path.join(logs_dir, 'errors.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    try:
        telegram_handler = TelegramAlertHandler()
        telegram_handler.setLevel(logging.ERROR)
        telegram_handler.setFormatter(formatter)
        root_logger.addHandler(telegram_handler)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            'Failed to initialize Telegram alert handler: %s', exc
        )

    trade_log_file = os.path.join(logs_dir, 'trades.log')
    trade_handler = RotatingFileHandler(
        trade_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.setFormatter(formatter)
    trade_handler.addFilter(TradeEventFilter())

    trade_logger = logging.getLogger('trade')
    trade_logger.handlers.clear()
    trade_logger.setLevel(logging.INFO)
    trade_logger.addHandler(trade_handler)
    trade_logger.propagate = True

    root_logger.info('Logging initialized')
    root_logger.info('Log directory: %s', logs_dir)
    root_logger.info('App log: %s', app_log_file)
    root_logger.info('Error log: %s', error_log_file)
    root_logger.info('Trade log: %s', trade_log_file)


def get_trading_logger(name: str = 'trading') -> logging.Logger:
    """Return a consistent logger for application modules."""
    return logging.getLogger(name)


def get_trade_logger() -> logging.Logger:
    """Return the trade event logger that writes to trades.log."""
    return logging.getLogger('trade')


def log_trade(
    logger: logging.Logger,
    action: str,
    symbol: str,
    quantity: int,
    price: float,
    pnl: float = None,
    order_id: str = None,
    strategy: str = None,
) -> None:
    """Log trading activity to the trade logger in structured JSON format."""
    log_data = {
        'action': action,
        'symbol': symbol,
        'quantity': quantity,
        'price': round(price, 2),
    }

    if pnl is not None:
        log_data['pnl'] = round(pnl, 2)

    if order_id:
        log_data['order_id'] = order_id

    if strategy:
        log_data['strategy'] = strategy

    logger.info('trade_event', extra={'trade_event': log_data})


if __name__ == '__main__':
    setup_logging(log_level='DEBUG')
    logger = get_trading_logger('test')

    logger.debug('This is a DEBUG message')
    logger.info('This is an INFO message')
    logger.warning('This is a WARNING message')
    logger.error('This is an ERROR message')

    trade_logger = get_trade_logger()
    log_trade(
        trade_logger,
        action='BUY',
        symbol='RELIANCE',
        quantity=100,
        price=2500.00,
        pnl=150.00,
        order_id='ORD123',
        strategy='TestStrategy',
    )

    print(f'✓ Logging test complete. Check logs in: {LOGS_DIR}')

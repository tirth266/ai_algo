"""
Core Backend Module

Contains trading system core components.
"""

from .trade_logger import TradeLogger
from .signal_logger import SignalLogger
from .trade_journal import TradeJournal
from .journal_integration import JournalIntegration, get_journal_integration

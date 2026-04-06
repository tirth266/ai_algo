"""
Indicator Engine Module

Technical indicators for trading strategy development.

Components:
- Supertrend: ATR-based trend following indicator
- Trendline: Dynamic support/resistance from pivot points
- Liquidity: Liquidity pool detection and sweep identification
- IndicatorManager: Central orchestrator for all indicators

Usage:
    >>> from indicators import get_indicator_manager
    >>> manager = get_indicator_manager()
    >>> result = manager.supertrend(candles)
"""

from .supertrend import supertrend, get_supertrend_signal
from .trendline import get_trendline_signal, calculate_trendline_channels, detect_breakouts
from .liquidity import get_liquidity_signal, identify_liquidity_levels, detect_sweeps
from .indicator_manager import IndicatorManager, get_indicator_manager

__all__ = [
    # Main manager
    'IndicatorManager',
    'get_indicator_manager',
    
    # Supertrend
    'supertrend',
    'get_supertrend_signal',
    
    # Trendline
    'get_trendline_signal',
    'calculate_trendline_channels',
    'detect_breakouts',
    
    # Liquidity
    'get_liquidity_signal',
    'identify_liquidity_levels',
    'detect_sweeps',
]

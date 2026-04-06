"""
Time Utilities Module

Time-related helper functions for the trading engine.

Features:
- Market hours detection
- Session management
- Timezone conversions
- Timestamp formatting

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from datetime import datetime, time
import pytz
import logging

logger = logging.getLogger(__name__)


class MarketHours:
    """
    Market hours utilities for Indian stock market (NSE/BSE).
    
    Market timings:
    - Open: 09:15 AM IST
    - Close: 03:30 PM IST
    - Pre-open: 09:00 - 09:08 AM
    """
    
    # Indian timezone
    IST = pytz.timezone('Asia/Kolkata')
    
    # Market hours
    MARKET_OPEN = time(9, 15)  # 9:15 AM
    MARKET_CLOSE = time(15, 30)  # 3:30 PM
    
    @classmethod
    def is_market_open(cls, check_time: datetime = None) -> bool:
        """
        Check if market is currently open.
        
        Args:
            check_time: Time to check (default: now)
        
        Returns:
            True if market is open
        
        Example:
            >>> if MarketHours.is_market_open():
            ...     # Safe to trade
        """
        if check_time is None:
            check_time = datetime.now(cls.IST)
        else:
            check_time = check_time.astimezone(cls.IST)
        
        # Check if weekend
        if check_time.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check time of day
        current_time = check_time.time()
        
        return cls.MARKET_OPEN <= current_time <= cls.MARKET_CLOSE
    
    @classmethod
    def get_next_open(cls, from_time: datetime = None) -> datetime:
        """
        Get next market open time.
        
        Args:
            from_time: Starting time (default: now)
        
        Returns:
            Next market open datetime
        """
        if from_time is None:
            from_time = datetime.now(cls.IST)
        else:
            from_time = from_time.astimezone(cls.IST)
        
        # If currently market hours, return now
        if cls.is_market_open(from_time):
            return from_time
        
        # If weekend, move to Monday
        if from_time.weekday() >= 5:
            days_to_add = 7 - from_time.weekday()
            next_open = from_time.replace(
                hour=cls.MARKET_OPEN.hour,
                minute=cls.MARKET_OPEN.minute,
                second=0,
                microsecond=0
            )
            from datetime import timedelta
            next_open += timedelta(days=days_to_add)
            return next_open
        
        # If after hours, move to next day
        next_open = from_time.replace(
            hour=cls.MARKET_OPEN.hour,
            minute=cls.MARKET_OPEN.minute,
            second=0,
            microsecond=0
        )
        
        if from_time.time() > cls.MARKET_CLOSE:
            from datetime import timedelta
            next_open += timedelta(days=1)
            
            # Skip weekends
            if next_open.weekday() >= 5:
                next_open += timedelta(days=(7 - next_open.weekday()))
        
        return next_open
    
    @classmethod
    def get_minutes_to_close(cls, check_time: datetime = None) -> int:
        """
        Get minutes remaining until market close.
        
        Args:
            check_time: Time to check (default: now)
        
        Returns:
            Minutes to close (0 if closed)
        """
        if not cls.is_market_open(check_time):
            return 0
        
        if check_time is None:
            check_time = datetime.now(cls.IST)
        else:
            check_time = check_time.astimezone(cls.IST)
        
        close_time = check_time.replace(
            hour=cls.MARKET_CLOSE.hour,
            minute=cls.MARKET_CLOSE.minute,
            second=0,
            microsecond=0
        )
        
        diff = close_time - check_time
        return int(diff.total_seconds() / 60)


def to_ist(dt: datetime) -> datetime:
    """
    Convert datetime to Indian Standard Time.
    
    Args:
        dt: Datetime to convert
    
    Returns:
        IST datetime
    
    Example:
        >>> ist_time = to_ist(utc_time)
    """
    return dt.astimezone(MarketHours.IST)


def format_timestamp(dt: datetime, include_time: bool = True) -> str:
    """
    Format timestamp for display/logging.
    
    Args:
        dt: Datetime to format
        include_time: Include time in output
    
    Returns:
        Formatted string
    
    Example:
        >>> format = format_timestamp(datetime.now())
        '2026-03-16 15:30:45'
    """
    if include_time:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return dt.strftime('%Y-%m-%d')


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse timestamp string to datetime.
    
    Args:
        timestamp_str: Timestamp string
    
    Returns:
        Parsed datetime
    
    Example:
        >>> dt = parse_timestamp('2026-03-16 15:30:45')
    """
    try:
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return datetime.strptime(timestamp_str, '%Y-%m-%d')

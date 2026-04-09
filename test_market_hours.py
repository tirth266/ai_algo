#!/usr/bin/env python3
"""
Test script for market hours functionality
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend/engine"))

from guardian import is_market_open

if __name__ == "__main__":
    print("Testing market hours functionality...")
    print(f"Market open: {is_market_open()}")

    # Test with different times
    from datetime import datetime, time
    import pytz

    IST = pytz.timezone("Asia/Kolkata")

    # Test market open time
    test_time_open = datetime.now(IST).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    print(
        f"Test time (10:00 AM): {test_time_open.time()} -> Market open: {is_market_open()}"
    )

    # Test market close time
    test_time_close = datetime.now(IST).replace(
        hour=15, minute=30, second=0, microsecond=0
    )
    print(
        f"Test time (3:30 PM): {test_time_close.time()} -> Market open: {is_market_open()}"
    )

    # Test after market close
    test_time_after = datetime.now(IST).replace(
        hour=16, minute=0, second=0, microsecond=0
    )
    print(
        f"Test time (4:00 PM): {test_time_after.time()} -> Market open: {is_market_open()}"
    )

    # Test before market open
    test_time_before = datetime.now(IST).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    print(
        f"Test time (9:00 AM): {test_time_before.time()} -> Market open: {is_market_open()}"
    )

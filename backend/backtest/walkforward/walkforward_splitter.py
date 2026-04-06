"""
Walk-Forward Data Splitter Module

Splits historical data into rolling training and testing windows for walk-forward analysis.

Features:
- Rolling window splitting
- Configurable train/test sizes
- Multiple walk-forward cycles
- Automatic date alignment

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WalkForwardSplitter:
    """
    Split historical data into rolling training and testing windows.
    
    Generates multiple train/test splits using a rolling window approach,
    where the training window rolls forward through time and each split
    is followed by an out-of-sample test period.
    
    Usage:
        >>> splitter = WalkForwardSplitter(train_years=3, test_years=1)
        >>> splits = splitter.split(data=df)
        >>> for i, split in enumerate(splits):
        ...     train_data = split['train_data']
        ...     test_data = split['test_data']
    """
    
    def __init__(
        self,
        train_years: int = 3,
        test_years: int = 1,
        train_months: int = None,
        test_months: int = None,
        min_train_bars: int = 252,
        step_size: Optional[int] = None
    ):
        """
        Initialize walk-forward splitter.
        
        Args:
            train_years: Training window size in years (default: 3)
            test_years: Test window size in years (default: 1)
            train_months: Training window size in months (overrides train_years)
            test_months: Test window size in months (overrides test_years)
            min_train_bars: Minimum number of bars required for training
            step_size: Number of bars to roll forward each cycle (default: test window size)
        
        Example:
            >>> splitter = WalkForwardSplitter(
            ...     train_years=3,
            ...     test_years=1,
            ...     min_train_bars=500
            ... )
        """
        if train_months is not None:
            self.train_delta = timedelta(days=train_months * 30)
            self.train_label = f"{train_months}M"
        else:
            self.train_delta = timedelta(days=train_years * 365)
            self.train_label = f"{train_years}Y"
        
        if test_months is not None:
            self.test_delta = timedelta(days=test_months * 30)
            self.test_label = f"{test_months}M"
        else:
            self.test_delta = timedelta(days=test_years * 365)
            self.test_label = f"{test_years}Y"
        
        self.min_train_bars = min_train_bars
        self.step_size = step_size
        
        logger.info(
            f"WalkForwardSplitter initialized: "
            f"train={self.train_label}, test={self.test_label}"
        )
    
    def split(
        self,
        data: pd.DataFrame,
        min_cycles: int = 1,
        require_complete: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Split data into walk-forward train/test splits.
        
        Args:
            data: DataFrame with datetime index
            min_cycles: Minimum number of complete cycles required
            require_complete: If True, only return complete cycles (default: True)
        
        Returns:
            List of dictionaries containing:
            - 'train_data': Training DataFrame
            - 'test_data': Testing DataFrame
            - 'train_start': Training start date
            - 'train_end': Training end date
            - 'test_start': Test start date
            - 'test_end': Test end date
            - 'cycle': Cycle number
        
        Example:
            >>> splitter = WalkForwardSplitter(train_years=2, test_years=1)
            >>> splits = splitter.split(data)
            >>> print(f"Generated {len(splits)} cycles")
        """
        if data.empty:
            raise ValueError("Input data cannot be empty")
        
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")
        
        # Sort by date
        data = data.sort_index()
        
        # Get date range
        start_date = data.index[0]
        end_date = data.index[-1]
        total_days = (end_date - start_date).days
        
        # Calculate minimum required data
        min_required_days = (self.train_delta + self.test_delta).days * min_cycles
        
        if total_days < min_required_days:
            error_msg = (
                f"Insufficient data for {min_cycles} cycles. "
                f"Need {min_required_days} days, have {total_days} days."
            )
            if require_complete:
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)
        
        # Generate splits
        splits = []
        cycle = 0
        
        # First training window end
        current_train_end = start_date + self.train_delta
        
        while True:
            # Check if we have enough data for test period
            remaining_days = (end_date - current_train_end).days
            test_days_needed = self.test_delta.days
            
            if remaining_days < test_days_needed:
                if require_complete:
                    break
                elif remaining_days < self.test_delta.days // 2:
                    # At least half the test period
                    break
            
            # Define test end
            test_end = min(current_train_end + self.test_delta, end_date)
            
            # Get train and test data
            train_mask = (data.index >= start_date) & (data.index <= current_train_end)
            test_mask = (data.index > current_train_end) & (data.index <= test_end)
            
            train_data = data[train_mask]
            test_data = data[test_mask]
            
            # Validate minimum training bars
            if len(train_data) < self.min_train_bars:
                # Move to next window
                step = self._calculate_step(data, start_date, current_train_end)
                start_date += step
                current_train_end = start_date + self.train_delta
                continue
            
            # Validate minimum test bars
            if len(test_data) < 20:  # Minimum 20 bars for meaningful test
                break
            
            cycle += 1
            
            splits.append({
                'train_data': train_data.copy(),
                'test_data': test_data.copy(),
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0] if len(test_data) > 0 else None,
                'test_end': test_data.index[-1] if len(test_data) > 0 else None,
                'cycle': cycle
            })
            
            logger.info(
                f"Cycle {cycle}: Train [{train_data.index[0].date()} to "
                f"{train_data.index[-1].date()}], "
                f"Test [{len(test_data)} bars]"
            )
            
            # Roll forward
            step = self._calculate_step(data, start_date, current_train_end)
            start_date += step
            current_train_end = start_date + self.train_delta
            
            # Check if we've reached the end
            if current_train_end >= end_date:
                break
        
        if not splits:
            raise ValueError(
                f"No valid walk-forward splits generated. "
                f"Try reducing train_years or test_years."
            )
        
        logger.info(f"Generated {len(splits)} walk-forward cycles")
        return splits
    
    def _calculate_step(
        self,
        data: pd.DataFrame,
        window_start: datetime,
        window_end: datetime
    ) -> timedelta:
        """Calculate step size for rolling forward."""
        if self.step_size is not None:
            # Use fixed step size in days
            return timedelta(days=self.step_size)
        
        # Default: use test window size
        return self.test_delta
    
    def get_cycle_statistics(
        self,
        splits: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Generate statistics for each walk-forward cycle.
        
        Args:
            splits: List of walk-forward splits from split() method
        
        Returns:
            DataFrame with cycle statistics
        
        Example:
            >>> stats = splitter.get_cycle_statistics(splits)
            >>> print(stats[['cycle', 'train_bars', 'test_bars']])
        """
        stats = []
        
        for split in splits:
            stats.append({
                'cycle': split['cycle'],
                'train_start': split['train_start'],
                'train_end': split['train_end'],
                'test_start': split['test_start'],
                'test_end': split['test_end'],
                'train_bars': len(split['train_data']),
                'test_bars': len(split['test_data']),
                'train_days': (split['train_end'] - split['train_start']).days,
                'test_days': (split['test_end'] - split['test_start']).days if split['test_end'] else 0
            })
        
        return pd.DataFrame(stats)


def create_walkforward_splits(
    data: pd.DataFrame,
    train_years: int = 3,
    test_years: int = 1,
    min_cycles: int = 1
) -> List[Dict[str, Any]]:
    """
    Convenience function to create walk-forward splits.
    
    Args:
        data: DataFrame with datetime index
        train_years: Training window size in years
        test_years: Test window size in years
        min_cycles: Minimum number of cycles required
    
    Returns:
        List of walk-forward split dictionaries
    
    Example:
        >>> splits = create_walkforward_splits(df, train_years=2, test_years=1)
    """
    splitter = WalkForwardSplitter(
        train_years=train_years,
        test_years=test_years
    )
    
    return splitter.split(data, min_cycles=min_cycles)


def validate_walkforward_splits(
    splits: List[Dict[str, Any]],
    min_train_bars: int = 100,
    min_test_bars: int = 20
) -> Tuple[bool, str]:
    """
    Validate walk-forward splits meet minimum requirements.
    
    Args:
        splits: List of walk-forward splits
        min_train_bars: Minimum training bars per cycle
        min_test_bars: Minimum test bars per cycle
    
    Returns:
        Tuple of (is_valid, message)
    
    Example:
        >>> is_valid, msg = validate_walkforward_splits(splits)
        >>> if not is_valid:
        ...     print(f"Invalid splits: {msg}")
    """
    if not splits:
        return False, "No splits provided"
    
    for i, split in enumerate(splits):
        if len(split['train_data']) < min_train_bars:
            return False, f"Cycle {i+1}: Insufficient training bars ({len(split['train_data'])} < {min_train_bars})"
        
        if len(split['test_data']) < min_test_bars:
            return False, f"Cycle {i+1}: Insufficient test bars ({len(split['test_data'])} < {min_test_bars})"
    
    return True, f"All {len(splits)} cycles validated successfully"

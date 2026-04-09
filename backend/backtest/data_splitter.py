"""
Data Splitter for Proper Backtesting Validation

Implements train/test split for time series data to prevent data leakage:
- TRAIN set: Used for parameter optimization (grid search)
- TEST set: Used for final evaluation and Monte Carlo simulation

Ensures:
- No future data leaks into past decisions
- Strict time-series ordering
- Separate metrics for train and test performance
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TimeSeriesDataSplitter:
    """
    Splits time series data into train and test sets for proper backtesting validation.

    Methods:
    - simple_split: Basic train/test split by ratio
    - walk_forward_split: Rolling window walk-forward split
    - purged_kfold: Purged k-fold cross-validation (advanced)
    """

    def __init__(self):
        logger.info("TimeSeriesDataSplitter initialized")

    def simple_split(
        self, data: pd.DataFrame, train_ratio: float = 0.7
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split data into train and test sets maintaining time order.

        Args:
            data: Time series DataFrame with datetime index
            train_ratio: Proportion of data for training (default: 0.7)

        Returns:
            Tuple of (train_data, test_data)
        """
        if len(data) < 10:
            raise ValueError("Insufficient data for splitting (minimum 10 rows)")

        split_idx = int(len(data) * train_ratio)

        train_data = data.iloc[:split_idx].copy()
        test_data = data.iloc[split_idx:].copy()

        logger.info(
            f"Data split: {len(train_data)} train rows, {len(test_data)} test rows"
        )
        logger.info(f"Train period: {train_data.index[0]} to {train_data.index[-1]}")
        logger.info(f"Test period: {test_data.index[0]} to {test_data.index[-1]}")

        return train_data, test_data

    def walk_forward_split(
        self,
        data: pd.DataFrame,
        train_window: int,
        test_window: int,
        step_size: Optional[int] = None,
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create rolling walk-forward splits.

        Args:
            data: Time series DataFrame with datetime index
            train_window: Number of rows in each training window
            test_window: Number of rows in each test window
            step_size: How much to shift window each iteration (default: test_window)

        Returns:
            List of (train_data, test_data) tuples for each window
        """
        if step_size is None:
            step_size = test_window

        windows = []
        start_idx = 0

        while start_idx + train_window + test_window <= len(data):
            train_end = start_idx + train_window
            test_end = train_end + test_window

            train_data = data.iloc[start_idx:train_end].copy()
            test_data = data.iloc[train_end:test_end].copy()

            windows.append((train_data, test_data))
            start_idx += step_size

        logger.info(f"Created {len(windows)} walk-forward windows")
        logger.info(f"Each window: {train_window} train + {test_window} test rows")

        return windows

    def purged_kfold_split(
        self,
        data: pd.DataFrame,
        n_splits: int = 5,
        purge_size: int = 0,
        embargo_size: int = 0,
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Purged k-fold cross-validation for time series (prevents leakage from overlapping windows).

        Args:
            data: Time series DataFrame with datetime index
            n_splits: Number of folds
            purge_size: Number of rows to purge from each side of test set
            embargo_size: Number of rows to embargo after test set

        Returns:
            List of (train_data, test_data) tuples
        """
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")

        fold_size = len(data) // n_splits
        splits = []

        for i in range(n_splits):
            # Test set indices
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < n_splits - 1 else len(data)

            # Apply purge
            test_start_purged = test_start + purge_size
            test_end_purged = test_end - purge_size

            if test_start_purged >= test_end_purged:
                continue  # Skip if purge removes all test data

            # Train set: everything before and after test set (with embargo)
            train_before = data.iloc[: max(0, test_start_purged - embargo_size)]
            train_after = data.iloc[min(len(data), test_end_purged + embargo_size) :]
            train_data = pd.concat([train_before, train_after]).copy()

            # Test set
            test_data = data.iloc[test_start_purged:test_end_purged].copy()

            splits.append((train_data, test_data))
            logger.info(f"Fold {i + 1}: {len(train_data)} train, {len(test_data)} test")

        return splits


def prepare_data_for_backtesting(
    data: pd.DataFrame, split_method: str = "simple", **kwargs
) -> Dict[str, Any]:
    """
    Prepare data for backtesting with proper train/test separation.

    Args:
        data: Historical OHLCV DataFrame
        split_method: "simple", "walk_forward", or "purged_kfold"
        **kwargs: Additional arguments for split method

    Returns:
        Dictionary containing:
        - train_data: DataFrame for parameter optimization
        - test_data: DataFrame for final evaluation
        - splitter: The splitter instance used
        - split_info: Information about the split
    """
    splitter = TimeSeriesDataSplitter()

    if split_method == "simple":
        train_ratio = kwargs.get("train_ratio", 0.7)
        train_data, test_data = splitter.simple_split(data, train_ratio)
        split_info = {
            "method": "simple",
            "train_ratio": train_ratio,
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "train_period": f"{train_data.index[0]} to {train_data.index[-1]}",
            "test_period": f"{test_data.index[0]} to {test_data.index[-1]}",
        }

    elif split_method == "walk_forward":
        train_window = kwargs.get("train_window", 100)
        test_window = kwargs.get("test_window", 30)
        step_size = kwargs.get("step_size", test_window)
        windows = splitter.walk_forward_split(
            data, train_window, test_window, step_size
        )

        # For simplicity, return first window (can be modified to return all)
        train_data, test_data = (
            windows[0] if windows else (pd.DataFrame(), pd.DataFrame())
        )
        split_info = {
            "method": "walk_forward",
            "train_window": train_window,
            "test_window": test_window,
            "step_size": step_size,
            "total_windows": len(windows),
            "current_window": 1,
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "train_period": f"{train_data.index[0] if len(train_data) > 0 else 'N/A'} to {train_data.index[-1] if len(train_data) > 0 else 'N/A'}",
            "test_period": f"{test_data.index[0] if len(test_data) > 0 else 'N/A'} to {test_data.index[-1] if len(test_data) > 0 else 'N/A'}",
        }

    elif split_method == "purged_kfold":
        n_splits = kwargs.get("n_splits", 5)
        purge_size = kwargs.get("purge_size", 0)
        embargo_size = kwargs.get("embargo_size", 0)
        splits = splitter.purged_kfold_split(data, n_splits, purge_size, embargo_size)

        # Return first split
        train_data, test_data = (
            splits[0] if splits else (pd.DataFrame(), pd.DataFrame())
        )
        split_info = {
            "method": "purged_kfold",
            "n_splits": n_splits,
            "purge_size": purge_size,
            "embargo_size": embargo_size,
            "total_splits": len(splits),
            "current_split": 1,
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "train_period": f"{train_data.index[0] if len(train_data) > 0 else 'N/A'} to {train_data.index[-1] if len(train_data) > 0 else 'N/A'}",
            "test_period": f"{test_data.index[0] if len(test_data) > 0 else 'N/A'} to {test_data.index[-1] if len(test_data) > 0 else 'N/A'}",
        }

    else:
        raise ValueError(
            f"Unknown split method: {split_method}. Use 'simple', 'walk_forward', or 'purged_kfold'"
        )

    return {
        "train_data": train_data,
        "test_data": test_data,
        "splitter": splitter,
        "split_info": split_info,
    }


def run_grid_search_on_train(
    optimizer_func, train_data: pd.DataFrame, **kwargs
) -> Dict[str, Any]:
    """
    Run parameter grid search ONLY on training data.

    Args:
        optimizer_func: Function to run grid search (should accept data parameter)
        train_data: Training data DataFrame
        **kwargs: Additional arguments for optimizer

    Returns:
        Optimization results from training data
    """
    logger.info("Running grid search on TRAIN data only")

    # Temporarily replace data in kwargs with train_data
    # This assumes optimizer_func accepts a data parameter
    optimizer_kwargs = kwargs.copy()
    optimizer_kwargs["data"] = train_data

    # Run optimization
    results = optimizer_func(**optimizer_kwargs)

    logger.info(f"Grid search completed. Best params: {results.get('best_params', {})}")
    return results


def run_final_backtest_on_test(
    backtest_func, test_data: pd.DataFrame, best_params: Dict[str, Any], **kwargs
) -> Dict[str, Any]:
    """
    Run final backtest ONLY on test data with best parameters.

    Args:
        backtest_func: Function to run backtest
        test_data: Test data DataFrame
        best_params: Parameters selected from training
        **kwargs: Additional arguments for backtest

    Returns:
        Backtest results from test data
    """
    logger.info("Running final backtest on TEST data only with optimized parameters")

    # Temporarily replace data in kwargs with test_data
    backtest_kwargs = kwargs.copy()
    backtest_kwargs["data"] = test_data
    backtest_kwargs["strategy_params"] = best_params  # Pass optimized params

    # Run backtest
    results = backtest_func(**backtest_kwargs)

    logger.info(
        f"Final backtest completed. Test performance: {results.get('summary', {})}"
    )
    return results


def run_monte_carlo_on_test_results(
    monte_carlo_func, test_results: Dict[str, Any], **kwargs
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation ONLY on test results (shuffling trade sequence).

    Args:
        monte_carlo_func: Function to run Monte Carlo simulation
        test_results: Results from test backtest
        **kwargs: Additional arguments for Monte Carlo

    Returns:
        Monte Carlo simulation results
    """
    logger.info("Running Monte Carlo simulation on TEST results only")

    # Extract trades and equity curve from test results
    trades = test_results.get("trades", [])
    equity_curve = test_results.get("equity_curve", [])

    if not trades:
        logger.warning("No trades found in test results for Monte Carlo simulation")
        return monte_carlo_func(trades=[], equity_curve=[], **kwargs)

    # Run Monte Carlo on test trade sequence only
    monte_carlo_kwargs = kwargs.copy()
    monte_carlo_kwargs.update({"trades": trades, "equity_curve": equity_curve})

    results = monte_carlo_func(**monte_carlo_kwargs)

    logger.info(
        f"Monte Carlo simulation completed. Risk of ruin: {results.get('risk_of_ruin', 0):.2%}"
    )
    return results


# Example usage functions for integration with existing code
def integrate_with_existing_backtest_routes():
    """
    Example of how to integrate data splitting with existing backtest routes.
    This shows the proper flow:
    1. Split data into train/test
    2. Run grid search on train data only
    3. Run final backtest on test data only
    4. Run Monte Carlo on test results only
    """
    pass  # Implementation would go in the route handlers


if __name__ == "__main__":
    # Example usage
    import yfinance as yf

    # Load sample data
    data = yf.download("RELIANCE.NS", start="2023-01-01", end="2024-12-31")

    # Split data
    split_data = prepare_data_for_backtesting(
        data, split_method="simple", train_ratio=0.7
    )

    print(f"Split Info: {split_data['split_info']}")
    print(f"Train shape: {split_data['train_data'].shape}")
    print(f"Test shape: {split_data['test_data'].shape}")

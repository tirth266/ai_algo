"""
Data Separation and Validation Framework
Prevents data leakage in backtesting by implementing proper train/test splits.

Features:
- Time-series aware data splitting
- Train/test data separation
- Rolling window validation
- Walk-forward analysis support
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataSplitter:
    """
    Handles proper data separation to prevent overfitting and data leakage.

    Key principles:
    - Grid search and parameter tuning ONLY on TRAIN data
    - Final evaluation ONLY on unseen TEST data
    - Strict time-series ordering (no future data in past decisions)
    - Rolling window validation for robustness testing
    """

    def __init__(self, train_ratio: float = 0.7, shuffle: bool = False):
        """
        Initialize data splitter.

        Args:
            train_ratio: Fraction of data for training (default: 0.7)
            shuffle: Whether to shuffle data (False for time-series)
        """
        self.train_ratio = train_ratio
        self.shuffle = shuffle

        if not 0 < train_ratio < 1:
            raise ValueError("train_ratio must be between 0 and 1")

        logger.info(
            f"DataSplitter initialized: train_ratio={train_ratio}, shuffle={shuffle}"
        )

    def split_data(
        self, data: pd.DataFrame, split_date: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split data into train and test sets.

        Args:
            data: OHLCV DataFrame with datetime index
            split_date: Specific date to split on (YYYY-MM-DD)

        Returns:
            Tuple of (train_data, test_data)
        """
        try:
            if data.empty:
                raise ValueError("Data cannot be empty")

            # Ensure data is sorted by datetime
            if not isinstance(data.index, pd.DatetimeIndex):
                data = data.set_index("timestamp")
                data.index = pd.to_datetime(data.index)

            data = data.sort_index()

            if split_date:
                # Split on specific date
                split_dt = pd.to_datetime(split_date)
                train_data = data[data.index < split_dt]
                test_data = data[data.index >= split_dt]
            else:
                # Split by ratio
                split_idx = int(len(data) * self.train_ratio)
                train_data = data.iloc[:split_idx]
                test_data = data.iloc[split_idx:]

            if len(train_data) == 0 or len(test_data) == 0:
                raise ValueError("Split resulted in empty train or test set")

            logger.info(
                f"Data split: Train={len(train_data)} candles, Test={len(test_data)} candles"
            )
            logger.info(
                f"Train period: {train_data.index[0]} to {train_data.index[-1]}"
            )
            logger.info(f"Test period: {test_data.index[0]} to {test_data.index[-1]}")

            return train_data, test_data

        except Exception as e:
            logger.error(f"Data split failed: {str(e)}")
            raise

    def create_rolling_windows(
        self, data: pd.DataFrame, train_size: int, test_size: int, overlap: int = 0
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create rolling windows for walk-forward validation.

        Args:
            data: OHLCV DataFrame
            train_size: Number of candles in training window
            test_size: Number of candles in test window
            overlap: Number of overlapping candles between windows

        Returns:
            List of (train_window, test_window) tuples
        """
        try:
            if len(data) < train_size + test_size:
                raise ValueError("Data too small for specified window sizes")

            windows = []
            step_size = test_size - overlap

            for start_idx in range(
                0, len(data) - train_size - test_size + 1, step_size
            ):
                train_end = start_idx + train_size
                test_end = train_end + test_size

                train_window = data.iloc[start_idx:train_end]
                test_window = data.iloc[train_end:test_end]

                windows.append((train_window, test_window))

            logger.info(f"Created {len(windows)} rolling windows")
            return windows

        except Exception as e:
            logger.error(f"Rolling window creation failed: {str(e)}")
            raise

    def create_walk_forward_windows(
        self,
        data: pd.DataFrame,
        in_sample_days: int,
        out_of_sample_days: int,
        overlap_percent: float = 0.0,
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create walk-forward analysis windows based on calendar days.

        Args:
            data: OHLCV DataFrame with datetime index
            in_sample_days: Number of days for training
            out_of_sample_days: Number of days for testing
            overlap_percent: Percentage of overlap between windows (0.0-1.0)

        Returns:
            List of (train_window, test_window) tuples
        """
        try:
            # Ensure datetime index
            if not isinstance(data.index, pd.DatetimeIndex):
                data = data.set_index("timestamp")
                data.index = pd.to_datetime(data.index)

            data = data.sort_index()

            windows = []
            start_date = data.index[0].date()
            end_date = data.index[-1].date()

            current_start = start_date
            overlap_days = int(in_sample_days * overlap_percent)

            while True:
                # Calculate window dates
                train_end_date = current_start + timedelta(days=in_sample_days - 1)
                test_end_date = train_end_date + timedelta(days=out_of_sample_days)

                if test_end_date > end_date:
                    break

                # Extract windows
                train_window = data[
                    (data.index.date >= current_start)
                    & (data.index.date <= train_end_date)
                ]
                test_window = data[
                    (data.index.date > train_end_date)
                    & (data.index.date <= test_end_date)
                ]

                if len(train_window) > 0 and len(test_window) > 0:
                    windows.append((train_window, test_window))

                # Move to next window with overlap
                current_start = current_start + timedelta(
                    days=out_of_sample_days - overlap_days
                )

            logger.info(f"Created {len(windows)} walk-forward windows")
            return windows

        except Exception as e:
            logger.error(f"Walk-forward window creation failed: {str(e)}")
            raise


class ValidationBacktestEngine:
    """
    Backtest engine for validation phase - runs with fixed parameters on test data.
    """

    def __init__(self, base_engine_config: Dict[str, Any]):
        """
        Initialize validation backtest engine.

        Args:
            base_engine_config: Base configuration for InstitutionalBacktestEngine
        """
        self.base_config = base_engine_config.copy()
        logger.info("ValidationBacktestEngine initialized")

    def run_validation_backtest(
        self,
        symbol: str,
        timeframe: str,
        test_data: pd.DataFrame,
        strategy_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run backtest on test data with fixed parameters.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            test_data: Test dataset (OHLCV DataFrame)
            strategy_config: Fixed strategy parameters

        Returns:
            Backtest results dictionary
        """
        try:
            logger.info(
                f"Running validation backtest on test data: {len(test_data)} candles"
            )

            # Import the institutional backtest engine
            from .institutional_backtest_engine import InstitutionalBacktestEngine

            # Create engine with fixed config
            config = self.base_config.copy()
            config["verbose"] = False  # Reduce logging for validation runs

            engine = InstitutionalBacktestEngine(**config)

            # Run backtest on test data only
            # We'll need to modify the engine to accept DataFrame directly
            results = self._run_backtest_on_dataframe(
                engine, symbol, timeframe, test_data, strategy_config
            )

            logger.info(
                f"Validation backtest complete. Test P&L: ₹{results['total_pnl']:,.2f}"
            )

            return results

        except Exception as e:
            logger.error(f"Validation backtest failed: {str(e)}")
            raise

    def _run_backtest_on_dataframe(
        self,
        engine: Any,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
        strategy_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run backtest directly on DataFrame (bypassing data loading).

        This is a workaround - ideally we'd modify InstitutionalBacktestEngine
        to accept DataFrame directly.
        """
        try:
            # Reset engine state
            engine._reset_state()

            # Create strategy
            from strategies.combined_power_strategy import CombinedPowerStrategy

            config = strategy_config.copy()
            config.update({"symbol": symbol, "timeframe": timeframe})
            strategy = CombinedPowerStrategy(config)

            # Run simulation
            engine._run_strategy_simulation(strategy, data, symbol)

            # Close remaining positions
            engine._close_remaining_positions(data.iloc[-1])

            # Calculate metrics
            results = engine._calculate_performance(symbol)

            return results

        except Exception as e:
            logger.error(f"DataFrame backtest failed: {str(e)}")
            raise


class ValidationFramework:
    """
    Complete validation framework implementing proper data separation.
    """

    def __init__(
        self,
        train_ratio: float = 0.7,
        base_engine_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize validation framework.

        Args:
            train_ratio: Fraction of data for training
            base_engine_config: Base configuration for backtest engines
        """
        self.data_splitter = DataSplitter(train_ratio=train_ratio)
        self.base_config = base_engine_config or {
            "initial_capital": 100000.0,
            "capital_per_trade": 25000.0,
            "slippage_percent": 0.0005,
            "brokerage_per_trade": 20.0,
            "stop_loss_percent": 0.02,
            "take_profit_percent": 0.04,
            "max_positions": 5,
            "verbose": False,
        }
        self.validation_engine = ValidationBacktestEngine(self.base_config)

        logger.info("ValidationFramework initialized")

    def run_complete_validation(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        split_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run complete validation: grid search on train, final test on test data.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            data: Full OHLCV dataset
            param_grid: Parameter grid for optimization
            split_date: Specific split date (optional)

        Returns:
            Complete validation results with train and test performance
        """
        try:
            logger.info("Starting complete validation framework")

            # Split data
            train_data, test_data = self.data_splitter.split_data(data, split_date)

            # Run grid search on train data
            from .parameter_optimizer import ParameterOptimizer

            optimizer = ParameterOptimizer(base_config=self.base_config)

            train_results = optimizer.run_grid_search(
                symbol=symbol,
                timeframe=timeframe,
                start_date=train_data.index[0].strftime("%Y-%m-%d"),
                end_date=train_data.index[-1].strftime("%Y-%m-%d"),
                param_grid=param_grid,
                n_jobs=1,  # Sequential for now
                show_progress=False,
            )

            # Get best parameters
            best_params = train_results["best_params"]["params"]
            logger.info(f"Best parameters from training: {best_params}")

            # Run validation on test data with best parameters
            strategy_config = {"symbol": symbol, "timeframe": timeframe}
            strategy_config.update(best_params)

            test_results = self.validation_engine.run_validation_backtest(
                symbol=symbol,
                timeframe=timeframe,
                test_data=test_data,
                strategy_config=strategy_config,
            )

            # Compile final results
            validation_results = {
                "data_split": {
                    "train_period": {
                        "start": str(train_data.index[0]),
                        "end": str(train_data.index[-1]),
                        "candles": len(train_data),
                    },
                    "test_period": {
                        "start": str(test_data.index[0]),
                        "end": str(test_data.index[-1]),
                        "candles": len(test_data),
                    },
                },
                "optimization_results": {
                    "total_combinations": train_results["total_combinations"],
                    "successful_runs": train_results["successful_runs"],
                    "best_params": best_params,
                    "train_sharpe": train_results["best_params"]["sharpe_ratio"],
                    "train_pnl": train_results["best_params"]["net_profit"],
                },
                "validation_results": {
                    "test_sharpe": test_results.get("sharpe_ratio", 0),
                    "test_pnl": test_results.get("total_pnl", 0),
                    "test_win_rate": test_results.get("win_rate", 0),
                    "test_max_drawdown": test_results.get("max_drawdown", 0),
                    "test_total_trades": test_results.get("total_trades", 0),
                },
                "overfitting_check": self._calculate_overfitting_metrics(
                    train_results["best_params"], test_results
                ),
                "train_performance": train_results["best_params"],
                "test_performance": test_results,
            }

            logger.info("Complete validation framework finished")
            return validation_results

        except Exception as e:
            logger.error(f"Complete validation failed: {str(e)}")
            raise

    def _calculate_overfitting_metrics(
        self, train_results: Dict[str, Any], test_results: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate overfitting metrics comparing train vs test performance.

        Args:
            train_results: Results from training optimization
            test_results: Results from test validation

        Returns:
            Overfitting analysis metrics
        """
        try:
            train_sharpe = train_results.get("sharpe_ratio", 0)
            test_sharpe = test_results.get("sharpe_ratio", 0)

            train_pnl = train_results.get("net_profit", 0)
            test_pnl = test_results.get("total_pnl", 0)

            # Sharpe degradation
            sharpe_degradation = train_sharpe - test_sharpe

            # P&L degradation
            pnl_degradation = train_pnl - test_pnl

            # Overfitting ratio (higher = more overfitting)
            if test_sharpe > 0:
                overfitting_ratio = train_sharpe / test_sharpe
            else:
                overfitting_ratio = float("inf")

            return {
                "sharpe_degradation": sharpe_degradation,
                "pnl_degradation": pnl_degradation,
                "overfitting_ratio": overfitting_ratio,
                "is_overfitted": overfitting_ratio > 2.0,  # Arbitrary threshold
            }

        except Exception as e:
            logger.error(f"Overfitting calculation failed: {str(e)}")
            return {}

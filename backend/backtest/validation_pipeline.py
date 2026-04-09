"""
Backtesting Validation Pipeline

Implements proper data separation to prevent overfitting:
- TRAIN set: For parameter optimization (grid search)
- TEST set: For final evaluation

Workflow:
1. Split data chronologically (70% train, 30% test)
2. Run grid search ONLY on train data
3. Run final backtest ONLY on test data with best params
4. Run Monte Carlo ONLY on test results
5. Output separate train/test metrics

Walk-Forward Validation:
- Rolling window optimization
- Train on historical data, test on future data
- Ensures no future data leaks into past decisions
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional, Callable
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from itertools import product

logger = logging.getLogger(__name__)


@dataclass
class TrainTestSplit:
    """Container for train/test data split"""

    train_data: pd.DataFrame
    test_data: pd.DataFrame
    split_info: Dict[str, Any]


@dataclass
class ValidationResult:
    """Container for validation results"""

    train_performance: Dict[str, Any]
    test_performance: Dict[str, Any]
    best_params: Dict[str, Any]
    split_info: Dict[str, Any]
    monte_carlo_results: Optional[Dict[str, Any]] = None


class DataValidator:
    """
    Validates and splits historical data for backtesting.

    Ensures:
    - No future data leaks into past decisions
    - Strict time-series ordering
    - Proper train/test separation
    """

    def __init__(self, train_ratio: float = 0.7):
        """
        Initialize data validator.

        Args:
            train_ratio: Proportion of data for training (default: 0.7)
        """
        if not 0.5 <= train_ratio <= 0.95:
            raise ValueError("train_ratio must be between 0.5 and 0.95")
        self.train_ratio = train_ratio
        logger.info(f"DataValidator initialized with train_ratio={train_ratio}")

    def split_data(
        self, data: pd.DataFrame, train_ratio: Optional[float] = None
    ) -> TrainTestSplit:
        """
        Split data into train and test sets chronologically.

        Args:
            data: Time series DataFrame with datetime index
            train_ratio: Override default train ratio

        Returns:
            TrainTestSplit with train/test data
        """
        ratio = train_ratio or self.train_ratio

        if len(data) < 50:
            raise ValueError("Insufficient data (minimum 50 rows required)")

        split_idx = int(len(data) * ratio)

        train_data = data.iloc[:split_idx].copy()
        test_data = data.iloc[split_idx:].copy()

        split_info = {
            "method": "chronological_split",
            "train_ratio": ratio,
            "total_rows": len(data),
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "train_period": {
                "start": str(train_data.index[0]),
                "end": str(train_data.index[-1]),
            },
            "test_period": {
                "start": str(test_data.index[0]),
                "end": str(test_data.index[-1]),
            },
        }

        logger.info(f"Data split: {len(train_data)} train, {len(test_data)} test")

        return TrainTestSplit(
            train_data=train_data, test_data=test_data, split_info=split_info
        )


class GridSearchValidator:
    """
    Runs grid search ONLY on training data.

    Selects best parameters based on train performance.
    """

    def __init__(self):
        logger.info("GridSearchValidator initialized")

    def run_optimization(
        self,
        train_data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        backtest_func: Callable,
        backtest_kwargs: Optional[Dict[str, Any]] = None,
        metric: str = "sharpe_ratio",
        maximize: bool = True,
    ) -> Dict[str, Any]:
        """
        Run grid search on training data only.

        Args:
            train_data: Training DataFrame
            param_grid: Dictionary of parameter names to value lists
            backtest_func: Function to run backtest (signature: func(data, params, **kwargs))
            backtest_kwargs: Additional arguments for backtest function
            metric: Metric to optimize
            maximize: Whether to maximize (True) or minimize (False) the metric

        Returns:
            Optimization results with best parameters
        """
        backtest_kwargs = backtest_kwargs or {}

        if len(train_data) < 50:
            raise ValueError("Insufficient training data (minimum 50 rows)")

        logger.info(f"Running grid search on {len(train_data)} training samples")
        logger.info(f"Parameter grid: {list(param_grid.keys())}")

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        logger.info(f"Testing {len(combinations)} parameter combinations")

        results = []
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))

            try:
                result = backtest_func(
                    data=train_data, params=params, **backtest_kwargs
                )

                results.append(
                    {"params": params, "metrics": result, metric: result.get(metric, 0)}
                )

            except Exception as e:
                logger.warning(f"Backtest failed for params {params}: {str(e)}")
                results.append(
                    {
                        "params": params,
                        "metrics": {},
                        metric: -float("inf") if maximize else float("inf"),
                    }
                )

            if (i + 1) % 20 == 0:
                logger.info(f"Progress: {i + 1}/{len(combinations)}")

        successful_results = [
            r for r in results if r.get(metric, -float("inf")) != -float("inf")
        ]

        if not successful_results:
            raise ValueError("All parameter combinations failed")

        if maximize:
            best_result = max(successful_results, key=lambda x: x[metric])
        else:
            best_result = min(successful_results, key=lambda x: x[metric])

        logger.info(f"Best parameters: {best_result['params']}")
        logger.info(f"Best {metric}: {best_result[metric]:.4f}")

        return {
            "best_params": best_result["params"],
            "best_metric": best_result[metric],
            "all_results": results,
            "successful_runs": len(successful_results),
            "failed_runs": len(results) - len(successful_results),
        }


class FinalEvaluator:
    """
    Runs final backtest ONLY on test data with selected parameters.

    Does NOT reuse training data.
    """

    def __init__(self):
        logger.info("FinalEvaluator initialized")

    def run_final_backtest(
        self,
        test_data: pd.DataFrame,
        best_params: Dict[str, Any],
        backtest_func: Callable,
        backtest_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run final backtest on test data only.

        Args:
            test_data: Test DataFrame
            best_params: Parameters selected from training
            backtest_func: Function to run backtest
            backtest_kwargs: Additional arguments for backtest function

        Returns:
            Backtest results from test data only
        """
        backtest_kwargs = backtest_kwargs or {}

        if len(test_data) < 20:
            raise ValueError("Insufficient test data (minimum 20 rows)")

        logger.info(f"Running final backtest on {len(test_data)} test samples")
        logger.info(f"Using parameters: {best_params}")

        result = backtest_func(data=test_data, params=best_params, **backtest_kwargs)

        logger.info(
            f"Test results: Return={result.get('return_percent', 0):.2f}%, "
            f"WinRate={result.get('win_rate', 0):.1f}%"
        )

        return result


class MonteCarloValidator:
    """
    Runs Monte Carlo simulation ONLY on test results.

    Shuffles trade sequence (NOT raw price data) to analyze:
    - Sequence risk
    - Probability of ruin
    - Confidence intervals
    """

    def __init__(self, num_simulations: int = 1000):
        """
        Initialize Monte Carlo validator.

        Args:
            num_simulations: Number of simulations to run
        """
        self.num_simulations = num_simulations
        logger.info(
            f"MonteCarloValidator initialized with {num_simulations} simulations"
        )

    def run_monte_carlo(
        self,
        test_results: Dict[str, Any],
        initial_capital: float = 100000,
        ruin_threshold: float = 0.20,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on test results only.

        Shuffles trade sequence, NOT raw price data.

        Args:
            test_results: Results from test backtest
            initial_capital: Starting capital
            ruin_threshold: Drawdown threshold for "ruin"

        Returns:
            Monte Carlo simulation results
        """
        trades = test_results.get("trades", [])

        if not trades:
            logger.warning("No trades in test results for Monte Carlo")
            return self._empty_result()

        logger.info(f"Running Monte Carlo on {len(trades)} test trades")

        trade_pnls = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) != 0]

        if not trade_pnls:
            logger.warning("No P&L data in trades for Monte Carlo")
            return self._empty_result()

        simulated_final_pnls = []
        max_drawdowns = []

        for _ in range(self.num_simulations):
            shuffled = np.random.permutation(trade_pnls)
            equity = initial_capital
            equity_curve = [equity]
            peak = equity

            for pnl in shuffled:
                equity += pnl
                equity_curve.append(equity)
                if equity > peak:
                    peak = equity

            final_pnl = equity - initial_capital
            simulated_final_pnls.append(final_pnl)

            max_dd = 0
            peak = initial_capital
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            max_drawdowns.append(max_dd)

        ruin_count = sum(1 for dd in max_drawdowns if dd >= ruin_threshold)

        result = {
            "num_simulations": self.num_simulations,
            "risk_of_ruin": ruin_count / self.num_simulations,
            "expected_max_drawdown": np.mean(
                sorted(max_drawdowns, reverse=True)[: int(0.05 * self.num_simulations)]
            ),
            "avg_final_pnl": np.mean(simulated_final_pnls),
            "std_final_pnl": np.std(simulated_final_pnls),
            "percentile_5th_pnl": np.percentile(simulated_final_pnls, 5),
            "percentile_25th_pnl": np.percentile(simulated_final_pnls, 25),
            "percentile_50th_pnl": np.percentile(simulated_final_pnls, 50),
            "percentile_75th_pnl": np.percentile(simulated_final_pnls, 75),
            "percentile_95th_pnl": np.percentile(simulated_final_pnls, 95),
            "confidence_metrics": {
                "avg_max_drawdown": np.mean(max_drawdowns),
                "std_max_drawdown": np.std(max_drawdowns),
                "worst_case_pnl": min(simulated_final_pnls),
                "best_case_pnl": max(simulated_final_pnls),
            },
        }

        logger.info(f"Monte Carlo complete. Risk of ruin: {result['risk_of_ruin']:.2%}")

        return result

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "num_simulations": self.num_simulations,
            "risk_of_ruin": 1.0,
            "expected_max_drawdown": 1.0,
            "error": "No trades to simulate",
        }


class WalkForwardValidator:
    """
    Implements rolling window walk-forward validation.

    Workflow for each window:
    1. Train = data[i : i + train_size]
    2. Test = data[i + train_size : i + train_size + test_size]
    3. Optimize on train
    4. Test on next window
    """

    def __init__(self, train_window: int = 100, test_window: int = 30):
        """
        Initialize walk-forward validator.

        Args:
            train_window: Number of rows in training window
            test_window: Number of rows in test window
        """
        self.train_window = train_window
        self.test_window = test_window
        logger.info(f"WalkForwardValidator: train={train_window}, test={test_window}")

    def run_walk_forward(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        backtest_func: Callable,
        backtest_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis.

        Args:
            data: Full time series DataFrame
            param_grid: Parameter grid for optimization
            backtest_func: Function to run backtest
            backtest_kwargs: Additional arguments for backtest function

        Returns:
            Walk-forward results with separate train/test metrics per window
        """
        backtest_kwargs = backtest_kwargs or {}

        if len(data) < self.train_window + self.test_window:
            raise ValueError("Insufficient data for walk-forward windows")

        windows = []
        start_idx = 0
        window_num = 0

        while start_idx + self.train_window + self.test_window <= len(data):
            window_num += 1

            train_data = data.iloc[start_idx : start_idx + self.train_window].copy()
            test_data = data.iloc[
                start_idx + self.train_window : start_idx
                + self.train_window
                + self.test_window
            ].copy()

            logger.info(
                f"Window {window_num}: Train {len(train_data)}, Test {len(test_data)}"
            )

            grid_validator = GridSearchValidator()
            opt_result = grid_validator.run_optimization(
                train_data=train_data,
                param_grid=param_grid,
                backtest_func=backtest_func,
                backtest_kwargs=backtest_kwargs,
            )

            final_evaluator = FinalEvaluator()
            test_result = final_evaluator.run_final_backtest(
                test_data=test_data,
                best_params=opt_result["best_params"],
                backtest_func=backtest_func,
                backtest_kwargs=backtest_kwargs,
            )

            train_return = opt_result["best_metric"]
            test_return = test_result.get("return_percent", 0)

            walk_forward_efficiency = (
                test_return / train_return if train_return > 0 else 0
            )

            windows.append(
                {
                    "window_number": window_num,
                    "train_period": {
                        "start": str(train_data.index[0]),
                        "end": str(train_data.index[-1]),
                        "rows": len(train_data),
                    },
                    "test_period": {
                        "start": str(test_data.index[0]),
                        "end": str(test_data.index[-1]),
                        "rows": len(test_data),
                    },
                    "best_params": opt_result["best_params"],
                    "train_metrics": opt_result.get("all_results", [{}])[0].get(
                        "metrics", {}
                    ),
                    "test_metrics": test_result,
                    "walk_forward_efficiency": walk_forward_efficiency,
                }
            )

            start_idx += self.test_window

        if not windows:
            raise ValueError("No walk-forward windows created")

        wfe_values = [w["walk_forward_efficiency"] for w in windows]

        aggregate = {
            "total_windows": len(windows),
            "avg_walk_forward_efficiency": np.mean(wfe_values),
            "std_walk_forward_efficiency": np.std(wfe_values),
            "min_wfe": min(wfe_values),
            "max_wfe": max(wfe_values),
        }

        logger.info(
            f"Walk-forward complete. Average WFE: {aggregate['avg_walk_forward_efficiency']:.3f}"
        )

        return {"windows": windows, "aggregate_metrics": aggregate}


class ValidationPipeline:
    """
    Main orchestrator for backtesting validation.

    Implements complete workflow:
    1. Split data (train/test)
    2. Grid search on train only
    3. Final backtest on test only
    4. Monte Carlo on test results

    Ensures no data leakage.
    """

    def __init__(
        self, train_ratio: float = 0.7, num_monte_carlo_simulations: int = 1000
    ):
        """
        Initialize validation pipeline.

        Args:
            train_ratio: Proportion for training (default: 0.7)
            num_monte_carlo_simulations: Number of MC simulations
        """
        self.data_validator = DataValidator(train_ratio)
        self.grid_validator = GridSearchValidator()
        self.final_evaluator = FinalEvaluator()
        self.mc_validator = MonteCarloValidator(num_monte_carlo_simulations)

        logger.info(f"ValidationPipeline initialized: train_ratio={train_ratio}")

    def run_complete_validation(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        backtest_func: Callable,
        backtest_kwargs: Optional[Dict[str, Any]] = None,
        run_monte_carlo: bool = True,
    ) -> ValidationResult:
        """
        Run complete validation pipeline.

        Args:
            data: Full time series DataFrame
            param_grid: Parameter grid for optimization
            backtest_func: Function to run backtest (signature: func(data, params, **kwargs))
            backtest_kwargs: Additional arguments for backtest function
            run_monte_carlo: Whether to run Monte Carlo simulation

        Returns:
            ValidationResult with train/test performance metrics
        """
        backtest_kwargs = backtest_kwargs or {}

        split = self.data_validator.split_data(data)

        logger.info("=" * 60)
        logger.info("STEP 1: Grid Search on TRAINING data")
        logger.info("=" * 60)

        opt_result = self.grid_validator.run_optimization(
            train_data=split.train_data,
            param_grid=param_grid,
            backtest_func=backtest_func,
            backtest_kwargs=backtest_kwargs,
        )

        train_performance = {
            "best_params": opt_result["best_params"],
            "best_metric": opt_result["best_metric"],
            "metric_used": "sharpe_ratio",
            "successful_runs": opt_result["successful_runs"],
        }

        logger.info("=" * 60)
        logger.info("STEP 2: Final Backtest on TEST data")
        logger.info("=" * 60)

        test_result = self.final_evaluator.run_final_backtest(
            test_data=split.test_data,
            best_params=opt_result["best_params"],
            backtest_func=backtest_func,
            backtest_kwargs=backtest_kwargs,
        )

        test_performance = {
            "return_percent": test_result.get("return_percent", 0),
            "total_pnl": test_result.get("total_pnl", 0),
            "win_rate": test_result.get("win_rate", 0),
            "sharpe_ratio": test_result.get("sharpe_ratio", 0),
            "max_drawdown": test_result.get("max_drawdown", 0),
            "profit_factor": test_result.get("profit_factor", 0),
            "total_trades": test_result.get("total_trades", 0),
        }

        mc_results = None
        if run_monte_carlo:
            logger.info("=" * 60)
            logger.info("STEP 3: Monte Carlo on TEST results")
            logger.info("=" * 60)

            mc_results = self.mc_validator.run_monte_carlo(
                test_results=test_result,
                initial_capital=backtest_kwargs.get("initial_capital", 100000),
            )

        return ValidationResult(
            train_performance=train_performance,
            test_performance=test_performance,
            best_params=opt_result["best_params"],
            split_info=split.split_info,
            monte_carlo_results=mc_results,
        )

    def run_walk_forward_validation(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        backtest_func: Callable,
        backtest_kwargs: Optional[Dict[str, Any]] = None,
        train_window: int = 100,
        test_window: int = 30,
    ) -> Dict[str, Any]:
        """
        Run walk-forward validation.

        Args:
            data: Full time series DataFrame
            param_grid: Parameter grid
            backtest_func: Backtest function
            backtest_kwargs: Additional arguments
            train_window: Training window size
            test_window: Test window size

        Returns:
            Walk-forward validation results
        """
        wfv = WalkForwardValidator(train_window, test_window)

        return wfv.run_walk_forward(
            data=data,
            param_grid=param_grid,
            backtest_func=backtest_func,
            backtest_kwargs=backtest_kwargs,
        )


def create_validation_pipeline(
    train_ratio: float = 0.7, num_monte_carlo_simulations: int = 1000
) -> ValidationPipeline:
    """
    Create a validation pipeline instance.

    Args:
        train_ratio: Training data ratio
        num_monte_carlo_simulations: Monte Carlo simulations count

    Returns:
        Configured ValidationPipeline
    """
    return ValidationPipeline(train_ratio, num_monte_carlo_simulations)

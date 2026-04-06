"""
Walk-Forward Optimizer Module

Optimizes strategy parameters using training data with grid search and random search.

Features:
- Grid search optimization
- Random search optimization
- Parameter ranking
- Best parameter selection
- Multiprocessing support

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Callable, Type
from datetime import datetime
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import itertools
import random

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Optimize strategy parameters for walk-forward analysis.
    
    Supports grid search and random search optimization methods
    to find optimal parameters for each training window.
    
    Usage:
        >>> optimizer = WalkForwardOptimizer(strategy_class=LuxAlgoStrategy)
        >>> best_params = optimizer.optimize_grid(train_data, param_grid)
    """
    
    def __init__(
        self,
        strategy_class: Type,
        backtest_engine_class: Optional[Type] = None,
        metric_name: str = 'sharpe_ratio',
        maximize: bool = True,
        n_jobs: int = 1,
        random_seed: int = None
    ):
        """
        Initialize walk-forward optimizer.
        
        Args:
            strategy_class: Strategy class to optimize
            backtest_engine_class: Backtest engine class (default: BacktestEngine)
            metric_name: Metric to optimize (default: 'sharpe_ratio')
            maximize: If True, maximize metric; if False, minimize (default: True)
            n_jobs: Number of parallel jobs (default: 1, -1 for all cores)
            random_seed: Random seed for reproducibility (optional)
        
        Example:
            >>> optimizer = WalkForwardOptimizer(
            ...     strategy_class=LuxAlgoTrendlineStrategy,
            ...     metric_name='sharpe_ratio',
            ...     n_jobs=4
            ... )
        """
        self.strategy_class = strategy_class
        self.backtest_engine_class = backtest_engine_class
        self.metric_name = metric_name
        self.maximize = maximize
        self.n_jobs = n_jobs
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
            random.seed(random_seed)
        
        # Import default backtest engine if not specified
        if backtest_engine_class is None:
            from backtest.backtest_engine import BacktestEngine
            self.backtest_engine_class = BacktestEngine
        
        logger.info(
            f"WalkForwardOptimizer initialized for {strategy_class.__name__}, "
            f"optimizing {metric_name}"
        )
    
    def optimize_grid(
        self,
        train_data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        initial_capital: float = 100000.0,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize parameters using grid search.
        
        Args:
            train_data: Training DataFrame
            param_grid: Dictionary of parameter names to lists of values
                       Example: {'swing_length': [10, 14, 20], 'atr_multiplier': [1.5, 2.0]}
            initial_capital: Initial capital for backtesting
            verbose: Enable progress output
        
        Returns:
            Dictionary containing:
            - 'best_params': Best parameter combination
            - 'best_score': Best metric score
            - 'all_results': All parameter combinations and scores
            - 'ranking': Ranked list of parameter combinations
        
        Example:
            >>> param_grid = {
            ...     'swing_length': [10, 14, 20],
            ...     'atr_multiplier': [1.5, 2.0, 2.5],
            ...     'risk_per_trade': [0.5, 1.0, 2.0]
            ... }
            >>> results = optimizer.optimize_grid(train_data, param_grid)
            >>> print(f"Best params: {results['best_params']}")
        """
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        all_combinations = list(itertools.product(*param_values))
        
        if verbose:
            print(f"\nGrid Search: Evaluating {len(all_combinations)} parameter combinations...")
        
        # Evaluate all combinations
        results = self._evaluate_combinations(
            train_data=train_data,
            combinations=all_combinations,
            param_names=param_names,
            initial_capital=initial_capital,
            verbose=verbose
        )
        
        # Rank results
        ranking = self._rank_results(results)
        
        if not ranking:
            logger.warning("No valid parameter combinations found. Using default parameters.")
            # Return default parameters if no valid results
            default_params = {key: values[0] for key, values in param_grid.items()}
            return {
                'best_params': default_params,
                'best_score': 0.0,
                'all_results': [],
                'ranking': [],
                'total_evaluated': 0
            }
        
        # Get best parameters
        best_result = ranking[0]
        best_params = best_result['params']
        best_score = best_result['score']
        
        if verbose:
            print(f"\n✓ Best Score: {best_score:.4f}")
            print(f"✓ Best Params: {best_params}")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results,
            'ranking': ranking,
            'total_evaluated': len(results)
        }
    
    def optimize_random(
        self,
        train_data: pd.DataFrame,
        param_distributions: Dict[str, Tuple[Any, Any]],
        n_iterations: int = 50,
        initial_capital: float = 100000.0,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize parameters using random search.
        
        Args:
            train_data: Training DataFrame
            param_distributions: Dictionary of parameter names to (min, max) tuples
            n_iterations: Number of random combinations to test
            initial_capital: Initial capital for backtesting
            verbose: Enable progress output
        
        Returns:
            Dictionary containing:
            - 'best_params': Best parameter combination
            - 'best_score': Best metric score
            - 'all_results': All evaluated combinations
            - 'ranking': Ranked list of results
        
        Example:
            >>> param_distributions = {
            ...     'swing_length': (5, 30),
            ...     'atr_multiplier': (1.0, 3.0),
            ...     'risk_per_trade': (0.5, 2.0)
            ... }
            >>> results = optimizer.optimize_random(train_data, param_distributions, n_iterations=100)
        """
        if verbose:
            print(f"\nRandom Search: Evaluating {n_iterations} random combinations...")
        
        # Generate random combinations
        combinations = []
        param_names = list(param_distributions.keys())
        
        for _ in range(n_iterations):
            combo = {}
            for param_name, (min_val, max_val) in param_distributions.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    combo[param_name] = np.random.randint(min_val, max_val + 1)
                else:
                    combo[param_name] = np.random.uniform(min_val, max_val)
            combinations.append(combo)
        
        # Evaluate combinations
        results = self._evaluate_random_combinations(
            train_data=train_data,
            combinations=combinations,
            initial_capital=initial_capital,
            verbose=verbose
        )
        
        # Rank results
        ranking = self._rank_results(results)
        
        if not ranking:
            logger.warning("No valid parameter combinations found. Using random parameters.")
            # Generate random parameters if no valid results
            default_params = {}
            for param_name, (min_val, max_val) in param_distributions.items():
                if isinstance(min_val, int):
                    default_params[param_name] = np.random.randint(min_val, min(max_val + 1, min_val + 10))
                else:
                    default_params[param_name] = np.random.uniform(min_val, min_val + (max_val - min_val) * 0.1)
            
            return {
                'best_params': default_params,
                'best_score': 0.0,
                'all_results': [],
                'ranking': [],
                'total_evaluated': len(combinations)
            }
        
        # Get best parameters
        best_result = ranking[0]
        best_params = best_result['params']
        best_score = best_result['score']
        
        if verbose:
            print(f"\n✓ Best Score: {best_score:.4f}")
            print(f"✓ Best Params: {best_params}")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results,
            'ranking': ranking,
            'total_evaluated': len(results)
        }
    
    def _evaluate_combinations(
        self,
        train_data: pd.DataFrame,
        combinations: List[Tuple],
        param_names: List[str],
        initial_capital: float,
        verbose: bool
    ) -> List[Dict[str, Any]]:
        """Evaluate all parameter combinations."""
        results = []
        
        # Prepare arguments for parallel execution
        args_list = []
        for combo in combinations:
            params = dict(zip(param_names, combo))
            args_list.append((train_data, params, initial_capital))
        
        # Execute with parallelism if requested
        if self.n_jobs > 1 or self.n_jobs == -1:
            n_workers = self.n_jobs if self.n_jobs > 0 else -1
            with ProcessPoolExecutor(max_workers=n_workers if n_workers > 0 else None) as executor:
                futures = [
                    executor.submit(self._run_single_backtest, *args)
                    for args in args_list
                ]
                for i, future in enumerate(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        logger.error(f"Error evaluating combination {i}: {str(e)}")
                        if verbose:
                            print(f"❌ Error in combination {i}: {str(e)}")
        else:
            # Sequential execution
            for i, args in enumerate(args_list):
                try:
                    result = self._run_single_backtest(*args)
                    if result is not None:
                        results.append(result)
                    
                    if verbose and (i + 1) % 10 == 0:
                        print(f"Progress: {i + 1}/{len(combinations)} evaluated...")
                
                except Exception as e:
                    logger.error(f"Error evaluating combination {i}: {str(e)}")
                    if verbose:
                        print(f"❌ Error in combination {i}: {str(e)}")
        
        return results
    
    def _evaluate_random_combinations(
        self,
        train_data: pd.DataFrame,
        combinations: List[Dict[str, Any]],
        initial_capital: float,
        verbose: bool
    ) -> List[Dict[str, Any]]:
        """Evaluate random parameter combinations."""
        results = []
        
        for i, params in enumerate(combinations):
            try:
                result = self._run_single_backtest(train_data, params, initial_capital)
                if result is not None:
                    results.append(result)
                
                if verbose and (i + 1) % 10 == 0:
                    print(f"Progress: {i + 1}/{len(combinations)} evaluated...")
            
            except Exception as e:
                logger.error(f"Error evaluating combination {i}: {str(e)}")
                if verbose:
                    print(f"❌ Error in combination {i}: {str(e)}")
        
        return results
    
    def _run_single_backtest(
        self,
        train_data: pd.DataFrame,
        params: Dict[str, Any],
        initial_capital: float
    ) -> Optional[Dict[str, Any]]:
        """Run single backtest with given parameters."""
        try:
            # Create strategy instance
            strategy = self.strategy_class(params)
            
            # Create backtest engine
            engine = self.backtest_engine_class(
                initial_capital=initial_capital,
                verbose=False
            )
            
            # Run backtest
            results = engine.run(
                strategy_class=self.strategy_class,
                data=train_data,
                strategy_config=params
            )
            
            # Extract metric
            metric_value = results['metrics'].get(self.metric_name, 0.0)
            
            return {
                'params': params,
                'score': metric_value,
                'metrics': results['metrics'],
                'total_trades': results['metrics'].get('total_trades', 0),
                'success': True
            }
        
        except Exception as e:
            logger.debug(f"Backtest failed for params {params}: {str(e)}")
            return None
    
    def _rank_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank results by metric score."""
        if not results:
            return []
        
        # Sort by score (ascending or descending based on maximize flag)
        ranked = sorted(
            results,
            key=lambda x: x['score'],
            reverse=self.maximize
        )
        
        # Add rank to each result
        for i, result in enumerate(ranked):
            result['rank'] = i + 1
        
        return ranked


def optimize_walkforward_parameters(
    train_data: pd.DataFrame,
    strategy_class: Type,
    param_grid: Dict[str, List[Any]],
    method: str = 'grid',
    n_iterations: int = 50,
    n_jobs: int = 1,
    metric_name: str = 'sharpe_ratio',
    initial_capital: float = 100000.0,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function for walk-forward parameter optimization.
    
    Args:
        train_data: Training DataFrame
        strategy_class: Strategy class to optimize
        param_grid: Parameter grid for grid search or distributions for random search
        method: Optimization method ('grid' or 'random')
        n_iterations: Number of iterations for random search
        n_jobs: Number of parallel jobs
        metric_name: Metric to optimize
        initial_capital: Initial capital
        verbose: Enable progress output
    
    Returns:
        Dictionary with best parameters and results
    
    Example:
        >>> best_params = optimize_walkforward_parameters(
        ...     train_data=df,
        ...     strategy_class=LuxAlgoTrendlineStrategy,
        ...     param_grid={'swing_length': [10, 14, 20]},
        ...     method='grid'
        ... )
    """
    optimizer = WalkForwardOptimizer(
        strategy_class=strategy_class,
        metric_name=metric_name,
        n_jobs=n_jobs
    )
    
    if method == 'grid':
        return optimizer.optimize_grid(
            train_data=train_data,
            param_grid=param_grid,
            initial_capital=initial_capital,
            verbose=verbose
        )
    elif method == 'random':
        return optimizer.optimize_random(
            train_data=train_data,
            param_distributions=param_grid,
            n_iterations=n_iterations,
            initial_capital=initial_capital,
            verbose=verbose
        )
    else:
        raise ValueError(f"Unknown optimization method: {method}. Use 'grid' or 'random'.")

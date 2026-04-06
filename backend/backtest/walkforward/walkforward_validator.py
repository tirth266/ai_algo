"""
Walk-Forward Validator Module

Tests optimized parameters on unseen test data for out-of-sample validation.

Features:
- Apply optimized parameters to test data
- Record out-of-sample performance
- Calculate comprehensive metrics
- Track parameter stability

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Type
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Validate optimized parameters on out-of-sample test data.
    
    Applies the best parameters from training to test data and
    records comprehensive performance metrics for each cycle.
    
    Usage:
        >>> validator = WalkForwardValidator(strategy_class=LuxAlgoStrategy)
        >>> results = validator.validate_cycle(train_data, test_data, best_params)
    """
    
    def __init__(
        self,
        strategy_class: Type,
        backtest_engine_class: Optional[Type] = None,
        initial_capital: float = 100000.0
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            strategy_class: Strategy class to validate
            backtest_engine_class: Backtest engine class (default: BacktestEngine)
            initial_capital: Initial capital for backtesting
        
        Example:
            >>> validator = WalkForwardValidator(
            ...     strategy_class=LuxAlgoTrendlineStrategy,
            ...     initial_capital=100000
            ... )
        """
        self.strategy_class = strategy_class
        self.initial_capital = initial_capital
        
        # Import default backtest engine if not specified
        if backtest_engine_class is None:
            from backtest.backtest_engine import BacktestEngine
            self.backtest_engine_class = BacktestEngine
        else:
            self.backtest_engine_class = backtest_engine_class
        
        logger.info(
            f"WalkForwardValidator initialized for {strategy_class.__name__} "
            f"with capital {initial_capital}"
        )
    
    def validate_cycle(
        self,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
        params: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Validate parameters on a single train/test cycle.
        
        Args:
            train_data: Training DataFrame
            test_data: Test DataFrame
            params: Parameters optimized on training data
            verbose: Enable progress output
        
        Returns:
            Dictionary containing:
            - 'train_metrics': Metrics from in-sample training
            - 'test_metrics': Metrics from out-of-sample testing
            - 'params': Parameters used
            - 'is_overfit': Whether strategy appears overfit
        
        Example:
            >>> result = validator.validate_cycle(train_df, test_df, best_params)
            >>> print(f"Test Sharpe: {result['test_metrics']['sharpe_ratio']:.2f}")
        """
        if verbose:
            print(f"Validating on test data ({len(test_data)} bars)...")
        
        # Run backtest on training data (in-sample)
        train_results = self._run_backtest(train_data, params)
        train_metrics = train_results['metrics']
        
        # Run backtest on test data (out-of-sample)
        test_results = self._run_backtest(test_data, params)
        test_metrics = test_results['metrics']
        
        # Check for overfitting
        is_overfit = self._detect_overfitting(train_metrics, test_metrics)
        
        if verbose:
            print(f"✓ Train Sharpe: {train_metrics.get('sharpe_ratio', 0):.2f}")
            print(f"✓ Test Sharpe: {test_metrics.get('sharpe_ratio', 0):.2f}")
            print(f"{'⚠' if is_overfit else '✓'} Overfitting: {'Detected' if is_overfit else 'Not detected'}")
        
        return {
            'train_metrics': train_metrics,
            'test_metrics': test_metrics,
            'params': params,
            'is_overfit': is_overfit,
            'train_bars': len(train_data),
            'test_bars': len(test_data)
        }
    
    def validate_all_cycles(
        self,
        splits: List[Dict[str, Any]],
        optimization_results: List[Dict[str, Any]],
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Validate all walk-forward cycles.
        
        Args:
            splits: Walk-forward splits from WalkForwardSplitter
            optimization_results: Optimization results for each cycle
            verbose: Enable progress output
        
        Returns:
            List of validation results for each cycle
        
        Example:
            >>> all_results = validator.validate_all_cycles(splits, opt_results)
            >>> avg_test_sharpe = np.mean([r['test_metrics']['sharpe_ratio'] for r in all_results])
        """
        all_results = []
        
        for i, split in enumerate(splits):
            if verbose:
                print(f"\n{'='*60}")
                print(f"Cycle {split['cycle']}: Validating...")
                print(f"{'='*60}")
            
            # Get best parameters for this cycle
            if i < len(optimization_results):
                best_params = optimization_results[i]['best_params']
            else:
                # Use first cycle's parameters if not available
                best_params = optimization_results[0]['best_params']
                logger.warning(
                    f"No optimization results for cycle {i+1}, using cycle 1 parameters"
                )
            
            # Validate
            result = self.validate_cycle(
                train_data=split['train_data'],
                test_data=split['test_data'],
                params=best_params,
                verbose=verbose
            )
            
            # Add cycle info
            result['cycle'] = split['cycle']
            result['train_start'] = split['train_start']
            result['train_end'] = split['train_end']
            result['test_start'] = split['test_start']
            result['test_end'] = split['test_end']
            
            all_results.append(result)
        
        return all_results
    
    def _run_backtest(
        self,
        data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run single backtest with given parameters."""
        try:
            # Create strategy instance
            strategy = self.strategy_class(params)
            
            # Create backtest engine
            engine = self.backtest_engine_class(
                initial_capital=self.initial_capital,
                verbose=False
            )
            
            # Run backtest
            results = engine.run(
                strategy_class=self.strategy_class,
                data=data,
                strategy_config=params
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}")
            raise
    
    def _detect_overfitting(
        self,
        train_metrics: Dict[str, Any],
        test_metrics: Dict[str, Any]
    ) -> bool:
        """
        Detect potential overfitting by comparing train and test metrics.
        
        Overfitting is detected if:
        - Test Sharpe ratio is less than 50% of train Sharpe ratio
        - OR test return is negative while train return is strongly positive
        - OR test max drawdown is more than 2x train max drawdown
        """
        train_sharpe = train_metrics.get('sharpe_ratio', 0)
        test_sharpe = test_metrics.get('sharpe_ratio', 0)
        
        train_return = train_metrics.get('total_return_pct', 0)
        test_return = test_metrics.get('total_return_pct', 0)
        
        train_dd = abs(train_metrics.get('max_drawdown', 0))
        test_dd = abs(test_metrics.get('max_drawdown', 0))
        
        # Check Sharpe degradation
        if train_sharpe > 0.5:  # Only check if train Sharpe is meaningful
            if test_sharpe < train_sharpe * 0.5:
                return True
        
        # Check return reversal
        if train_return > 20 and test_return < 0:
            return True
        
        # Check drawdown explosion
        if train_dd > 0 and test_dd > train_dd * 2:
            return True
        
        return False
    
    def calculate_parameter_stability(
        self,
        all_params: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate stability of optimized parameters across cycles.
        
        Args:
            all_params: List of best parameters from each cycle
        
        Returns:
            Dictionary containing:
            - 'stability_score': Overall stability score (0-100)
            - 'parameter_stats': Statistics for each parameter
        
        Example:
            >>> stability = validator.calculate_parameter_stability(all_best_params)
            >>> print(f"Stability Score: {stability['stability_score']}/100")
        """
        if not all_params or len(all_params) < 2:
            return {
                'stability_score': 0,
                'parameter_stats': {},
                'message': 'Insufficient cycles for stability analysis'
            }
        
        # Convert to DataFrame for easier analysis
        params_df = pd.DataFrame(all_params)
        
        # Calculate coefficient of variation for each numeric parameter
        stability_scores = []
        param_stats = {}
        
        for col in params_df.columns:
            values = params_df[col].dropna()
            
            if len(values) < 2:
                continue
            
            # Calculate statistics
            mean_val = values.mean()
            std_val = values.std()
            cv = std_val / abs(mean_val) if mean_val != 0 else 0
            
            # Convert CV to stability score (lower CV = higher stability)
            # CV of 0 = 100 stability, CV of 1 = 50 stability, CV of 2+ = 0 stability
            stability = max(0, 100 - (cv * 50))
            stability_scores.append(stability)
            
            param_stats[col] = {
                'mean': mean_val,
                'std': std_val,
                'cv': cv,
                'min': values.min(),
                'max': values.max(),
                'stability': stability
            }
        
        # Overall stability score (weighted average)
        overall_stability = np.mean(stability_scores) if stability_scores else 0
        
        return {
            'stability_score': round(overall_stability, 1),
            'parameter_stats': param_stats,
            'num_parameters': len(param_stats),
            'num_cycles': len(all_params)
        }


def validate_walkforward_results(
    splits: List[Dict[str, Any]],
    optimization_results: List[Dict[str, Any]],
    strategy_class: Type,
    initial_capital: float = 100000.0,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function to validate all walk-forward cycles.
    
    Args:
        splits: Walk-forward splits
        optimization_results: Optimization results for each cycle
        strategy_class: Strategy class to validate
        initial_capital: Initial capital
        verbose: Enable progress output
    
    Returns:
        List of validation results for each cycle
    
    Example:
        >>> results = validate_walkforward_results(splits, opt_results, LuxAlgoStrategy)
    """
    validator = WalkForwardValidator(
        strategy_class=strategy_class,
        initial_capital=initial_capital
    )
    
    return validator.validate_all_cycles(
        splits=splits,
        optimization_results=optimization_results,
        verbose=verbose
    )


def analyze_out_of_sample_performance(
    validation_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze overall out-of-sample performance.
    
    Args:
        validation_results: Results from validate_all_cycles()
    
    Returns:
        Dictionary with aggregated statistics
    
    Example:
        >>> summary = analyze_out_of_sample_performance(results)
        >>> print(f"Average Test Sharpe: {summary['avg_test_sharpe']:.2f}")
    """
    if not validation_results:
        return {'error': 'No validation results provided'}
    
    # Extract metrics
    train_sharpes = [r['train_metrics'].get('sharpe_ratio', 0) for r in validation_results]
    test_sharpes = [r['test_metrics'].get('sharpe_ratio', 0) for r in validation_results]
    
    train_returns = [r['train_metrics'].get('total_return_pct', 0) for r in validation_results]
    test_returns = [r['test_metrics'].get('total_return_pct', 0) for r in validation_results]
    
    train_drawdowns = [r['train_metrics'].get('max_drawdown', 0) for r in validation_results]
    test_drawdowns = [r['test_metrics'].get('max_drawdown', 0) for r in validation_results]
    
    # Count overfitting
    overfit_count = sum(1 for r in validation_results if r.get('is_overfit', False))
    overfit_ratio = overfit_count / len(validation_results)
    
    return {
        'num_cycles': len(validation_results),
        'avg_train_sharpe': np.mean(train_sharpes),
        'avg_test_sharpe': np.mean(test_sharpes),
        'sharpe_degradation': np.mean(test_sharpes) / np.mean(train_sharpes) if np.mean(train_sharpes) > 0 else 0,
        'avg_train_return': np.mean(train_returns),
        'avg_test_return': np.mean(test_returns),
        'avg_train_drawdown': np.mean(train_drawdowns),
        'avg_test_drawdown': np.mean(test_drawdowns),
        'overfitting_detected': overfit_ratio,
        'cycles_with_profitable_test': sum(1 for r in test_returns if r > 0),
        'test_profitability_rate': sum(1 for r in test_returns if r > 0) / len(test_returns)
    }

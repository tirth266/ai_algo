"""
Parameter Optimization Engine

Grid search and optimization for Combined Power Strategy.

Features:
- Grid search across multiple parameters
- Parallel execution using multiprocessing
- Sharpe ratio and net profit mapping
- Robust zone detection (plateau finding)
- Overfitting analysis

Usage:
    >>> optimizer = ParameterOptimizer()
    >>> results = optimizer.run_grid_search(
    ...     symbol='RELIANCE',
    ...     start_date='2024-01-01',
    ...     end_date='2024-12-31',
    ...     param_grid=param_grid,
    ...     n_jobs=4  # Parallel processes
    ... )
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import logging
from pathlib import Path
import json
from itertools import product
from multiprocessing import Pool, cpu_count
import traceback

from .institutional_backtest_engine import InstitutionalBacktestEngine
from strategies.combined_power_strategy import CombinedPowerStrategy

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Parameter optimization engine for strategy tuning.
    
    Performs grid search to find robust parameter combinations
    that avoid overfitting while maximizing performance.
    
    Key Metrics:
    - Sharpe Ratio: Risk-adjusted returns
    - Net Profit: Total P&L
    - Robustness Score: Stability across parameter changes
    - Overfitting Index: Sensitivity to parameter variations
    """
    
    def __init__(self, base_config: Optional[Dict[str, Any]] = None):
        """
        Initialize parameter optimizer.
        
        Args:
            base_config: Base configuration for backtest engine
        """
        self.base_config = base_config or {
            'initial_capital': 100000.0,
            'capital_per_trade': 25000.0,
            'slippage_percent': 0.0005,
            'brokerage_per_trade': 20.0,
            'stop_loss_percent': 0.02,
            'take_profit_percent': 0.04,
            'max_positions': 5,
            'verbose': False  # Disable verbose for parallel execution
        }
        
        logger.info("ParameterOptimizer initialized")
    
    def run_grid_search(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List[Any]],
        n_jobs: int = -1,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Run grid search optimization.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')
            param_grid: Dictionary of parameter names to value lists
                       Example: {
                           'supertrend_factor': [2.0, 2.5, 3.0, 3.5, 4.0],
                           'min_votes': [2, 3, 4, 5]
                       }
            n_jobs: Number of parallel processes (-1 = all CPUs)
            show_progress: Show progress bar
        
        Returns:
            Dictionary with optimization results:
            {
                'results_matrix': 2D array of results,
                'best_params': Best parameter combination,
                'robust_zone': Region of stable performance,
                'overfitting_analysis': Overfitting metrics
            }
        """
        try:
            logger.info(f"Starting grid search for {symbol}")
            logger.info(f"Parameters: {list(param_grid.keys())}")
            
            # Generate all parameter combinations
            param_names = list(param_grid.keys())
            param_values = list(param_grid.values())
            combinations = list(product(*param_values))
            
            total_combinations = len(combinations)
            logger.info(f"Total combinations to test: {total_combinations}")
            
            # Determine number of processes
            if n_jobs == -1:
                n_jobs = cpu_count()
            n_jobs = min(n_jobs, total_combinations)
            
            logger.info(f"Using {n_jobs} parallel processes")
            
            # Prepare arguments for parallel execution
            args_list = []
            for i, combo in enumerate(combinations):
                params = dict(zip(param_names, combo))
                args_list.append((
                    symbol,
                    timeframe,
                    start_date,
                    end_date,
                    params,
                    self.base_config.copy(),
                    i
                ))
            
            # Run parallel optimization
            if n_jobs > 1 and total_combinations > 1:
                logger.info("Running parallel grid search...")
                with Pool(processes=n_jobs) as pool:
                    results = pool.starmap(
                        self._run_single_backtest,
                        args_list,
                        chunksize=max(1, total_combinations // (n_jobs * 2))
                    )
            else:
                logger.info("Running sequential grid search...")
                results = []
                for i, args in enumerate(args_list):
                    result = self._run_single_backtest(*args)
                    results.append(result)
                    if show_progress and (i + 1) % 10 == 0:
                        logger.info(f"Progress: {i + 1}/{total_combinations}")
            
            # Process results
            optimization_results = self._process_grid_results(
                results, param_names, param_grid, show_progress
            )
            
            logger.info(
                f"Grid search complete. "
                f"Best Sharpe: {optimization_results['best_params']['sharpe_ratio']:.2f}"
            )
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Grid search failed: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def _run_single_backtest(
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        params: Dict[str, Any],
        base_config: Dict[str, Any],
        job_id: int
    ) -> Dict[str, Any]:
        """
        Run single backtest for parameter combination.
        
        This is a static method for easy multiprocessing pickling.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            start_date: Start date
            end_date: End date
            params: Parameter values for this run
            base_config: Base engine configuration
            job_id: Job identifier
        
        Returns:
            Dictionary with parameters and results
        """
        try:
            # Create engine with config
            config = base_config.copy()
            
            # Apply strategy-specific parameters
            strategy_config = {
                'symbol': symbol,
                'timeframe': timeframe,
                'min_confidence': params.get('min_confidence', 0.6)
            }
            
            # Add Supertrend parameters if provided
            if 'supertrend_factor' in params:
                strategy_config['supertrend_factor'] = params['supertrend_factor']
            if 'supertrend_atr_period' in params:
                strategy_config['supertrend_atr_period'] = params['supertrend_atr_period']
            
            # Add minimum votes parameter if provided
            if 'min_votes' in params:
                strategy_config['min_votes'] = params['min_votes']
            
            # Run backtest
            engine = InstitutionalBacktestEngine(**config)
            results = engine.run_backtest(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                kite_client=None,  # Use mock data
                strategy_config=strategy_config
            )
            
            # Extract key metrics
            result_dict = {
                'job_id': job_id,
                'params': params,
                'sharpe_ratio': results.get('sharpe_ratio', 0),
                'net_profit': results.get('total_pnl', 0),
                'return_percent': results.get('return_percent', 0),
                'win_rate': results.get('win_rate', 0),
                'max_drawdown': results.get('max_drawdown', 0),
                'profit_factor': results.get('profit_factor', 0),
                'total_trades': results.get('total_trades', 0),
                'expectancy': results.get('expectancy', 0),
                'status': 'success'
            }
            
            return result_dict
            
        except Exception as e:
            logger.warning(f"Job {job_id} failed: {str(e)}")
            return {
                'job_id': job_id,
                'params': params,
                'sharpe_ratio': 0,
                'net_profit': 0,
                'return_percent': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'profit_factor': 0,
                'total_trades': 0,
                'expectancy': 0,
                'status': 'failed',
                'error': str(e)
            }
    
    def _process_grid_results(
        self,
        results: List[Dict[str, Any]],
        param_names: List[str],
        param_grid: Dict[str, List[Any]],
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Process grid search results into structured format.
        
        Args:
            results: List of backtest results
            param_names: Names of parameters
            param_grid: Original parameter grid
            show_progress: Show processing progress
        
        Returns:
            Structured optimization results
        """
        try:
            # Filter out failed runs
            successful_results = [r for r in results if r.get('status') == 'success']
            failed_count = len(results) - len(successful_results)
            
            if failed_count > 0:
                logger.warning(f"{failed_count} backtests failed")
            
            if len(successful_results) == 0:
                logger.error("All backtests failed!")
                return self._create_empty_optimization_results()
            
            # Find best parameters
            best_result = max(successful_results, key=lambda x: x['sharpe_ratio'])
            
            # Create results matrix
            results_matrix = self._create_results_matrix(
                successful_results, param_names, param_grid
            )
            
            # Analyze robustness
            robust_zone = self._find_robust_zone(
                successful_results, param_names, param_grid
            )
            
            # Overfitting analysis
            overfitting_analysis = self._analyze_overfitting(
                successful_results, param_names
            )
            
            # Build comprehensive results
            optimization_results = {
                'total_combinations': len(results),
                'successful_runs': len(successful_results),
                'failed_runs': failed_count,
                'best_params': best_result,
                'results_matrix': results_matrix,
                'robust_zone': robust_zone,
                'overfitting_analysis': overfitting_analysis,
                'all_results': successful_results  # For detailed analysis
            }
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error processing results: {str(e)}", exc_info=True)
            raise
    
    def _create_results_matrix(
        self,
        results: List[Dict[str, Any]],
        param_names: List[str],
        param_grid: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Create 2D matrix of results for visualization.
        
        Focuses on first two parameters for 2D heatmap.
        
        Args:
            results: Successful backtest results
            param_names: Parameter names
            param_grid: Parameter ranges
        
        Returns:
            2D matrix suitable for heatmap visualization
        """
        try:
            # Use first two parameters for 2D matrix
            x_param = param_names[0] if len(param_names) > 0 else 'unknown'
            y_param = param_names[1] if len(param_names) > 1 else 'unknown'
            
            x_values = sorted(param_grid.get(x_param, []))
            y_values = sorted(param_grid.get(y_param, []))
            
            # Create matrices for Sharpe and Profit
            sharpe_matrix = np.zeros((len(y_values), len(x_values)))
            profit_matrix = np.zeros((len(y_values), len(x_values)))
            trades_matrix = np.zeros((len(y_values), len(x_values)), dtype=int)
            
            # Fill matrices
            for result in results:
                params = result['params']
                x_val = params.get(x_param)
                y_val = params.get(y_param)
                
                if x_val is not None and y_val is not None:
                    try:
                        x_idx = x_values.index(x_val)
                        y_idx = y_values.index(y_val)
                        
                        sharpe_matrix[y_idx, x_idx] = result['sharpe_ratio']
                        profit_matrix[y_idx, x_idx] = result['net_profit']
                        trades_matrix[y_idx, x_idx] = result['total_trades']
                    except (ValueError, IndexError):
                        continue
            
            return {
                'x_parameter': x_param,
                'y_parameter': y_param,
                'x_values': x_values,
                'y_values': y_values,
                'sharpe_matrix': sharpe_matrix.tolist(),
                'profit_matrix': profit_matrix.tolist(),
                'trades_matrix': trades_matrix.tolist(),
                'x_label': x_param.replace('_', ' ').title(),
                'y_label': y_param.replace('_', ' ').title()
            }
            
        except Exception as e:
            logger.error(f"Error creating results matrix: {str(e)}")
            return {}
    
    def _find_robust_zone(
        self,
        results: List[Dict[str, Any]],
        param_names: List[str],
        param_grid: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Find region of parameter space with stable performance.
        
        A "robust zone" is where small parameter changes don't cause
        wild performance swings.
        
        Args:
            results: Successful backtest results
            param_names: Parameter names
            param_grid: Parameter ranges
        
        Returns:
            Dictionary describing robust parameter region
        """
        try:
            # Sort by Sharpe ratio
            sorted_results = sorted(results, key=lambda x: x['sharpe_ratio'], reverse=True)
            
            # Take top 20% performers
            top_count = max(1, int(len(sorted_results) * 0.2))
            top_results = sorted_results[:top_count]
            
            # Calculate statistics for each parameter
            robust_ranges = {}
            for param_name in param_names:
                values = [r['params'].get(param_name) for r in top_results if r['params'].get(param_name) is not None]
                
                if len(values) > 0:
                    robust_ranges[param_name] = {
                        'min': min(values),
                        'max': max(values),
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'median': np.median(values)
                    }
            
            # Calculate robustness score (inverse of variance)
            avg_std = np.mean([r['std'] for r in robust_ranges.values()]) if robust_ranges else float('inf')
            robustness_score = 1.0 / (1.0 + avg_std) if avg_std != float('inf') else 0
            
            return {
                'robust_ranges': robust_ranges,
                'top_performers_count': top_count,
                'avg_sharpe_top': np.mean([r['sharpe_ratio'] for r in top_results]),
                'avg_profit_top': np.mean([r['net_profit'] for r in top_results]),
                'robustness_score': round(robustness_score, 3)
            }
            
        except Exception as e:
            logger.error(f"Error finding robust zone: {str(e)}")
            return {}
    
    def _analyze_overfitting(
        self,
        results: List[Dict[str, Any]],
        param_names: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze overfitting risk.
        
        High sensitivity to parameter changes = high overfitting risk.
        
        Args:
            results: Successful backtest results
            param_names: Parameter names
        
        Returns:
            Overfitting analysis metrics
        """
        try:
            if len(results) < 3:
                return {
                    'risk_level': 'UNKNOWN',
                    'message': 'Insufficient data points'
                }
            
            # Calculate performance variance
            sharpe_values = [r['sharpe_ratio'] for r in results]
            profit_values = [r['net_profit'] for r in results]
            
            sharpe_std = np.std(sharpe_values)
            profit_std = np.std(profit_values)
            
            sharpe_mean = np.mean(sharpe_values)
            profit_mean = np.mean(profit_values)
            
            # Coefficient of variation (CV)
            sharpe_cv = sharpe_std / abs(sharpe_mean) if sharpe_mean != 0 else float('inf')
            profit_cv = profit_std / abs(profit_mean) if profit_mean != 0 else float('inf')
            
            # Overfitting index (higher = more overfitting risk)
            overfitting_index = (sharpe_cv + profit_cv) / 2
            
            # Risk level classification
            if overfitting_index < 0.5:
                risk_level = 'LOW'
                message = 'Strategy appears robust to parameter changes'
            elif overfitting_index < 1.0:
                risk_level = 'MEDIUM'
                message = 'Moderate sensitivity to parameters'
            else:
                risk_level = 'HIGH'
                message = 'High sensitivity - possible overfitting'
            
            return {
                'overfitting_index': round(overfitting_index, 3),
                'sharpe_coefficient_of_variation': round(sharpe_cv, 3),
                'profit_coefficient_of_variation': round(profit_cv, 3),
                'risk_level': risk_level,
                'message': message,
                'sharpe_std': round(sharpe_std, 3),
                'profit_std': round(profit_std, 3)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing overfitting: {str(e)}")
            return {}
    
    def _create_empty_optimization_results(self) -> Dict[str, Any]:
        """Create empty results structure when optimization fails."""
        return {
            'total_combinations': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'best_params': {},
            'results_matrix': {},
            'robust_zone': {},
            'overfitting_analysis': {},
            'all_results': []
        }
    
    def export_to_csv(
        self,
        optimization_results: Dict[str, Any],
        filepath: str
    ):
        """
        Export optimization results to CSV.
        
        Args:
            optimization_results: Results from run_grid_search()
            filepath: Output CSV file path
        """
        try:
            all_results = optimization_results.get('all_results', [])
            
            if len(all_results) == 0:
                logger.warning("No results to export")
                return
            
            # Convert to DataFrame
            df = pd.DataFrame(all_results)
            
            # Expand params column
            params_df = pd.json_normalize(df['params'])
            df = pd.concat([df.drop('params', axis=1), params_df], axis=1)
            
            # Sort by Sharpe ratio
            df.sort_values('sharpe_ratio', ascending=False, inplace=True)
            
            # Save to CSV
            df.to_csv(filepath, index=False)
            logger.info(f"Exported {len(df)} rows to {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
    
    def export_to_json(
        self,
        optimization_results: Dict[str, Any],
        filepath: str
    ):
        """
        Export optimization results to JSON.
        
        Args:
            optimization_results: Results from run_grid_search()
            filepath: Output JSON file path
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(optimization_results, f, indent=2, default=str)
            
            logger.info(f"Exported results to {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}")


def run_parameter_optimization(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    param_grid: Dict[str, List[Any]],
    n_jobs: int = -1
) -> Dict[str, Any]:
    """
    Convenience function to run parameter optimization.
    
    Args:
        symbol: Trading symbol
        timeframe: Candle timeframe
        start_date: Start date
        end_date: End date
        param_grid: Parameter grid to search
        n_jobs: Number of parallel processes
    
    Returns:
        Optimization results dictionary
    
    Example:
        >>> results = run_parameter_optimization(
        ...     symbol='RELIANCE',
        ...     timeframe='5minute',
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31',
        ...     param_grid={
        ...         'supertrend_factor': [2.0, 2.5, 3.0, 3.5, 4.0],
        ...         'min_votes': [2, 3, 4, 5]
        ...     },
        ...     n_jobs=4
        ... )
    """
    optimizer = ParameterOptimizer()
    return optimizer.run_grid_search(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        param_grid=param_grid,
        n_jobs=n_jobs
    )

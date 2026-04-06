"""
Walk-Forward Runner Module

Main entry point for walk-forward optimization and validation.

Features:
- Complete workflow orchestration
- Progress tracking
- Multiprocessing support
- Memory efficient processing
- Comprehensive result compilation

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Type
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class WalkForwardRunner:
    """
    Orchestrate complete walk-forward optimization and validation workflow.
    
    Integrates data splitting, parameter optimization, out-of-sample validation,
    and report generation into a unified pipeline.
    
    Usage:
        >>> runner = WalkForwardRunner(strategy_class=LuxAlgoStrategy)
        >>> results = runner.run_walkforward_analysis(data=df, param_grid=param_grid)
    """
    
    def __init__(
        self,
        strategy_class: Type,
        backtest_engine_class: Optional[Type] = None,
        train_years: int = 3,
        test_years: int = 1,
        n_jobs: int = 1,
        random_seed: int = None,
        initial_capital: float = 100000.0,
        verbose: bool = True
    ):
        """
        Initialize walk-forward runner.
        
        Args:
            strategy_class: Strategy class to optimize and validate
            backtest_engine_class: Backtest engine class (default: BacktestEngine)
            train_years: Training window size in years
            test_years: Test window size in years
            n_jobs: Number of parallel jobs for optimization
            random_seed: Random seed for reproducibility
            initial_capital: Initial capital for backtesting
            verbose: Enable progress output
        
        Example:
            >>> runner = WalkForwardRunner(
            ...     strategy_class=LuxAlgoTrendlineStrategy,
            ...     train_years=2,
            ...     test_years=1,
            ...     n_jobs=4
            ... )
        """
        self.strategy_class = strategy_class
        self.train_years = train_years
        self.test_years = test_years
        self.n_jobs = n_jobs
        self.random_seed = random_seed
        self.initial_capital = initial_capital
        self.verbose = verbose
        
        # Import default backtest engine if not specified
        if backtest_engine_class is None:
            from backtest.backtest_engine import BacktestEngine
            self.backtest_engine_class = BacktestEngine
        else:
            self.backtest_engine_class = backtest_engine_class
        
        logger.info(
            f"WalkForwardRunner initialized for {strategy_class.__name__}, "
            f"train={train_years}Y, test={test_years}Y"
        )
    
    def run_walkforward_analysis(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        optimization_method: str = 'grid',
        n_iterations: int = 50,
        metric_name: str = 'sharpe_ratio',
        generate_reports: bool = True,
        output_dir: str = None,
        min_cycles: int = 1
    ) -> Dict[str, Any]:
        """
        Run complete walk-forward analysis.
        
        Args:
            data: DataFrame with OHLCV data and datetime index
            param_grid: Parameter grid for optimization
            optimization_method: 'grid' or 'random' search
            n_iterations: Number of iterations for random search
            metric_name: Metric to optimize
            generate_reports: Whether to generate reports
            output_dir: Directory for saving reports
            min_cycles: Minimum number of cycles required
        
        Returns:
            Dictionary containing:
            - 'splits': Walk-forward splits used
            - 'optimization_results': Optimization results per cycle
            - 'validation_results': Validation results per cycle
            - 'summary': Aggregated statistics
            - 'parameter_stability': Parameter stability analysis
            - 'robustness_assessment': Overall robustness assessment
            - 'reports': Generated report files (if enabled)
        
        Example:
            >>> results = runner.run_walkforward_analysis(
            ...     data=df,
            ...     param_grid={'swing_length': [10, 14, 20]},
            ...     train_years=2,
            ...     test_years=1
            ... )
            >>> print(f"Average Test Sharpe: {results['summary']['avg_test_sharpe']:.2f}")
        """
        if self.verbose:
            print("\n" + "=" * 70)
            print("WALK-FORWARD OPTIMIZATION & VALIDATION")
            print("=" * 70)
            print(f"Strategy: {self.strategy_class.__name__}")
            print(f"Data: {len(data)} bars from {data.index[0]} to {data.index[-1]}")
            print(f"Training Window: {self.train_years} year(s)")
            print(f"Test Window: {self.test_years} year(s)")
            print(f"Optimization Method: {optimization_method}")
            print(f"Metric: {metric_name}")
            print("=" * 70 + "\n")
        
        # Step 1: Create walk-forward splits
        if self.verbose:
            print("Step 1/4: Creating walk-forward splits...")
        
        from backtest.walkforward.walkforward_splitter import WalkForwardSplitter
        
        splitter = WalkForwardSplitter(
            train_years=self.train_years,
            test_years=self.test_years
        )
        
        splits = splitter.split(data, min_cycles=min_cycles)
        
        if self.verbose:
            print(f"✓ Generated {len(splits)} walk-forward cycles")
            for split in splits:
                print(f"  Cycle {split['cycle']}: Train [{split['train_start'].date()} to {split['train_end'].date()}], Test [{split['test_start'].date() if split['test_start'] else 'N/A'} to {split['test_end'].date() if split['test_end'] else 'N/A'}]")
            print()
        
        # Step 2: Optimize parameters for each cycle
        if self.verbose:
            print("Step 2/4: Optimizing parameters for each cycle...")
            print("-" * 70)
        
        from backtest.walkforward.walkforward_optimizer import WalkForwardOptimizer
        
        optimization_results = []
        all_best_params = []
        
        for i, split in enumerate(splits):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"Cycle {split['cycle']}: Optimization")
                print(f"{'='*60}")
            
            optimizer = WalkForwardOptimizer(
                strategy_class=self.strategy_class,
                backtest_engine_class=self.backtest_engine_class,
                metric_name=metric_name,
                n_jobs=self.n_jobs,
                random_seed=self.random_seed
            )
            
            if optimization_method == 'grid':
                opt_result = optimizer.optimize_grid(
                    train_data=split['train_data'],
                    param_grid=param_grid,
                    initial_capital=self.initial_capital,
                    verbose=self.verbose
                )
            elif optimization_method == 'random':
                opt_result = optimizer.optimize_random(
                    train_data=split['train_data'],
                    param_distributions=param_grid,
                    n_iterations=n_iterations,
                    initial_capital=self.initial_capital,
                    verbose=self.verbose
                )
            else:
                raise ValueError(f"Unknown optimization method: {optimization_method}")
            
            optimization_results.append(opt_result)
            all_best_params.append(opt_result['best_params'])
            
            if self.verbose:
                print(f"✓ Cycle {split['cycle']} optimized: Score={opt_result['best_score']:.4f}")
        
        if self.verbose:
            print(f"\n✓ All {len(splits)} cycles optimized")
            print()
        
        # Step 3: Validate on test data
        if self.verbose:
            print("Step 3/4: Validating on out-of-sample test data...")
            print("-" * 70)
        
        from backtest.walkforward.walkforward_validator import WalkForwardValidator
        
        validator = WalkForwardValidator(
            strategy_class=self.strategy_class,
            backtest_engine_class=self.backtest_engine_class,
            initial_capital=self.initial_capital
        )
        
        validation_results = validator.validate_all_cycles(
            splits=splits,
            optimization_results=optimization_results,
            verbose=self.verbose
        )
        
        if self.verbose:
            print(f"\n✓ All {len(validation_results)} cycles validated")
            print()
        
        # Step 4: Generate summary and reports
        if self.verbose:
            print("Step 4/4: Generating summary and reports...")
            print("-" * 70)
        
        from backtest.walkforward.walkforward_report_generator import WalkForwardReportGenerator
        
        generator = WalkForwardReportGenerator(output_dir=output_dir)
        
        # Generate summary statistics
        summary_stats = generator.generate_summary_statistics(validation_results)
        
        # Generate parameter stability report
        stability_report = generator.generate_parameter_stability_report(
            all_best_params,
            validation_results
        )
        
        # Assess strategy robustness
        robustness_assessment = generator.assess_strategy_robustness(
            summary_stats,
            stability_report
        )
        
        # Compile comprehensive results
        results = {
            'splits': splits,
            'optimization_results': optimization_results,
            'validation_results': validation_results,
            'all_best_params': all_best_params,
            'summary': summary_stats,
            'parameter_stability': stability_report,
            'robustness_assessment': robustness_assessment,
            'config': {
                'strategy_class': self.strategy_class.__name__,
                'train_years': self.train_years,
                'test_years': self.test_years,
                'optimization_method': optimization_method,
                'metric_name': metric_name,
                'n_jobs': self.n_jobs,
                'initial_capital': self.initial_capital
            }
        }
        
        # Generate reports if requested
        if generate_reports:
            if self.verbose:
                print("Generating reports...")
            
            reports = generator.generate_full_report(
                validation_results=validation_results,
                all_params=all_best_params,
                filename_prefix=f'walkforward_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            results['reports'] = reports
            
            if self.verbose:
                print(f"✓ Reports generated: {len(reports)} formats")
                for report_type, filepath in reports.items():
                    print(f"  {report_type}: {filepath}")
        
        # Print summary
        if self.verbose:
            print("\n" + "=" * 70)
            print("WALK-FORWARD ANALYSIS COMPLETE")
            print("=" * 70)
            print(f"Total Cycles: {summary_stats['num_cycles']}")
            print(f"Average Train Sharpe: {summary_stats['avg_train_sharpe']:.2f}")
            print(f"Average Test Sharpe: {summary_stats['avg_test_sharpe']:.2f}")
            print(f"Sharpe Degradation: {summary_stats['sharpe_degradation']:.2f}x")
            print(f"Average Test Return: {summary_stats['avg_test_return']:.2f}%")
            print(f"Test Profitability Rate: {summary_stats['test_profitability_rate']*100:.1f}%")
            print(f"Parameter Stability: {stability_report['stability_score']:.1f}/100 ({stability_report['rating']})")
            print(f"Overall Robustness Score: {robustness_assessment['score']:.1f}/{robustness_assessment['max_score']}")
            print(f"Strategy Status: {robustness_assessment['status']}")
            print("=" * 70)
            print(f"\n{robustness_assessment['recommendation']}\n")
        
        logger.info(f"Walk-forward analysis completed: {len(splits)} cycles")
        return results
    
    def run_quick_analysis(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        n_cycles: int = 3,
        metric_name: str = 'sharpe_ratio'
    ) -> Dict[str, Any]:
        """
        Run quick walk-forward analysis with reduced simulations.
        
        Useful for rapid prototyping and initial testing.
        
        Args:
            data: Input data
            param_grid: Parameter grid
            n_cycles: Number of cycles to run
            metric_name: Metric to optimize
        
        Returns:
            Results dictionary
        
        Example:
            >>> quick_results = runner.run_quick_analysis(df, param_grid)
        """
        # Reduce training period for quick analysis
        self.train_years = max(1, self.train_years // 2)
        self.test_years = max(0.5, self.test_years // 2)
        self.n_jobs = 1  # Use single core for quick tests
        
        return self.run_walkforward_analysis(
            data=data,
            param_grid=param_grid,
            metric_name=metric_name,
            generate_reports=False,
            min_cycles=n_cycles
        )


def run_walkforward_analysis(
    data: pd.DataFrame,
    strategy_class: Type,
    param_grid: Dict[str, List[Any]],
    train_years: int = 3,
    test_years: int = 1,
    optimization_method: str = 'grid',
    n_iterations: int = 50,
    metric_name: str = 'sharpe_ratio',
    n_jobs: int = 1,
    random_seed: int = None,
    initial_capital: float = 100000.0,
    generate_reports: bool = True,
    output_dir: str = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function for running walk-forward analysis.
    
    Args:
        data: DataFrame with OHLCV data and datetime index
        strategy_class: Strategy class to optimize
        param_grid: Parameter grid for optimization
        train_years: Training window size in years
        test_years: Test window size in years
        optimization_method: 'grid' or 'random'
        n_iterations: Number of iterations for random search
        metric_name: Metric to optimize
        n_jobs: Number of parallel jobs
        random_seed: Random seed
        initial_capital: Initial capital
        generate_reports: Whether to generate reports
        output_dir: Output directory for reports
        verbose: Enable progress output
    
    Returns:
        Complete results dictionary
    
    Example:
        >>> from backtest.walkforward import run_walkforward_analysis
        >>> results = run_walkforward_analysis(
        ...     data=df,
        ...     strategy_class=LuxAlgoTrendlineStrategy,
        ...     param_grid={
        ...         'swing_length': [10, 14, 20],
        ...         'atr_multiplier': [1.5, 2.0, 2.5],
        ...         'risk_per_trade': [0.5, 1.0, 2.0]
        ...     },
        ...     train_years=3,
        ...     test_years=1
        ... )
    """
    runner = WalkForwardRunner(
        strategy_class=strategy_class,
        train_years=train_years,
        test_years=test_years,
        n_jobs=n_jobs,
        random_seed=random_seed,
        initial_capital=initial_capital,
        verbose=verbose
    )
    
    return runner.run_walkforward_analysis(
        data=data,
        param_grid=param_grid,
        optimization_method=optimization_method,
        n_iterations=n_iterations,
        metric_name=metric_name,
        generate_reports=generate_reports,
        output_dir=output_dir
    )


def quick_walkforward_check(
    data: pd.DataFrame,
    strategy_class: Type,
    param_grid: Dict[str, List[Any]],
    metric_name: str = 'sharpe_ratio'
) -> Dict[str, Any]:
    """
    Quick walk-forward check for rapid prototyping.
    
    Args:
        data: Input data
        strategy_class: Strategy class
        param_grid: Parameter grid
        metric_name: Metric to optimize
    
    Returns:
        Simplified results dictionary
    
    Example:
        >>> from backtest.walkforward import quick_walkforward_check
        >>> results = quick_walkforward_check(df, LuxAlgoStrategy, param_grid)
        >>> print(f"Avg Test Sharpe: {results['summary']['avg_test_sharpe']:.2f}")
    """
    runner = WalkForwardRunner(
        strategy_class=strategy_class,
        train_years=1,
        test_years=0.5,
        n_jobs=1,
        initial_capital=100000.0,
        verbose=False
    )
    
    return runner.run_quick_analysis(
        data=data,
        param_grid=param_grid,
        n_cycles=2,
        metric_name=metric_name
    )

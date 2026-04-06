"""
Walk-Forward Optimization Engine Package

Professional walk-forward optimization and validation system for algorithmic trading strategies.

This package provides:
- Rolling window data splitting
- Parameter optimization (grid search, random search)
- Out-of-sample validation
- Comprehensive reporting
- Strategy robustness assessment

Usage:
    from backtest.walkforward import run_walkforward_analysis
    
    results = run_walkforward_analysis(
        data=df,
        strategy_class=LuxAlgoTrendlineStrategy,
        param_grid=param_grid,
        train_years=3,
        test_years=1
    )
    
    print(f"Average Test Sharpe: {results['summary']['avg_test_sharpe']:.2f}")
    print(f"Parameter Stability: {results['parameter_stability']['stability_score']}/100")
    print(f"Strategy Status: {results['robustness_assessment']['status']}")

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from .walkforward_splitter import (
    WalkForwardSplitter,
    create_walkforward_splits,
    validate_walkforward_splits
)

from .walkforward_optimizer import (
    WalkForwardOptimizer,
    optimize_walkforward_parameters
)

from .walkforward_validator import (
    WalkForwardValidator,
    validate_walkforward_results,
    analyze_out_of_sample_performance
)

from .walkforward_report import (
    WalkForwardReportGenerator,
    generate_walkforward_report
)

from .walkforward_runner import (
    WalkForwardRunner,
    run_walkforward_analysis,
    quick_walkforward_check
)

__all__ = [
    # Main interface
    'WalkForwardRunner',
    'run_walkforward_analysis',
    'quick_walkforward_check',
    
    # Data splitting
    'WalkForwardSplitter',
    'create_walkforward_splits',
    'validate_walkforward_splits',
    
    # Optimization
    'WalkForwardOptimizer',
    'optimize_walkforward_parameters',
    
    # Validation
    'WalkForwardValidator',
    'validate_walkforward_results',
    'analyze_out_of_sample_performance',
    
    # Reporting
    'WalkForwardReportGenerator',
    'generate_walkforward_report'
]

__version__ = '1.0.0'
__author__ = 'Quantitative Trading Systems Engineer'

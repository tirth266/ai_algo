"""
Robustness Testing Package

Monte Carlo simulation and strategy robustness testing for algorithmic trading.

This package provides:
- Monte Carlo simulations for trade sequences
- Trade shuffling and bootstrap sampling
- Robustness metrics calculation
- Professional report generation

Usage:
    from backtest.robustness import run_robustness_test
    
    results = run_robustness_test(
        trades=trade_log,
        n_simulations=1000
    )
    
    print(f"Robustness score: {results['robustness_score']:.1f}/100")
    print(f"Probability of loss: {results['probability_of_loss']:.2%}")

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from .monte_carlo import MonteCarloSimulator, run_monte_carlo
from .trade_shuffler import TradeShuffler, shuffle_trades, analyze_sequence_stability
from .robustness_metrics import RobustnessMetrics
from .robustness_report import RobustnessReportGenerator
from .robustness_runner import (
    RobustnessTester,
    run_robustness_test,
    quick_robustness_check
)

__all__ = [
    # Main interface
    'RobustnessTester',
    'run_robustness_test',
    'quick_robustness_check',
    
    # Monte Carlo
    'MonteCarloSimulator',
    'run_monte_carlo',
    
    # Trade shuffler
    'TradeShuffler',
    'shuffle_trades',
    'analyze_sequence_stability',
    
    # Metrics
    'RobustnessMetrics',
    
    # Reports
    'RobustnessReportGenerator'
]

__version__ = '1.0.0'
__author__ = 'Quantitative Trading Systems Engineer'

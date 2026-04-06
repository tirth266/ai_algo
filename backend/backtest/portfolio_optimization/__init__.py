"""
Portfolio Optimization and Multi-Asset Allocation Engine Package

Professional portfolio optimization system for algorithmic trading.

This package provides:
- Return calculation and covariance matrix estimation
- Mean-variance optimization (MPT)
- Risk metrics calculation (VaR, CVaR, diversification)
- Portfolio simulation with rebalancing
- Comprehensive reporting

Usage:
    from backtest.portfolio_optimization import run_portfolio_optimization
    
    results = run_portfolio_optimization(
        returns=returns_df,
        method='max_sharpe',
        risk_free_rate=0.03
    )
    
    print(f"Optimal weights: {results['weights']}")
    print(f"Sharpe ratio: {results['metrics']['sharpe_ratio']:.2f}")

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

from .portfolio_returns import (
    PortfolioReturnsCalculator,
    calculate_portfolio_returns,
    prepare_returns_for_optimization
)

from .mean_variance_optimizer import (
    MeanVarianceOptimizer,
    optimize_portfolio
)

from .risk_models import (
    PortfolioRiskCalculator,
    analyze_portfolio_risk
)

from .portfolio_simulator import (
    PortfolioSimulator,
    simulate_portfolio_performance
)

from .portfolio_report import (
    PortfolioReportGenerator,
    generate_portfolio_report
)

from .portfolio_optimizer_runner import (
    PortfolioOptimizerRunner,
    run_portfolio_optimization,
    compare_optimization_methods
)

__all__ = [
    # Main interface
    'PortfolioOptimizerRunner',
    'run_portfolio_optimization',
    'compare_optimization_methods',
    
    # Return calculation
    'PortfolioReturnsCalculator',
    'calculate_portfolio_returns',
    'prepare_returns_for_optimization',
    
    # Optimization
    'MeanVarianceOptimizer',
    'optimize_portfolio',
    
    # Risk analysis
    'PortfolioRiskCalculator',
    'analyze_portfolio_risk',
    
    # Simulation
    'PortfolioSimulator',
    'simulate_portfolio_performance',
    
    # Reporting
    'PortfolioReportGenerator',
    'generate_portfolio_report'
]

__version__ = '1.0.0'
__author__ = 'Quantitative Trading Systems Engineer'

"""
Portfolio Optimizer Runner Module

Main entry point for portfolio optimization and analysis.

Features:
- Complete workflow orchestration
- Integration of all components
- Progress tracking
- Comprehensive result compilation

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class PortfolioOptimizerRunner:
    """
    Orchestrate complete portfolio optimization workflow.
    
    Integrates return calculation, optimization, risk analysis,
    simulation, and reporting into a unified pipeline.
    
    Usage:
        >>> runner = PortfolioOptimizerRunner()
        >>> results = runner.run_optimization(returns_df, method='max_sharpe')
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        initial_capital: float = 100000.0,
        annualization_factor: int = 252,
        verbose: bool = True
    ):
        """
        Initialize portfolio optimizer runner.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 5%)
            initial_capital: Initial capital for simulation
            annualization_factor: Trading days per year
            verbose: Enable progress output
        
        Example:
            >>> runner = PortfolioOptimizerRunner(
            ...     risk_free_rate=0.03,
            ...     initial_capital=500000,
            ...     verbose=True
            ... )
        """
        self.risk_free_rate = risk_free_rate
        self.initial_capital = initial_capital
        self.annualization_factor = annualization_factor
        self.verbose = verbose
        
        logger.info(
            f"PortfolioOptimizerRunner initialized: "
            f"risk_free_rate={risk_free_rate:.2%}, capital={initial_capital}"
        )
    
    def run_optimization(
        self,
        returns: pd.DataFrame,
        method: str = 'max_sharpe',
        constraints: Optional[Dict[str, Any]] = None,
        rebalance: str = 'monthly',
        generate_reports: bool = True,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        Run complete portfolio optimization workflow.
        
        Args:
            returns: DataFrame with asset returns (columns = assets, index = dates)
            method: Optimization method ('max_sharpe', 'min_volatility', 'erc')
            constraints: Additional optimization constraints (optional)
            rebalance: Rebalancing frequency ('daily', 'monthly', 'quarterly', 'yearly')
            generate_reports: Whether to generate reports
            output_dir: Directory for saving reports
        
        Returns:
            Dictionary containing:
            - 'weights': Optimal asset weights
            - 'metrics': Portfolio metrics
            - 'risk_metrics': Risk analysis results
            - 'simulation_results': Simulation output
            - 'reports': Generated report files (if enabled)
        
        Example:
            >>> results = runner.run_optimization(
            ...     returns_df,
            ...     method='max_sharpe',
            ...     rebalance='quarterly'
            ... )
            >>> print(f"Optimal weights: {results['weights']}")
            >>> print(f"Sharpe ratio: {results['metrics']['sharpe_ratio']:.2f}")
        """
        if self.verbose:
            print("\n" + "=" * 70)
            print("PORTFOLIO OPTIMIZATION & ANALYSIS")
            print("=" * 70)
            print(f"Assets: {len(returns.columns)}")
            print(f"Time Period: {returns.index[0]} to {returns.index[-1]}")
            print(f"Observations: {len(returns)}")
            print(f"Optimization Method: {method}")
            print("=" * 70 + "\n")
        
        # Step 1: Calculate covariance matrix
        if self.verbose:
            print("Step 1/5: Calculating returns and covariance matrix...")
        
        from .portfolio_returns import PortfolioReturnsCalculator
        
        returns_calc = PortfolioReturnsCalculator(
            annualization_factor=self.annualization_factor
        )
        
        cov_matrix = returns_calc.build_covariance_matrix(returns)
        
        if self.verbose:
            print(f"[OK] Covariance matrix calculated: {cov_matrix.shape}")
            print()
        
        # Step 2: Run optimization
        if self.verbose:
            print("Step 2/5: Optimizing portfolio weights...")
        
        from .mean_variance_optimizer import MeanVarianceOptimizer
        
        optimizer = MeanVarianceOptimizer(
            risk_free_rate=self.risk_free_rate,
            annualization_factor=self.annualization_factor
        )
        
        if method == 'max_sharpe':
            weights = optimizer.optimize_max_sharpe(returns, cov_matrix, constraints)
        elif method == 'min_volatility':
            weights = optimizer.optimize_min_volatility(returns, cov_matrix, constraints)
        elif method == 'erc' or method == 'equal_risk_contribution':
            weights = optimizer.optimize_equal_risk_contribution(returns, cov_matrix)
        else:
            raise ValueError(f"Unknown optimization method: {method}")
        
        # Calculate portfolio metrics
        metrics = optimizer.calculate_portfolio_metrics(weights, returns, cov_matrix)
        
        if self.verbose:
            print(f"[OK] Optimization completed")
            print(f"  Expected Return: {metrics['expected_return']:.2%}")
            print(f"  Volatility: {metrics['volatility']:.2%}")
            print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            print()
        
        # Step 3: Calculate risk metrics
        if self.verbose:
            print("Step 3/5: Calculating risk metrics...")
        
        from .risk_models import PortfolioRiskCalculator
        
        risk_calc = PortfolioRiskCalculator(
            annualization_factor=self.annualization_factor
        )
        
        risk_metrics = risk_calc.calculate_all_risk_metrics(returns, weights)
        
        if self.verbose:
            print(f"[OK] Risk metrics calculated")
            print(f"  VaR (95%): {risk_metrics['var']['95%']:.2%}")
            print(f"  CVaR (95%): {risk_metrics['cvar']['95%']:.2%}")
            print(f"  Diversification Ratio: {risk_metrics['diversification_ratio']:.2f}")
            print()
        
        # Step 4: Simulate portfolio performance
        if self.verbose:
            print(f"Step 4/5: Simulating portfolio with {rebalance} rebalancing...")
        
        from .portfolio_simulator import PortfolioSimulator
        
        simulator = PortfolioSimulator(
            initial_capital=self.initial_capital,
            annualization_factor=self.annualization_factor
        )
        
        simulation_results = simulator.simulate(
            returns=returns,
            weights=weights,
            rebalance=rebalance
        )
        
        if self.verbose:
            print(f"[OK] Simulation completed")
            print(f"  Final Capital: ${simulation_results['final_capital']:,.2f}")
            print(f"  Total Return: {simulation_results['metrics']['total_return']:.2%}")
            print(f"  Max Drawdown: {simulation_results['metrics']['max_drawdown']:.2%}")
            print()
        
        # Step 5: Generate reports
        if self.verbose:
            print("Step 5/5: Generating reports...")
        
        reports = {}
        
        if generate_reports:
            from .portfolio_report import PortfolioReportGenerator
            
            generator = PortfolioReportGenerator(output_dir=output_dir)
            
            reports = generator.generate_full_report(
                simulation_results=simulation_results,
                risk_metrics=risk_metrics,
                weights=weights,
                returns=returns,
                filename_prefix=f'portfolio_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            
            if self.verbose:
                print(f"[OK] Reports generated: {len(reports)} formats")
                for report_type, filepath in reports.items():
                    print(f"  {report_type}: {filepath}")
                print()
        
        # Compile comprehensive results
        results = {
            'weights': weights,
            'metrics': metrics,
            'risk_metrics': risk_metrics,
            'simulation_results': simulation_results,
            'reports': reports,
            'config': {
                'method': method,
                'risk_free_rate': self.risk_free_rate,
                'rebalance': rebalance,
                'initial_capital': self.initial_capital
            }
        }
        
        # Print summary
        if self.verbose:
            print("=" * 70)
            print("PORTFOLIO OPTIMIZATION COMPLETE")
            print("=" * 70)
            print(f"Optimization Method: {method}")
            print(f"Expected Annual Return: {metrics['expected_return']:.2%}")
            print(f"Expected Volatility: {metrics['volatility']:.2%}")
            print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            print(f"Final Capital: ${simulation_results['final_capital']:,.2f}")
            print(f"Maximum Drawdown: {simulation_results['metrics']['max_drawdown']:.2%}")
            print("=" * 70)
            print()
        
        logger.info(f"Portfolio optimization completed: method={method}")
        return results
    
    def run_comparison(
        self,
        returns: pd.DataFrame,
        methods: List[str] = None,
        rebalance: str = 'monthly'
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare different optimization methods.
        
        Args:
            returns: Asset returns DataFrame
            methods: List of methods to compare (default: ['max_sharpe', 'min_volatility', 'erc'])
            rebalance: Rebalancing frequency
        
        Returns:
            Dictionary mapping method name to results
        
        Example:
            >>> comparison = runner.run_comparison(returns_df)
            >>> for method, results in comparison.items():
            ...     print(f"{method}: Sharpe={results['metrics']['sharpe_ratio']:.2f}")
        """
        if methods is None:
            methods = ['max_sharpe', 'min_volatility', 'equal_weight']
        
        comparison_results = {}
        
        for method in methods:
            if self.verbose:
                print(f"\n{'='*70}")
                print(f"Running {method.upper()} optimization...")
                print(f"{'='*70}\n")
            
            if method == 'equal_weight':
                # Equal weight benchmark
                weights = {col: 1.0 / len(returns.columns) for col in returns.columns}
                
                # Calculate metrics
                from .mean_variance_optimizer import MeanVarianceOptimizer
                from .risk_models import PortfolioRiskCalculator
                from .portfolio_returns import PortfolioReturnsCalculator
                
                returns_calc = PortfolioReturnsCalculator(annualization_factor=self.annualization_factor)
                cov_matrix = returns_calc.build_covariance_matrix(returns)
                
                optimizer = MeanVarianceOptimizer(risk_free_rate=self.risk_free_rate)
                metrics = optimizer.calculate_portfolio_metrics(weights, returns, cov_matrix)
                
                risk_calc = PortfolioRiskCalculator()
                risk_metrics = risk_calc.calculate_all_risk_metrics(returns, weights)
                
                comparison_results[method] = {
                    'weights': weights,
                    'metrics': metrics,
                    'risk_metrics': risk_metrics
                }
            else:
                # Run full optimization
                results = self.run_optimization(
                    returns=returns,
                    method=method,
                    rebalance=rebalance,
                    generate_reports=False
                )
                
                comparison_results[method] = {
                    'weights': results['weights'],
                    'metrics': results['metrics'],
                    'risk_metrics': results['risk_metrics']
                }
        
        return comparison_results


def run_portfolio_optimization(
    returns: pd.DataFrame,
    method: str = 'max_sharpe',
    risk_free_rate: float = 0.05,
    initial_capital: float = 100000.0,
    constraints: Optional[Dict[str, Any]] = None,
    rebalance: str = 'monthly',
    generate_reports: bool = True,
    output_dir: str = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function for running portfolio optimization.
    
    Args:
        returns: DataFrame with asset returns
        method: Optimization method ('max_sharpe', 'min_volatility', 'erc')
        risk_free_rate: Annual risk-free rate
        initial_capital: Initial capital
        constraints: Additional optimization constraints
        rebalance: Rebalancing frequency
        generate_reports: Whether to generate reports
        output_dir: Output directory for reports
        verbose: Enable progress output
    
    Returns:
        Complete results dictionary
    
    Example:
        >>> from backtest.portfolio_optimization import run_portfolio_optimization
        >>> results = run_portfolio_optimization(
        ...     returns=returns_df,
        ...     method='max_sharpe',
        ...     risk_free_rate=0.03,
        ...     initial_capital=100000
        ... )
    """
    runner = PortfolioOptimizerRunner(
        risk_free_rate=risk_free_rate,
        initial_capital=initial_capital,
        verbose=verbose
    )
    
    return runner.run_optimization(
        returns=returns,
        method=method,
        constraints=constraints,
        rebalance=rebalance,
        generate_reports=generate_reports,
        output_dir=output_dir
    )


def compare_optimization_methods(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.05,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Compare different optimization methods and return comparison table.
    
    Args:
        returns: Asset returns DataFrame
        risk_free_rate: Annual risk-free rate
        verbose: Enable progress output
    
    Returns:
        DataFrame with method comparison
    
    Example:
        >>> comparison = compare_optimization_methods(returns_df)
        >>> print(comparison)
    """
    runner = PortfolioOptimizerRunner(
        risk_free_rate=risk_free_rate,
        verbose=verbose
    )
    
    # Run comparison
    comparison = runner.run_comparison(returns)
    
    # Create comparison table
    comparison_data = []
    
    for method, results in comparison.items():
        metrics = results['metrics']
        risk = results['risk_metrics']
        
        comparison_data.append({
            'Method': method,
            'Sharpe Ratio': metrics.get('sharpe_ratio', 0),
            'Expected Return': metrics.get('expected_return', 0),
            'Volatility': metrics.get('volatility', 0),
            'VaR (95%)': risk.get('var', {}).get('95%', 0),
            'Diversification Ratio': risk.get('diversification_ratio', 0)
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.set_index('Method', inplace=True)
    
    return comparison_df

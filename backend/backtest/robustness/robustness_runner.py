"""
Robustness Testing Runner Module

Main entry point for strategy robustness testing.

Orchestrates Monte Carlo simulations, trade shuffling,
metrics calculation, and report generation.

Usage:
    from backtest.robustness.robustness_runner import run_robustness_test
    
    results = run_robustness_test(
        trades=trade_log,
        simulations=1000
    )
    
    print(results["probability_of_loss"])
    print(results["worst_case_drawdown"])

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .monte_carlo import MonteCarloSimulator, run_monte_carlo
from .trade_shuffler import TradeShuffler, analyze_sequence_stability
from .robustness_metrics import RobustnessMetrics
from .robustness_report import RobustnessReportGenerator

logger = logging.getLogger(__name__)


class RobustnessTester:
    """
    Main orchestrator for strategy robustness testing.
    
    Coordinates all components of the robustness testing framework:
    - Monte Carlo simulations
    - Trade sequence shuffling
    - Metrics calculation
    - Report generation
    
    Usage:
        >>> tester = RobustnessTester()
        >>> results = tester.run_full_test(trades, n_simulations=5000)
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        confidence_levels: List[float] = None,
        random_seed: int = None
    ):
        """
        Initialize robustness tester.
        
        Args:
            n_simulations: Number of Monte Carlo simulations (default: 1000)
            confidence_levels: Confidence levels for statistics
            random_seed: Random seed for reproducibility
        
        Example:
            >>> tester = RobustnessTester(
            ...     n_simulations=5000,
            ...     confidence_levels=[0.90, 0.95, 0.99],
            ...     random_seed=42
            ... )
        """
        self.n_simulations = n_simulations
        self.confidence_levels = confidence_levels or [0.90, 0.95, 0.99]
        self.random_seed = random_seed
        
        # Initialize components
        self.monte_carlo = MonteCarloSimulator(
            n_simulations=n_simulations,
            confidence_levels=self.confidence_levels,
            random_seed=random_seed
        )
        
        self.trade_shuffler = TradeShuffler(random_seed=random_seed)
        self.metrics_calculator = RobustnessMetrics()
        self.report_generator = RobustnessReportGenerator()
        
        logger.info(
            f"RobustnessTester initialized with {n_simulations} simulations"
        )
    
    def run_full_test(
        self,
        trades: List[Any],
        initial_capital: float = 100000.0,
        sampling_method: str = 'bootstrap',
        generate_reports: bool = True,
        output_dir: str = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run comprehensive robustness testing.
        
        Args:
            trades: List of trade objects with pnl attribute
            initial_capital: Starting capital (default: 100,000)
            sampling_method: Sampling method ('bootstrap', 'random_shuffle', 'block')
            generate_reports: Generate report files (default: True)
            output_dir: Directory for report output (optional)
            verbose: Show progress and summary (default: True)
        
        Returns:
            Comprehensive results dictionary
        
        Example:
            >>> results = tester.run_full_test(trades, n_simulations=5000)
            >>> print(f"Robustness score: {results['robustness_score']:.1f}/100")
        """
        logger.info(
            f"Starting full robustness test: "
            f"{len(trades)} trades, {self.n_simulations} simulations"
        )
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"STRATEGY ROBUSTNESS TESTING")
            print(f"{'='*70}")
            print(f"Analyzing {len(trades)} historical trades")
            print(f"Running {self.n_simulations:,} Monte Carlo simulations")
            print(f"{'='*70}\n")
        
        # Step 1: Run Monte Carlo simulation
        if verbose:
            print("Step 1/3: Running Monte Carlo simulation...")
        
        mc_results = self.monte_carlo.run_simulation(
            trades=trades,
            initial_capital=initial_capital,
            sampling_method=sampling_method
        )
        
        if 'error' in mc_results:
            logger.error(f"Monte Carlo simulation failed: {mc_results['error']}")
            return {'error': mc_results['error']}
        
        if verbose:
            print(f"  ✓ Completed {mc_results['n_simulations']} simulations")
            print(f"  Median return: {mc_results['median_return']:.2%}")
            print(f"  Probability of loss: {mc_results['probability_of_loss']:.2%}")
            print()
        
        # Step 2: Calculate robustness metrics
        if verbose:
            print("Step 2/3: Calculating robustness metrics...")
        
        equity_curves = mc_results.get('simulated_equity_curves', np.array([]))
        returns = mc_results.get('return_distribution', np.array([]))
        success_rate = mc_results.get('success_rate', 0)
        
        robustness_metrics = self.metrics_calculator.calculate_all(
            equity_curves=equity_curves,
            returns=returns,
            success_rate=success_rate
        )
        
        if verbose:
            print(f"  ✓ Robustness score: {robustness_metrics['robustness_score']:.1f}/100")
            print(f"  ✓ Expected drawdown: {robustness_metrics['expected_drawdown']:.2f}%")
            print(f"  ✓ Probability of ruin: {robustness_metrics['probability_of_ruin']:.2%}")
            print()
        
        # Step 3: Analyze sequence stability
        if verbose:
            print("Step 3/3: Analyzing sequence stability...")
        
        stability_analysis = analyze_sequence_stability(
            trades=trades,
            n_simulations=min(500, self.n_simulations)  # Limit for performance
        )
        
        if verbose:
            overall_stability = stability_analysis.get('overall', {})
            print(f"  ✓ Stability score: {overall_stability.get('stability_score', 0):.4f}")
            print(f"  ✓ Coefficient of variation: {overall_stability.get('coefficient_of_variation', 0):.4f}")
            print()
        
        # Compile comprehensive results
        results = {
            **mc_results,
            **robustness_metrics,
            'stability_analysis': stability_analysis,
            'n_trades_analyzed': len(trades),
            'sampling_method': sampling_method,
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate reports if requested
        if generate_reports and output_dir:
            if verbose:
                print("Generating reports...")
            
            self._generate_all_reports(results, output_dir)
            
            if verbose:
                print(f"  ✓ Reports saved to {output_dir}")
                print()
        
        # Print summary
        if verbose:
            self._print_summary(results)
        
        logger.info(
            f"Robustness test completed: "
            f"Score={robustness_metrics['robustness_score']:.1f}/100"
        )
        
        return results
    
    def _generate_all_reports(
        self,
        results: Dict[str, Any],
        output_dir: str
    ):
        """Generate all report formats."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Text report
        text_filepath = os.path.join(output_dir, 'robustness_report.txt')
        self.report_generator.generate_text_report(results, text_filepath)
        
        # JSON export
        json_filepath = os.path.join(output_dir, 'robustness_results.json')
        self.report_generator.export_to_json(results, json_filepath)
        
        # CSV exports
        csv_filepath = os.path.join(output_dir, 'robustness_results')
        self.report_generator.export_to_csv(results, csv_filepath)
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print test summary."""
        print(f"{'='*70}")
        print("ROBUSTNESS TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Simulations Run:         {results['n_simulations']:,}")
        print(f"Trades Analyzed:         {results['n_trades_analyzed']}")
        print(f"Sampling Method:         {results['sampling_method']}")
        print()
        print("--- Performance Metrics ---")
        print(f"Median Return:           {results['median_return']:>10.2%}")
        print(f"Worst Case Return:       {results['worst_case_return']:>10.2%}")
        print(f"Best Case Return:        {results['best_case_return']:>10.2%}")
        print(f"Probability of Loss:     {results['probability_of_loss']:>10.2%}")
        print(f"Success Rate:            {results['success_rate']:>10.2%}")
        print()
        print("--- Risk Metrics ---")
        print(f"Expected Drawdown:       {results['expected_drawdown']:>10.2f}%")
        print(f"Worst Drawdown:          {results['worst_drawdown']:>10.2f}%")
        print(f"Probability of Ruin:     {results['probability_of_ruin']:>10.2%}")
        print(f"Value at Risk (95%):     {results['var_95']:>10.2%}")
        print(f"Conditional VaR (95%):   {results['cvar_95']:>10.2%}")
        print()
        print("--- Stability Assessment ---")
        print(f"Return Stability:        {results['return_stability']:>10.4f}")
        print(f"Equity Volatility:       {results['equity_volatility']:>10.4f}")
        print(f"Robustness Score:        {results['robustness_score']:>10.1f}/100")
        print(f"{'='*70}\n")


def run_robustness_test(
    trades: List[Any],
    n_simulations: int = 1000,
    initial_capital: float = 100000.0,
    sampling_method: str = 'bootstrap',
    confidence_levels: List[float] = None,
    random_seed: int = None,
    generate_reports: bool = False,
    output_dir: str = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to run robustness testing.
    
    Args:
        trades: List of trade objects
        n_simulations: Number of simulations (default: 1000)
        initial_capital: Starting capital (default: 100,000)
        sampling_method: Sampling method ('bootstrap', 'random_shuffle', 'block')
        confidence_levels: Confidence levels for statistics
        random_seed: Random seed for reproducibility
        generate_reports: Generate report files
        output_dir: Directory for reports
        verbose: Show progress and summary
    
    Returns:
        Comprehensive results dictionary
    
    Example:
        >>> results = run_robustness_test(
        ...     trades,
        ...     n_simulations=5000,
        ...     initial_capital=100000
        ... )
        >>> print(f"Robustness score: {results['robustness_score']:.1f}")
    """
    tester = RobustnessTester(
        n_simulations=n_simulations,
        confidence_levels=confidence_levels,
        random_seed=random_seed
    )
    
    return tester.run_full_test(
        trades=trades,
        initial_capital=initial_capital,
        sampling_method=sampling_method,
        generate_reports=generate_reports,
        output_dir=output_dir,
        verbose=verbose
    )


def quick_robustness_check(
    trades: List[Any],
    n_simulations: int = 500,
    initial_capital: float = 100000.0
) -> Dict[str, float]:
    """
    Quick robustness check with minimal output.
    
    Args:
        trades: List of trade objects
        n_simulations: Number of simulations (default: 500)
        initial_capital: Starting capital
    
    Returns:
        Key metrics dictionary
    
    Example:
        >>> metrics = quick_robustness_check(trades)
        >>> print(f"Prob loss: {metrics['probability_of_loss']:.2%}")
    """
    logger.info(f"Running quick robustness check with {n_simulations} simulations")
    
    # Run Monte Carlo
    mc_results = run_monte_carlo(
        trades=trades,
        n_simulations=n_simulations,
        initial_capital=initial_capital,
        sampling_method='bootstrap'
    )
    
    # Calculate key metrics
    equity_curves = mc_results.get('simulated_equity_curves', np.array([]))
    returns = mc_results.get('return_distribution', np.array([]))
    
    metrics_calc = RobustnessMetrics()
    metrics = metrics_calc.calculate_all(
        equity_curves=equity_curves,
        returns=returns,
        success_rate=mc_results.get('success_rate', 0)
    )
    
    # Return only key metrics
    key_metrics = {
        'probability_of_loss': metrics['probability_of_loss'],
        'robustness_score': metrics['robustness_score'],
        'expected_drawdown': metrics['expected_drawdown'],
        'median_return': metrics['median_return'],
        'var_95': metrics['var_95']
    }
    
    logger.info(
        f"Quick check complete: "
        f"Score={key_metrics['robustness_score']:.1f}, "
        f"Prob(loss)={key_metrics['probability_of_loss']:.2%}"
    )
    
    return key_metrics

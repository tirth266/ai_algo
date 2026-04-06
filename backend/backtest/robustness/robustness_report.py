"""
Robustness Report Generator Module

Generate professional robustness testing reports.

Reports include:
- Return distribution analysis
- Drawdown distribution analysis
- Worst-case scenarios
- Strategy stability rating

Export formats:
- JSON
- CSV
- Text report

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import json
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class RobustnessReportGenerator:
    """
    Generate comprehensive robustness testing reports.
    
    Creates professional reports with statistics, visualizations,
    and strategy stability assessments.
    
    Usage:
        >>> generator = RobustnessReportGenerator()
        >>> generator.generate_text_report(results, 'report.txt')
    """
    
    def __init__(self):
        """Initialize report generator."""
        logger.info("RobustnessReportGenerator initialized")
    
    def generate_summary_statistics(
        self,
        simulation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from simulation results.
        
        Args:
            simulation_results: Results from Monte Carlo simulation
        
        Returns:
            Dictionary with summary statistics
        
        Example:
            >>> summary = generator.generate_summary_statistics(results)
            >>> print(f"Median return: {summary['median_return']:.2%}")
        """
        returns = simulation_results.get('return_distribution', np.array([]))
        drawdowns = simulation_results.get('drawdown_distribution', np.array([]))
        
        if len(returns) == 0:
            return {'error': 'No simulation data available'}
        
        # Return statistics
        return_stats = {
            'median_return': float(np.median(returns)),
            'mean_return': float(np.mean(returns)),
            'std_return': float(np.std(returns)),
            'min_return': float(np.min(returns)),
            'max_return': float(np.max(returns)),
            'skewness': float(self._calculate_skewness(returns)),
            'kurtosis': float(self._calculate_kurtosis(returns))
        }
        
        # Drawdown statistics
        drawdown_stats = {
            'median_drawdown': float(np.median(drawdowns)),
            'mean_drawdown': float(np.mean(drawdowns)),
            'min_drawdown': float(np.min(drawdowns)),
            'max_drawdown': float(np.max(drawdowns)),
            'std_drawdown': float(np.std(drawdowns))
        }
        
        # Percentiles
        percentiles = {
            'returns': {
                '1pct': float(np.percentile(returns, 1)),
                '5pct': float(np.percentile(returns, 5)),
                '10pct': float(np.percentile(returns, 10)),
                '25pct': float(np.percentile(returns, 25)),
                '75pct': float(np.percentile(returns, 75)),
                '90pct': float(np.percentile(returns, 90)),
                '95pct': float(np.percentile(returns, 95)),
                '99pct': float(np.percentile(returns, 99))
            },
            'drawdowns': {
                '10pct': float(np.percentile(drawdowns, 10)),
                '25pct': float(np.percentile(drawdowns, 25)),
                '50pct': float(np.percentile(drawdowns, 50)),
                '75pct': float(np.percentile(drawdowns, 75)),
                '90pct': float(np.percentile(drawdowns, 90)),
                '95pct': float(np.percentile(drawdowns, 95))
            }
        }
        
        # Success metrics
        success_metrics = {
            'probability_of_loss': float(simulation_results.get('probability_of_loss', 0)),
            'success_rate': float(simulation_results.get('success_rate', 0)),
            'n_simulations': int(simulation_results.get('n_simulations', 0))
        }
        
        return {
            'returns': return_stats,
            'drawdowns': drawdown_stats,
            'percentiles': percentiles,
            'success_metrics': success_metrics
        }
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """Calculate skewness of distribution."""
        if len(data) < 3:
            return 0.0
        
        n = len(data)
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        
        if std == 0:
            return 0.0
        
        skew = (np.sum(((data - mean) / std) ** 3) * n) / ((n - 1) * (n - 2))
        return skew
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """Calculate excess kurtosis of distribution."""
        if len(data) < 4:
            return 0.0
        
        n = len(data)
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        
        if std == 0:
            return 0.0
        
        kurt = (np.sum(((data - mean) / std) ** 4) * n * (n + 1)) / \
               ((n - 1) * (n - 2) * (n - 3))
        
        # Excess kurtosis (subtract 3 for normal distribution)
        excess = kurt - (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))
        return excess
    
    def assess_strategy_stability(
        self,
        simulation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess overall strategy stability.
        
        Args:
            simulation_results: Results from Monte Carlo simulation
        
        Returns:
            Stability assessment dictionary
        
        Example:
            >>> assessment = generator.assess_strategy_stability(results)
            >>> print(f"Stability rating: {assessment['rating']}")
        """
        returns = simulation_results.get('return_distribution', np.array([]))
        prob_loss = simulation_results.get('probability_of_loss', 0)
        median_return = simulation_results.get('median_return', 0)
        worst_case = simulation_results.get('worst_case_return', 0)
        
        if len(returns) == 0:
            return {'rating': 'UNKNOWN', 'score': 0}
        
        # Calculate stability components
        return_std = np.std(returns)
        return_mean = np.mean(returns)
        
        # Coefficient of variation
        cv = return_std / abs(return_mean) if return_mean != 0 else float('inf')
        
        # Scoring (0-100 scale)
        # Lower CV is better
        cv_score = max(0, min(100, 100 - cv * 50))
        
        # Lower probability of loss is better
        prob_loss_score = (1 - prob_loss) * 100
        
        # Higher median return is better (scaled)
        return_score = min(100, max(0, median_return * 200 + 50))
        
        # Better worst case is better
        worst_case_score = (1 - max(0, -worst_case)) * 100
        
        # Weighted average
        overall_score = (
            cv_score * 0.30 +
            prob_loss_score * 0.30 +
            return_score * 0.20 +
            worst_case_score * 0.20
        )
        
        # Determine rating
        if overall_score >= 80:
            rating = 'EXCELLENT'
        elif overall_score >= 65:
            rating = 'GOOD'
        elif overall_score >= 50:
            rating = 'FAIR'
        elif overall_score >= 35:
            rating = 'POOR'
        else:
            rating = 'VERY POOR'
        
        assessment = {
            'rating': rating,
            'score': round(overall_score, 1),
            'components': {
                'cv_score': round(cv_score, 1),
                'prob_loss_score': round(prob_loss_score, 1),
                'return_score': round(return_score, 1),
                'worst_case_score': round(worst_case_score, 1)
            },
            'interpretation': self._get_rating_interpretation(rating)
        }
        
        logger.info(f"Strategy stability assessed: {rating} ({overall_score:.1f}/100)")
        
        return assessment
    
    def _get_rating_interpretation(self, rating: str) -> str:
        """Get interpretation text for rating."""
        interpretations = {
            'EXCELLENT': 'Strategy shows excellent robustness across simulations',
            'GOOD': 'Strategy demonstrates good robustness with acceptable risk',
            'FAIR': 'Strategy shows moderate robustness, monitor closely',
            'POOR': 'Strategy has poor robustness, use with caution',
            'VERY POOR': 'Strategy shows very poor robustness, not recommended'
        }
        return interpretations.get(rating, 'Unknown rating')
    
    def export_to_json(
        self,
        results: Dict[str, Any],
        filepath: str,
        include_equity_curves: bool = False
    ):
        """
        Export results to JSON file.
        
        Args:
            results: Simulation results
            filepath: Output file path
            include_equity_curves: Include equity curve data (large)
        
        Example:
            >>> generator.export_to_json(results, 'results.json')
        """
        logger.info(f"Exporting results to JSON: {filepath}")
        
        # Prepare export data
        export_data = results.copy()
        
        # Remove large arrays unless requested
        if not include_equity_curves:
            if 'simulated_equity_curves' in export_data:
                del export_data['simulated_equity_curves']
        
        # Convert numpy types to Python types
        export_data = self._convert_numpy_types(export_data)
        
        # Add metadata
        export_data['metadata'] = {
            'generated_at': datetime.now().isoformat(),
            'generator': 'RobustnessReportGenerator'
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Results exported to {filepath}")
    
    def export_to_csv(
        self,
        results: Dict[str, Any],
        base_filepath: str
    ):
        """
        Export results to CSV files.
        
        Creates multiple CSV files:
        - {base}_return_distribution.csv
        - {base}_drawdown_distribution.csv
        - {base}_summary.csv
        
        Args:
            results: Simulation results
            base_filepath: Base output file path (without extension)
        
        Example:
            >>> generator.export_to_csv(results, 'robustness_results')
        """
        logger.info(f"Exporting results to CSV: {base_filepath}")
        
        # Export return distribution
        if 'return_distribution' in results:
            returns_df = pd.DataFrame({
                'simulation_id': range(len(results['return_distribution'])),
                'return': results['return_distribution']
            })
            returns_df.to_csv(f"{base_filepath}_return_distribution.csv", index=False)
        
        # Export drawdown distribution
        if 'drawdown_distribution' in results:
            drawdowns_df = pd.DataFrame({
                'simulation_id': range(len(results['drawdown_distribution'])),
                'drawdown': results['drawdown_distribution']
            })
            drawdowns_df.to_csv(f"{base_filepath}_drawdown_distribution.csv", index=False)
        
        # Export summary statistics
        summary = self.generate_summary_statistics(results)
        summary_flat = self._flatten_dict(summary)
        summary_df = pd.DataFrame([summary_flat])
        summary_df.to_csv(f"{base_filepath}_summary.csv", index=False)
        
        logger.info(f"Results exported to {base_filepath}_*.csv")
    
    def generate_text_report(
        self,
        results: Dict[str, Any],
        filepath: str = None
    ) -> str:
        """
        Generate professional text report.
        
        Args:
            results: Simulation results
            filepath: Output file path (optional, returns string if None)
        
        Returns:
            Formatted text report
        
        Example:
            >>> report = generator.generate_text_report(results)
            >>> print(report)
        """
        logger.info("Generating text report")
        
        # Get summary and assessment
        summary = self.generate_summary_statistics(results)
        assessment = self.assess_strategy_stability(results)
        
        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append("STRATEGY ROBUSTNESS TESTING REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Simulations Run: {results.get('n_simulations', 0):,}")
        lines.append("")
        
        # Executive Summary
        lines.append("-" * 80)
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Strategy Stability Rating: {assessment['rating']} ({assessment['score']:.1f}/100)")
        lines.append(f"Interpretation: {assessment['interpretation']}")
        lines.append("")
        
        # Return Analysis
        lines.append("-" * 80)
        lines.append("RETURN DISTRIBUTION ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Median Return:           {summary['returns']['median_return']:>10.2%}")
        lines.append(f"Mean Return:             {summary['returns']['mean_return']:>10.2%}")
        lines.append(f"Std Deviation:           {summary['returns']['std_return']:>10.4f}")
        lines.append(f"Minimum Return:          {summary['returns']['min_return']:>10.2%}")
        lines.append(f"Maximum Return:          {summary['returns']['max_return']:>10.2%}")
        lines.append(f"Skewness:                {summary['returns']['skewness']:>10.2f}")
        lines.append(f"Kurtosis:                {summary['returns']['kurtosis']:>10.2f}")
        lines.append("")
        
        # Key Percentiles
        lines.append("Return Percentiles:")
        for pct, value in summary['percentiles']['returns'].items():
            lines.append(f"  {pct:>6}: {value:>10.2%}")
        lines.append("")
        
        # Drawdown Analysis
        lines.append("-" * 80)
        lines.append("DRAWDOWN DISTRIBUTION ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Median Drawdown:         {summary['drawdowns']['median_drawdown']:>10.2f}%")
        lines.append(f"Mean Drawdown:           {summary['drawdowns']['mean_drawdown']:>10.2f}%")
        lines.append(f"Worst Drawdown:          {summary['drawdowns']['max_drawdown']:>10.2f}%")
        lines.append("")
        
        lines.append("Drawdown Percentiles:")
        for pct, value in summary['percentiles']['drawdowns'].items():
            lines.append(f"  {pct:>6}: {value:>10.2f}%")
        lines.append("")
        
        # Risk Metrics
        lines.append("-" * 80)
        lines.append("RISK METRICS")
        lines.append("-" * 80)
        lines.append(f"Probability of Loss:     {summary['success_metrics']['probability_of_loss']:>10.2%}")
        lines.append(f"Success Rate:            {summary['success_metrics']['success_rate']:>10.2%}")
        lines.append("")
        
        # Worst Case Scenarios
        lines.append("-" * 80)
        lines.append("WORST CASE SCENARIOS")
        lines.append("-" * 80)
        lines.append(f"Worst Case Return:       {results.get('worst_case_return', 0):>10.2%}")
        lines.append(f"Best Case Return:        {results.get('best_case_return', 0):>10.2%}")
        
        if 'percentiles' in results:
            for key, value in results['percentiles'].items():
                lines.append(f"{key:>24}: {value:>10.2%}")
        lines.append("")
        
        # Stability Assessment
        lines.append("-" * 80)
        lines.append("STABILITY ASSESSMENT")
        lines.append("-" * 80)
        lines.append(f"Overall Score:           {assessment['score']:>10.1f}/100")
        lines.append(f"Rating:                  {assessment['rating']:>10}")
        lines.append("")
        lines.append("Component Scores:")
        for component, score in assessment['components'].items():
            lines.append(f"  {component.replace('_', ' ').title():>20}: {score:>10.1f}")
        lines.append("")
        
        # Disclaimer
        lines.append("-" * 80)
        lines.append("DISCLAIMER")
        lines.append("-" * 80)
        lines.append("Past performance does not guarantee future results.")
        lines.append("Monte Carlo simulations are based on historical data and")
        lines.append("assume similar market conditions. Actual trading results")
        lines.append("may vary significantly.")
        lines.append("")
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        
        # Save to file if requested
        if filepath:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(report)
            logger.info(f"Text report saved to {filepath}")
        
        return report
    
    def _convert_numpy_types(self, obj: Any) -> Any:
        """Convert numpy types to Python native types for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

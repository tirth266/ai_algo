"""
Walk-Forward Report Generator Module

Generate professional walk-forward analysis reports in multiple formats.

Features:
- Performance per cycle analysis
- Train vs test comparison
- Parameter stability reporting
- Aggregated results summary
- Export to JSON, CSV, and text formats

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


class WalkForwardReportGenerator:
    """
    Generate professional walk-forward analysis reports.
    
    Creates comprehensive reports including performance metrics,
    parameter stability analysis, and strategy robustness assessment.
    
    Usage:
        >>> generator = WalkForwardReportGenerator()
        >>> generator.generate_report(results, output_dir='./reports')
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory for saving reports (default: None)
        
        Example:
            >>> generator = WalkForwardReportGenerator(output_dir='wf_reports')
        """
        self.output_dir = output_dir
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        logger.info("WalkForwardReportGenerator initialized")
    
    def generate_summary_statistics(
        self,
        validation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from walk-forward analysis.
        
        Args:
            validation_results: Results from validation
        
        Returns:
            Dictionary with aggregated statistics
        
        Example:
            >>> stats = generator.generate_summary_statistics(results)
            >>> print(f"Average Test Sharpe: {stats['avg_test_sharpe']:.2f}")
        """
        if not validation_results:
            return {'error': 'No results provided'}
        
        # Extract metrics
        train_sharpes = [r['train_metrics'].get('sharpe_ratio', 0) for r in validation_results]
        test_sharpes = [r['test_metrics'].get('sharpe_ratio', 0) for r in validation_results]
        
        train_returns = [r['train_metrics'].get('total_return_pct', 0) for r in validation_results]
        test_returns = [r['test_metrics'].get('total_return_pct', 0) for r in validation_results]
        
        train_drawdowns = [r['train_metrics'].get('max_drawdown', 0) for r in validation_results]
        test_drawdowns = [r['test_metrics'].get('max_drawdown', 0) for r in validation_results]
        
        # Calculate averages and statistics
        summary = {
            'num_cycles': len(validation_results),
            
            # Sharpe ratio statistics
            'avg_train_sharpe': round(np.mean(train_sharpes), 4),
            'avg_test_sharpe': round(np.mean(test_sharpes), 4),
            'std_train_sharpe': round(np.std(train_sharpes), 4),
            'std_test_sharpe': round(np.std(test_sharpes), 4),
            'min_test_sharpe': round(min(test_sharpes), 4),
            'max_test_sharpe': round(max(test_sharpes), 4),
            
            # Return statistics
            'avg_train_return': round(np.mean(train_returns), 2),
            'avg_test_return': round(np.mean(test_returns), 2),
            'std_train_return': round(np.std(train_returns), 2),
            'std_test_return': round(np.std(test_returns), 2),
            'total_train_return': round(sum(train_returns), 2),
            'total_test_return': round(sum(test_returns), 2),
            
            # Drawdown statistics
            'avg_train_drawdown': round(np.mean(train_drawdowns), 2),
            'avg_test_drawdown': round(np.mean(test_drawdowns), 2),
            'worst_test_drawdown': round(min(test_drawdowns), 2),
            
            # Consistency metrics
            'profitable_test_cycles': sum(1 for r in test_returns if r > 0),
            'test_profitability_rate': round(sum(1 for r in test_returns if r > 0) / len(test_returns), 4),
            
            # Overfitting check
            'overfit_cycles': sum(1 for r in validation_results if r.get('is_overfit', False)),
            'overfit_ratio': round(sum(1 for r in validation_results if r.get('is_overfit', False)) / len(validation_results), 4)
        }
        
        # Calculate Sharpe degradation
        if summary['avg_train_sharpe'] > 0:
            summary['sharpe_degradation'] = round(
                summary['avg_test_sharpe'] / summary['avg_train_sharpe'], 4
            )
        else:
            summary['sharpe_degradation'] = 0
        
        logger.info(f"Generated summary statistics for {summary['num_cycles']} cycles")
        return summary
    
    def generate_parameter_stability_report(
        self,
        all_params: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate parameter stability analysis report.
        
        Args:
            all_params: List of best parameters from each cycle
            validation_results: Validation results
        
        Returns:
            Dictionary with parameter stability analysis
        
        Example:
            >>> stability = generator.generate_parameter_stability_report(params, results)
            >>> print(f"Stability Score: {stability['stability_score']}/100")
        """
        if not all_params or len(all_params) < 2:
            return {
                'stability_score': 0,
                'rating': 'INSUFFICIENT_DATA',
                'message': 'Need at least 2 cycles for stability analysis'
            }
        
        # Convert to DataFrame
        params_df = pd.DataFrame(all_params)
        
        # Calculate stability for each parameter
        param_stats = {}
        stability_scores = []
        
        for col in params_df.columns:
            values = params_df[col].dropna()
            
            if len(values) < 2:
                continue
            
            mean_val = values.mean()
            std_val = values.std()
            cv = std_val / abs(mean_val) if mean_val != 0 else float('inf')
            
            # Convert CV to stability score
            if cv == float('inf'):
                stability = 0
            else:
                stability = max(0, min(100, 100 - (cv * 50)))
            
            stability_scores.append(stability)
            
            param_stats[col] = {
                'mean': round(mean_val, 4),
                'std': round(std_val, 4),
                'cv': round(cv, 4),
                'min': round(values.min(), 4),
                'max': round(values.max(), 4),
                'stability': round(stability, 1)
            }
        
        # Overall stability score
        overall_stability = np.mean(stability_scores) if stability_scores else 0
        
        # Rating based on stability score
        if overall_stability >= 80:
            rating = 'EXCELLENT'
        elif overall_stability >= 65:
            rating = 'GOOD'
        elif overall_stability >= 50:
            rating = 'FAIR'
        elif overall_stability >= 35:
            rating = 'POOR'
        else:
            rating = 'VERY POOR'
        
        return {
            'stability_score': round(overall_stability, 1),
            'rating': rating,
            'parameter_stats': param_stats,
            'num_parameters': len(param_stats),
            'num_cycles': len(all_params)
        }
    
    def assess_strategy_robustness(
        self,
        summary_stats: Dict[str, Any],
        stability_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess overall strategy robustness.
        
        Args:
            summary_stats: Summary statistics
            stability_report: Parameter stability report
        
        Returns:
            Dictionary with robustness assessment
        
        Example:
            >>> assessment = generator.assess_strategy_robustness(summary, stability)
            >>> print(f"Strategy Status: {assessment['status']}")
        """
        # Scoring criteria
        score = 0
        max_score = 100
        
        # Test profitability rate (max 30 points)
        profit_rate = summary_stats.get('test_profitability_rate', 0)
        score += min(30, profit_rate * 30)
        
        # Average test Sharpe (max 25 points)
        avg_test_sharpe = summary_stats.get('avg_test_sharpe', 0)
        score += min(25, avg_test_sharpe * 12.5)  # Sharpe of 2 = 25 points
        
        # Sharpe degradation (max 20 points)
        degradation = summary_stats.get('sharpe_degradation', 0)
        if degradation >= 0.8:
            score += 20
        elif degradation >= 0.6:
            score += 15
        elif degradation >= 0.4:
            score += 10
        elif degradation >= 0.2:
            score += 5
        
        # Parameter stability (max 25 points)
        stability_score = stability_report.get('stability_score', 0)
        score += (stability_score / 100) * 25
        
        # Determine status
        if score >= 80:
            status = 'ROBUST'
            recommendation = 'Strategy shows strong robustness. Consider for live deployment.'
        elif score >= 65:
            status = 'GOOD'
            recommendation = 'Strategy shows good potential. Monitor closely in production.'
        elif score >= 50:
            status = 'MODERATE'
            recommendation = 'Strategy shows moderate robustness. Further optimization recommended.'
        elif score >= 35:
            status = 'WEAK'
            recommendation = 'Strategy robustness is weak. Caution advised for deployment.'
        else:
            status = 'POOR'
            recommendation = 'Strategy lacks robustness. Not recommended for live trading.'
        
        return {
            'score': round(score, 1),
            'max_score': max_score,
            'status': status,
            'recommendation': recommendation,
            'breakdown': {
                'profitability_score': round(min(30, profit_rate * 30), 1),
                'sharpe_score': round(min(25, avg_test_sharpe * 12.5), 1),
                'consistency_score': round(min(20, degradation * 25), 1),
                'stability_score': round((stability_score / 100) * 25, 1)
            }
        }
    
    def export_to_json(
        self,
        results: Dict[str, Any],
        filename: str = 'walkforward_results.json'
    ) -> str:
        """
        Export results to JSON format.
        
        Args:
            results: Complete results dictionary
            filename: Output filename
        
        Returns:
            Full path to saved file
        """
        # Prepare serializable data
        serializable_results = self._make_serializable(results)
        
        # Determine output path
        if self.output_dir:
            filepath = os.path.join(self.output_dir, filename)
        else:
            filepath = filename
        
        # Save to JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        logger.info(f"Results exported to JSON: {filepath}")
        return filepath
    
    def export_to_csv(
        self,
        validation_results: List[Dict[str, Any]],
        filename_prefix: str = 'walkforward'
    ) -> Dict[str, str]:
        """
        Export results to CSV format.
        
        Args:
            validation_results: Validation results list
            filename_prefix: Prefix for output filenames
        
        Returns:
            Dictionary mapping report type to filepath
        """
        if not self.output_dir:
            self.output_dir = '.'
        
        files_saved = {}
        
        # Export cycle performance
        cycle_data = []
        for result in validation_results:
            row = {
                'cycle': result.get('cycle', 0),
                'train_start': result.get('train_start', ''),
                'train_end': result.get('train_end', ''),
                'test_start': result.get('test_start', ''),
                'test_end': result.get('test_end', ''),
                'train_sharpe': result['train_metrics'].get('sharpe_ratio', 0),
                'test_sharpe': result['test_metrics'].get('sharpe_ratio', 0),
                'train_return': result['train_metrics'].get('total_return_pct', 0),
                'test_return': result['test_metrics'].get('total_return_pct', 0),
                'train_drawdown': result['train_metrics'].get('max_drawdown', 0),
                'test_drawdown': result['test_metrics'].get('max_drawdown', 0),
                'is_overfit': result.get('is_overfit', False)
            }
            cycle_data.append(row)
        
        cycle_df = pd.DataFrame(cycle_data)
        cycle_filepath = os.path.join(self.output_dir, f'{filename_prefix}_cycles.csv')
        cycle_df.to_csv(cycle_filepath, index=False)
        files_saved['cycles'] = cycle_filepath
        
        # Export parameters
        param_data = []
        for result in validation_results:
            row = {'cycle': result.get('cycle', 0)}
            row.update(result.get('params', {}))
            param_data.append(row)
        
        param_df = pd.DataFrame(param_data)
        param_filepath = os.path.join(self.output_dir, f'{filename_prefix}_parameters.csv')
        param_df.to_csv(param_filepath, index=False)
        files_saved['parameters'] = param_filepath
        
        logger.info(f"Results exported to CSV: {len(files_saved)} files")
        return files_saved
    
    def generate_text_report(
        self,
        summary_stats: Dict[str, Any],
        stability_report: Dict[str, Any],
        robustness_assessment: Dict[str, Any],
        filename: str = 'walkforward_summary.txt'
    ) -> str:
        """
        Generate formatted text report.
        
        Args:
            summary_stats: Summary statistics
            stability_report: Parameter stability report
            robustness_assessment: Robustness assessment
            filename: Output filename
        
        Returns:
            Full path to saved file
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("WALK-FORWARD ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Summary Statistics
        lines.append("-" * 70)
        lines.append("SUMMARY STATISTICS")
        lines.append("-" * 70)
        lines.append(f"Walk-Forward Cycles: {summary_stats.get('num_cycles', 0)}")
        lines.append("")
        
        lines.append("Sharpe Ratio:")
        lines.append(f"  Average Train Sharpe: {summary_stats.get('avg_train_sharpe', 0):.2f}")
        lines.append(f"  Average Test Sharpe:  {summary_stats.get('avg_test_sharpe', 0):.2f}")
        lines.append(f"  Sharpe Degradation:   {summary_stats.get('sharpe_degradation', 0):.2f}x")
        lines.append("")
        
        lines.append("Returns:")
        lines.append(f"  Average Train Return: {summary_stats.get('avg_train_return', 0):.2f}%")
        lines.append(f"  Average Test Return:  {summary_stats.get('avg_test_return', 0):.2f}%")
        lines.append(f"  Total Test Return:    {summary_stats.get('total_test_return', 0):.2f}%")
        lines.append("")
        
        lines.append("Risk Metrics:")
        lines.append(f"  Average Train Drawdown: {summary_stats.get('avg_train_drawdown', 0):.2f}%")
        lines.append(f"  Average Test Drawdown:  {summary_stats.get('avg_test_drawdown', 0):.2f}%")
        lines.append(f"  Worst Test Drawdown:    {summary_stats.get('worst_test_drawdown', 0):.2f}%")
        lines.append("")
        
        lines.append("Consistency:")
        lines.append(f"  Profitable Test Cycles: {summary_stats.get('profitable_test_cycles', 0)}/{summary_stats.get('num_cycles', 0)}")
        lines.append(f"  Test Profitability Rate: {summary_stats.get('test_profitability_rate', 0)*100:.1f}%")
        lines.append(f"  Overfitting Detected: {summary_stats.get('overfit_cycles', 0)} cycles ({summary_stats.get('overfit_ratio', 0)*100:.1f}%)")
        lines.append("")
        
        # Parameter Stability
        lines.append("-" * 70)
        lines.append("PARAMETER STABILITY")
        lines.append("-" * 70)
        lines.append(f"Stability Score: {stability_report.get('stability_score', 0):.1f}/100")
        lines.append(f"Rating: {stability_report.get('rating', 'N/A')}")
        lines.append("")
        
        param_stats = stability_report.get('parameter_stats', {})
        if param_stats:
            lines.append("Parameter Statistics:")
            for param_name, stats in param_stats.items():
                lines.append(f"  {param_name}:")
                lines.append(f"    Mean: {stats.get('mean', 0):.4f} ± {stats.get('std', 0):.4f}")
                lines.append(f"    Range: [{stats.get('min', 0):.4f}, {stats.get('max', 0):.4f}]")
                lines.append(f"    Stability: {stats.get('stability', 0):.1f}/100")
            lines.append("")
        
        # Robustness Assessment
        lines.append("-" * 70)
        lines.append("STRATEGY ROBUSTNESS ASSESSMENT")
        lines.append("-" * 70)
        lines.append(f"Overall Score: {robustness_assessment.get('score', 0):.1f}/{robustness_assessment.get('max_score', 100)}")
        lines.append(f"Status: {robustness_assessment.get('status', 'UNKNOWN')}")
        lines.append("")
        lines.append("Score Breakdown:")
        breakdown = robustness_assessment.get('breakdown', {})
        lines.append(f"  Profitability:     {breakdown.get('profitability_score', 0):.1f}/30")
        lines.append(f"  Risk-Adjusted:     {breakdown.get('sharpe_score', 0):.1f}/25")
        lines.append(f"  Consistency:       {breakdown.get('consistency_score', 0):.1f}/20")
        lines.append(f"  Parameter Stability: {breakdown.get('stability_score', 0):.1f}/25")
        lines.append("")
        lines.append(f"Recommendation: {robustness_assessment.get('recommendation', 'N/A')}")
        lines.append("")
        
        # Footer
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        
        # Join lines
        report_text = "\n".join(lines)
        
        # Save to file
        if self.output_dir:
            filepath = os.path.join(self.output_dir, filename)
        else:
            filepath = filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"Text report generated: {filepath}")
        return filepath
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    def generate_full_report(
        self,
        validation_results: List[Dict[str, Any]],
        all_params: List[Dict[str, Any]],
        filename_prefix: str = 'walkforward'
    ) -> Dict[str, str]:
        """
        Generate complete walk-forward analysis report.
        
        Args:
            validation_results: Validation results
            all_params: Best parameters from each cycle
            filename_prefix: Prefix for output files
        
        Returns:
            Dictionary mapping report types to filepaths
        """
        # Generate all components
        summary_stats = self.generate_summary_statistics(validation_results)
        stability_report = self.generate_parameter_stability_report(all_params, validation_results)
        robustness_assessment = self.assess_strategy_robustness(summary_stats, stability_report)
        
        # Compile full results
        full_results = {
            'summary': summary_stats,
            'parameter_stability': stability_report,
            'robustness_assessment': robustness_assessment,
            'validation_results': validation_results
        }
        
        # Export to different formats
        files_generated = {}
        
        # JSON export
        json_path = self.export_to_json(full_results, f'{filename_prefix}_results.json')
        files_generated['json'] = json_path
        
        # CSV export
        csv_files = self.export_to_csv(validation_results, filename_prefix)
        files_generated['csv'] = csv_files
        
        # Text report
        txt_path = self.generate_text_report(
            summary_stats,
            stability_report,
            robustness_assessment,
            f'{filename_prefix}_summary.txt'
        )
        files_generated['text'] = txt_path
        
        logger.info(f"Full report generated: {len(files_generated)} formats")
        return files_generated


def generate_walkforward_report(
    validation_results: List[Dict[str, Any]],
    all_params: List[Dict[str, Any]],
    output_dir: str = None,
    filename_prefix: str = 'walkforward'
) -> Dict[str, str]:
    """
    Convenience function to generate walk-forward report.
    
    Args:
        validation_results: Validation results
        all_params: Best parameters from each cycle
        output_dir: Output directory
        filename_prefix: Prefix for output files
    
    Returns:
        Dictionary mapping report types to filepaths
    
    Example:
        >>> files = generate_walkforward_report(results, params, output_dir='reports')
    """
    generator = WalkForwardReportGenerator(output_dir=output_dir)
    
    return generator.generate_full_report(
        validation_results=validation_results,
        all_params=all_params,
        filename_prefix=filename_prefix
    )

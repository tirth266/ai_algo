"""
Portfolio Report Generator Module

Generate professional portfolio analytics reports.

Include:
- Asset allocation chart data
- Portfolio equity curve
- Diversification statistics
- Contribution to risk

Export formats:
- JSON
- CSV
- Text report

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


class PortfolioReportGenerator:
    """
    Generate comprehensive portfolio analytics reports.
    
    Creates detailed reports including performance metrics,
    risk analysis, and asset allocation breakdowns.
    
    Usage:
        >>> generator = PortfolioReportGenerator(output_dir='./reports')
        >>> files = generator.generate_report(portfolio_results)
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory for saving reports (default: None)
        
        Example:
            >>> generator = PortfolioReportGenerator(output_dir='portfolio_reports')
        """
        self.output_dir = output_dir
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        logger.info("PortfolioReportGenerator initialized")
    
    def generate_summary_statistics(
        self,
        simulation_results: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from portfolio simulation.
        
        Args:
            simulation_results: Results from portfolio simulation
            risk_metrics: Risk metrics dictionary
            weights: Asset weights
        
        Returns:
            Dictionary with summary statistics
        
        Example:
            >>> stats = generator.generate_summary_statistics(results, risk, weights)
        """
        metrics = simulation_results.get('metrics', {})
        
        summary = {
            # Performance metrics
            'total_return': metrics.get('total_return', 0),
            'annualized_return': metrics.get('annualized_return', 0),
            'annualized_volatility': metrics.get('annualized_volatility', 0),
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'max_drawdown': metrics.get('max_drawdown', 0),
            'calmar_ratio': metrics.get('calmar_ratio', 0),
            
            # Risk metrics
            'var_95': risk_metrics.get('var', {}).get('95%', 0),
            'cvar_95': risk_metrics.get('cvar', {}).get('95%', 0),
            'diversification_ratio': risk_metrics.get('diversification_ratio', 0),
            
            # Portfolio characteristics
            'final_capital': metrics.get('final_capital', 0),
            'num_assets': len(weights),
            'effective_num_assets': self._calculate_effective_n_assets(weights),
            
            # Simulation details
            'n_periods': metrics.get('n_periods', 0),
            'n_years': metrics.get('n_years', 0)
        }
        
        logger.info(f"Generated summary statistics")
        return summary
    
    def generate_asset_allocation_report(
        self,
        weights: Dict[str, float],
        risk_contributions: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Generate asset allocation breakdown.
        
        Args:
            weights: Asset weights
            risk_contributions: Risk contributions (optional)
        
        Returns:
            Allocation report dictionary
        
        Example:
            >>> allocation = generator.generate_asset_allocation_report(weights)
        """
        # Sort by weight
        sorted_weights = dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))
        
        # Calculate concentration metrics
        total_weight = sum(sorted_weights.values())
        normalized_weights = {k: v / total_weight for k, v in sorted_weights.items()}
        
        # Herfindahl-Hirschman Index (concentration measure)
        hhi = sum(w ** 2 for w in normalized_weights.values())
        
        allocation_report = {
            'weights': normalized_weights,
            'num_assets': len(weights),
            'effective_num_assets': 1 / hhi if hhi > 0 else len(weights),
            'top_3_concentration': sum(list(normalized_weights.values())[:3]),
            'risk_contributions': risk_contributions or {}
        }
        
        logger.info(f"Generated asset allocation report")
        return allocation_report
    
    def generate_performance_attribution(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Generate performance attribution analysis.
        
        Args:
            returns: Asset returns DataFrame
            weights: Asset weights
        
        Returns:
            Attribution analysis dictionary
        
        Example:
            >>> attribution = generator.generate_performance_attribution(returns, weights)
        """
        # Calculate contribution to return
        mean_returns = returns.mean() * 252  # Annualized
        
        contributions = {}
        for asset in weights:
            if asset in mean_returns.index:
                contributions[asset] = weights[asset] * mean_returns[asset]
        
        total_return = sum(contributions.values())
        
        # Normalize to percentages
        contribution_pcts = {
            k: (v / total_return * 100) if total_return != 0 else 0
            for k, v in contributions.items()
        }
        
        return {
            'asset_contributions': contributions,
            'contribution_percentages': contribution_pcts,
            'total_return': total_return
        }
    
    def export_to_json(
        self,
        results: Dict[str, Any],
        filename: str = 'portfolio_results.json'
    ) -> str:
        """
        Export results to JSON format.
        
        Args:
            results: Complete results dictionary
            filename: Output filename
        
        Returns:
            Full path to saved file
        """
        # Make serializable
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
        equity_curve: pd.DataFrame,
        filename_prefix: str = 'portfolio'
    ) -> Dict[str, str]:
        """
        Export equity curve and allocations to CSV.
        
        Args:
            equity_curve: Equity curve DataFrame
            filename_prefix: Prefix for output filenames
        
        Returns:
            Dictionary mapping report type to filepath
        """
        if not self.output_dir:
            self.output_dir = '.'
        
        files_saved = {}
        
        # Export equity curve
        equity_filepath = os.path.join(self.output_dir, f'{filename_prefix}_equity.csv')
        equity_curve.to_csv(equity_filepath)
        files_saved['equity'] = equity_filepath
        
        logger.info(f"Results exported to CSV: {len(files_saved)} files")
        return files_saved
    
    def generate_text_report(
        self,
        summary_stats: Dict[str, Any],
        allocation_report: Dict[str, Any],
        filename: str = 'portfolio_summary.txt'
    ) -> str:
        """
        Generate formatted text report.
        
        Args:
            summary_stats: Summary statistics
            allocation_report: Asset allocation report
            filename: Output filename
        
        Returns:
            Full path to saved file
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("PORTFOLIO OPTIMIZATION & ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Performance Summary
        lines.append("-" * 70)
        lines.append("PERFORMANCE SUMMARY")
        lines.append("-" * 70)
        lines.append(f"Total Return:           {summary_stats.get('total_return', 0):>10.2%}")
        lines.append(f"Annualized Return:      {summary_stats.get('annualized_return', 0):>10.2%}")
        lines.append(f"Annualized Volatility:  {summary_stats.get('annualized_volatility', 0):>10.2%}")
        lines.append(f"Sharpe Ratio:           {summary_stats.get('sharpe_ratio', 0):>10.2f}")
        lines.append(f"Maximum Drawdown:       {summary_stats.get('max_drawdown', 0):>10.2%}")
        lines.append(f"Calmar Ratio:           {summary_stats.get('calmar_ratio', 0):>10.2f}")
        lines.append("")
        
        # Risk Metrics
        lines.append("-" * 70)
        lines.append("RISK METRICS")
        lines.append("-" * 70)
        lines.append(f"VaR (95%):              {summary_stats.get('var_95', 0):>10.2%}")
        lines.append(f"CVaR (95%):             {summary_stats.get('cvar_95', 0):>10.2%}")
        lines.append(f"Diversification Ratio:  {summary_stats.get('diversification_ratio', 0):>10.2f}")
        lines.append("")
        
        # Asset Allocation
        lines.append("-" * 70)
        lines.append("ASSET ALLOCATION")
        lines.append("-" * 70)
        
        weights = allocation_report.get('weights', {})
        for asset, weight in weights.items():
            lines.append(f"{asset:<20} {weight:>10.2%}")
        lines.append("")
        lines.append(f"Effective Number of Assets: {allocation_report.get('effective_num_assets', 0):.1f}")
        lines.append(f"Top 3 Concentration:        {allocation_report.get('top_3_concentration', 0):.1%}")
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
    
    def _calculate_effective_n_assets(
        self,
        weights: Dict[str, float]
    ) -> float:
        """Calculate effective number of assets (1/HHI)."""
        total_weight = sum(weights.values())
        if total_weight == 0:
            return len(weights)
        
        normalized_weights = [w / total_weight for w in weights.values()]
        hhi = sum(w ** 2 for w in normalized_weights)
        
        return 1 / hhi if hhi > 0 else len(weights)
    
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
        simulation_results: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        weights: Dict[str, float],
        returns: pd.DataFrame,
        filename_prefix: str = 'portfolio'
    ) -> Dict[str, str]:
        """
        Generate complete portfolio analysis report.
        
        Args:
            simulation_results: Simulation results
            risk_metrics: Risk metrics
            weights: Asset weights
            returns: Asset returns DataFrame
            filename_prefix: Prefix for output files
        
        Returns:
            Dictionary mapping report types to filepaths
        """
        # Generate all components
        summary_stats = self.generate_summary_statistics(
            simulation_results, risk_metrics, weights
        )
        
        allocation_report = self.generate_asset_allocation_report(
            weights,
            risk_metrics.get('risk_contributions')
        )
        
        # Compile full results
        full_results = {
            'summary': summary_stats,
            'asset_allocation': allocation_report,
            'performance_attribution': self.generate_performance_attribution(returns, weights),
            'simulation': simulation_results,
            'risk_metrics': risk_metrics
        }
        
        # Export to different formats
        files_generated = {}
        
        # JSON export
        json_path = self.export_to_json(full_results, f'{filename_prefix}_results.json')
        files_generated['json'] = json_path
        
        # CSV export
        if 'equity_curve' in simulation_results:
            csv_files = self.export_to_csv(
                simulation_results['equity_curve'],
                filename_prefix
            )
            files_generated['csv'] = csv_files
        
        # Text report
        txt_path = self.generate_text_report(
            summary_stats,
            allocation_report,
            f'{filename_prefix}_summary.txt'
        )
        files_generated['text'] = txt_path
        
        logger.info(f"Full report generated: {len(files_generated)} formats")
        return files_generated


def generate_portfolio_report(
    simulation_results: Dict[str, Any],
    risk_metrics: Dict[str, Any],
    weights: Dict[str, float],
    returns: pd.DataFrame,
    output_dir: str = None
) -> Dict[str, str]:
    """
    Convenience function to generate portfolio report.
    
    Args:
        simulation_results: Simulation results
        risk_metrics: Risk metrics
        weights: Asset weights
        returns: Asset returns DataFrame
        output_dir: Output directory
    
    Returns:
        Dictionary mapping report types to filepaths
    
    Example:
        >>> files = generate_portfolio_report(results, risk, weights, returns)
    """
    generator = PortfolioReportGenerator(output_dir=output_dir)
    
    return generator.generate_full_report(
        simulation_results=simulation_results,
        risk_metrics=risk_metrics,
        weights=weights,
        returns=returns
    )

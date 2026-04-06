"""
Report Generator Module

Generate comprehensive backtest reports and visualizations.

Features:
- Performance summary
- Equity curve analysis
- Drawdown charts
- Trade statistics
- Export to multiple formats

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generate professional backtest reports.
    
    Creates:
    - Performance summary
    - Equity curve charts
    - Drawdown analysis
    - Trade lists
    - Statistical reports
    
    Usage:
        >>> generator = ReportGenerator()
        >>> generator.generate_report(results, output_dir='reports')
    """
    
    def __init__(self):
        """Initialize report generator."""
        logger.info("ReportGenerator initialized")
    
    def generate_summary_report(
        self,
        results: Dict[str, Any]
    ) -> str:
        """
        Generate text summary report.
        
        Args:
            results: Backtest results dictionary
        
        Returns:
            Formatted text report
        
        Example:
            >>> report = generator.generate_summary_report(results)
            >>> print(report)
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("BACKTEST PERFORMANCE REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Basic info
        lines.append(f"Symbol: {results.get('symbol', 'N/A')}")
        lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Capital & Returns
        lines.append("-" * 70)
        lines.append("CAPITAL & RETURNS")
        lines.append("-" * 70)
        
        initial = results.get('initial_capital', 0)
        final = results.get('final_capital', 0)
        total_return = results.get('total_return', 0)
        
        lines.append(f"Initial Capital:      ${initial:>15,.2f}")
        lines.append(f"Final Capital:        ${final:>15,.2f}")
        lines.append(f"Total Return:         {total_return:>14.2f}%")
        lines.append(f"Absolute Profit:      ${final - initial:>15,.2f}")
        lines.append("")
        
        # Performance Metrics
        lines.append("-" * 70)
        lines.append("PERFORMANCE METRICS")
        lines.append("-" * 70)
        
        metrics = results.get('metrics', {})
        
        lines.append(f"Total Trades:         {metrics.get('total_trades', 0):>15}")
        lines.append(f"Win Rate:             {metrics.get('win_rate', 0):>14.2f}%")
        lines.append(f"Profit Factor:        {metrics.get('profit_factor', 0):>15.2f}")
        lines.append(f"Expectancy:           ${metrics.get('expectancy', 0):>14.2f}/trade")
        lines.append("")
        
        # Risk Metrics
        lines.append("-" * 70)
        lines.append("RISK METRICS")
        lines.append("-" * 70)
        
        lines.append(f"Max Drawdown:         {metrics.get('max_drawdown', 0):>14.2f}%")
        lines.append(f"Sharpe Ratio:         {metrics.get('sharpe_ratio', 0):>15.2f}")
        lines.append(f"Sortino Ratio:        {metrics.get('sortino_ratio', 0):>15.2f}")
        lines.append(f"Calmar Ratio:         {metrics.get('calmar_ratio', 0):>15.2f}")
        lines.append("")
        
        # Trade Statistics
        lines.append("-" * 70)
        lines.append("TRADE STATISTICS")
        lines.append("-" * 70)
        
        lines.append(f"Average Win:          ${metrics.get('avg_win', 0):>14,.2f}")
        lines.append(f"Average Loss:         ${metrics.get('avg_loss', 0):>14,.2f}")
        lines.append(f"Risk/Reward:          {metrics.get('risk_reward_ratio', 0):>15.2f}")
        lines.append(f"Consecutive Losses:   {metrics.get('consecutive_losses', 0):>15}")
        lines.append("")
        
        # Execution Stats
        lines.append("-" * 70)
        lines.append("EXECUTION STATISTICS")
        lines.append("-" * 70)
        
        lines.append(f"Candles Processed:    {results.get('candles_processed', 0):>15}")
        lines.append(f"Signals Generated:    {results.get('signals_generated', 0):>15}")
        lines.append(f"Trades Executed:      {results.get('trades_executed', 0):>15}")
        lines.append(f"Elapsed Time:         {results.get('elapsed_time', 0):>14.2f}s")
        lines.append("")
        
        # Footer
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def export_to_json(
        self,
        results: Dict[str, Any],
        filepath: str
    ):
        """
        Export results to JSON file.
        
        Args:
            results: Backtest results
            filepath: Output JSON path
        
        Example:
            >>> generator.export_to_json(results, 'results.json')
        """
        try:
            # Convert equity curve DataFrame to list
            export_data = results.copy()
            
            if 'equity_curve' in export_data:
                df = export_data['equity_curve']
                if isinstance(df, pd.DataFrame):
                    export_data['equity_curve'] = df.to_dict('records')
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Results exported to JSON: {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {str(e)}")
    
    def export_trades_to_csv(
        self,
        results: Dict[str, Any],
        filepath: str
    ):
        """
        Export trade list to CSV.
        
        Args:
            results: Backtest results
            filepath: Output CSV path
        
        Example:
            >>> generator.export_trades_to_csv(results, 'trades.csv')
        """
        try:
            trades = results.get('closed_trades', [])
            
            if not trades:
                logger.warning("No trades to export")
                return
            
            df = pd.DataFrame(trades)
            df.to_csv(filepath, index=False)
            
            logger.info(f"Trades exported to CSV: {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting trades: {str(e)}")
    
    def export_equity_curve_to_csv(
        self,
        results: Dict[str, Any],
        filepath: str
    ):
        """
        Export equity curve to CSV.
        
        Args:
            results: Backtest results
            filepath: Output CSV path
        """
        try:
            equity_curve = results.get('equity_curve')
            
            if equity_curve is None or len(equity_curve) == 0:
                logger.warning("No equity curve data to export")
                return
            
            if isinstance(equity_curve, pd.DataFrame):
                equity_curve.to_csv(filepath)
                logger.info(f"Equity curve exported to CSV: {filepath}")
            
        except Exception as e:
            logger.error(f"Error exporting equity curve: {str(e)}")
    
    def generate_html_report(
        self,
        results: Dict[str, Any],
        output_path: str
    ):
        """
        Generate HTML report (simplified version).
        
        Args:
            results: Backtest results
            output_path: Output HTML path
        
        Example:
            >>> generator.generate_html_report(results, 'report.html')
        """
        try:
            # Get summary text
            summary = self.generate_summary_report(results)
            
            # Simple HTML template
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        pre {{ background: #f5f5f5; padding: 20px; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>Backtest Performance Report</h1>
    <pre>{summary}</pre>
    
    <h2>Trade Details</h2>
    <p>Total Trades: {results.get('metrics', {}).get('total_trades', 0)}</p>
    <p>Win Rate: {results.get('metrics', {}).get('win_rate', 0):.2f}%</p>
    <p>Profit Factor: {results.get('metrics', {}).get('profit_factor', 0):.2f}</p>
</body>
</html>
"""
            
            with open(output_path, 'w') as f:
                f.write(html)
            
            logger.info(f"HTML report generated: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {str(e)}")


def generate_report(
    results: Dict[str, Any],
    output_dir: str = 'backtest_reports'
) -> Dict[str, str]:
    """
    Convenience function to generate all reports.
    
    Args:
        results: Backtest results
        output_dir: Output directory
    
    Returns:
        Dictionary of generated report paths
    """
    import os
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    generator = ReportGenerator()
    
    generated_files = {}
    
    # Text summary
    txt_path = os.path.join(output_dir, 'summary.txt')
    with open(txt_path, 'w') as f:
        f.write(generator.generate_summary_report(results))
    generated_files['summary'] = txt_path
    
    # JSON export
    json_path = os.path.join(output_dir, 'results.json')
    generator.export_to_json(results, json_path)
    generated_files['json'] = json_path
    
    # Trades CSV
    trades_path = os.path.join(output_dir, 'trades.csv')
    generator.export_trades_to_csv(results, trades_path)
    generated_files['trades'] = trades_path
    
    # Equity curve CSV
    equity_path = os.path.join(output_dir, 'equity_curve.csv')
    generator.export_equity_curve_to_csv(results, equity_path)
    generated_files['equity_curve'] = equity_path
    
    # HTML report
    html_path = os.path.join(output_dir, 'report.html')
    generator.generate_html_report(results, html_path)
    generated_files['html'] = html_path
    
    logger.info(f"All reports generated in: {output_dir}")
    
    return generated_files

"""
Walk-Forward Analysis Manager

Implements rolling window optimization and out-of-sample testing
to eliminate data-snooping bias and validate parameter stability.

Author: Quantitative Trading Systems Engineer
Date: March 22, 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Results from a single walk-forward iteration"""
    window_number: int
    in_sample_start: str
    in_sample_end: str
    out_of_sample_start: str
    out_of_sample_end: str
    optimal_params: Dict[str, Any]
    in_sample_metrics: Dict[str, float]
    out_of_sample_metrics: Dict[str, float]
    walk_forward_efficiency: float
    parameters_drift: Dict[str, float]


@dataclass
class WalkForwardAnalysisResult:
    """Complete walk-forward analysis results"""
    total_windows: int
    in_sample_period_days: int
    out_of_sample_period_days: int
    window_results: List[WalkForwardResult]
    aggregate_metrics: Dict[str, float]
    anchored_equity_curve: List[Dict[str, Any]]
    parameter_stability: Dict[str, float]
    regime_analysis: Dict[str, Any]


class WalkForwardManager:
    """
    Manages walk-forward analysis for strategy validation.
    
    Implements rolling window approach:
    1. Optimize on In-Sample (IS) period
    2. Test on Out-of-Sample (OOS) period
    3. Shift window forward
    4. Repeat
    
    Usage:
        >>> manager = WalkForwardManager()
        >>> results = manager.run_walk_forward_analysis(
        ...     symbol='RELIANCE',
        ...     timeframe='5minute',
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31',
        ...     in_sample_days=30,
        ...     out_of_sample_days=7,
        ...     param_grid={'supertrend_factor': [2, 3, 4]}
        ... )
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        Initialize Walk-Forward Manager.
        
        Args:
            initial_capital: Starting capital for all backtests
        """
        self.initial_capital = initial_capital
        self.results: Optional[WalkForwardAnalysisResult] = None
        
        logger.info("WalkForwardManager initialized")
    
    def _create_rolling_windows(
        self,
        start_date: datetime,
        end_date: datetime,
        in_sample_days: int,
        out_of_sample_days: int,
        overlap_percent: float = 0.0
    ) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """
        Create rolling window periods for walk-forward analysis.
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            in_sample_days: Training period length
            out_of_sample_days: Testing period length
            overlap_percent: Overlap between consecutive IS periods
            
        Returns:
            List of tuples: (is_start, is_end, oos_start, oos_end)
        """
        windows = []
        
        # Calculate step size (how much to shift each window)
        step_days = int(in_sample_days * (1 - overlap_percent))
        
        current_is_start = start_date
        
        while True:
            # In-Sample period
            current_is_end = current_is_start + timedelta(days=in_sample_days)
            
            # Out-of-Sample period
            current_oos_start = current_is_end
            current_oos_end = current_oos_start + timedelta(days=out_of_sample_days)
            
            # Check if we have enough data
            if current_oos_end > end_date:
                break
            
            windows.append((
                current_is_start,
                current_is_end,
                current_oos_start,
                current_oos_end
            ))
            
            # Shift window forward
            current_is_start += timedelta(days=step_days)
        
        logger.info(f"Created {len(windows)} walk-forward windows")
        return windows
    
    def _optimize_for_window(
        self,
        symbol: str,
        timeframe: str,
        is_start: datetime,
        is_end: datetime,
        param_grid: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Run parameter optimization for in-sample period.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            is_start: In-sample start date
            is_end: In-sample end date
            param_grid: Parameter grid to optimize
            
        Returns:
            Optimal parameters dictionary
        """
        from .parameter_optimizer import ParameterOptimizer
        
        optimizer = ParameterOptimizer()
        
        logger.info(f"Optimizing on IS period: {is_start.date()} to {is_end.date()}")
        
        # Run grid search on in-sample period
        results = optimizer.run_grid_search(
            symbol=symbol,
            timeframe=timeframe,
            start_date=is_start.strftime('%Y-%m-%d'),
            end_date=is_end.strftime('%Y-%m-%d'),
            param_grid=param_grid,
            n_jobs=-1,  # Use all CPUs
            show_progress=False
        )
        
        # Extract best parameters
        best_params = results['best_params']['params']
        
        logger.info(f"Best params for window: {best_params}")
        
        return best_params
    
    def _backtest_on_oos(
        self,
        symbol: str,
        timeframe: str,
        oos_start: datetime,
        oos_end: datetime,
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Run backtest on out-of-sample period with fixed parameters.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            oos_start: OOS start date
            oos_end: OOS end date
            params: Fixed parameters from IS optimization
            
        Returns:
            Backtest metrics dictionary
        """
        from .institutional_backtest_engine import InstitutionalBacktestEngine
        
        engine = InstitutionalBacktestEngine(
            initial_capital=self.initial_capital,
            capital_per_trade=self.initial_capital * 0.1,
            slippage_percent=0.0005,
            brokerage_per_trade=20.0,
            stop_loss_percent=0.02,
            take_profit_percent=0.04,
            max_positions=5,
            verbose=False
        )
        
        logger.info(f"Backtesting on OOS period: {oos_start.date()} to {oos_end.date()}")
        
        # Run backtest with fixed parameters
        results = engine.run_backtest_with_params(
            symbol=symbol,
            timeframe=timeframe,
            start_date=oos_start.strftime('%Y-%m-%d'),
            end_date=oos_end.strftime('%Y-%m-%d'),
            fixed_params=params,
            kite_client=None  # Use mock data
        )
        
        # Extract key metrics
        metrics = {
            'total_return': results.get('return_percent', 0.0),
            'sharpe_ratio': results.get('sharpe_ratio', 0.0),
            'max_drawdown': results.get('max_drawdown', 0.0),
            'win_rate': results.get('win_rate', 0.0),
            'profit_factor': results.get('profit_factor', 0.0),
            'total_trades': results.get('total_trades', 0),
            'final_capital': results.get('final_capital', self.initial_capital),
            'equity_curve': results.get('equity_curve', [])
        }
        
        return metrics
    
    def _calculate_walk_forward_efficiency(
        self,
        is_metrics: Dict[str, float],
        oos_metrics: Dict[str, float]
    ) -> float:
        """
        Calculate Walk-Forward Efficiency ratio.
        
        WFE = (OOS Annualized Return) / (IS Annualized Return)
        
        Args:
            is_metrics: In-sample metrics
            oos_metrics: Out-of-sample metrics
            
        Returns:
            WFE ratio (0.0 to 1.0+)
        """
        is_return = is_metrics.get('total_return', 0.0)
        oos_return = oos_metrics.get('total_return', 0.0)
        
        # Avoid division by zero
        if abs(is_return) < 0.001:
            return 0.0
        
        # Calculate efficiency
        wfe = oos_return / is_return
        
        # Clamp to reasonable range
        return max(0.0, min(2.0, wfe))
    
    def _analyze_parameter_stability(
        self,
        window_results: List[WalkForwardResult]
    ) -> Dict[str, float]:
        """
        Analyze how much optimal parameters drift across windows.
        
        Args:
            window_results: Results from all windows
            
        Returns:
            Dictionary with stability metrics per parameter
        """
        if not window_results:
            return {}
        
        # Collect all parameter values
        param_values = {}
        for result in window_results:
            for param_name, param_value in result.optimal_params.items():
                if param_name not in param_values:
                    param_values[param_name] = []
                param_values[param_name].append(param_value)
        
        # Calculate stability metrics
        stability = {}
        for param_name, values in param_values.items():
            if len(values) < 2:
                stability[param_name] = 1.0  # Perfect stability
                continue
            
            # Calculate coefficient of variation (CV)
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            # CV = std / mean (lower = more stable)
            cv = std_val / abs(mean_val) if abs(mean_val) > 0.001 else 0.0
            
            # Convert to stability score (1.0 = perfectly stable, 0.0 = unstable)
            stability_score = 1.0 / (1.0 + cv)
            
            stability[param_name] = stability_score
            
            logger.info(f"Parameter {param_name}: stability={stability_score:.3f}")
        
        return stability
    
    def run_walk_forward_analysis(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List[float]],
        in_sample_days: int = 30,
        out_of_sample_days: int = 7,
        overlap_percent: float = 0.0
    ) -> WalkForwardAnalysisResult:
        """
        Run complete walk-forward analysis.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)
            param_grid: Parameter grid to optimize
            in_sample_days: Training period length (days)
            out_of_sample_days: Testing period length (days)
            overlap_percent: Overlap between consecutive IS periods
            
        Returns:
            Complete WFA results
        """
        logger.info(f"Starting WFA for {symbol}")
        logger.info(f"IS: {in_sample_days} days, OOS: {out_of_sample_days} days")
        
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Create rolling windows
        windows = self._create_rolling_windows(
            start_dt, end_dt, in_sample_days, out_of_sample_days, overlap_percent
        )
        
        if not windows:
            raise ValueError("No valid windows created. Check date range and period lengths.")
        
        # Process each window
        window_results = []
        anchored_curve = []
        
        for i, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
            logger.info(f"\n{'='*60}")
            logger.info(f"Window {i+1}/{len(windows)}")
            logger.info(f"{'='*60}")
            
            # Step 1: Optimize on IS period
            optimal_params = self._optimize_for_window(
                symbol, timeframe, is_start, is_end, param_grid
            )
            
            # Step 2: Backtest on OOS period
            oos_metrics = self._backtest_on_oos(
                symbol, timeframe, oos_start, oos_end, optimal_params
            )
            
            # Also get IS metrics for comparison
            is_metrics = self._backtest_on_oos(
                symbol, timeframe, is_start, is_end, optimal_params
            )
            
            # Step 3: Calculate WFE
            wfe = self._calculate_walk_forward_efficiency(is_metrics, oos_metrics)
            
            # Create result object
            result = WalkForwardResult(
                window_number=i + 1,
                in_sample_start=is_start.strftime('%Y-%m-%d'),
                in_sample_end=is_end.strftime('%Y-%m-%d'),
                out_of_sample_start=oos_start.strftime('%Y-%m-%d'),
                out_of_sample_end=oos_end.strftime('%Y-%m-%d'),
                optimal_params=optimal_params,
                in_sample_metrics=is_metrics,
                out_of_sample_metrics=oos_metrics,
                walk_forward_efficiency=wfe,
                parameters_drift={}
            )
            
            window_results.append(result)
            
            # Add to anchored equity curve
            if oos_metrics.get('equity_curve'):
                anchored_curve.extend(oos_metrics['equity_curve'])
            
            logger.info(f"Window {i+1} WFE: {wfe:.3f}")
        
        # Calculate aggregate metrics
        all_wfe = [r.walk_forward_efficiency for r in window_results]
        avg_wfe = np.mean(all_wfe)
        std_wfe = np.std(all_wfe)
        
        # Parameter stability
        parameter_stability = self._analyze_parameter_stability(window_results)
        
        # Regime analysis (simplified)
        regime_analysis = {
            'avg_is_return': np.mean([r.in_sample_metrics['total_return'] for r in window_results]),
            'avg_oos_return': np.mean([r.out_of_sample_metrics['total_return'] for r in window_results]),
            'is_volatility': np.std([r.in_sample_metrics['total_return'] for r in window_results]),
            'oos_volatility': np.std([r.out_of_sample_metrics['total_return'] for r in window_results])
        }
        
        # Create final result
        final_result = WalkForwardAnalysisResult(
            total_windows=len(windows),
            in_sample_period_days=in_sample_days,
            out_of_sample_period_days=out_of_sample_days,
            window_results=window_results,
            aggregate_metrics={
                'avg_walk_forward_efficiency': avg_wfe,
                'std_walk_forward_efficiency': std_wfe,
                'min_wfe': min(all_wfe),
                'max_wfe': max(all_wfe),
                'windows_with_wfe_above_50': sum(1 for wfe in all_wfe if wfe >= 0.5),
                'windows_with_wfe_above_80': sum(1 for wfe in all_wfe if wfe >= 0.8)
            },
            anchored_equity_curve=anchored_curve,
            parameter_stability=parameter_stability,
            regime_analysis=regime_analysis
        )
        
        self.results = final_result
        
        logger.info(f"\n{'='*60}")
        logger.info(f"WFA Complete!")
        logger.info(f"Average WFE: {avg_wfe:.3f}")
        logger.info(f"Parameter Stability: {parameter_stability}")
        logger.info(f"{'='*60}\n")
        
        return final_result
    
    def to_dict(self, result: WalkForwardAnalysisResult) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization"""
        return {
            'total_windows': result.total_windows,
            'in_sample_period_days': result.in_sample_period_days,
            'out_of_sample_period_days': result.out_of_sample_period_days,
            'window_results': [
                {
                    'window_number': r.window_number,
                    'in_sample_period': f"{r.in_sample_start} to {r.in_sample_end}",
                    'out_of_sample_period': f"{r.out_of_sample_start} to {r.out_of_sample_end}",
                    'optimal_params': r.optimal_params,
                    'in_sample_metrics': r.in_sample_metrics,
                    'out_of_sample_metrics': r.out_of_sample_metrics,
                    'walk_forward_efficiency': r.walk_forward_efficiency
                }
                for r in result.window_results
            ],
            'aggregate_metrics': result.aggregate_metrics,
            'parameter_stability': result.parameter_stability,
            'regime_analysis': result.regime_analysis,
            'anchored_equity_curve': result.anchored_equity_curve[:100]  # First 100 points
        }
    
    def get_recommendation(self, result: WalkForwardAnalysisResult) -> Dict[str, Any]:
        """
        Generate trading recommendation based on WFA results.
        
        Args:
            result: WFA results
            
        Returns:
            Recommendation dictionary
        """
        avg_wfe = result.aggregate_metrics['avg_walk_forward_efficiency']
        
        if avg_wfe >= 0.8:
            recommendation = "STRONG_BUY"
            confidence = "HIGH"
            message = "Excellent walk-forward efficiency. Strategy adapts well to changing markets."
        elif avg_wfe >= 0.5:
            recommendation = "BUY"
            confidence = "MEDIUM"
            message = "Acceptable WFE. Strategy shows moderate robustness."
        else:
            recommendation = "DO_NOT_TRADE"
            confidence = "LOW"
            message = "Poor WFE. Strategy likely overfit. Do not trade live."
        
        return {
            'recommendation': recommendation,
            'confidence': confidence,
            'message': message,
            'avg_wfe': avg_wfe,
            'parameter_stability_avg': np.mean(list(result.parameter_stability.values())),
            'oos_success_rate': result.aggregate_metrics['windows_with_wfe_above_50'] / result.total_windows
        }

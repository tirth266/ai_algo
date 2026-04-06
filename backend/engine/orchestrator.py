"""
Trade Orchestrator Module

High-level orchestrator that handles the complete trading lifecycle:
1. Parameter Optimization → Find robust parameters
2. Monte Carlo Validation → Verify sequence independence
3. Walk-Forward Analysis → Validate on unseen data
4. Live Runner Initialization → Start paper/live trading

This is the "brain" that connects UI buttons to the full backend pipeline.

Author: Quantitative Trading Systems Engineer
Date: March 22, 2026
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeOrchestrator:
    """
    End-to-end trading workflow orchestrator.
    
    This class manages the complete validation pipeline:
    - Runs parameter optimization (grid search)
    - Validates with Monte Carlo simulation
    - Confirms with Walk-Forward Analysis
    - Initializes Live Runner for execution
    
    Usage:
        >>> orchestrator = TradeOrchestrator()
        >>> result = orchestrator.full_workflow_init(
        ...     symbol='RELIANCE',
        ...     config={'param_grid': {...}}
        ... )
    """
    
    def __init__(self):
        """Initialize the trade orchestrator."""
        self.optimizer = None
        self.monte_carlo = None
        self.wfa_manager = None
        self.live_runner = None
        
        logger.info("TradeOrchestrator initialized")
    
    def _lazy_load_components(self):
        """Lazy load heavy components to avoid circular imports."""
        if self.optimizer is None:
            from backend.backtest.parameter_optimizer import ParameterOptimizer
            self.optimizer = ParameterOptimizer()
            
        if self.monte_carlo is None:
            from backend.backtest.monte_carlo_analyzer import MonteCarloAnalyzer
            self.monte_carlo = MonteCarloAnalyzer(num_simulations=1000)
            
        if self.wfa_manager is None:
            from backend.backtest.wfa_manager import WalkForwardManager
            self.wfa_manager = WalkForwardManager(initial_capital=100000)
            
        if self.live_runner is None:
            from backend.engine.runner.live_runner import LiveRunner
            self.live_runner = LiveRunner(paper_trading=True)
    
    async def full_workflow_init(self, symbol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete validation pipeline: Optimize → Validate → Paper Trade.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'NIFTY50')
            config: Configuration dictionary containing:
                - param_grid: Parameter grid for optimization
                - timeframe: Candle timeframe (default: '5minute')
                - days: Number of days for backtest (default: 90)
                - in_sample_days: Days for in-sample period (WFA)
                - out_sample_days: Days for out-of-sample period (WFA)
        
        Returns:
            Dictionary with:
                - status: 'Active' or 'Failed'
                - best_params: Optimized parameters
                - risk_profile: Monte Carlo results
                - wfe: Walk-Forward Efficiency
                - position_size: Recommended position size (%)
                - message: Human-readable status
        """
        try:
            # Lazy load components
            self._lazy_load_components()
            
            logger.info(f"Starting full workflow for {symbol}")
            logger.info(f"Configuration: {config}")
            
            # =====================================================================
            # STEP 1: PARAMETER OPTIMIZATION
            # =====================================================================
            logger.info("="*80)
            logger.info("STEP 1: PARAMETER OPTIMIZATION")
            logger.info("="*80)
            
            from datetime import timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=config.get('days', 90))
            
            opt_results = self.optimizer.run_grid_search(
                symbol=symbol,
                timeframe=config.get('timeframe', '5minute'),
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                param_grid=config['param_grid'],
                n_jobs=-1,
                show_progress=False
            )
            
            best_params = opt_results['best_params']['params']
            robustness_score = opt_results['robust_zone']['robustness_score']
            
            logger.info(f"✓ Best params found: {best_params}")
            logger.info(f"✓ Robustness score: {robustness_score:.2f}")
            
            # Check if parameters are robust enough
            if robustness_score < 2.0:
                logger.warning(f"Low robustness score ({robustness_score:.2f}). Strategy may be overfit.")
            
            # =====================================================================
            # STEP 2: MONTE CARLO VALIDATION
            # =====================================================================
            logger.info("="*80)
            logger.info("STEP 2: MONTE CARLO VALIDATION")
            logger.info("="*80)
            
            trades = opt_results.get('trades', [])
            equity_curve = opt_results.get('equity_curve', [])
            
            if not trades:
                return {
                    'status': 'Failed',
                    'error': 'No trades generated from optimization',
                    'message': 'Optimization failed to generate any trades'
                }
            
            # Load trades into Monte Carlo analyzer
            self.monte_carlo.load_trades([t.to_dict() if hasattr(t, 'to_dict') else t for t in trades])
            
            if equity_curve:
                self.monte_carlo.set_original_equity_curve(equity_curve)
            
            # Run simulation
            mc_result = self.monte_carlo.run_simulation(initial_capital=100000)
            
            risk_of_ruin = mc_result.risk_of_ruin
            expected_max_dd = mc_result.expected_max_drawdown
            
            logger.info(f"✓ Risk of Ruin: {(risk_of_ruin * 100):.2f}%")
            logger.info(f"✓ Expected Max DD: {(expected_max_dd * 100):.2f}%")
            
            # Auto-adjust position size based on risk
            if risk_of_ruin > 0.10:
                position_size = 2  # Conservative (2%)
                risk_message = "High risk detected - Position size reduced to 2%"
            elif risk_of_ruin > 0.05:
                position_size = 5  # Moderate (5%)
                risk_message = "Moderate risk - Position size set to 5%"
            else:
                position_size = 10  # Aggressive (10%)
                risk_message = "Low risk - Position size set to 10%"
            
            logger.info(f"✓ {risk_message}")
            
            # =====================================================================
            # STEP 3: WALK-FORWARD ANALYSIS
            # =====================================================================
            logger.info("="*80)
            logger.info("STEP 3: WALK-FORWARD ANALYSIS")
            logger.info("="*80)
            
            # Estimate window sizes
            total_days = config.get('days', 90)
            windows = 4
            oos_days = int((total_days / windows) * 0.3)
            is_days = int((total_days / windows) * 0.7)
            
            wfa_results = self.wfa_manager.run_walk_forward_analysis(
                symbol=symbol,
                timeframe=config.get('timeframe', '5minute'),
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                param_grid=config['param_grid'],
                in_sample_days=is_days,
                out_of_sample_days=oos_days,
                overlap_percent=0.0
            )
            
            avg_wfe = wfa_results.aggregate_metrics['avg_walk_forward_efficiency']
            
            logger.info(f"✓ Average WFE: {(avg_wfe * 100):.1f}%")
            
            # Check if WFE passes threshold
            min_wfe_threshold = 0.50
            if avg_wfe < min_wfe_threshold:
                logger.error(f"WFE below threshold ({avg_wfe*100:.1f}% < {min_wfe_threshold*100:.0f}%)")
                return {
                    'status': 'Failed',
                    'error': 'Walk-Forward Efficiency below threshold',
                    'wfe': avg_wfe,
                    'message': f'Strategy overfit - WFE {(avg_wfe*100):.1f}% < {min_wfe_threshold*100:.0f}% minimum'
                }
            
            logger.info(f"✓ WFE validated - Strategy shows robustness")
            
            # =====================================================================
            # STEP 4: LIVE RUNNER INITIALIZATION
            # =====================================================================
            logger.info("="*80)
            logger.info("STEP 4: LIVE RUNNER INITIALIZATION")
            logger.info("="*80)
            
            # Import combined power strategy
            from strategies.combined_power_strategy import CombinedPowerStrategy
            
            # Create strategy config with optimized parameters
            strategy_config = {
                'symbol': symbol,
                'timeframe': config.get('timeframe', '5minute'),
                **best_params  # Merge optimized parameters
            }
            
            # Start live runner with optimized parameters
            success = await self.live_runner.start_strategy(
                strategy_name='combined_power',
                symbol=symbol,
                timeframe=config.get('timeframe', '5minute'),
                params=strategy_config
            )
            
            if not success:
                return {
                    'status': 'Failed',
                    'error': 'Live runner initialization failed',
                    'message': 'Failed to initialize live trading engine'
                }
            
            # Get live runner status
            runner_status = self.live_runner.get_status()
            
            # =====================================================================
            # FINAL RESULTS
            # =====================================================================
            logger.info("="*80)
            logger.info("WORKFLOW COMPLETE - ALL STEPS PASSED")
            logger.info("="*80)
            
            result = {
                'status': 'Active',
                'best_params': best_params,
                'robustness_score': robustness_score,
                'risk_profile': {
                    'risk_of_ruin': risk_of_ruin,
                    'expected_max_drawdown': expected_max_dd,
                    'position_size_pct': position_size,
                    'message': risk_message
                },
                'walk_forward': {
                    'avg_wfe': avg_wfe,
                    'oos_success_rate': wfa_results.aggregate_metrics['windows_with_wfe_above_50'] / wfa_results.total_windows,
                    'total_windows': wfa_results.total_windows
                },
                'live_runner': {
                    'paper_trading': runner_status['paper_trading'],
                    'active_strategies': runner_status['active_strategies'],
                    'kill_switch_ready': not runner_status['kill_switch_active']
                },
                'message': f"Strategy validated and activated. {risk_message}. WFE: {avg_wfe*100:.1f}%"
            }
            
            logger.info(f"✅ WORKFLOW SUCCESSFUL")
            logger.info(f"   Status: {result['status']}")
            logger.info(f"   Params: {best_params}")
            logger.info(f"   Risk: {risk_of_ruin*100:.2f}%")
            logger.info(f"   WFE: {avg_wfe*100:.1f}%")
            logger.info(f"   Position Size: {position_size}%")
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}", exc_info=True)
            return {
                'status': 'Failed',
                'error': str(e),
                'message': f'Workflow execution failed: {str(e)}'
            }
    
    async def quick_start(self, symbol: str, supertrend_factor: float = 3.0, min_votes: int = 3) -> Dict[str, Any]:
        """
        Simplified workflow with predefined parameters.
        
        For users who want to skip optimization and use known-good parameters.
        
        Args:
            symbol: Trading symbol
            supertrend_factor: Supertrend multiplier (default: 3.0)
            min_votes: Minimum strategy votes required (default: 3)
        
        Returns:
            Workflow result dictionary
        """
        config = {
            'param_grid': {
                'supertrend_factor': [supertrend_factor],
                'min_votes': [min_votes]
            },
            'days': 90,
            'timeframe': '5minute'
        }
        
        return await self.full_workflow_init(symbol, config)


# Global orchestrator instance
_orchestrator: Optional[TradeOrchestrator] = None


def get_orchestrator() -> TradeOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TradeOrchestrator()
    return _orchestrator

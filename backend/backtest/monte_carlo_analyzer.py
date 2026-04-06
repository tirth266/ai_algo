"""
Monte Carlo Simulation Engine for Backtesting
Analyzes sequence risk and probability of ruin through trade shuffling
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json


@dataclass
class Trade:
    """Represents a single trade from backtest"""
    entry_date: str
    exit_date: str
    pnl: float
    return_pct: float
    max_drawdown: float
    max_profit: float
    duration_bars: int
    direction: str  # 'LONG' or 'SHORT'


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    original_equity_curve: List[float]
    simulated_curves: List[List[float]]
    percentiles: Dict[str, List[float]]
    risk_of_ruin: float
    expected_max_drawdown: float
    confidence_metrics: Dict[str, float]


class MonteCarloAnalyzer:
    """
    Monte Carlo simulation engine for strategy stress testing
    
    Shuffles trade sequences to analyze:
    - Sequence risk (order dependency)
    - Probability of ruin
    - Confidence intervals
    - Expected maximum drawdown
    """
    
    def __init__(self, num_simulations: int = 1000):
        """
        Initialize Monte Carlo analyzer
        
        Args:
            num_simulations: Number of simulations to run (default: 1000)
        """
        self.num_simulations = num_simulations
        self.trades: List[Trade] = []
        self.original_equity_curve: List[float] = []
        
    def load_trades(self, trades_data: List[Dict]) -> None:
        """
        Load trades from backtest results
        
        Args:
            trades_data: List of trade dictionaries from backtest engine
        """
        self.trades = []
        for trade in trades_data:
            self.trades.append(Trade(
                entry_date=trade.get('entry_date', ''),
                exit_date=trade.get('exit_date', ''),
                pnl=trade.get('pnl', 0.0),
                return_pct=trade.get('return_pct', 0.0),
                max_drawdown=trade.get('max_drawdown', 0.0),
                max_profit=trade.get('max_profit', 0.0),
                duration_bars=trade.get('duration_bars', 0),
                direction=trade.get('direction', 'LONG')
            ))
        
    def set_original_equity_curve(self, equity_curve: List[float]) -> None:
        """Set the original (unshuffled) equity curve"""
        self.original_equity_curve = equity_curve
        
    def _shuffle_trades(self, seed: Optional[int] = None) -> List[Trade]:
        """
        Randomly shuffle trade order
        
        Args:
            seed: Random seed for reproducibility
            
        Returns:
            Shuffled list of trades
        """
        if seed is not None:
            np.random.seed(seed)
        
        indices = np.random.permutation(len(self.trades))
        return [self.trades[i] for i in indices]
    
    def _build_equity_curve(self, trades: List[Trade], initial_capital: float = 100000) -> List[float]:
        """
        Build cumulative equity curve from list of trades
        
        Args:
            trades: List of trades (can be shuffled)
            initial_capital: Starting capital
            
        Returns:
            List of cumulative equity values
        """
        equity_curve = [initial_capital]
        current_equity = initial_capital
        
        for trade in trades:
            current_equity += trade.pnl
            equity_curve.append(current_equity)
            
        return equity_curve
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """
        Calculate maximum drawdown percentage from equity curve
        
        Args:
            equity_curve: List of equity values
            
        Returns:
            Maximum drawdown as percentage (e.g., -0.25 for 25% drawdown)
        """
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_dd:
                max_dd = drawdown
                
        return max_dd
    
    def run_simulation(self, initial_capital: float = 100000, 
                      ruin_threshold: float = 0.20) -> MonteCarloResult:
        """
        Run Monte Carlo simulation
        
        Args:
            initial_capital: Starting capital for simulation
            ruin_threshold: Drawdown threshold for "ruin" (default: 20%)
            
        Returns:
            MonteCarloResult with all simulation metrics
        """
        if len(self.trades) == 0:
            raise ValueError("No trades loaded. Call load_trades() first.")
        
        # Store all simulated curves
        simulated_curves: List[List[float]] = []
        
        # Track metrics
        max_drawdowns: List[float] = []
        final_returns: List[float] = []
        ruin_count = 0
        
        # Run simulations
        for i in range(self.num_simulations):
            # Shuffle trades
            shuffled_trades = self._shuffle_trades()
            
            # Build equity curve
            equity_curve = self._build_equity_curve(shuffled_trades, initial_capital)
            simulated_curves.append(equity_curve)
            
            # Calculate metrics
            max_dd = self._calculate_max_drawdown(equity_curve)
            max_drawdowns.append(max_dd)
            
            final_return = (equity_curve[-1] - initial_capital) / initial_capital
            final_returns.append(final_return)
            
            # Check for ruin
            if max_dd >= ruin_threshold:
                ruin_count += 1
        
        # Calculate percentiles at each point in curve
        curves_array = np.array(simulated_curves)
        percentiles = {
            '5th': np.percentile(curves_array, 5, axis=0).tolist(),
            '25th': np.percentile(curves_array, 25, axis=0).tolist(),
            '50th': np.percentile(curves_array, 50, axis=0).tolist(),  # Median
            '75th': np.percentile(curves_array, 75, axis=0).tolist(),
            '95th': np.percentile(curves_array, 95, axis=0).tolist()
        }
        
        # Calculate confidence metrics
        avg_max_drawdown = np.mean(max_drawdowns)
        std_max_drawdown = np.std(max_drawdowns)
        
        avg_final_return = np.mean(final_returns)
        std_final_return = np.std(final_returns)
        
        # Risk of ruin
        risk_of_ruin = ruin_count / self.num_simulations
        
        # Expected max drawdown (average of worst 5%)
        worst_5_percent_idx = int(np.ceil(0.05 * self.num_simulations))
        sorted_drawdowns = sorted(max_drawdowns, reverse=True)
        expected_max_drawdown = np.mean(sorted_drawdowns[:worst_5_percent_idx])
        
        # Create result object
        result = MonteCarloResult(
            original_equity_curve=self.original_equity_curve if self.original_equity_curve 
                                   else self._build_equity_curve(self.trades, initial_capital),
            simulated_curves=simulated_curves,
            percentiles=percentiles,
            risk_of_ruin=risk_of_ruin,
            expected_max_drawdown=expected_max_drawdown,
            confidence_metrics={
                'avg_max_drawdown': avg_max_drawdown,
                'std_max_drawdown': std_max_drawdown,
                'avg_final_return': avg_final_return,
                'std_final_return': std_final_return,
                'risk_of_ruin': risk_of_ruin,
                'expected_max_drawdown': expected_max_drawdown,
                'win_rate': sum(1 for t in self.trades if t.pnl > 0) / len(self.trades),
                'profit_factor': self._calculate_profit_factor(),
                'num_simulations': self.num_simulations
            }
        )
        
        return result
    
    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor from loaded trades"""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_position_size_recommendation(self, account_balance: float,
                                        target_risk_of_ruin: float = 0.05) -> Dict:
        """
        Recommend position size based on Monte Carlo results
        
        Args:
            account_balance: Total account balance
            target_risk_of_ruin: Maximum acceptable risk of ruin (default: 5%)
            
        Returns:
            Dictionary with position size recommendations
        """
        # This would require running multiple simulations with different position sizes
        # For now, return basic recommendation based on current risk
        current_risk = self.confidence_metrics.get('risk_of_ruin', 0) if hasattr(self, 'confidence_metrics') else 0
        
        if current_risk <= target_risk_of_ruin:
            recommendation = "SAFE"
            suggested_size = account_balance * 0.10  # 10% per trade
        elif current_risk <= target_risk_of_ruin * 2:
            recommendation = "MODERATE"
            suggested_size = account_balance * 0.05  # 5% per trade
        else:
            recommendation = "REDUCE_RISK"
            suggested_size = account_balance * 0.02  # 2% per trade
        
        return {
            'recommendation': recommendation,
            'suggested_position_size': suggested_size,
            'position_pct': (suggested_size / account_balance) * 100,
            'current_risk_of_ruin': current_risk,
            'target_risk_of_ruin': target_risk_of_ruin
        }
    
    def to_dict(self, result: MonteCarloResult) -> Dict:
        """Convert MonteCarloResult to dictionary for JSON serialization"""
        return {
            'original_equity_curve': result.original_equity_curve,
            'simulated_curves_sample': result.simulated_curves[:100],  # First 100 for display
            'num_simulations': len(result.simulated_curves),
            'percentiles': result.percentiles,
            'risk_of_ruin': result.risk_of_ruin,
            'expected_max_drawdown': result.expected_max_drawdown,
            'confidence_metrics': result.confidence_metrics
        }


# Convenience function for API endpoint
def analyze_sequence_risk(trades: List[Dict], 
                         equity_curve: List[float],
                         num_simulations: int = 1000,
                         initial_capital: float = 100000) -> Dict:
    """
    Analyze sequence risk using Monte Carlo simulation
    
    Args:
        trades: List of trades from backtest
        equity_curve: Original equity curve
        num_simulations: Number of simulations to run
        initial_capital: Starting capital
        
    Returns:
        Dictionary with Monte Carlo analysis results
    """
    analyzer = MonteCarloAnalyzer(num_simulations=num_simulations)
    analyzer.load_trades(trades)
    analyzer.set_original_equity_curve(equity_curve)
    
    result = analyzer.run_simulation(initial_capital=initial_capital)
    
    return analyzer.to_dict(result)

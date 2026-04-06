"""
Demo script for Monte Carlo Simulation and Strategy Robustness Testing Module

This script demonstrates how to use the robustness testing framework
to evaluate trading strategy performance.
"""

import numpy as np
from datetime import datetime, timedelta
from backtest.robustness import (
    run_robustness_test,
    quick_robustness_check,
    RobustnessTester
)


class MockTrade:
    """Mock trade object for demonstration"""
    def __init__(self, pnl: float, symbol: str = 'TEST'):
        self.pnl = pnl
        self.pnl_percent = (pnl / 100) * 100
        self.symbol = symbol
        self.entry_time = datetime.now()
        self.exit_time = datetime.now() + timedelta(hours=1)


def generate_mock_trades(n_trades: int = 100, win_rate: float = 0.55):
    """Generate realistic mock trades for testing"""
    trades = []
    np.random.seed(42)
    
    for i in range(n_trades):
        if np.random.random() < win_rate:
            # Winning trade: average gain $800
            pnl = np.random.normal(800, 300)
        else:
            # Losing trade: average loss $500
            pnl = -np.abs(np.random.normal(-500, 200))
        
        trades.append(MockTrade(pnl=pnl))
    
    return trades


def main():
    print("=" * 80)
    print("Monte Carlo Simulation & Strategy Robustness Testing Demo")
    print("=" * 80)
    print()
    
    # Generate mock trades
    print("Generating 100 mock trades with 55% win rate...")
    trades = generate_mock_trades(n_trades=100, win_rate=0.55)
    total_pnl = sum(t.pnl for t in trades)
    print(f"Generated {len(trades)} trades")
    print(f"Total PnL: ${total_pnl:,.2f}")
    print()
    
    # Example 1: Full robustness test
    print("-" * 80)
    print("Example 1: Full Robustness Test")
    print("-" * 80)
    results = run_robustness_test(
        trades=trades,
        n_simulations=500,
        initial_capital=100000,
        sampling_method='bootstrap',
        verbose=True
    )
    
    print("\nKey Results:")
    print(f"  Robustness Score: {results['robustness_score']:.1f}/100")
    print(f"  Probability of Loss: {results['probability_of_loss']:.2%}")
    print(f"  Expected Drawdown: {results['expected_drawdown']:.2f}%")
    print(f"  Median Return: {results['median_return']:.2f}%")
    print(f"  Worst Case Return: {results['worst_case_return']:.2f}%")
    print(f"  95% VaR: {results['var_95']:.2f}%")
    print()
    
    # Example 2: Quick check
    print("-" * 80)
    print("Example 2: Quick Robustness Check")
    print("-" * 80)
    quick_results = quick_robustness_check(
        trades=trades,
        n_simulations=200
    )
    
    print(f"\nQuick Results:")
    print(f"  Probability of Loss: {quick_results['probability_of_loss']:.2%}")
    print(f"  Robustness Score: {quick_results['robustness_score']:.1f}/100")
    print()
    
    # Example 3: Compare different sampling methods
    print("-" * 80)
    print("Example 3: Comparing Sampling Methods")
    print("-" * 80)
    
    methods = ['bootstrap', 'random_shuffle', 'block']
    
    for method in methods:
        result = run_robustness_test(
            trades=trades,
            n_simulations=300,
            sampling_method=method,
            verbose=False
        )
        print(f"\n{method.upper()}:")
        print(f"  Robustness Score: {result['robustness_score']:.1f}/100")
        print(f"  Prob of Loss: {result['probability_of_loss']:.2%}")
        print(f"  Median Return: {result['median_return']:.2f}%")
    
    print()
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print()
    print("Next Steps:")
    print("1. Review the generated reports in the output directory")
    print("2. Adjust parameters based on your risk tolerance")
    print("3. Run on your actual backtest trade log")
    print()
    print("For detailed documentation, see: backtest/robustness/README.md")
    print()


if __name__ == '__main__':
    main()

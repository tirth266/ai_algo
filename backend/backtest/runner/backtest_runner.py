"""
Backtest Runner Module

Main orchestrator for backtesting simulation.

Features:
- Complete backtest workflow
- Strategy integration
- Real-time simulation
- Progress tracking
- Results compilation

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import pandas as pd
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import time

from ..data.data_loader import DataLoader, get_data_loader
from ..simulator.candle_simulator import CandleSimulator
from ..execution.trade_executor import TradeExecutor
from ..portfolio.portfolio_manager import PortfolioManager
from ..analytics.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Run complete backtesting simulation.
    
    Orchestrates all components:
    1. Load historical data
    2. Initialize strategy
    3. Simulate candle-by-candle
    4. Generate signals
    5. Execute trades
    6. Track portfolio
    7. Calculate metrics
    
    Usage:
        >>> runner = BacktestRunner()
        >>> results = runner.run_backtest(
        ...     strategy=strategy,
        ...     data=df,
        ...     initial_capital=100000
        ... )
    """
    
    def __init__(self):
        """Initialize backtest runner."""
        self.data_loader = get_data_loader()
        
        # Components (initialized per backtest)
        self.simulator = None
        self.trade_executor = None
        self.portfolio_manager = None
        self.metrics_calculator = None
        
        # Results storage
        self.results = {}
        
        logger.info("BacktestRunner initialized")
    
    def run_backtest(
        self,
        strategy: Any,
        data: pd.DataFrame,
        initial_capital: float = 100000.0,
        symbol: str = 'TEST',
        use_atr_sizing: bool = True,
        slippage_percent: float = 0.0,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete backtest simulation.
        
        Args:
            strategy: Trading strategy instance
            data: Historical OHLCV DataFrame
            initial_capital: Starting capital
            symbol: Trading symbol
            use_atr_sizing: Use ATR-based position sizing
            slippage_percent: Slippage percentage
            verbose: Show progress
        
        Returns:
            Dictionary with backtest results
        
        Example:
            >>> results = runner.run_backtest(
            ...     strategy=strategy,
            ...     data=df,
            ...     initial_capital=100000
            ... )
        """
        start_time = time.time()
        
        logger.info(f"Starting backtest for {symbol}...")
        
        try:
            # Validate data
            if not self.data_loader.validate_data(data):
                logger.error("Data validation failed")
                return {'error': 'Data validation failed'}
            
            # Initialize components
            self.simulator = CandleSimulator(data)
            self.trade_executor = TradeExecutor()
            self.trade_executor.configure(slippage_percent=slippage_percent)
            self.portfolio_manager = PortfolioManager(initial_capital)
            self.metrics_calculator = PerformanceMetrics()
            
            # Trading loop
            candles_processed = 0
            signals_generated = 0
            trades_executed = 0
            
            if verbose:
                print(f"\n{'='*60}")
                print(f"Backtesting {symbol}")
                print(f"{'='*60}")
                print(f"Initial Capital: ${initial_capital:,.2f}")
                print(f"Data Range: {data.index.min()} to {data.index.max()}")
                print(f"Total Bars: {len(data)}")
                print(f"{'='*60}\n")
            
            while self.simulator.has_next():
                # Get next candle
                candle = self.simulator.next_candle()
                
                if not candle:
                    break
                
                candles_processed += 1
                
                # Get available historical data
                historical_df = self.simulator.get_available_data()
                
                # Need minimum data for indicators
                if len(historical_df) < 50:
                    continue
                
                # Generate signal
                try:
                    signal = strategy.generate_signal(historical_df)
                    
                    if signal and signal.get('type') in ['BUY', 'SELL']:
                        signals_generated += 1
                        
                        # Execute trade
                        trade_id = self.trade_executor.open_trade(
                            signal=signal,
                            candle=candle,
                            use_atr_sizing=use_atr_sizing
                        )
                        
                        if trade_id:
                            trades_executed += 1
                            
                            # Add to portfolio
                            trade = self.trade_executor.trade_manager.get_trade_by_id(trade_id)
                            if trade:
                                self.portfolio_manager.add_position(trade)
                    
                    # Check stop losses on open trades
                    current_prices = {symbol: candle['close']}
                    closed_trades = self.trade_executor.check_stop_losses(current_prices)
                    
                    # Update portfolio for closed trades
                    if closed_trades:
                        recently_closed = [
                            t for t in self.trade_executor.get_closed_trades()
                            if getattr(t, 'trade_id', None) in closed_trades
                        ]
                        
                        if recently_closed:
                            self.portfolio_manager.update_equity(
                                recently_closed,
                                candle['time']
                            )
                            
                            # Remove from open positions
                            for trade in recently_closed:
                                self.portfolio_manager.remove_position(trade.symbol)
                    
                except Exception as e:
                    logger.error(f"Error processing candle {candles_processed}: {str(e)}")
                    continue
                
                # Progress reporting
                if verbose and candles_processed % 100 == 0:
                    progress = self.simulator.get_progress() * 100
                    print(
                        f"Progress: {progress:.1f}% | "
                        f"Signals: {signals_generated} | "
                        f"Trades: {trades_executed} | "
                        f"Equity: ${self.portfolio_manager.get_portfolio_value():,.2f}"
                    )
            
            # Close all remaining open trades
            final_prices = {symbol: candle['close']}
            self.trade_executor.close_all_trades(
                final_prices,
                candle['time'],
                reason='end_of_backtest'
            )
            
            # Update portfolio with remaining closed trades
            for trade in self.trade_executor.get_closed_trades():
                if trade.status.value == 'CLOSED':
                    self.portfolio_manager.remove_position(trade.symbol)
            
            # Calculate final metrics
            elapsed_time = time.time() - start_time
            
            results = self._compile_results(
                initial_capital=initial_capital,
                symbol=symbol,
                candles_processed=candles_processed,
                signals_generated=signals_generated,
                trades_executed=trades_executed,
                elapsed_time=elapsed_time
            )
            
            # Store results
            self.results = results
            
            if verbose:
                self._print_summary(results)
            
            logger.info(
                f"Backtest completed: "
                f"Return={results['metrics']['total_return']:.2f}%, "
                f"WinRate={results['metrics']['win_rate']:.1f}%"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            return {'error': str(e)}
    
    def _compile_results(
        self,
        initial_capital: float,
        symbol: str,
        candles_processed: int,
        signals_generated: int,
        trades_executed: int,
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        Compile backtest results.
        
        Args:
            initial_capital: Starting capital
            symbol: Trading symbol
            candles_processed: Number of candles processed
            signals_generated: Number of signals
            trades_executed: Number of trades
            elapsed_time: Execution time
        
        Returns:
            Results dictionary
        """
        # Get portfolio stats
        portfolio_stats = self.portfolio_manager.get_stats()
        
        # Get trade stats
        trade_stats = self.trade_executor.get_stats()
        
        # Calculate performance metrics
        closed_trades = self.trade_executor.get_closed_trades()
        equity_curve = self.portfolio_manager.get_equity_curve()
        
        # Calculate returns series
        if len(equity_curve) > 0:
            returns = equity_curve['equity'].pct_change().dropna()
        else:
            returns = pd.Series()
        
        # Determine years
        if len(equity_curve) > 0:
            # Reset index to access timestamp column
            equity_curve_reset = equity_curve.reset_index()
            time_span = equity_curve_reset['timestamp'].iloc[-1] - equity_curve_reset['timestamp'].iloc[0]
            years = time_span.total_seconds() / (365.25 * 24 * 3600)
        else:
            years = 1.0
        
        # Calculate all metrics
        metrics = self.metrics_calculator.calculate_all(
            initial_capital=initial_capital,
            final_capital=portfolio_stats['current_equity'],
            trades=closed_trades,
            equity_curve=equity_curve['equity'] if len(equity_curve) > 0 else pd.Series(),
            returns=returns,
            years=years
        )
        
        return {
            'symbol': symbol,
            'initial_capital': initial_capital,
            'final_capital': portfolio_stats['current_equity'],
            'total_return': portfolio_stats['total_return'],
            'candles_processed': candles_processed,
            'signals_generated': signals_generated,
            'trades_executed': trades_executed,
            'elapsed_time': round(elapsed_time, 2),
            'portfolio': portfolio_stats,
            'trades': trade_stats,
            'metrics': metrics,
            'equity_curve': equity_curve,
            'closed_trades': [t.to_dict() for t in closed_trades],
            'timestamp': datetime.now().isoformat()
        }
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print backtest summary."""
        print(f"\n{'='*60}")
        print("BACKTEST RESULTS SUMMARY")
        print(f"{'='*60}")
        
        print(f"\nSymbol: {results['symbol']}")
        print(f"Period: {results['candles_processed']} bars")
        print(f"Time: {results['elapsed_time']:.2f}s")
        
        print(f"\n--- Performance ---")
        print(f"Initial Capital: ${results['initial_capital']:,.2f}")
        print(f"Final Capital: ${results['final_capital']:,.2f}")
        print(f"Total Return: {results['metrics']['total_return']:.2f}%")
        print(f"Absolute Return: ${results['metrics']['total_return_abs']:,.2f}")
        
        print(f"\n--- Risk Metrics ---")
        print(f"Max Drawdown: {results['metrics']['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
        print(f"Sortino Ratio: {results['metrics']['sortino_ratio']:.2f}")
        
        print(f"\n--- Trade Statistics ---")
        print(f"Total Trades: {results['metrics']['total_trades']}")
        print(f"Win Rate: {results['metrics']['win_rate']:.1f}%")
        print(f"Avg Win: ${results['metrics']['avg_win']:,.2f}")
        print(f"Avg Loss: ${results['metrics']['avg_loss']:,.2f}")
        print(f"Profit Factor: {results['metrics']['profit_factor']:.2f}")
        print(f"Expectancy: ${results['metrics']['expectancy']:.2f}/trade")
        
        print(f"\n{'='*60}\n")


# Global runner instance
_backtest_runner: Optional[BacktestRunner] = None


def get_backtest_runner() -> BacktestRunner:
    """Get or create global backtest runner."""
    global _backtest_runner
    
    if _backtest_runner is None:
        _backtest_runner = BacktestRunner()
    
    return _backtest_runner


def run_backtest(
    strategy: Any,
    data: pd.DataFrame,
    initial_capital: float = 100000.0,
    symbol: str = 'TEST',
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to run backtest.
    
    Args:
        strategy: Trading strategy
        data: Historical data
        initial_capital: Starting capital
        symbol: Trading symbol
        **kwargs: Additional arguments
    
    Returns:
        Backtest results
    """
    runner = get_backtest_runner()
    return runner.run_backtest(strategy, data, initial_capital, symbol, **kwargs)

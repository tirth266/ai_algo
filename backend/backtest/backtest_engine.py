"""
Backtest Engine Module

Main orchestrator for running backtests on historical data.

Workflow:
1. Load historical data
2. Initialize strategy with indicators
3. Iterate through candles candle-by-candle
4. Calculate indicators at each step
5. Generate trading signals
6. Simulate trade execution
7. Track equity and performance
8. Return comprehensive results

Usage:
    >>> engine = BacktestEngine()
    >>> results = engine.run(
    ...     strategy=MyStrategy,
    ...     data=data,
    ...     initial_capital=100000
    ... )
"""

from typing import Dict, Any, Optional, Type, List
import pandas as pd
from datetime import datetime
import logging

from .historical_data_loader import HistoricalDataLoader
from .trade_simulator import TradeSimulator
from .performance_metrics import PerformanceMetrics
from .equity_curve import EquityCurve

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Main backtesting orchestrator.
    
    Simulates strategy execution on historical data with realistic:
    - Trade execution (slippage, brokerage)
    - Position management
    - Performance tracking
    - Risk metrics
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        slippage_percent: float = 0.0005,
        brokerage_per_trade: float = 20.0,
        verbose: bool = True
    ):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital (default: 100,000)
            slippage_percent: Slippage as percentage (default: 0.05%)
            brokerage_per_trade: Fixed brokerage per trade (default: 20)
            verbose: Enable detailed logging (default: True)
        """
        self.initial_capital = initial_capital
        self.slippage_percent = slippage_percent
        self.brokerage_per_trade = brokerage_per_trade
        self.verbose = verbose
        
        # Components (initialized in run())
        self.data_loader: Optional[HistoricalDataLoader] = None
        self.trade_simulator: Optional[TradeSimulator] = None
        self.performance_metrics: Optional[PerformanceMetrics] = None
        self.equity_curve: Optional[EquityCurve] = None
        
        logger.info(f"BacktestEngine initialized with capital: {initial_capital}")
    
    def run(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        strategy_config: Optional[Dict[str, Any]] = None,
        symbol: str = 'SYMBOL'
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            strategy_class: Strategy class type (must inherit BaseStrategy)
            data: DataFrame with OHLCV data
            strategy_config: Strategy configuration (optional)
            symbol: Trading symbol
        
        Returns:
            Dictionary with backtest results:
            {
                'trades': List of completed trades,
                'equity_curve': DataFrame with equity time series,
                'metrics': Performance statistics,
                'summary': Summary statistics
            }
        
        Raises:
            ValueError: If strategy_class is invalid or data is insufficient
        """
        logger.info(f"Starting backtest for {strategy_class.__name__}")
        
        # Validate inputs
        self._validate_inputs(strategy_class, data)
        
        # Initialize components
        self._initialize_components()
        
        # Create strategy instance
        config = strategy_config or {}
        strategy = strategy_class(config)
        
        # Get number of bars
        num_bars = len(data)
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"BACKTEST RUNNING")
            print(f"{'='*60}")
            print(f"Strategy: {strategy.name}")
            print(f"Symbol: {symbol}")
            print(f"Bars: {num_bars}")
            print(f"Initial Capital: INR {self.initial_capital:,.2f}")
            print(f"{'='*60}\n")
        
        # Warm-up period for indicators (first 30 bars)
        warmup_period = min(30, num_bars // 10)
        
        # Main backtest loop
        for i in range(warmup_period, num_bars):
            # Get current candle
            current_candle = data.iloc[i:i+1]
            current_price = current_candle['close'].iloc[-1]
            timestamp = current_candle.index[-1]
            
            # Use all data up to current point for indicator calculation
            historical_data = data.iloc[:i+1]
            
            # Update position price if open
            if self.trade_simulator.has_position():
                position = self.trade_simulator.get_current_position()
                position.update_price(current_price)
                
                # Record equity
                position_value = position.quantity * current_price
                self.equity_curve.record(
                    timestamp=timestamp,
                    capital=self.trade_simulator.capital,
                    position_value=position_value
                )
            
            # Generate signal
            try:
                signal = strategy.generate_signal(historical_data)
            except Exception as e:
                logger.error(f"Error generating signal at {timestamp}: {str(e)}")
                if self.verbose:
                    print(f"❌ Error at {timestamp}: {str(e)}")
                continue
            
            # Process signal
            if signal:
                action = signal.get('action', '')
                
                if action in ['BUY', 'SELL'] and not self.trade_simulator.has_position():
                    # Entry signal
                    self.trade_simulator.simulate_entry(
                        signal=signal,
                        current_price=current_price,
                        timestamp=timestamp,
                        symbol=symbol
                    )
                    
                    # Record equity after entry
                    if self.trade_simulator.has_position():
                        pos = self.trade_simulator.get_current_position()
                        position_value = pos.quantity * current_price
                        self.equity_curve.record(
                            timestamp=timestamp,
                            capital=self.trade_simulator.capital,
                            position_value=position_value
                        )
                
                elif action == 'EXIT' and self.trade_simulator.has_position():
                    # Exit signal
                    self.trade_simulator.simulate_exit(
                        current_price=current_price,
                        timestamp=timestamp,
                        reason=signal.get('reason', 'Exit signal')
                    )
                    
                    # Record equity after exit
                    last_trade = self.trade_simulator.trades[-1] if self.trade_simulator.trades else None
                    if last_trade:
                        self.equity_curve.record_from_trade(
                            timestamp=timestamp,
                            trade_pnl=last_trade.pnl
                        )
        
        # Close any open position at the end
        if self.trade_simulator.has_position():
            final_price = data['close'].iloc[-1]
            final_time = data.index[-1]
            self.trade_simulator.simulate_exit(
                current_price=final_price,
                timestamp=final_time,
                reason='End of data'
            )
        
        # Calculate final metrics
        results = self._calculate_results()
        
        # Print summary
        if self.verbose:
            self._print_summary(results)
        
        logger.info("Backtest completed successfully")
        
        return results
    
    def _validate_inputs(self, strategy_class: Type, data: pd.DataFrame):
        """Validate backtest inputs."""
        from engine.base_strategy import BaseStrategy
        
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError("strategy_class must inherit from BaseStrategy")
        
        if data.empty or len(data) < 50:
            raise ValueError("Insufficient data for backtesting (minimum 50 bars)")
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
    
    def _initialize_components(self):
        """Initialize backtest components."""
        self.data_loader = HistoricalDataLoader()
        
        self.trade_simulator = TradeSimulator(
            initial_capital=self.initial_capital,
            slippage_percent=self.slippage_percent,
            brokerage_per_trade=self.brokerage_per_trade
        )
        
        self.performance_metrics = PerformanceMetrics()
        
        self.equity_curve = EquityCurve(initial_capital=self.initial_capital)
    
    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate comprehensive backtest results."""
        # Get trade history
        trades = self.trade_simulator.get_trade_history()
        
        # Get equity curve data
        equity_df = self.equity_curve.get_equity_dataframe()
        
        # Calculate performance metrics
        metrics = self.performance_metrics.calculate_all(
            trades=trades,
            equity_curve=equity_df,
            initial_capital=self.initial_capital
        )
        
        # Get simulator statistics
        sim_stats = self.trade_simulator.get_statistics()
        
        # Get equity statistics
        eq_stats = self.equity_curve.get_statistics()
        
        # Build results dictionary
        results = {
            'trades': trades,
            'equity_curve': equity_df,
            'metrics': metrics,
            'summary': {
                'initial_capital': self.initial_capital,
                'final_capital': metrics.get('final_capital', self.initial_capital),
                'total_return': metrics.get('total_return', 0.0),
                'total_return_pct': metrics.get('total_return_pct', 0.0),
                'total_trades': metrics.get('total_trades', 0),
                'win_rate': metrics.get('win_rate', 0.0),
                'profit_factor': metrics.get('profit_factor', 0.0),
                'max_drawdown': metrics.get('max_drawdown', 0.0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0.0),
                'avg_holding_period_minutes': metrics.get('avg_holding_period_minutes', 0.0),
                'brokerage_paid': sim_stats.get('total_brokerage', 0.0),
                'slippage_cost': sim_stats.get('total_slippage_cost', 0.0)
            }
        }
        
        return results
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print backtest summary to console."""
        summary = results['summary']
        metrics = results['metrics']
        
        print(f"\n{'='*60}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"Initial Capital:    INR {summary['initial_capital']:>12,.2f}")
        print(f"Final Capital:      INR {summary['final_capital']:>12,.2f}")
        print(f"Total Return:       INR {summary['total_return']:>12,.2f} ({summary['total_return_pct']:>6.2f}%)")
        print(f"{'-'*60}")
        print(f"Total Trades:       {metrics['total_trades']:>12}")
        print(f"Win Rate:           {metrics['win_rate']*100:>11.1f}%")
        print(f"Profit Factor:      {metrics['profit_factor']:>12.2f}")
        print(f"Avg Profit:         INR {metrics['avg_profit']:>11,.2f}")
        print(f"Avg Loss:           INR {metrics['avg_loss']:>11,.2f}")
        print(f"{'-'*60}")
        print(f"Max Drawdown:       {metrics['max_drawdown']:>11.2f}%")
        print(f"Sharpe Ratio:       {metrics['sharpe_ratio']:>12.2f}")
        print(f"Sortino Ratio:      {metrics['sortino_ratio']:>12.2f}")
        print(f"{'-'*60}")
        print(f"Brokerage Paid:     INR {summary['brokerage_paid']:>11,.2f}")
        print(f"Slippage Cost:      INR {summary['slippage_cost']:>11,.2f}")
        print(f"{'='*60}\n")

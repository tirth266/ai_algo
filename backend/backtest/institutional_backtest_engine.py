"""
Institutional-Level Backtesting Engine

Complete backtesting system for Combined Power Strategy.

Features:
- Realistic trade simulation (slippage, brokerage)
- Risk management rules
- Performance metrics calculation
- Equity curve tracking
- Trade logging
- Results export
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
import json
from pathlib import Path

from .data_loader import BacktestDataLoader
from strategies.combined_power_strategy import CombinedPowerStrategy

logger = logging.getLogger(__name__)


class InstitutionalBacktestEngine:
    """
    Professional-grade backtesting engine.
    
    Simulates trading with:
    - Realistic execution (slippage, brokerage)
    - Risk management (position sizing, stop loss, take profit)
    - Complete performance analytics
    - Trade-by-trade logging
    
    Usage:
        >>> engine = InstitutionalBacktestEngine(initial_capital=100000)
        >>> results = engine.run_backtest(
        ...     symbol='RELIANCE',
        ...     timeframe='5minute',
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31'
        ... )
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        capital_per_trade: float = 25000.0,
        slippage_percent: float = 0.0005,
        brokerage_per_trade: float = 20.0,
        stop_loss_percent: float = 0.02,
        take_profit_percent: float = 0.04,
        max_positions: int = 5,
        verbose: bool = True
    ):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Total capital available
            capital_per_trade: Capital allocated per trade
            slippage_percent: Slippage as percentage (default: 0.05%)
            brokerage_per_trade: Fixed brokerage per trade (default: 20 INR)
            stop_loss_percent: Stop loss percentage (default: 2%)
            take_profit_percent: Take profit percentage (default: 4%)
            max_positions: Maximum concurrent positions (default: 5)
            verbose: Enable detailed logging
        """
        self.initial_capital = initial_capital
        self.capital_per_trade = capital_per_trade
        self.slippage_percent = slippage_percent
        self.brokerage_per_trade = brokerage_per_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.max_positions = max_positions
        self.verbose = verbose
        
        # State variables
        self.cash = initial_capital
        self.positions: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        
        logger.info(f"InstitutionalBacktestEngine initialized")
        logger.info(f"  Initial Capital: ₹{initial_capital:,.2f}")
        logger.info(f"  Capital/Trade: ₹{capital_per_trade:,.2f}")
        logger.info(f"  Slippage: {slippage_percent*100:.2f}%")
        logger.info(f"  Brokerage: ₹{brokerage_per_trade}/trade")
    
    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        kite_client: Any = None,
        strategy_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run complete backtest.
        
        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')
            kite_client: Zerodha Kite client (optional)
            strategy_config: Strategy configuration
        
        Returns:
            Dictionary with backtest results
        """
        try:
            logger.info(f"Starting backtest for {symbol} ({timeframe})")
            logger.info(f"Period: {start_date} to {end_date}")
            
            # Reset state
            self._reset_state()
            
            # Load historical data
            data_loader = BacktestDataLoader()
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            data = data_loader.load_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_dt,
                end_date=end_dt,
                kite_client=kite_client
            )
            
            if data is None or len(data) == 0:
                logger.error("No data loaded for backtest")
                return self._create_empty_results(symbol)
            
            logger.info(f"Loaded {len(data)} candles")
            
            # Create strategy
            config = strategy_config or {'symbol': symbol, 'timeframe': timeframe}
            strategy = CombinedPowerStrategy(config)
            
            # Run backtest candle by candle
            self._run_strategy_simulation(strategy, data, symbol)
            
            # Close any remaining positions at end
            self._close_remaining_positions(data.iloc[-1])
            
            # Calculate performance metrics
            results = self._calculate_performance(symbol)
            
            # Save results
            self._save_results(results, symbol, start_date, end_date)
            
            logger.info(f"Backtest complete. Total Profit: ₹{results['total_pnl']:,.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            return self._create_empty_results(symbol)
    
    def _reset_state(self):
        """Reset engine state for new backtest."""
        self.cash = self.initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
    
    def _run_strategy_simulation(
        self,
        strategy: CombinedPowerStrategy,
        data: pd.DataFrame,
        symbol: str
    ):
        """
        Run strategy simulation candle by candle.
        
        Args:
            strategy: Combined Power Strategy instance
            data: Historical OHLCV data
            symbol: Trading symbol
        """
        logger.info("Running strategy simulation...")
        
        # Need minimum bars for strategy
        min_bars = 50
        
        for i in range(min_bars, len(data)):
            try:
                # Get current candle
                current_candle = data.iloc[i]
                
                # Get historical data up to this point (for indicator calculation)
                historical_data = data.iloc[:i+1].copy()
                
                # Generate signal
                signal = strategy.generate_signal(historical_data)
                
                if signal is None:
                    continue
                
                # Check for exit signals on existing positions
                self._check_exits(current_candle, symbol)
                
                # Process entry signal
                if signal.get('action') in ['BUY', 'SELL']:
                    self._process_signal(signal, current_candle, symbol)
                
                # Update equity curve
                equity = self._calculate_current_equity(current_candle)
                self.equity_curve.append({
                    'timestamp': str(current_candle.name),
                    'equity': equity,
                    'cash': self.cash,
                    'positions_value': equity - self.cash,
                    'open_positions': len(self.positions)
                })
            except Exception as e:
                logger.warning(f"Error processing candle {i}: {str(e)}")
                continue  # Skip this candle and continue
        
        logger.info(f"Simulation complete. Generated {len(self.trades)} trades.")
    
    def _process_signal(
        self,
        signal: Dict[str, Any],
        candle: pd.Series,
        symbol: str
    ):
        """
        Process trading signal.
        
        Args:
            signal: Trading signal from strategy
            candle: Current candle data
            symbol: Trading symbol
        """
        action = signal.get('action')
        
        # Check if we can open new position
        if len(self.positions) >= self.max_positions:
            logger.debug(f"Max positions reached ({self.max_positions})")
            return
        
        # Calculate position size
        price = candle['close']
        quantity = int(self.capital_per_trade / price)
        
        if quantity <= 0:
            return
        
        # Apply slippage
        if action == 'BUY':
            execution_price = price * (1 + self.slippage_percent)
        else:  # SELL
            execution_price = price * (1 - self.slippage_percent)
        
        # Calculate total cost including brokerage
        total_cost = (execution_price * quantity) + self.brokerage_per_trade
        
        # Check if we have enough cash
        if total_cost > self.cash:
            logger.debug(f"Insufficient cash: need ₹{total_cost:,.2f}, have ₹{self.cash:,.2f}")
            return
        
        # Open position
        position = {
            'symbol': symbol,
            'entry_time': candle.name,
            'entry_price': execution_price,
            'quantity': quantity,
            'direction': action,
            'stop_loss': execution_price * (1 - self.stop_loss_percent) if action == 'BUY' else execution_price * (1 + self.stop_loss_percent),
            'take_profit': execution_price * (1 + self.take_profit_percent) if action == 'BUY' else execution_price * (1 - self.take_profit_percent)
        }
        
        self.positions.append(position)
        self.cash -= self.brokerage_per_trade  # Deduct brokerage
        
        logger.debug(
            f"OPENED {action} {quantity} {symbol} @ ₹{execution_price:.2f} "
            f"(SL: ₹{position['stop_loss']:.2f}, TP: ₹{position['take_profit']:.2f})"
        )
    
    def _check_exits(self, candle: pd.Series, symbol: str):
        """
        Check and execute exits for open positions.
        
        Args:
            candle: Current candle data
            symbol: Trading symbol
        """
        current_price = candle['close']
        
        positions_to_close = []
        
        for position in self.positions:
            if position['symbol'] != symbol:
                continue
            
            should_close = False
            exit_reason = ''
            
            # Check stop loss
            if position['direction'] == 'BUY':
                if current_price <= position['stop_loss']:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
                elif current_price >= position['take_profit']:
                    should_close = True
                    exit_reason = 'TAKE_PROFIT'
            else:  # SELL
                if current_price >= position['stop_loss']:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
                elif current_price <= position['take_profit']:
                    should_close = True
                    exit_reason = 'TAKE_PROFIT'
            
            if should_close:
                positions_to_close.append((position, exit_reason, current_price))
        
        # Execute exits
        for position, reason, exit_price in positions_to_close:
            self._close_position(position, reason, exit_price, candle.name)
    
    def _close_position(
        self,
        position: Dict[str, Any],
        reason: str,
        exit_price: float,
        exit_time: Any
    ):
        """
        Close a position.
        
        Args:
            position: Position to close
            reason: Reason for closing
            exit_price: Exit price
            exit_time: Exit timestamp
        """
        # Apply slippage
        if position['direction'] == 'BUY':
            actual_exit_price = exit_price * (1 - self.slippage_percent)
        else:
            actual_exit_price = exit_price * (1 + self.slippage_percent)
        
        # Calculate P&L
        if position['direction'] == 'BUY':
            pnl = (actual_exit_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - actual_exit_price) * position['quantity']
        
        # Subtract brokerage
        pnl -= (2 * self.brokerage_per_trade)  # Entry + Exit brokerage
        
        # Record trade
        trade = {
            'trade_id': len(self.trades) + 1,
            'symbol': position['symbol'],
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'exit_price': actual_exit_price,
            'quantity': position['quantity'],
            'pnl': pnl,
            'exit_reason': reason
        }
        
        self.trades.append(trade)
        self.cash += pnl
        
        # Remove from positions
        self.positions.remove(position)
        
        logger.debug(
            f"CLOSED {position['direction']} {position['quantity']} {position['symbol']} "
            f"@ ₹{actual_exit_price:.2f} | P&L: ₹{pnl:,.2f} ({reason})"
        )
    
    def _close_remaining_positions(self, last_candle: pd.Series):
        """Close all remaining positions at end of backtest."""
        for position in self.positions.copy():
            self._close_position(
                position,
                'END_OF_BACKTEST',
                last_candle['close'],
                last_candle.name
            )
    
    def _calculate_current_equity(self, candle: pd.Series) -> float:
        """Calculate current total equity."""
        equity = self.cash
        
        # Add value of open positions
        for position in self.positions:
            if position['direction'] == 'BUY':
                equity += (candle['close'] - position['entry_price']) * position['quantity']
            else:
                equity += (position['entry_price'] - candle['close']) * position['quantity']
        
        return equity
    
    def _calculate_performance(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.
        
        Returns:
            Dictionary with performance statistics
        """
        if len(self.trades) == 0:
            return self._create_empty_results(symbol)
        
        # Convert trades to DataFrame
        trades_df = pd.DataFrame(self.trades)
        
        # Basic stats
        total_trades = len(self.trades)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        loss_rate = (losing_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        avg_pnl = trades_df['pnl'].mean()
        
        # Win/Loss analysis
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if losing_trades > 0 else 0
        
        # Profit factor
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if winning_trades > 0 else 0
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if losing_trades > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) - (loss_rate/100 * avg_loss)
        
        # Drawdown analysis
        equity_df = pd.DataFrame(self.equity_curve)
        if len(equity_df) > 0:
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
            max_drawdown = equity_df['drawdown'].min()
        else:
            max_drawdown = 0
        
        # Sharpe ratio (simplified)
        if len(equity_df) > 1:
            equity_df['returns'] = equity_df['equity'].pct_change()
            sharpe_ratio = (equity_df['returns'].mean() / equity_df['returns'].std()) * np.sqrt(252) if equity_df['returns'].std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Build results
        results = {
            'symbol': symbol,
            'initial_capital': self.initial_capital,
            'final_capital': self.cash,
            'total_pnl': total_pnl,
            'return_percent': ((self.cash - self.initial_capital) / self.initial_capital) * 100,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'loss_rate': round(loss_rate, 2),
            'avg_pnl': round(avg_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        
        logger.info(f"Performance Metrics:")
        logger.info(f"  Total Trades: {total_trades}")
        logger.info(f"  Win Rate: {win_rate:.2f}%")
        logger.info(f"  Total P&L: ₹{total_pnl:,.2f}")
        logger.info(f"  Max Drawdown: {max_drawdown:.2f}%")
        logger.info(f"  Sharpe Ratio: {sharpe_ratio:.2f}")
        
        return results
    
    def _create_empty_results(self, symbol: str) -> Dict[str, Any]:
        """Create empty results dictionary."""
        return {
            'symbol': symbol,
            'initial_capital': self.initial_capital,
            'final_capital': self.initial_capital,
            'total_pnl': 0,
            'return_percent': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'loss_rate': 0,
            'avg_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'expectancy': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'trades': [],
            'equity_curve': []
        }
    
    def _save_results(
        self,
        results: Dict[str, Any],
        symbol: str,
        start_date: str,
        end_date: str
    ):
        """Save backtest results to files."""
        try:
            # Create results directory
            results_dir = Path('backtest/results')
            results_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save summary JSON
            summary_file = results_dir / f"{symbol}_backtest_{timestamp}.json"
            summary_data = results.copy()
            summary_data.pop('trades')  # Don't include full trade list in summary
            summary_data.pop('equity_curve')
            
            with open(summary_file, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            logger.info(f"Saved summary to {summary_file}")
            
            # Save trades CSV
            if results['trades']:
                trades_file = results_dir / f"{symbol}_trades_{timestamp}.csv"
                trades_df = pd.DataFrame(results['trades'])
                trades_df.to_csv(trades_file, index=False)
                logger.info(f"Saved trades to {trades_file}")
            
            # Save equity curve CSV
            if results['equity_curve']:
                equity_file = results_dir / f"{symbol}_equity_{timestamp}.csv"
                equity_df = pd.DataFrame(results['equity_curve'])
                equity_df.to_csv(equity_file, index=False)
                logger.info(f"Saved equity curve to {equity_file}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")


def run_backtest(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    kite_client: Any = None
) -> Dict[str, Any]:
    """
    Convenience function to run backtest.
    
    Args:
        symbol: Stock symbol
        timeframe: Candle timeframe
        start_date: Start date ('YYYY-MM-DD')
        end_date: End date ('YYYY-MM-DD')
        initial_capital: Starting capital
        kite_client: Zerodha Kite client
    
    Returns:
        Dictionary with backtest results
    
    Example:
        >>> results = run_backtest(
        ...     symbol='RELIANCE',
        ...     timeframe='5minute',
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31',
        ...     initial_capital=100000
        ... )
    """
    engine = InstitutionalBacktestEngine(initial_capital=initial_capital)
    return engine.run_backtest(symbol, timeframe, start_date, end_date, kite_client)

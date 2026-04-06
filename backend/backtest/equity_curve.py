"""
Equity Curve Module

Tracks account equity over time for performance analysis.

Features:
- Real-time equity tracking
- Drawdown calculation
- Peak equity monitoring
- Time-series data export
"""

import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EquityCurve:
    """
    Tracks and analyzes account equity over time.
    
    Records:
    - Equity value at each timestamp
    - Peak equity (high-water mark)
    - Drawdown from peak
    - Trade impacts on equity
    """
    
    def __init__(self, initial_capital: float):
        """
        Initialize equity curve tracker.
        
        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Time series data
        self.equity_points: List[Dict[str, Any]] = []
        
        # Peak tracking
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        
        logger.info(f"EquityCurve initialized with capital: {initial_capital}")
    
    def record(
        self, 
        timestamp: datetime, 
        capital: float,
        position_value: float = 0.0
    ):
        """
        Record equity point in time.
        
        Args:
            timestamp: Time of recording
            capital: Current cash capital
            position_value: Current position market value (if any)
        """
        total_equity = capital + position_value
        
        # Update peak
        if total_equity > self.peak_equity:
            self.peak_equity = total_equity
        
        # Calculate drawdown
        drawdown = total_equity - self.peak_equity
        drawdown_pct = ((total_equity - self.peak_equity) / self.peak_equity * 100) if self.peak_equity > 0 else 0.0
        
        # Update max drawdown
        if drawdown < self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_pct = drawdown_pct
        
        # Record point
        point = {
            'timestamp': timestamp,
            'equity': total_equity,
            'capital': capital,
            'position_value': position_value,
            'peak_equity': self.peak_equity,
            'drawdown': drawdown,
            'drawdown_pct': drawdown_pct
        }
        
        self.equity_points.append(point)
        
        logger.debug(f"Recorded equity: {total_equity:.2f}, drawdown: {drawdown_pct:.2f}%")
    
    def record_from_trade(self, timestamp: datetime, trade_pnl: float):
        """
        Record equity change from a completed trade.
        
        Args:
            timestamp: Trade exit time
            trade_pnl: P&L from the trade
        """
        self.current_capital += trade_pnl
        self.record(timestamp, self.current_capital, 0.0)
        
        logger.debug(f"Trade recorded: PnL={trade_pnl:.2f}, New equity={self.current_capital:.2f}")
    
    def get_equity_dataframe(self) -> pd.DataFrame:
        """
        Convert equity curve to DataFrame.
        
        Returns:
            pd.DataFrame: Equity time series with columns:
                         [timestamp, equity, peak_equity, drawdown, drawdown_pct]
        """
        if not self.equity_points:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.equity_points)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def get_current_equity(self) -> float:
        """Get current total equity."""
        if self.equity_points:
            return self.equity_points[-1]['equity']
        return self.initial_capital
    
    def get_total_return(self) -> float:
        """
        Calculate total return percentage.
        
        Returns:
            Total return as percentage
        """
        current = self.get_current_equity()
        return ((current - self.initial_capital) / self.initial_capital) * 100
    
    def get_max_drawdown(self) -> float:
        """
        Get maximum drawdown experienced.
        
        Returns:
            Maximum drawdown as percentage
        """
        return abs(self.max_drawdown_pct)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get equity curve statistics.
        
        Returns:
            Dictionary with key statistics
        """
        if not self.equity_points:
            return {
                'final_equity': self.initial_capital,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'avg_equity': self.initial_capital,
                'volatility': 0.0
            }
        
        df = self.get_equity_dataframe()
        
        # Calculate volatility (standard deviation of returns)
        returns = df['equity'].pct_change().dropna()
        volatility = returns.std() * 100 if len(returns) > 0 else 0.0
        
        return {
            'final_equity': self.get_current_equity(),
            'total_return': self.get_total_return(),
            'max_drawdown': self.get_max_drawdown(),
            'peak_equity': self.peak_equity,
            'avg_equity': df['equity'].mean(),
            'volatility': volatility,
            'num_points': len(self.equity_points)
        }
    
    def plot_equity_curve(self, show: bool = True):
        """
        Create equity curve plot.
        
        Args:
            show: Whether to display plot (default: True)
        
        Returns:
            matplotlib Figure object
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for plotting")
            return None
        
        df = self.get_equity_dataframe()
        
        if df.empty:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot equity
        ax.plot(df.index, df['equity'], label='Equity', linewidth=2)
        
        # Plot peak
        ax.plot(df.index, df['peak_equity'], label='Peak Equity', linestyle='--', alpha=0.7)
        
        # Add fill for drawdown periods
        ax.fill_between(df.index, df['equity'], df['peak_equity'], 
                       where=df['equity'] < df['peak_equity'],
                       alpha=0.3, color='red', label='Drawdown')
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Equity ($)')
        ax.set_title('Equity Curve')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if show:
            plt.show()
        
        return fig
    
    def reset(self):
        """Reset equity curve to initial state."""
        self.current_capital = self.initial_capital
        self.equity_points = []
        self.peak_equity = self.initial_capital
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        logger.info("EquityCurve reset")

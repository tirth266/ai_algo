"""
Trading Dashboard Data Module

Provide real-time data for monitoring dashboards with metrics:
- Live equity curve
- Open positions
- PnL tracking
- Risk status
- Order statistics

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd

from .broker_interface import BrokerInterface, Order, Position
from .order_manager import OrderManager
from .risk_controller import RiskController

logger = logging.getLogger(__name__)


class TradingDashboardDataProvider:
    """
    Provide comprehensive data for trading dashboards.
    
    Features:
    - Real-time equity curve
    - Position tracking
    - PnL analytics
    - Risk metrics
    - Order statistics
    
    Usage:
        >>> provider = TradingDashboardDataProvider(broker)
        >>> dashboard_data = provider.get_dashboard_data()
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        order_manager: OrderManager = None,
        risk_controller: RiskController = None,
        initial_capital: float = 100000.0
    ):
        """
        Initialize dashboard data provider.
        
        Args:
            broker: Broker instance
            order_manager: Order manager instance
            risk_controller: Risk controller instance
            initial_capital: Starting capital for tracking
        """
        self.broker = broker
        self.order_manager = order_manager
        self.risk_controller = risk_controller
        self.initial_capital = initial_capital
        
        # Historical tracking
        self.equity_history: List[Dict[str, Any]] = []
        self.pnl_history: List[Dict[str, Any]] = []
        
        logger.info("TradingDashboardDataProvider initialized")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Returns:
            Dictionary with all dashboard metrics
        
        Example:
            >>> data = provider.get_dashboard_data()
            >>> print(f"Current PnL: {data['pnl']['total']:.2f}")
        """
        try:
            # Get current state from broker
            positions = self.broker.get_positions()
            balance = self.broker.get_account_balance()
            open_orders = self.broker.get_open_orders()
            
            # Calculate metrics
            equity = balance.get('total_net_value', self.initial_capital)
            total_pnl = sum(pos.pnl for pos in positions) if positions else 0.0
            
            # Update history
            self._update_equity_history(equity, balance)
            self._update_pnl_history(total_pnl, positions)
            
            # Compile dashboard data
            dashboard_data = {
                'account': {
                    'equity': equity,
                    'cash': balance.get('available_cash', 0.0),
                    'margin_used': balance.get('utilized_debits', 0.0),
                    'initial_capital': self.initial_capital,
                    'total_return': equity - self.initial_capital,
                    'total_return_pct': (equity - self.initial_capital) / self.initial_capital * 100
                },
                
                'pnl': {
                    'total': total_pnl,
                    'realized': sum(pos.realized_pnl for pos in positions) if positions else 0.0,
                    'unrealized': sum(pos.unrealized_pnl for pos in positions) if positions else 0.0,
                    'daily': self._calculate_daily_pnl(positions),
                },
                
                'positions': {
                    'count': len(positions),
                    'long_count': sum(1 for p in positions if p.quantity > 0),
                    'short_count': sum(1 for p in positions if p.quantity < 0),
                    'exposure': sum(p.value for p in positions),
                    'details': [pos.to_dict() for pos in positions]
                },
                
                'orders': {
                    'open_count': len(open_orders),
                    'pending_queue': self.order_manager.get_pending_count() if self.order_manager else 0,
                    'active_list': [o.to_dict() for o in open_orders[:10]]  # Last 10
                },
                
                'risk': self._get_risk_metrics(balance, positions),
                
                'statistics': self._get_statistics(),
                
                'timestamp': datetime.now().isoformat()
            }
            
            logger.debug(f"Dashboard data updated: equity={equity:.2f}, pnl={total_pnl:.2f}")
            return dashboard_data
        
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {str(e)}")
            return self._get_empty_dashboard()
    
    def get_equity_curve(self, last_n_points: int = 100) -> pd.DataFrame:
        """
        Get equity curve data.
        
        Args:
            last_n_points: Number of data points to return
        
        Returns:
            DataFrame with equity curve
        
        Example:
            >>> df = provider.get_equity_curve(last_n_points=50)
            >>> print(df.tail())
        """
        if not self.equity_history:
            return pd.DataFrame(columns=['timestamp', 'equity'])
        
        # Get last N points
        recent = self.equity_history[-last_n_points:]
        
        df = pd.DataFrame(recent)
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def get_pnl_breakdown(self) -> Dict[str, Any]:
        """
        Get detailed PnL breakdown.
        
        Returns:
            PnL breakdown by position and totals
        """
        try:
            positions = self.broker.get_positions()
            
            # By symbol
            pnl_by_symbol = {}
            for pos in positions:
                pnl_by_symbol[pos.symbol] = {
                    'realized': pos.realized_pnl,
                    'unrealized': pos.unrealized_pnl,
                    'total': pos.pnl
                }
            
            # Totals
            total_realized = sum(pos.realized_pnl for pos in positions)
            total_unrealized = sum(pos.unrealized_pnl for pos in positions)
            
            return {
                'by_symbol': pnl_by_symbol,
                'totals': {
                    'realized': total_realized,
                    'unrealized': total_unrealized,
                    'net': total_realized + total_unrealized
                },
                'top_performers': self._get_top_performers(positions),
                'worst_performers': self._get_worst_performers(positions)
            }
        
        except Exception as e:
            logger.error(f"Failed to get PnL breakdown: {str(e)}")
            return {}
    
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Get current risk status.
        
        Returns:
            Risk metrics and status
        """
        if not self.risk_controller:
            return {'status': 'NO_CONTROLLER'}
        
        try:
            positions = self.broker.get_positions()
            balance = self.broker.get_account_balance()
            
            # Update risk controller
            self.risk_controller.update_metrics(positions, balance)
            
            # Get report
            risk_report = self.risk_controller.get_risk_report()
            
            return {
                'status': 'OK' if risk_report['status'] else 'HALTED',
                'halt_reason': risk_report.get('halt_reason'),
                'metrics': risk_report['metrics'],
                'limits': risk_report['limits'],
                'utilization': risk_report['utilization']
            }
        
        except Exception as e:
            logger.error(f"Failed to get risk status: {str(e)}")
            return {'status': 'ERROR', 'message': str(e)}
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order execution statistics."""
        if not self.order_manager:
            return {'status': 'NO_MANAGER'}
        
        stats = self.order_manager.get_statistics()
        
        return {
            **stats,
            'recent_orders': list(self.order_manager.failed_orders)[-10:],
            'completion_rate': stats.get('success_rate', 0)
        }
    
    def _update_equity_history(self, equity: float, balance: Dict[str, Any]):
        """Update equity history tracking."""
        entry = {
            'timestamp': datetime.now(),
            'equity': equity,
            'cash': balance.get('available_cash', 0.0),
            'margin_used': balance.get('utilized_debits', 0.0)
        }
        
        self.equity_history.append(entry)
        
        # Keep last 1000 points
        if len(self.equity_history) > 1000:
            self.equity_history = self.equity_history[-1000:]
    
    def _update_pnl_history(self, total_pnl: float, positions: List[Position]):
        """Update PnL history tracking."""
        entry = {
            'timestamp': datetime.now(),
            'total_pnl': total_pnl,
            'realized_pnl': sum(pos.realized_pnl for pos in positions),
            'unrealized_pnl': sum(pos.unrealized_pnl for pos in positions)
        }
        
        self.pnl_history.append(entry)
        
        # Keep last 1000 points
        if len(self.pnl_history) > 1000:
            self.pnl_history = self.pnl_history[-1000:]
    
    def _calculate_daily_pnl(self, positions: List[Position]) -> float:
        """Calculate daily PnL."""
        # Simplified: In production, track from start of day
        return sum(pos.unrealized_pnl for pos in positions)
    
    def _get_risk_metrics(
        self,
        balance: Dict[str, Any],
        positions: List[Position]
    ) -> Dict[str, Any]:
        """Calculate risk metrics."""
        try:
            # Exposure
            long_exposure = sum(p.value for p in positions if p.quantity > 0)
            short_exposure = sum(p.value for p in positions if p.quantity < 0)
            
            # Concentration
            total_exposure = long_exposure + short_exposure
            concentration = {}
            
            if total_exposure > 0:
                for pos in positions:
                    weight = pos.value / total_exposure * 100
                    concentration[pos.symbol] = round(weight, 2)
            
            return {
                'long_exposure': long_exposure,
                'short_exposure': short_exposure,
                'net_exposure': long_exposure - short_exposure,
                'total_exposure': total_exposure,
                'concentration': concentration,
                'trading_halted': self.risk_controller.trading_halted if self.risk_controller else False
            }
        
        except Exception as e:
            logger.error(f"Failed to calculate risk metrics: {str(e)}")
            return {}
    
    def _get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        return {
            'equity_peak': max([e['equity'] for e in self.equity_history]) if self.equity_history else self.initial_capital,
            'equity_low': min([e['equity'] for e in self.equity_history]) if self.equity_history else self.initial_capital,
            'max_drawdown': self._calculate_max_drawdown(),
            'avg_pnl': sum(p['total_pnl'] for p in self.pnl_history) / len(self.pnl_history) if self.pnl_history else 0.0
        }
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity history."""
        if not self.equity_history:
            return 0.0
        
        peak = self.initial_capital
        max_dd = 0.0
        
        for entry in self.equity_history:
            equity = entry['equity']
            
            if equity > peak:
                peak = equity
            
            drawdown = (peak - equity) / peak
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _get_top_performers(
        self,
        positions: List[Position],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """Get top performing positions."""
        sorted_pos = sorted(positions, key=lambda p: p.pnl, reverse=True)
        return [p.to_dict() for p in sorted_pos[:top_n]]
    
    def _get_worst_performers(
        self,
        positions: List[Position],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """Get worst performing positions."""
        sorted_pos = sorted(positions, key=lambda p: p.pnl)
        return [p.to_dict() for p in sorted_pos[:top_n]]
    
    def _get_empty_dashboard(self) -> Dict[str, Any]:
        """Return empty dashboard structure."""
        return {
            'account': {'equity': self.initial_capital, 'cash': 0.0},
            'pnl': {'total': 0.0, 'realized': 0.0, 'unrealized': 0.0},
            'positions': {'count': 0, 'details': []},
            'orders': {'open_count': 0, 'pending_queue': 0},
            'risk': {},
            'statistics': {},
            'timestamp': datetime.now().isoformat()
        }


def create_dashboard_provider(
    broker: BrokerInterface,
    initial_capital: float = 100000.0
) -> TradingDashboardDataProvider:
    """
    Convenience function to create dashboard provider.
    
    Args:
        broker: Broker instance
        initial_capital: Starting capital
    
    Returns:
        TradingDashboardDataProvider instance
    """
    return TradingDashboardDataProvider(
        broker=broker,
        initial_capital=initial_capital
    )

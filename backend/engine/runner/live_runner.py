"""
Live Execution Supervisor & Paper Trading Engine

Manages real-time trading with:
- Paper trading toggle (simulated fills)
- Live slippage tracking
- WebSocket integration
- Emergency kill-switch
- Position persistence and recovery

Author: Quantitative Trading Systems Engineer
Date: March 22, 2026
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


class LiveRunner:
    """
    Live execution supervisor for paper and real trading.
    
    Features:
    1. Paper Trading Mode: Simulate fills without real orders
    2. Slippage Tracking: Compare expected vs actual fills
    3. WebSocket Integration: Stream live candles
    4. Kill-Switch: Emergency position closure
    5. Persistence: Recover positions after restart
    
    Usage:
        >>> runner = LiveRunner(paper_trading=True)
        >>> await runner.start_strategy('combined_power', 'RELIANCE', '5minute')
        >>> # Monitor in real-time via dashboard
    """
    
    def __init__(self, 
                 paper_trading: bool = True,
                 initial_capital: float = 100000.0,
                 max_daily_loss_percent: float = 2.0):
        """
        Initialize Live Runner.
        
        Args:
            paper_trading: If True, simulate fills (no real orders)
            initial_capital: Starting capital
            max_daily_loss_percent: Daily loss limit (%)
        """
        self.paper_trading = paper_trading
        self.initial_capital = initial_capital
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_daily_loss_abs = initial_capital * (max_daily_loss_percent / 100)
        
        # State tracking
        self.active_strategies: Dict[str, Dict] = {}
        self.open_positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.total_trades_today = 0
        self.winning_trades_today = 0
        self.losing_trades_today = 0
        
        # Slippage tracking
        self.slippage_events: List[Dict] = []
        self.avg_slippage_bps = 0.0
        
        # Kill-switch state
        self.kill_switch_active = False
        self.last_kill_switch_trigger = None
        
        # Trade count tracking
        self.trade_count = 0
        
        logger.info(f"LiveRunner initialized (Paper Trading: {paper_trading})")
    
    async def start_strategy(self, 
                            strategy_name: str,
                            symbol: str,
                            timeframe: str,
                            params: Optional[Dict] = None) -> bool:
        """
        Start a live trading strategy.
        
        Args:
            strategy_name: Strategy identifier
            symbol: Trading symbol
            timeframe: Candle timeframe
            params: Strategy parameters
            
        Returns:
            Success status
        """
        if self.kill_switch_active:
            logger.error("Cannot start strategy: Kill-switch is active")
            return False
        
        try:
            logger.info(f"Starting {strategy_name} on {symbol} ({timeframe})")
            
            # Load or initialize strategy
            from .trading_controller import TradingController
            
            controller = TradingController()
            
            # Configure strategy
            strategy_config = {
                'name': strategy_name,
                'symbol': symbol,
                'timeframe': timeframe,
                'params': params or {},
                'paper_trading': self.paper_trading,
                'initial_capital': self.initial_capital
            }
            
            # Register with execution loop
            await controller.register_strategy(
                strategy_id=f"{strategy_name}_{symbol}_{timeframe}",
                config=strategy_config
            )
            
            # Track active strategy
            self.active_strategies[f"{strategy_name}_{symbol}_{timeframe}"] = {
                'controller': controller,
                'config': strategy_config,
                'start_time': datetime.now(),
                'status': 'running'
            }
            
            # Recover existing positions if any
            await self._recover_positions(symbol)
            
            logger.info(f"Strategy {strategy_name} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start strategy: {str(e)}", exc_info=True)
            return False
    
    async def stop_strategy(self, strategy_key: str) -> bool:
        """
        Stop a running strategy.
        
        Args:
            strategy_key: Strategy identifier
            
        Returns:
            Success status
        """
        try:
            if strategy_key not in self.active_strategies:
                logger.error(f"Strategy {strategy_key} not found")
                return False
            
            strategy = self.active_strategies[strategy_key]
            controller = strategy['controller']
            
            # Close all positions for this strategy
            await self._close_strategy_positions(strategy_key)
            
            # Unregister from execution loop
            await controller.unregister_strategy(strategy_key)
            
            # Update status
            strategy['status'] = 'stopped'
            strategy['stop_time'] = datetime.now()
            
            logger.info(f"Strategy {strategy_key} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping strategy: {str(e)}", exc_info=True)
            return False
    
    async def on_candle(self, candle: Dict) -> None:
        """
        Process incoming live candle from WebSocket.
        
        Args:
            candle: Candle data from KiteTicker
        """
        symbol = candle.get('instrument_token')
        
        # Update unrealized P&L
        await self._update_unrealized_pnl(candle)
        
        # Check daily loss limit
        if abs(self.daily_pnl) >= self.max_daily_loss_abs:
            logger.error(f"Daily loss limit hit! PnL: {self.daily_pnl}")
            await self.trigger_kill_switch(reason='daily_loss_limit')
            return
        
        # Forward candle to all relevant strategies
        for strategy_key, strategy in self.active_strategies.items():
            if strategy['config']['symbol'] == symbol:
                await strategy['controller'].on_candle(candle)
    
    async def place_order(self, 
                         strategy_key: str,
                         order_type: str,
                         quantity: int,
                         price: Optional[float] = None,
                         trigger_price: Optional[float] = None) -> Optional[str]:
        """
        Place an order (real or simulated).
        
        Args:
            strategy_key: Strategy identifier
            order_type: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Limit price (optional)
            trigger_price: Stop-loss trigger (optional)
            
        Returns:
            Order ID if successful, None otherwise
        """
        if self.kill_switch_active:
            logger.error("Order rejected: Kill-switch active")
            return None
        
        try:
            strategy = self.active_strategies.get(strategy_key)
            if not strategy:
                logger.error(f"Strategy {strategy_key} not found")
                return None
            
            symbol = strategy['config']['symbol']
            
            # Get current LTP from WebSocket
            ltp = await self._get_ltp(symbol)
            
            if not ltp:
                logger.error(f"No LTP available for {symbol}")
                return None
            
            # First-Trade-Size Protocol
            if not self.paper_trading and self.trade_count < 3:
                original_quantity = quantity
                quantity = 1  # Force 1 share/lot
                logger.warning(f"Protocol: First-Trade-Size limit applied (First 3 trades only). Original: {original_quantity}, New: {quantity}")
            
            # Calculate fill price
            if self.paper_trading:
                # Simulate fill with slight slippage
                fill_price = self._simulate_fill_price(order_type, ltp, price)
                
                # Track slippage
                if price:
                    slippage_bps = abs(fill_price - price) / price * 10000
                    self._record_slippage(symbol, price, fill_price, slippage_bps)
            else:
                # Real order placement
                fill_price = await self._place_real_order(
                    symbol, order_type, quantity, price, trigger_price
                )
                
                if not fill_price:
                    return None
            
            # Create order record
            order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            order = {
                'order_id': order_id,
                'strategy_key': strategy_key,
                'symbol': symbol,
                'order_type': order_type,
                'quantity': quantity,
                'price': price or ltp,
                'fill_price': fill_price,
                'trigger_price': trigger_price,
                'timestamp': datetime.now(),
                'paper_trade': self.paper_trading
            }
            
            # Add to pending orders
            self.pending_orders[order_id] = order
            
            # Update trade count
            self.trade_count += 1
            
            logger.info(f"Order placed: {order_type} {quantity} {symbol} @ {fill_price}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}", exc_info=True)
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        if order_id not in self.pending_orders:
            return False
        
        try:
            order = self.pending_orders[order_id]
            
            if not self.paper_trading:
                # Cancel real order via API
                await self._cancel_real_order(order_id)
            
            # Remove from pending
            del self.pending_orders[order_id]
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return False
    
    async def close_position(self, position_key: str) -> bool:
        """Close an open position"""
        if position_key not in self.open_positions:
            return False
        
        try:
            position = self.open_positions[position_key]
            symbol = position['symbol']
            quantity = position['quantity']
            side = position['side']
            
            # Opposite order to close
            close_type = 'SELL' if side == 'BUY' else 'BUY'
            
            # Get LTP
            ltp = await self._get_ltp(symbol)
            
            # Calculate P&L
            pnl = (ltp - position['avg_price']) * quantity if side == 'BUY' \
                  else (position['avg_price'] - ltp) * quantity
            
            # Execute close
            if self.paper_trading:
                fill_price = ltp  # Simulate instant fill at LTP
            else:
                fill_price = await self._place_real_order(symbol, close_type, quantity)
            
            # Update P&L
            self.realized_pnl += pnl
            self.daily_pnl += pnl
            self.total_trades_today += 1
            
            if pnl > 0:
                self.winning_trades_today += 1
            else:
                self.losing_trades_today += 1
            
            # Record trade
            trade_record = {
                'entry_time': position['entry_time'],
                'exit_time': datetime.now(),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': position['avg_price'],
                'exit_price': fill_price,
                'pnl': pnl,
                'paper_trade': self.paper_trading
            }
            
            await self._save_trade_record(trade_record)
            
            # Remove position
            del self.open_positions[position_key]
            
            logger.info(f"Position closed: {symbol} PnL: {pnl:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}", exc_info=True)
            return False
    
    async def trigger_kill_switch(self, reason: str = 'manual') -> bool:
        """
        Emergency kill-switch: Close all positions immediately.
        
        Args:
            reason: Trigger reason ('manual', 'daily_loss_limit', 'system_error')
        """
        logger.critical(f"KILL-SWITCH TRIGGERED: {reason}")
        
        try:
            self.kill_switch_active = True
            self.last_kill_switch_trigger = datetime.now()
            
            # Cancel all pending orders
            order_ids = list(self.pending_orders.keys())
            for order_id in order_ids:
                await self.cancel_order(order_id)
            
            # Close all open positions
            position_keys = list(self.open_positions.keys())
            for position_key in position_keys:
                await self.close_position(position_key)
            
            # Stop all strategies
            strategy_keys = list(self.active_strategies.keys())
            for strategy_key in strategy_keys:
                await self.stop_strategy(strategy_key)
            
            logger.critical(f"All positions closed. Total PnL: {self.daily_pnl:.2f}")
            
            # Save state
            await self._save_state()
            
            return True
            
        except Exception as e:
            logger.critical(f"Kill-switch failed: {str(e)}", exc_info=True)
            return False
    
    async def reset_kill_switch(self) -> bool:
        """Reset kill-switch to allow new trades"""
        self.kill_switch_active = False
        logger.info("Kill-switch reset - trading resumed")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current runner status"""
        return {
            'paper_trading': self.paper_trading,
            'kill_switch_active': self.kill_switch_active,
            'active_strategies': len(self.active_strategies),
            'open_positions': len(self.open_positions),
            'pending_orders': len(self.pending_orders),
            'daily_pnl': self.daily_pnl,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_trades_today': self.total_trades_today,
            'win_rate_today': (self.winning_trades_today / max(1, self.total_trades_today)) * 100,
            'avg_slippage_bps': self.avg_slippage_bps,
            'slippage_events_count': len(self.slippage_events),
            'last_kill_switch_trigger': self.last_kill_switch_trigger.isoformat() if self.last_kill_switch_trigger else None
        }
    
    async def _recover_positions(self, symbol: str) -> None:
        """Recover existing positions from broker API"""
        try:
            if self.paper_trading:
                # Load from persisted state
                await self._load_state()
            else:
                # Query Zerodha positions API
                from .api_wrapper import KiteAPIWrapper
                
                kite = KiteAPIWrapper()
                positions = await kite.get_positions()
                
                for position in positions:
                    if position['symbol'] == symbol and position['quantity'] != 0:
                        position_key = f"{symbol}_{position['product']}"
                        
                        self.open_positions[position_key] = {
                            'symbol': symbol,
                            'side': 'BUY' if position['quantity'] > 0 else 'SELL',
                            'quantity': abs(position['quantity']),
                            'avg_price': position['average_price'],
                            'entry_time': datetime.now(),  # Approximate
                            'product': position['product']
                        }
                        
                        logger.info(f"Recovered position: {position_key}")
                        
        except Exception as e:
            logger.error(f"Error recovering positions: {str(e)}")
    
    def _simulate_fill_price(self, 
                            order_type: str, 
                            ltp: float, 
                            limit_price: Optional[float]) -> float:
        """
        Simulate realistic fill price with slippage.
        
        Args:
            order_type: 'BUY' or 'SELL'
            ltp: Last traded price
            limit_price: Intended limit price
            
        Returns:
            Simulated fill price
        """
        # Add random slippage (0.01% to 0.05%)
        import random
        slippage_pct = random.uniform(0.0001, 0.0005)
        
        if order_type == 'BUY':
            # Buy fills slightly higher
            slippage = ltp * slippage_pct
            return ltp + slippage
        else:
            # Sell fills slightly lower
            slippage = ltp * slippage_pct
            return ltp - slippage
    
    def _record_slippage(self, 
                        symbol: str, 
                        expected: float, 
                        actual: float, 
                        slippage_bps: float) -> None:
        """Record slippage event for analysis"""
        event = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'expected_price': expected,
            'actual_price': actual,
            'slippage_bps': slippage_bps
        }
        
        self.slippage_events.append(event)
        
        # Update average
        if self.slippage_events:
            total_bps = sum(e['slippage_bps'] for e in self.slippage_events)
            self.avg_slippage_bps = total_bps / len(self.slippage_events)
    
    async def _get_ltp(self, symbol: str) -> Optional[float]:
        """Get last traded price from WebSocket"""
        # This would integrate with your WebSocket service
        # For now, return mock price
        return 100.0  # TODO: Implement WebSocket integration
    
    async def _place_real_order(self, 
                               symbol: str,
                               order_type: str,
                               quantity: int,
                               price: Optional[float] = None,
                               trigger_price: Optional[float] = None) -> Optional[float]:
        """Place real order via broker API"""
        from .api_wrapper import KiteAPIWrapper
        
        kite = KiteAPIWrapper()
        
        try:
            order_id = await kite.place_order(
                symbol=symbol,
                transaction_type=order_type,
                quantity=quantity,
                price=price,
                trigger_price=trigger_price,
                product='MIS'  # Intraday
            )
            
            # Wait for fill confirmation
            fill_price = await kite.wait_for_order_fill(order_id)
            
            return fill_price
            
        except Exception as e:
            logger.error(f"Real order failed: {str(e)}")
            return None
    
    async def _cancel_real_order(self, order_id: str) -> None:
        """Cancel real order via broker API"""
        from .api_wrapper import KiteAPIWrapper
        
        kite = KiteAPIWrapper()
        await kite.cancel_order(order_id)
    
    async def _update_unrealized_pnl(self, candle: Dict) -> None:
        """Update unrealized P&L based on current prices"""
        total_unrealized = 0.0
        
        for position_key, position in self.open_positions.items():
            current_price = candle.get('close', 0)
            
            if position['side'] == 'BUY':
                pnl = (current_price - position['avg_price']) * position['quantity']
            else:
                pnl = (position['avg_price'] - current_price) * position['quantity']
            
            total_unrealized += pnl
        
        self.unrealized_pnl = total_unrealized
    
    async def _close_strategy_positions(self, strategy_key: str) -> None:
        """Close all positions for a specific strategy"""
        positions_to_close = [
            key for key, pos in self.open_positions.items()
            if self.open_positions.get(key, {}).get('strategy_key') == strategy_key
        ]
        
        for position_key in positions_to_close:
            await self.close_position(position_key)
    
    async def _save_state(self) -> None:
        """Save current state to disk for recovery"""
        state = {
            'open_positions': {
                k: {**v, 'entry_time': v['entry_time'].isoformat()}
                for k, v in self.open_positions.items()
            },
            'pending_orders': {
                k: {**v, 'timestamp': v['timestamp'].isoformat()}
                for k, v in self.pending_orders.items()
            },
            'daily_pnl': self.daily_pnl,
            'realized_pnl': self.realized_pnl,
            'timestamp': datetime.now().isoformat()
        }
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info("State saved")
    
    async def _load_state(self) -> None:
        """Load state from disk"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Restore positions
            for key, pos_data in state.get('open_positions', {}).items():
                pos_data['entry_time'] = datetime.fromisoformat(pos_data['entry_time'])
                self.open_positions[key] = pos_data
            
            # Restore P&L
            self.daily_pnl = state.get('daily_pnl', 0.0)
            self.realized_pnl = state.get('realized_pnl', 0.0)
            
            logger.info("State loaded")
            
        except Exception as e:
            logger.error(f"Error loading state: {str(e)}")
    
    async def _save_trade_record(self, trade: Dict) -> None:
        """Save trade record to logs"""
        trades_dir = Path('logs/trades')
        trades_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime('%Y-%m-%d')
        trades_file = trades_dir / f"trades_{today}.json"
        
        # Load existing trades
        trades = []
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                trades = json.load(f)
        
        # Append new trade
        trade_serializable = {
            **trade,
            'entry_time': trade['entry_time'].isoformat(),
            'exit_time': trade['exit_time'].isoformat()
        }
        trades.append(trade_serializable)
        
        # Save
        with open(trades_file, 'w') as f:
            json.dump(trades, f, indent=2)
        
        logger.debug(f"Trade recorded: {trade['symbol']} PnL: {trade['pnl']:.2f}")


# Global live runner instance
_live_runner: Optional[LiveRunner] = None


def get_live_runner(paper_trading: Optional[bool] = None) -> LiveRunner:
    """Get or create global live runner"""
    global _live_runner
    
    if _live_runner is None:
        if paper_trading is None:
            # Check environment variable
            mode = os.getenv('TRADING_MODE', 'paper').lower()
            paper_trading = (mode == 'paper')
        
        _live_runner = LiveRunner(paper_trading=paper_trading)
    
    return _live_runner

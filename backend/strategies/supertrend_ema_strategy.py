"""
Supertrend EMA Strategy

Multi-indicator trend-following strategy combining:
- Supertrend (ATR-based trend detection)
- EMA 20/50/100/200 alignment
- Volume confirmation
- Market structure (HH/HL or LH/LL)

Entry Rules:
  BUY: EMA bullish stack + Supertrend flip + pullback + volume
  SELL: EMA bearish stack + Supertrend flip + pullback + volume

Filters:
  - Trend: EMA alignment
  - Structure: HH/HL or LH/LL
  - Volume: above average
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend

logger = logging.getLogger(__name__)


class SupertrendEMAStrategy(BaseStrategy):
    def __init__(
        self,
        capital: float = 25000.0,
        atr_period: int = 10,
        supertrend_multiplier: float = 3.0,
        ema_periods: List[int] = None,
        volume_ma_period: int = 20,
        ssl_period: int = 14,
        risk_reward_ratio: float = 2.0,
        atr_sl_multiplier: float = 1.5,
        min_atr_filter: float = 0.0,
        max_spread_pct: float = 0.0
    ):
        super().__init__(name="SupertrendEMA", capital=capital)
        
        self.atr_period = atr_period
        self.supertrend_multiplier = supertrend_multiplier
        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.volume_ma_period = volume_ma_period
        self.ssl_period = ssl_period
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.min_atr_filter = min_atr_filter
        self.max_spread_pct = max_spread_pct
        
        self.last_signal = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None

    def calculate_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        
        for period in self.ema_periods:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=self.atr_period).mean()
        
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        
        supertrend_df = calculate_supertrend(
            df[['open', 'high', 'low', 'close']].copy(),
            period=self.atr_period,
            multiplier=self.supertrend_multiplier
        )
        if not supertrend_df.empty:
            df['supertrend'] = supertrend_df['supertrend']
            df['trend_direction'] = supertrend_df['trend_direction']
        
        return df

    def check_ema_alignment(self, df: pd.DataFrame, lookback: int = 1) -> str:
        if len(df) < lookback + 1:
            return "neutral"
        
        idx = -1
        ema20 = df[f'ema_{self.ema_periods[0]}'].iloc[idx]
        ema50 = df[f'ema_{self.ema_periods[1]}'].iloc[idx]
        ema100 = df[f'ema_{self.ema_periods[2]}'].iloc[idx]
        ema200 = df[f'ema_{self.ema_periods[3]}'].iloc[idx]
        
        if ema20 > ema50 > ema100 > ema200:
            return "bullish"
        elif ema20 < ema50 < ema100 < ema200:
            return "bearish"
        return "neutral"

    def detect_market_structure(self, df: pd.DataFrame, lookback: int = 5) -> str:
        if len(df) < lookback + 1:
            return "neutral"
        
        recent_highs = df['high'].rolling(window=lookback).max()
        recent_lows = df['low'].rolling(window=lookback).min()
        
        last_high = df['high'].iloc[-1]
        last_low = df['low'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        if last_high > prev_high and last_low > prev_low:
            return "hh_hl"
        elif last_high < prev_high and last_low < prev_low:
            return "lh_ll"
        return "neutral"

    def detect.swing_points(self, df: pd.DataFrame, period: int = 5) -> Tuple[Optional[float], Optional[float]]:
        if len(df) < period * 2 + 1:
            return None, None
        
        highs = df['high']
        lows = df['low']
        
        swing_high = None
        swing_low = None
        
        for i in range(period, len(df) - period):
            if highs.iloc[i] == highs.iloc[i-period:i+period].max():
                swing_high = highs.iloc[i]
            if lows.iloc[i] == lows.iloc[i-period:i+period].min():
                swing_low = lows.iloc[i]
        
        return swing_high, swing_low

    def detect_trend_change(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        if len(df) < 2:
            return False, False
        
        current = df['trend_direction'].iloc[-1]
        previous = df['trend_direction'].iloc[-2]
        
        bullish_flip = False
        bearish_flip = False
        
        if previous == -1 and current == 1:
            bullish_flip = True
        elif previous == 1 and current == -1:
            bearish_flip = True
        
        return bullish_flip, bearish_flip

    def is_sideways_market(self, df: pd.DataFrame) -> bool:
        if len(df) < 20:
            return True
        
        if self.min_atr_filter > 0 and df['atr'].iloc[-1] < self.min_atr_filter:
            return True
        
        ema20 = df[f'ema_{self.ema_periods[0]}'].iloc[-1]
        ema200 = df[f'ema_{self.ema_periods[3]}'].iloc[-1]
        
        spread_pct = abs(ema20 - ema200) / ema200 * 100 if ema200 != 0 else 0
        
        if spread_pct < self.max_spread_pct and self.max_spread_pct > 0:
            return True
        
        return False

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        if len(candles) < 50:
            return None
        
        df = self.calculate_indicators(candles)
        
        if df.empty or 'supertrend' not in df.columns:
            return None
        
        ema_alignment = self.check_ema_alignment(df)
        structure = self.detect_market_structure(df)
        
        if self.is_sideways_market(df):
            logger.debug("Sideways market detected, skipping")
            return None
        
        current_close = df['close'].iloc[-1]
        ema20 = df[f'ema_{self.ema_periods[0]}'].iloc[-1]
        ema50 = df[f'ema_{self.ema_periods[1]}'].iloc[-1]
        volume = df['volume'].iloc[-1]
        volume_ma = df['volume_ma'].iloc[-1]
        trend_dir = df['trend_direction'].iloc[-1]
        
        bullish_flip, bearish_flip = self.detect_trend_change(df)
        
        prev_trend_dir = df['trend_direction'].iloc[-2]
        
        if bullish_flip and ema_alignment == "bullish" and structure == "hh_hl":
            if volume > volume_ma and current_close > ema50:
                self.last_signal = "BUY"
                self.entry_price = current_close
                self.stop_loss = current_close - (self.atr_sl_multiplier * df['atr'].iloc[-1])
                self.take_profit = current_close + (self.risk_reward_ratio * self.atr_sl_multiplier * df['atr'].iloc[-1])
                logger.info(f"BUY SIGNAL: Trend flip + EMA bullish + HH/HL + volume confirmation")
                return "BUY"
        
        if bearish_flip and ema_alignment == "bearish" and structure == "lh_ll":
            if volume > volume_ma and current_close < ema50:
                self.last_signal = "SELL"
                self.entry_price = current_close
                self.stop_loss = current_close + (self.atr_sl_multiplier * df['atr'].iloc[-1])
                self.take_profit = current_close - (self.risk_reward_ratio * self.atr_sl_multiplier * df['atr'].iloc[-1])
                logger.info(f"SELL SIGNAL: Trend flip + EMA bearish + LH/LL + volume confirmation")
                return "SELL"
        
        return None

    def get_risk_levels(self) -> Dict[str, float]:
        return {
            'entry_price': self.entry_price or 0.0,
            'stop_loss': self.stop_loss or 0.0,
            'take_profit': self.take_profit or 0.0,
            'risk': abs(self.entry_price - self.stop_loss) if self.entry_price and self.stop_loss else 0.0,
            'reward': abs(self.take_profit - self.entry_price) if self.entry_price and self.take_profit else 0.0,
            'risk_reward': self.risk_reward_ratio
        }


class Backtester:
    def __init__(
        self,
        strategy: SupertrendEMAStrategy,
        initial_capital: float = 100000.0,
        slippage_percent: float = 0.001,
        brokerage: float = 20.0
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.slippage_percent = slippage_percent
        self.brokerage = brokerage
        
        self.cash = initial_capital
        self.positions: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []

    def run(self, candles: pd.DataFrame) -> Dict[str, Any]:
        df = self.strategy.calculate_indicators(candles)
        
        for i in range(50, len(df)):
            current_df = df.iloc[:i+1].copy()
            current_candle = current_df.iloc[-1]
            
            signal = self.strategy.generate_signal(current_df)
            
            if signal and not self.positions:
                self._execute_entry(signal, current_candle)
            
            if self.positions:
                self._check_exits(current_candle)
            
            equity = self._calculate_equity(current_candle)
            self.equity_curve.append({
                'time': current_candle.name,
                'equity': equity,
                'position': len(self.positions)
            })
        
        if self.positions:
            self._close_all(df.iloc[-1])
        
        return self._calculate_metrics()

    def _execute_entry(self, signal: str, candle: pd.Series):
        quantity = self.strategy.get_quantity(candle['close'])
        cost = quantity * candle['close']
        
        if cost > self.cash:
            return
        
        entry_price = candle['close'] * (1 + self.slippage_percent if signal == "BUY" else 1 - self.slippage_percent)
        
        sl = self.strategy.stop_loss
        tp = self.strategy.take_profit
        
        position = {
            'direction': signal,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': sl,
            'take_profit': tp,
            'entry_time': candle.name
        }
        
        self.positions.append(position)
        self.cash -= (entry_price * quantity + self.brokerage)
        
        self.trades.append({
            'entry_time': candle.name,
            'direction': signal,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': sl,
            'take_profit': tp
        })

    def _check_exits(self, candle: pd.Series):
        price = candle['close']
        
        for position in self.positions[:]:
            exit_price = None
            reason = None
            
            if position['direction'] == "BUY":
                if price <= position['stop_loss']:
                    exit_price = price * (1 - self.slippage_percent)
                    reason = "STOP_LOSS"
                elif price >= position['take_profit']:
                    exit_price = price * (1 - self.slippage_percent)
                    reason = "TAKE_PROFIT"
            else:
                if price >= position['stop_loss']:
                    exit_price = price * (1 + self.slippage_percent)
                    reason = "STOP_LOSS"
                elif price <= position['take_profit']:
                    exit_price = price * (1 + self.slippage_percent)
                    reason = "TAKE_PROFIT"
            
            if exit_price:
                self._execute_exit(position, exit_price, reason, candle.name)

    def _execute_exit(self, position: Dict, exit_price: float, reason: str, exit_time):
        if position['direction'] == "BUY":
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        pnl -= self.brokerage
        
        self.cash += (exit_price * position['quantity'] + pnl)
        
        self.trades[-1].update({
            'exit_time': exit_time,
            'exit_price': exit_price,
            'pnl': pnl,
            'exit_reason': reason
        })
        
        self.positions.remove(position)

    def _close_all(self, candle: pd.Series):
        for position in self.positions:
            self._execute_exit(position, candle['close'], "END_OF_BACKTEST", candle.name)

    def _calculate_equity(self, candle: pd.Series) -> float:
        equity = self.cash
        for position in self.positions:
            if position['direction'] == "BUY":
                equity += (candle['close'] - position['entry_price']) * position['quantity']
            else:
                equity += (position['entry_price'] - candle['close']) * position['quantity']
        return equity

    def _calculate_metrics(self) -> Dict[str, Any]:
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'trades': []
            }
        
        completed = [t for t in self.trades if 'pnl' in t]
        if not completed:
            return {'total_trades': 0, 'win_rate': 0.0}
        
        df = pd.DataFrame(completed)
        
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] < 0]
        
        win_rate = len(wins) / len(df) * 100 if len(df) > 0 else 0
        
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        equity_df = pd.DataFrame(self.equity_curve)
        if len(equity_df) > 0:
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
            max_drawdown = equity_df['drawdown'].min()
        else:
            max_drawdown = 0
        
        return {
            'total_trades': len(completed),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown': round(max_drawdown, 2),
            'total_pnl': round(df['pnl'].sum(), 2),
            'return_percent': round((self.cash - self.initial_capital) / self.initial_capital * 100, 2),
            'trades': completed,
            'equity_curve': self.equity_curve
        }


STRATEGY_CONFIG = {
    "indicator": "Supertrend EMA",
    "indicators": ["EMA 20/50/100/200", "Supertrend", "Volume"],
    "entry": {
        "buy": "EMA bullish stack + Supertrend flip + pullback + volume",
        "sell": "EMA bearish stack + Supertrend flip + pullback + volume"
    },
    "exit": {
        "buy": "Opposite signal or SL/TP hit",
        "sell": "Opposite signal or SL/TP hit"
    },
    "filters": {
        "trend": "EMA alignment (20>50>100>200 or reverse)",
        "structure": "HH/HL or LH/LL",
        "volume": "Above 20-period average",
        "sideways": "Avoid when EMAs tangled or low ATR"
    },
    "risk_management": {
        "stop_loss": "1.5 × ATR",
        "take_profit": "2.0 × Risk (RR 1:2)",
        "position_sizing": "Capital / Entry Price"
    }
}
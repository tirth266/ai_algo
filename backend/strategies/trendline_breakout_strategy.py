"""
Trendline Breakout Strategy

Institutional-grade trend-following strategy combining:
- Trendline Breakout (pivot-based dynamic support/resistance)
- Supertrend (trend direction)
- EMA 20/50/100/200 (trend strength)
- Volume confirmation
- Market structure (HH/HL or LH/LL)

Entry Rules:
  BUY: Trendline breakout up + EMA bullish + Supertrend + volume
  SELL: Trendline breakout down + EMA bearish + Supertrend + volume

Filters:
  - Trend: EMA alignment
  - Volume: above average
  - Structure: HH/HL or LH/LL
  - Fake breakout: low volume / rejection candle
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import (
    calculate_trendline_channels,
    detect_breakouts,
    identify_pivots,
)

logger = logging.getLogger(__name__)


class TrendlineBreakoutStrategy(BaseStrategy):
    def __init__(
        self,
        capital: float = 25000.0,
        pivot_period: int = 14,
        atr_period: int = 10,
        supertrend_multiplier: float = 3.0,
        ema_periods: List[int] = None,
        volume_ma_period: int = 20,
        risk_reward_ratio: float = 2.0,
        atr_sl_multiplier: float = 1.5,
        min_breakout_strength: float = 0.5,
        min_channel_width: float = 1.0,
    ):
        super().__init__(name="TrendlineBreakout", capital=capital)

        self.pivot_period = pivot_period
        self.atr_period = atr_period
        self.supertrend_multiplier = supertrend_multiplier
        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.volume_ma_period = volume_ma_period
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.min_breakout_strength = min_breakout_strength
        self.min_channel_width = min_channel_width

        self.last_signal = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.broken_trendline = None

    def calculate_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()

        for period in self.ema_periods:
            df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()

        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = true_range.rolling(window=self.atr_period).mean()

        df["volume_ma"] = df["volume"].rolling(window=self.volume_ma_period).mean()

        pivot_highs, pivot_lows = identify_pivots(df, self.pivot_period)
        df["is_pivot_high"] = pivot_highs
        df["is_pivot_low"] = pivot_lows

        trendline_df = calculate_trendline_channels(df, self.pivot_period)
        df["trendline_upper"] = trendline_df["trendline_upper"]
        df["trendline_lower"] = trendline_df["trendline_lower"]
        df["swing_high_price"] = trendline_df["swing_high_price"]
        df["swing_low_price"] = trendline_df["swing_low_price"]

        supertrend_df = calculate_supertrend(
            df[["open", "high", "low", "close"]].copy(),
            period=self.atr_period,
            multiplier=self.supertrend_multiplier,
        )
        if not supertrend_df.empty:
            df["supertrend"] = supertrend_df["supertrend"]
            df["trend_direction"] = supertrend_df["trend_direction"]

        return df

    def check_ema_alignment(self, df: pd.DataFrame) -> str:
        if len(df) < max(self.ema_periods) + 1:
            return "neutral"

        idx = -1
        ema20 = df[f"ema_{self.ema_periods[0]}"].iloc[idx]
        ema50 = df[f"ema_{self.ema_periods[1]}"].iloc[idx]
        ema100 = df[f"ema_{self.ema_periods[2]}"].iloc[idx]
        ema200 = df[f"ema_{self.ema_periods[3]}"].iloc[idx]

        if ema20 > ema50 > ema100 > ema200:
            return "bullish"
        elif ema20 < ema50 < ema100 < ema200:
            return "bearish"
        return "neutral"

    def detect_market_structure(self, df: pd.DataFrame, lookback: int = 5) -> str:
        if len(df) < lookback + 2:
            return "neutral"

        highs = df["high"].rolling(window=lookback).max()
        lows = df["low"].rolling(window=lookback).min()

        last_high = df["high"].iloc[-1]
        last_low = df["low"].iloc[-1]
        prev_high = df["high"].iloc[-2]
        prev_low = df["low"].iloc[-2]

        if last_high > prev_high and last_low > prev_low:
            return "hh_hl"
        elif last_high < prev_high and last_low < prev_low:
            return "lh_ll"
        return "neutral"

    def check_breakout_confirmation(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        if len(df) < 2:
            return False, False

        current = df.iloc[-1]
        previous = df.iloc[-2]

        current_close = current["close"]
        current_open = current["open"]
        current_volume = current["volume"]
        volume_ma = current["volume_ma"]

        upper_trendline = current["trendline_upper"]
        lower_trendline = current["trendline_lower"]

        bullish_confirmation = False
        bearish_confirmation = False

        if not pd.isna(upper_trendline) and current_close > upper_trendline:
            candle_strength = ((current_close - current_open) / current_open) * 100
            is_bullish_candle = current_close > current_open
            has_volume = current_volume > volume_ma

            if is_bullish_candle and has_volume and candle_strength > 0.2:
                bullish_confirmation = True

        if not pd.isna(lower_trendline) and current_close < lower_trendline:
            candle_strength = ((current_open - current_close) / current_close) * 100
            is_bearish_candle = current_close < current_open
            has_volume = current_volume > volume_ma

            if is_bearish_candle and has_volume and candle_strength > 0.2:
                bearish_confirmation = True

        return bullish_confirmation, bearish_confirmation

    def detect_trend_change(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        if len(df) < 2 or "trend_direction" not in df.columns:
            return False, False

        current = df["trend_direction"].iloc[-1]
        previous = df["trend_direction"].iloc[-2]

        bullish_flip = previous == -1 and current == 1
        bearish_flip = previous == 1 and current == -1

        return bullish_flip, bearish_flip

    def is_sideways_market(self, df: pd.DataFrame) -> bool:
        if len(df) < 20:
            return True

        if self.min_channel_width > 0:
            upper = df["trendline_upper"].iloc[-1]
            lower = df["trendline_lower"].iloc[-1]

            if not pd.isna(upper) and not pd.isna(lower):
                channel_width = ((upper - lower) / lower) * 100
                if channel_width < self.min_channel_width:
                    return True

        return False

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        if len(candles) < 50:
            return None

        df = self.calculate_indicators(candles)

        if df.empty or "supertrend" not in df.columns:
            return None

        if self.is_sideways_market(df):
            logger.debug("Sideways market detected, skipping")
            return None

        ema_alignment = self.check_ema_alignment(df)
        structure = self.detect_market_structure(df)

        current = df.iloc[-1]
        prev = df.iloc[-2]

        upper_broken = (
            not pd.isna(current["trendline_upper"])
            and current["close"] > current["trendline_upper"]
        )
        lower_broken = (
            not pd.isna(current["trendline_lower"])
            and current["close"] < current["trendline_lower"]
        )

        prev_upper_intact = (
            not pd.isna(prev["trendline_upper"])
            and prev["close"] <= prev["trendline_upper"]
        )
        prev_lower_intact = (
            not pd.isna(prev["trendline_lower"])
            and prev["close"] >= prev["trendline_lower"]
        )

        breakout_above = upper_broken and prev_upper_intact
        breakout_below = lower_broken and prev_lower_intact

        bullish_confirm, bearish_confirm = self.check_breakout_confirmation(df)

        trend_dir = df["trend_direction"].iloc[-1]
        volume = current["volume"]
        volume_ma = current["volume_ma"]
        ema50 = current[f"ema_{self.ema_periods[1]}"]

        if breakout_above and bullish_confirm:
            if ema_alignment == "bullish" and trend_dir == 1 and structure == "hh_hl":
                if volume > volume_ma and current["close"] > ema50:
                    self.last_signal = "BUY"
                    self.entry_price = current["close"]

                    if not pd.isna(prev["trendline_upper"]):
                        self.stop_loss = prev["trendline_upper"]
                    else:
                        self.stop_loss = current["close"] - (
                            self.atr_sl_multiplier * current["atr"]
                        )

                    risk = abs(self.entry_price - self.stop_loss)
                    self.take_profit = self.entry_price + (
                        self.risk_reward_ratio * risk
                    )
                    self.broken_trendline = prev["trendline_upper"]

                    logger.info(
                        f"BUY: Trendline breakout up + EMA bullish + HH/HL + volume"
                    )
                    return "BUY"

        if breakout_below and bearish_confirm:
            if ema_alignment == "bearish" and trend_dir == -1 and structure == "lh_ll":
                if volume > volume_ma and current["close"] < ema50:
                    self.last_signal = "SELL"
                    self.entry_price = current["close"]

                    if not pd.isna(prev["trendline_lower"]):
                        self.stop_loss = prev["trendline_lower"]
                    else:
                        self.stop_loss = current["close"] + (
                            self.atr_sl_multiplier * current["atr"]
                        )

                    risk = abs(self.entry_price - self.stop_loss)
                    self.take_profit = self.entry_price - (
                        self.risk_reward_ratio * risk
                    )
                    self.broken_trendline = prev["trendline_lower"]

                    logger.info(
                        f"SELL: Trendline breakout down + EMA bearish + LH/LL + volume"
                    )
                    return "SELL"

        return None

    def get_risk_levels(self) -> Dict[str, float]:
        return {
            "entry_price": self.entry_price or 0.0,
            "stop_loss": self.stop_loss or 0.0,
            "take_profit": self.take_profit or 0.0,
            "risk": abs(self.entry_price - self.stop_loss)
            if self.entry_price and self.stop_loss
            else 0.0,
            "reward": abs(self.take_profit - self.entry_price)
            if self.entry_price and self.take_profit
            else 0.0,
            "risk_reward": self.risk_reward_ratio,
            "broken_trendline": self.broken_trendline or 0.0,
        }


class Backtester:
    def __init__(
        self,
        strategy: TrendlineBreakoutStrategy,
        initial_capital: float = 100000.0,
        slippage_percent: float = 0.001,
        brokerage: float = 20.0,
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
            current_df = df.iloc[: i + 1].copy()
            current_candle = current_df.iloc[-1]

            signal = self.strategy.generate_signal(current_df)

            if signal and not self.positions:
                self._execute_entry(signal, current_candle)

            if self.positions:
                self._check_exits(current_candle)

            equity = self._calculate_equity(current_candle)
            self.equity_curve.append(
                {
                    "time": current_candle.name,
                    "equity": equity,
                    "position": len(self.positions),
                }
            )

        if self.positions:
            self._close_all(df.iloc[-1])

        return self._calculate_metrics()

    def _execute_entry(self, signal: str, candle: pd.Series):
        quantity = self.strategy.get_quantity(candle["close"])

        entry_price = candle["close"] * (
            1 + self.slippage_percent if signal == "BUY" else 1 - self.slippage_percent
        )

        cost = quantity * entry_price
        if cost > self.cash:
            return

        position = {
            "direction": signal,
            "entry_price": entry_price,
            "quantity": quantity,
            "stop_loss": self.strategy.stop_loss,
            "take_profit": self.strategy.take_profit,
            "entry_time": candle.name,
        }

        self.positions.append(position)
        self.cash -= cost + self.brokerage

        self.trades.append(
            {
                "entry_time": candle.name,
                "direction": signal,
                "entry_price": entry_price,
                "quantity": quantity,
                "stop_loss": self.strategy.stop_loss,
                "take_profit": self.strategy.take_profit,
            }
        )

    def _check_exits(self, candle: pd.Series):
        price = candle["close"]

        to_remove = []

        for i, position in enumerate(self.positions):
            exit_price = None
            reason = None

            if position["direction"] == "BUY":
                if price <= position["stop_loss"]:
                    exit_price = price * (1 - self.slippage_percent)
                    reason = "STOP_LOSS"
                elif price >= position["take_profit"]:
                    exit_price = price * (1 - self.slippage_percent)
                    reason = "TAKE_PROFIT"
            else:
                if price >= position["stop_loss"]:
                    exit_price = price * (1 + self.slippage_percent)
                    reason = "STOP_LOSS"
                elif price <= position["take_profit"]:
                    exit_price = price * (1 + self.slippage_percent)
                    reason = "TAKE_PROFIT"

            if exit_price:
                self._execute_exit(i, exit_price, reason, candle.name)
                to_remove.append(i)

        for i in reversed(to_remove):
            self.positions.pop(i)

    def _execute_exit(
        self, position_idx: int, exit_price: float, reason: str, exit_time
    ):
        position = self.positions[position_idx]

        if position["direction"] == "BUY":
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
        else:
            pnl = (position["entry_price"] - exit_price) * position["quantity"]

        pnl -= self.brokerage

        self.cash += exit_price * position["quantity"] + pnl

        self.trades[position_idx].update(
            {
                "exit_time": exit_time,
                "exit_price": exit_price,
                "pnl": pnl,
                "exit_reason": reason,
            }
        )

    def _close_all(self, candle: pd.Series):
        for i in range(len(self.positions)):
            self._execute_exit(i, candle["close"], "END_OF_BACKTEST", candle.name)
        self.positions.clear()

    def _calculate_equity(self, candle: pd.Series) -> float:
        equity = self.cash
        for position in self.positions:
            if position["direction"] == "BUY":
                equity += (candle["close"] - position["entry_price"]) * position[
                    "quantity"
                ]
            else:
                equity += (position["entry_price"] - candle["close"]) * position[
                    "quantity"
                ]
        return equity

    def _calculate_metrics(self) -> Dict[str, Any]:
        completed = [t for t in self.trades if "pnl" in t]

        if not completed:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "trades": [],
            }

        df = pd.DataFrame(completed)

        wins = df[df["pnl"] > 0]
        losses = df[df["pnl"] < 0]

        win_rate = len(wins) / len(df) * 100 if len(df) > 0 else 0

        gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        equity_df = pd.DataFrame(self.equity_curve)
        if len(equity_df) > 0:
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (
                (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"] * 100
            )
            max_drawdown = equity_df["drawdown"].min()
        else:
            max_drawdown = 0

        return {
            "total_trades": len(completed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "total_pnl": round(df["pnl"].sum(), 2),
            "return_percent": round(
                (self.cash - self.initial_capital) / self.initial_capital * 100, 2
            ),
            "trades": completed,
            "equity_curve": self.equity_curve,
        }


STRATEGY_CONFIG = {
    "indicator": "Trendline Breakout",
    "indicators": ["Supertrend", "EMA 20/50/100/200", "Trendline Breakout", "Volume"],
    "entry": {
        "buy": "Trendline breakout up + EMA bullish + Supertrend + volume",
        "sell": "Trendline breakout down + EMA bearish + Supertrend + volume",
    },
    "exit": {
        "buy": "Opposite signal or SL/TP hit",
        "sell": "Opposite signal or SL/TP hit",
    },
    "filters": {
        "trend": "EMA alignment (20>50>100>200 or reverse)",
        "volume": "Above 20-period average",
        "structure": "HH/HL or LH/LL",
        "fake_breakout": "Requires strong candle + volume spike",
        "sideways": "Avoid when channel width < 1%",
    },
    "risk_management": {
        "stop_loss": "Below/above broken trendline or 1.5×ATR",
        "take_profit": "2.0× Risk (RR 1:2)",
        "position_sizing": "Capital / Entry Price",
    },
}

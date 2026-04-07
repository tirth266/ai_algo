"""
VWAP Mean Reversion Strategy

Institutional-grade mean reversion strategy using VWAP bands.
Integrates with existing trend-following system for market condition switching.

Entry Rules:
  BUY: Price below VWAP band + RSI oversold/divergence + volume + reversal
  SELL: Price above VWAP band + RSI overbought/divergence + volume + reversal

Filters:
  - Market condition: sideways only
  - Volume: above average
  - Momentum: RSI extreme/divergence
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import identify_pivots
from ..indicators.vwap_tv import TradingViewVWAP

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def detect_rsi_divergence(
    prices: pd.Series, rsi: pd.Series, pivot_period: int = 5
) -> Dict[str, Any]:
    """Detect RSI divergence patterns."""
    if len(prices) < pivot_period * 2 + 1:
        return {"type": "none", "bullish": False, "bearish": False, "strength": 0.0}

    price_highs = []
    price_lows = []
    rsi_highs = []
    rsi_lows = []

    for i in range(pivot_period, len(prices) - pivot_period):
        is_high = (
            prices.iloc[i] == prices.iloc[i - pivot_period : i + pivot_period].max()
        )
        is_low = (
            prices.iloc[i] == prices.iloc[i - pivot_period : i + pivot_period].min()
        )

        if is_high:
            price_highs.append(prices.iloc[i])
            rsi_highs.append(rsi.iloc[i])

        if is_low:
            price_lows.append(prices.iloc[i])
            rsi_lows.append(rsi.iloc[i])

    if len(price_highs) < 2 or len(price_lows) < 2:
        return {"type": "none", "bullish": False, "bearish": False, "strength": 0.0}

    bullish_div = (
        price_lows[-1] < price_lows[-2] and rsi_lows[-1] > rsi_lows[-2]
        if len(price_lows) >= 2 and len(rsi_lows) >= 2
        else False
    )
    bearish_div = (
        price_highs[-1] > price_highs[-2] and rsi_highs[-1] < rsi_highs[-2]
        if len(price_highs) >= 2 and len(rsi_highs) >= 2
        else False
    )

    div_type = "none"
    if bullish_div:
        div_type = "regular_bullish"
    elif bearish_div:
        div_type = "regular_bearish"

    return {
        "type": div_type,
        "bullish": bullish_div,
        "bearish": bearish_div,
        "strength": 0.0,
    }


class VWAPMeanReversionStrategy(BaseStrategy):
    def __init__(
        self,
        capital: float = 25000.0,
        vwap_anchor: str = "Session",
        band_multiplier: float = 2.0,
        atr_period: int = 14,
        rsi_period: int = 14,
        ema_periods: List[int] = None,
        volume_ma_period: int = 20,
        risk_reward_ratio: float = 1.5,
        atr_sl_multiplier: float = 1.2,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        sideways_threshold: float = 0.5,
    ):
        super().__init__(name="VWAPMeanReversion", capital=capital)

        self.vwap_anchor = vwap_anchor
        self.band_multiplier = band_multiplier
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.ema_periods = ema_periods or [20, 50, 100]
        self.volume_ma_period = volume_ma_period
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.sideways_threshold = sideways_threshold

        self.vwap = TradingViewVWAP(
            anchor_period=vwap_anchor,
            band_multiplier_1=1.0,
            band_multiplier_2=band_multiplier,
            band_multiplier_3=band_multiplier * 1.5,
        )

        self.last_signal = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None

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

        df["rsi"] = calculate_rsi(close, self.rsi_period)

        vwap_result = self.vwap.calculate(df)

        df["vwap"] = vwap_result.get("vwap")
        df["vwap_upper_1"] = vwap_result.get("upper_band_1")
        df["vwap_lower_1"] = vwap_result.get("lower_band_1")
        df["vwap_upper_2"] = vwap_result.get("upper_band_2")
        df["vwap_lower_2"] = vwap_result.get("lower_band_2")

        df["vwap_deviation"] = abs(close - df["vwap"]) / df["vwap"] * 100

        df["price_above_vwap"] = close > df["vwap"]

        supertrend_df = calculate_supertrend(
            df[["open", "high", "low", "close"]].copy(),
            period=self.atr_period,
            multiplier=3.0,
        )
        if not supertrend_df.empty:
            df["trend_direction"] = supertrend_df["trend_direction"]

        return df

    def detect_market_condition(self, df: pd.DataFrame) -> str:
        """Determine if market is trending or sideways."""
        if len(df) < max(self.ema_periods) + 1:
            return "unknown"

        ema20 = df[f"ema_{self.ema_periods[0]}"].iloc[-1]
        ema50 = df[f"ema_{self.ema_periods[1]}"].iloc[-1]
        ema100 = df[f"ema_{self.ema_periods[2]}"].iloc[-1]

        spread_pct = abs(ema20 - ema100) / ema100 * 100 if ema100 != 0 else 0

        if ema20 > ema50 > ema100:
            return "trending_up"
        elif ema20 < ema50 < ema100:
            return "trending_down"

        if spread_pct < self.sideways_threshold:
            return "sideways"

        return "weak_trend"

    def detect_liquidity_sweep(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Detect liquidity sweeps (stop hunts)."""
        if len(df) < 5:
            return False, False

        current = df.iloc[-1]
        prev_highs = df["high"].iloc[-5:-1].max()
        prev_lows = df["low"].iloc[-5:-1].min()

        sweep_above = (
            current["close"] > prev_highs and current["close"] > current["open"]
        )
        sweep_below = (
            current["close"] < prev_lows and current["close"] < current["open"]
        )

        return sweep_above, sweep_below

    def is_extreme_price(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Check if price is at VWAP band extremes."""
        if len(df) < 1:
            return False, False

        current = df.iloc[-1]
        close = current["close"]
        lower_band = current["vwap_lower_2"]
        upper_band = current["vwap_upper_2"]

        at_lower_extreme = not pd.isna(lower_band) and close <= lower_band
        at_upper_extreme = not pd.isna(upper_band) and close >= upper_band

        return at_lower_extreme, at_upper_extreme

    def check_reversal_candle(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Check for reversal candle confirmation."""
        if len(df) < 1:
            return False, False

        current = df.iloc[-1]
        open_price = current["open"]
        close_price = current["close"]
        high = current["high"]
        low = current["low"]

        body = abs(close_price - open_price)
        upper_wick = high - max(close_price, open_price)
        lower_wick = min(close_price, open_price) - low

        bullish_reversal = (
            close_price > open_price
            and body > (high - low) * 0.6
            and upper_wick < body * 0.3
        )

        bearish_reversal = (
            close_price < open_price
            and body > (high - low) * 0.6
            and lower_wick < body * 0.3
        )

        return bullish_reversal, bearish_reversal

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        if len(candles) < 50:
            return None

        df = self.calculate_indicators(candles)

        if df.empty or "vwap" not in df.columns:
            return None

        market_condition = self.detect_market_condition(df)

        if market_condition in ["trending_up", "trending_down"]:
            return None

        current = df.iloc[-1]

        at_lower, at_upper = self.is_extreme_price(df)
        sweep_above, sweep_below = self.detect_liquidity_sweep(df)
        bullish_rev, bearish_rev = self.check_reversal_candle(df)

        rsi = current["rsi"]
        volume = current["volume"]
        volume_ma = current["volume_ma"]

        has_volume = volume > volume_ma

        rsi_div = detect_rsi_divergence(df["close"], df["rsi"], 5)

        if at_lower and has_volume:
            rsi_oversold = rsi < self.rsi_oversold
            has_divergence = rsi_div["bullish"]

            if rsi_oversold or has_divergence:
                if bullish_rev:
                    self.last_signal = "BUY"
                    self.entry_price = current["close"]
                    self.stop_loss = current["vwap_lower_2"] - (
                        self.atr_sl_multiplier * current["atr"]
                    )
                    risk = abs(self.entry_price - self.stop_loss)
                    self.take_profit = current["vwap"]

                    logger.info(
                        f"BUY: VWAP lower band + RSI oversold/div + volume + reversal"
                    )
                    return "BUY"

        if at_upper and has_volume:
            rsi_overbought = rsi > self.rsi_overbought
            has_divergence = rsi_div["bearish"]

            if rsi_overbought or has_divergence:
                if bearish_rev:
                    self.last_signal = "SELL"
                    self.entry_price = current["close"]
                    self.stop_loss = current["vwap_upper_2"] + (
                        self.atr_sl_multiplier * current["atr"]
                    )
                    risk = abs(self.entry_price - self.stop_loss)
                    self.take_profit = current["vwap"]

                    logger.info(
                        f"SELL: VWAP upper band + RSI overbought/div + volume + reversal"
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
        }


class MasterStrategy:
    """Master strategy that switches between trend-following and mean reversion."""

    def __init__(
        self,
        capital: float = 25000.0,
        vwap_strategy: Optional[VWAPMeanReversionStrategy] = None,
        trend_strategy: Any = None,
    ):
        self.name = "MasterStrategy"
        self.capital = capital
        self.vwap_strategy = vwap_strategy or VWAPMeanReversionStrategy(capital=capital)
        self.trend_strategy = trend_strategy

        self.last_signal = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.current_mode = None

    def detect_market_condition(self, df: pd.DataFrame) -> str:
        """Determine market condition for strategy selection."""
        ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
        ema100 = df["close"].ewm(span=100, adjust=False).mean().iloc[-1]

        spread_pct = abs(ema20 - ema100) / ema100 * 100 if ema100 != 0 else 0

        if ema20 > ema50 > ema100:
            return "trending_up"
        elif ema20 < ema50 < ema100:
            return "trending_down"

        if spread_pct < 0.5:
            return "sideways"

        return "weak_trend"

    def generate_signals(self, candles: pd.DataFrame) -> Optional[str]:
        """Generate signals based on market condition."""
        if len(candles) < 50:
            return None

        df = candles.copy()

        market_condition = self.detect_market_condition(df)
        self.current_mode = market_condition

        if market_condition in ["trending_up", "trending_down", "weak_trend"]:
            if self.trend_strategy:
                signal = self.trend_strategy.generate_signal(candles)
                if signal:
                    self.last_signal = signal
                    self.entry_price = self.trend_strategy.entry_price
                    self.stop_loss = self.trend_strategy.stop_loss
                    self.take_profit = self.trend_strategy.take_profit
                    logger.info(f"Trend mode: {signal}")
                    return signal
            return None

        else:
            signal = self.vwap_strategy.generate_signal(candles)
            if signal:
                self.last_signal = signal
                self.entry_price = self.vwap_strategy.entry_price
                self.stop_loss = self.vwap_strategy.stop_loss
                self.take_profit = self.vwap_strategy.take_profit
                logger.info(f"VWAP Mean Reversion mode: {signal}")
                return signal

        return None

    def get_risk_levels(self) -> Dict[str, float]:
        return {
            "entry_price": self.entry_price or 0.0,
            "stop_loss": self.stop_loss or 0.0,
            "take_profit": self.take_profit or 0.0,
            "mode": self.current_mode or "unknown",
        }


class Backtester:
    def __init__(
        self,
        strategy: Any,
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
        if hasattr(self.strategy, "calculate_indicators"):
            df = self.strategy.calculate_indicators(candles)
        else:
            df = candles

        for i in range(50, len(df)):
            current_df = df.iloc[: i + 1].copy()
            current_candle = current_df.iloc[-1]

            signal = (
                self.strategy.generate_signals(current_df)
                if hasattr(self.strategy, "generate_signals")
                else self.strategy.generate_signal(current_df)
            )

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
        quantity = max(1, int(self.strategy.capital / candle["close"]))

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
        max_drawdown = 0.0

        if len(equity_df) > 0:
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (
                (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"] * 100
            )
            max_drawdown = equity_df["drawdown"].min()

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
    "type": "Mean Reversion",
    "indicator": "VWAP",
    "indicators": ["VWAP", "RSI", "Volume"],
    "entry": {
        "buy": "Price below VWAP band + RSI oversold/divergence + volume + reversal",
        "sell": "Price above VWAP band + RSI overbought/divergence + volume + reversal",
    },
    "exit": {"target": "VWAP", "stop_loss": "ATR or liquidity"},
    "filters": {
        "market_condition": "sideways only",
        "volume": "above average",
        "momentum": "RSI extreme/divergence",
    },
    "risk_management": {
        "stop_loss": "1.2×ATR below/above band",
        "take_profit": "VWAP or 1.5×Risk",
        "position_sizing": "Capital / Entry Price",
    },
}

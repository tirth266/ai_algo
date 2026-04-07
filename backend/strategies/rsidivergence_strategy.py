"""
RSI Divergence Master Strategy

Institutional-grade multi-indicator strategy combining:
- Trendline Breakout (structure + liquidity)
- Supertrend (trend direction)
- EMA 20/50/100/200 (trend strength)
- RSI Divergence (momentum confirmation)
- Volume (confirmation)
- Market Structure (HH/HL, LH/LL)

Entry Rules:
  BUY: Trendline breakout + EMA bullish + Supertrend + RSI bullish divergence + volume
  SELL: Trendline breakout + EMA bearish + Supertrend + RSI bearish divergence + volume

Filters:
  - Trend: EMA alignment
  - Momentum: RSI divergence
  - Volume: above average
  - Structure: HH/HL or LH/LL
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import calculate_trendline_channels, identify_pivots

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
    """
    Detect RSI divergence patterns.

    Returns:
        Dict with divergence type and strength
    """
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

    bullish_divergence = False
    bearish_divergence = False
    hidden_bullish = False
    hidden_bearish = False

    price_lower_low = price_lows[-1] < price_lows[-2] if len(price_lows) >= 2 else False
    rsi_higher_low = rsi_lows[-1] > rsi_lows[-2] if len(rsi_lows) >= 2 else False

    if price_lower_low and rsi_higher_low:
        bullish_divergence = True

    price_higher_high = (
        price_highs[-1] > price_highs[-2] if len(price_highs) >= 2 else False
    )
    rsi_lower_high = rsi_highs[-1] < rsi_highs[-2] if len(rsi_highs) >= 2 else False

    if price_higher_high and rsi_lower_high:
        bearish_divergence = True

    price_higher_low = (
        price_lows[-1] > price_lows[-2] if len(price_lows) >= 2 else False
    )
    rsi_lower_low = rsi_lows[-1] < rsi_lows[-2] if len(rsi_lows) >= 2 else False

    if price_higher_low and rsi_lower_low:
        hidden_bullish = True

    price_lower_high = (
        price_highs[-1] < price_highs[-2] if len(price_highs) >= 2 else False
    )
    rsi_higher_high = rsi_highs[-1] > rsi_highs[-2] if len(rsi_highs) >= 2 else False

    if price_lower_high and rsi_higher_high:
        hidden_bearish = True

    div_type = "none"
    if bullish_divergence:
        div_type = "regular_bullish"
    elif bearish_divergence:
        div_type = "regular_bearish"
    elif hidden_bullish:
        div_type = "hidden_bullish"
    elif hidden_bearish:
        div_type = "hidden_bearish"

    strength = 0.0
    if div_type != "none":
        if "bullish" in div_type:
            strength = rsi_lows[-1] - rsi_lows[-2] if len(rsi_lows) >= 2 else 0.0
        else:
            strength = rsi_highs[-2] - rsi_highs[-1] if len(rsi_highs) >= 2 else 0.0

    return {
        "type": div_type,
        "bullish": bullish_divergence or hidden_bullish,
        "bearish": bearish_divergence or hidden_bearish,
        "regular_bullish": bullish_divergence,
        "regular_bearish": bearish_divergence,
        "hidden_bullish": hidden_bullish,
        "hidden_bearish": hidden_bearish,
        "strength": abs(strength),
    }


class RSIDivergenceStrategy(BaseStrategy):
    def __init__(
        self,
        capital: float = 25000.0,
        pivot_period: int = 14,
        rsi_period: int = 14,
        atr_period: int = 10,
        supertrend_multiplier: float = 3.0,
        ema_periods: List[int] = None,
        volume_ma_period: int = 20,
        risk_reward_ratio: float = 2.0,
        atr_sl_multiplier: float = 1.5,
        min_channel_width: float = 1.0,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
    ):
        super().__init__(name="RSIDivergence", capital=capital)

        self.pivot_period = pivot_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.supertrend_multiplier = supertrend_multiplier
        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.volume_ma_period = volume_ma_period
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.min_channel_width = min_channel_width
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

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

        df["rsi"] = calculate_rsi(close, self.rsi_period)

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

        last_high = df["high"].iloc[-1]
        last_low = df["low"].iloc[-1]
        prev_high = df["high"].iloc[-2]
        prev_low = df["low"].iloc[-2]

        if last_high > prev_high and last_low > prev_low:
            return "hh_hl"
        elif last_high < prev_high and last_low < prev_low:
            return "lh_ll"
        return "neutral"

    def check_breakout(self, df: pd.DataFrame) -> Tuple[bool, bool, float, float]:
        """Check for trendline breakout conditions."""
        if len(df) < 2:
            return False, False, 0.0, 0.0

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

        breakout_up = upper_broken and prev_upper_intact
        breakout_down = lower_broken and prev_lower_intact

        candle_strength = 0.0
        if breakout_up:
            candle_strength = (
                (current["close"] - current["open"]) / current["open"]
            ) * 100
        elif breakout_down:
            candle_strength = (
                (current["open"] - current["close"]) / current["close"]
            ) * 100

        return (
            breakout_up,
            breakout_down,
            candle_strength,
            prev["trendline_upper"]
            if not pd.isna(prev["trendline_upper"])
            else prev["trendline_lower"],
        )

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
            return None

        ema_alignment = self.check_ema_alignment(df)
        structure = self.detect_market_structure(df)

        current = df.iloc[-1]
        prev = df.iloc[-2]

        breakout_up, breakout_down, candle_strength, trendline = self.check_breakout(df)

        rsi = current["rsi"]
        rsi_div = detect_rsi_divergence(df["close"], df["rsi"], self.pivot_period)

        volume = current["volume"]
        volume_ma = current["volume_ma"]
        ema50 = current[f"ema_{self.ema_periods[1]}"]
        trend_dir = df["trend_direction"].iloc[-1]

        bullish_candle = current["close"] > current["open"]
        bearish_candle = current["close"] < current["open"]

        has_volume_confirm = volume > volume_ma

        rsi_bullish_zone = rsi < self.rsi_overbought and rsi > self.rsi_oversold
        rsi_bearish_zone = rsi > self.rsi_oversold and rsi < self.rsi_overbought

        if breakout_up and bullish_candle and candle_strength > 0.2:
            if (
                ema_alignment == "bullish"
                and trend_dir == 1
                and structure == "hh_hl"
                and has_volume_confirm
            ):
                if rsi_div["bullish"] or (
                    rsi_div["regular_bullish"] or rsi_div["hidden_bullish"]
                ):
                    if current["close"] > ema50:
                        self.last_signal = "BUY"
                        self.entry_price = current["close"]
                        self.stop_loss = (
                            trendline
                            if not pd.isna(trendline)
                            else current["close"]
                            - (self.atr_sl_multiplier * current["atr"])
                        )
                        risk = abs(self.entry_price - self.stop_loss)
                        self.take_profit = self.entry_price + (
                            self.risk_reward_ratio * risk
                        )

                        logger.info(
                            f"BUY: Trendline breakout + EMA bullish + RSI divergence + volume"
                        )
                        return "BUY"

        if breakout_down and bearish_candle and candle_strength > 0.2:
            if (
                ema_alignment == "bearish"
                and trend_dir == -1
                and structure == "lh_ll"
                and has_volume_confirm
            ):
                if rsi_div["bearish"] or (
                    rsi_div["regular_bearish"] or rsi_div["hidden_bearish"]
                ):
                    if current["close"] < ema50:
                        self.last_signal = "SELL"
                        self.entry_price = current["close"]
                        self.stop_loss = (
                            trendline
                            if not pd.isna(trendline)
                            else current["close"]
                            + (self.atr_sl_multiplier * current["atr"])
                        )
                        risk = abs(self.entry_price - self.stop_loss)
                        self.take_profit = self.entry_price - (
                            self.risk_reward_ratio * risk
                        )

                        logger.info(
                            f"SELL: Trendline breakout + EMA bearish + RSI divergence + volume"
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


class Backtester:
    def __init__(
        self,
        strategy: RSIDivergenceStrategy,
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
                "sharpe_ratio": 0.0,
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
        sharpe_ratio = 0.0

        if len(equity_df) > 0:
            equity_df["peak"] = equity_df["equity"].cummax()
            equity_df["drawdown"] = (
                (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"] * 100
            )
            max_drawdown = equity_df["drawdown"].min()

            if len(equity_df) > 1:
                equity_df["returns"] = equity_df["equity"].pct_change()
                sharpe_ratio = (
                    (equity_df["returns"].mean() / equity_df["returns"].std())
                    * np.sqrt(252)
                    if equity_df["returns"].std() > 0
                    else 0
                )

        return {
            "total_trades": len(completed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "total_pnl": round(df["pnl"].sum(), 2),
            "return_percent": round(
                (self.cash - self.initial_capital) / self.initial_capital * 100, 2
            ),
            "trades": completed,
            "equity_curve": self.equity_curve,
        }


STRATEGY_CONFIG = {
    "indicator": "RSI Divergence Master",
    "indicators": [
        "Supertrend",
        "EMA 20/50/100/200",
        "Trendline Breakout",
        "RSI Divergence",
        "Volume",
    ],
    "entry": {
        "buy": "Trendline breakout + EMA bullish + Supertrend + RSI bullish divergence + volume",
        "sell": "Trendline breakout + EMA bearish + Supertrend + RSI bearish divergence + volume",
    },
    "exit": {
        "buy": "Opposite signal or SL/TP hit",
        "sell": "Opposite signal or SL/TP hit",
    },
    "filters": {
        "trend": "EMA alignment (20>50>100>200 or reverse)",
        "momentum": "RSI divergence (regular or hidden)",
        "volume": "Above 20-period average",
        "structure": "HH/HL or LH/LL",
        "sideways": "Avoid when channel width < 1%",
    },
    "risk_management": {
        "stop_loss": "Below/above broken trendline or 1.5×ATR",
        "take_profit": "2.0× Risk (RR 1:2)",
        "position_sizing": "Capital / Entry Price",
        "risk_per_trade": "1-2%",
    },
}

"""
Order Block Strategy

Institutional smart money strategy detecting order blocks.
Integrates with existing multi-strategy system.

Entry Rules:
  BUY: Bullish OB + liquidity sweep + RSI divergence + volume
  SELL: Bearish OB + liquidity sweep + RSI divergence + volume

Filters:
  - Mitigation: ignore mitigated OB
  - Volume: above average
  - Momentum: RSI confirmation
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import identify_pivots

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
        return {"type": "none", "bullish": False, "bearish": False}

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
        return {"type": "none", "bullish": False, "bearish": False}

    bullish_div = (
        len(price_lows) >= 2
        and len(rsi_lows) >= 2
        and price_lows[-1] < price_lows[-2]
        and rsi_lows[-1] > rsi_lows[-2]
    )
    bearish_div = (
        len(price_highs) >= 2
        and len(rsi_highs) >= 2
        and price_highs[-1] > price_highs[-2]
        and rsi_highs[-1] < rsi_highs[-2]
    )

    div_type = "none"
    if bullish_div:
        div_type = "regular_bullish"
    elif bearish_div:
        div_type = "regular_bearish"

    return {"type": div_type, "bullish": bullish_div, "bearish": bearish_div}


class OrderBlock:
    """Represents a single order block."""

    def __init__(
        self,
        block_type: str,
        high: float,
        low: float,
        volume: float,
        start_index: int,
        start_time: Any,
        direction: int,
    ):
        self.block_type = block_type
        self.high = high
        self.low = low
        self.volume = volume
        self.start_index = start_index
        self.start_time = start_time
        self.direction = direction
        self.mitigated = False
        self.mitigated_time = None

    @property
    def is_bullish(self) -> bool:
        return self.block_type == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.block_type == "bearish"

    def contains(self, price: float) -> bool:
        if self.is_bullish:
            return self.low <= price <= self.high
        else:
            return self.low <= price <= self.high

    def __repr__(self):
        return f"OrderBlock({self.block_type}, high={self.high:.2f}, low={self.low:.2f}, mitigated={self.mitigated})"


def detect_order_blocks(
    data: pd.DataFrame,
    lookback: int = 50,
    volume_threshold: float = 1.5,
    min_bars_before_move: int = 3,
) -> List[OrderBlock]:
    """
    Detect bullish and bearish order blocks.

    Bullish OB: Last bearish candle before strong upward move
    Bearish OB: Last bullish candle before strong downward move
    """
    blocks = []

    if len(data) < lookback + min_bars_before_move:
        return blocks

    volumes = data["volume"]
    volume_ma = volumes.rolling(window=20).mean()

    for i in range(min_bars_before_move, len(data) - min_bars_before_move):
        current_bar = data.iloc[i]
        next_bars = data.iloc[i + 1 : i + 1 + min_bars_before_move]

        if len(next_bars) < min_bars_before_move:
            break

        is_bullish_move = (
            next_bars["close"].iloc[-1] - current_bar["close"]
        ) / current_bar["close"] > 0.01
        is_bearish_move = (
            current_bar["close"] - next_bars["close"].iloc[-1]
        ) / next_bars["close"].iloc[-1] > 0.01

        is_high_volume = current_bar["volume"] > volume_ma.iloc[i] * volume_threshold

        if is_high_volume:
            if is_bullish_move and current_bar["close"] < current_bar["open"]:
                block = OrderBlock(
                    block_type="bullish",
                    high=current_bar["high"],
                    low=current_bar["low"],
                    volume=current_bar["volume"],
                    start_index=i,
                    start_time=current_bar.name,
                    direction=1,
                )
                blocks.append(block)
                logger.debug(
                    f"Bullish OB detected at {current_bar.name}: h={current_bar['high']:.2f} l={current_bar['low']:.2f}"
                )

            elif is_bearish_move and current_bar["close"] > current_bar["open"]:
                block = OrderBlock(
                    block_type="bearish",
                    high=current_bar["high"],
                    low=current_bar["low"],
                    volume=current_bar["volume"],
                    start_index=i,
                    start_time=current_bar.name,
                    direction=-1,
                )
                blocks.append(block)
                logger.debug(
                    f"Bearish OB detected at {current_bar.name}: h={current_bar['high']:.2f} l={current_bar['low']:.2f}"
                )

    logger.info(f"Detected {len(blocks)} order blocks")
    return blocks


def check_mitigation(
    blocks: List[OrderBlock], current_price: float, direction: str
) -> List[OrderBlock]:
    """Check which order blocks are mitigated."""
    for block in blocks:
        if block.mitigated:
            continue

        if direction == "bullish" and block.is_bearish:
            if current_price >= block.high:
                block.mitigated = True
                logger.debug(f"Bearish OB mitigated at {current_price:.2f}")

        elif direction == "bearish" and block.is_bullish:
            if current_price <= block.low:
                block.mitigated = True
                logger.debug(f"Bullish OB mitigated at {current_price:.2f}")

    return blocks


def detect_liquidity_sweep(data: pd.DataFrame, lookback: int = 10) -> Tuple[bool, bool]:
    """Detect liquidity sweeps (stop hunts)."""
    if len(data) < lookback + 1:
        return False, False

    current = data.iloc[-1]
    current_close = current["close"]

    recent_highs = data["high"].iloc[-lookback:-1].max()
    recent_lows = data["low"].iloc[-lookback:-1].min()

    above_sweep = current_close > recent_highs and current["close"] > current["open"]
    below_sweep = current_close < recent_lows and current["close"] < current["open"]

    if above_sweep:
        logger.debug(f"Liquidity sweep above at {current_close:.2f}")
    if below_sweep:
        logger.debug(f"Liquidity sweep below at {current_close:.2f}")

    return above_sweep, below_sweep


def calculate_vwap_bands(data: pd.DataFrame, anchor: str = "Session") -> pd.DataFrame:
    """Calculate VWAP bands."""
    df = data.copy()

    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    tpv = tp * df["volume"]

    index = df.index

    if anchor == "Session":
        groups = pd.Series(index.date, index=index)
    else:
        groups = pd.Series(index, index=index)

    vwap_values = pd.Series(index=df.index, dtype=float)

    for group_key in groups.unique():
        mask = groups == group_key
        indices = df.index[mask]

        if len(indices) == 0:
            continue

        cum_tpv = tpv.loc[indices].cumsum()
        cum_vol = df["volume"].loc[indices].cumsum()

        vwap_values.loc[indices] = cum_tpv / cum_vol

    vwap_values = vwap_values.ffill()

    deviation = tp - vwap_values
    stdev = deviation.expanding(min_periods=2).std().ffill()

    df["vwap"] = vwap_values
    df["vwap_upper"] = vwap_values + stdev * 2
    df["vwap_lower"] = vwap_values - stdev * 2

    return df


class OrderBlockStrategy(BaseStrategy):
    def __init__(
        self,
        capital: float = 25000.0,
        atr_period: int = 14,
        rsi_period: int = 14,
        ema_periods: List[int] = None,
        volume_ma_period: int = 20,
        volume_threshold: float = 1.5,
        risk_reward_ratio: float = 2.0,
        atr_sl_multiplier: float = 1.2,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
    ):
        super().__init__(name="OrderBlock", capital=capital)

        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.volume_ma_period = volume_ma_period
        self.volume_threshold = volume_threshold
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

        self.order_blocks: List[OrderBlock] = []
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

        vwap_df = calculate_vwap_bands(df)
        df["vwap"] = vwap_df["vwap"]
        df["vwap_upper"] = vwap_df["vwap_upper"]
        df["vwap_lower"] = vwap_df["vwap_lower"]

        pivot_highs, pivot_lows = identify_pivots(df, 5)
        df["is_pivot_high"] = pivot_highs
        df["is_pivot_low"] = pivot_lows

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

        if spread_pct < 0.5:
            return "sideways"

        return "weak_trend"

    def find_active_blocks(
        self, current_price: float, direction: str
    ) -> List[OrderBlock]:
        """Find active (unmitigated) order blocks."""
        active = []

        for block in self.order_blocks:
            if block.mitigated:
                continue

            if direction == "bullish" and block.is_bullish:
                if current_price >= block.low:
                    active.append(block)

            elif direction == "bearish" and block.is_bearish:
                if current_price <= block.high:
                    active.append(block)

        return active

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        if len(candles) < 50:
            return None

        df = self.calculate_indicators(candles)

        if df.empty:
            return None

        self.order_blocks = detect_order_blocks(
            df, volume_threshold=self.volume_threshold
        )

        current = df.iloc[-1]
        close = current["close"]

        market_condition = self.detect_market_condition(df)

        above_sweep, below_sweep = detect_liquidity_sweep(df)

        rsi = current["rsi"]
        volume = current["volume"]
        volume_ma = current["volume_ma"]
        atr = current["atr"]

        has_volume = volume > volume_ma

        rsi_div = detect_rsi_divergence(df["close"], df["rsi"], 5)

        bullish_candle = close > current["open"]
        bearish_candle = close < current["open"]

        active_bullish = self.find_active_blocks(close, "bullish")
        active_bearish = self.find_active_blocks(close, "bearish")

        in_bullish_ob = any(ob.contains(close) for ob in active_bullish)
        in_bearish_ob = any(ob.contains(close) for ob in active_bearish)

        if has_volume:
            if in_bullish_ob and below_sweep:
                rsi_oversold = rsi < self.rsi_oversold
                has_divergence = rsi_div["bullish"]

                if rsi_oversold or has_divergence:
                    if bullish_candle:
                        self.last_signal = "BUY"
                        self.entry_price = close

                        if active_bullish:
                            recent = active_bullish[0]
                            self.stop_loss = recent.low - (self.atr_sl_multiplier * atr)
                        else:
                            self.stop_loss = close - (self.atr_sl_multiplier * atr)

                        risk = abs(self.entry_price - self.stop_loss)
                        self.take_profit = close + (self.risk_reward_ratio * risk)

                        logger.info(
                            f"BUY: Bullish OB + liquidity sweep + RSI/divergence + volume"
                        )
                        return "BUY"

            elif in_bearish_ob and above_sweep:
                rsi_overbought = rsi > self.rsi_overbought
                has_divergence = rsi_div["bearish"]

                if rsi_overbought or has_divergence:
                    if bearish_candle:
                        self.last_signal = "SELL"
                        self.entry_price = close

                        if active_bearish:
                            recent = active_bearish[0]
                            self.stop_loss = recent.high + (
                                self.atr_sl_multiplier * atr
                            )
                        else:
                            self.stop_loss = close + (self.atr_sl_multiplier * atr)

                        risk = abs(self.entry_price - self.stop_loss)
                        self.take_profit = close - (self.risk_reward_ratio * risk)

                        logger.info(
                            f"SELL: Bearish OB + liquidity sweep + RSI/divergence + volume"
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
    """Master strategy integrating trend, VWAP, and order block strategies."""

    def __init__(
        self,
        capital: float = 25000.0,
        order_block_strategy: Optional[OrderBlockStrategy] = None,
        trend_strategy: Any = None,
        vwap_strategy: Any = None,
    ):
        self.name = "MasterStrategy"
        self.capital = capital
        self.ob_strategy = order_block_strategy or OrderBlockStrategy(capital=capital)
        self.trend_strategy = trend_strategy
        self.vwap_strategy = vwap_strategy

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
        """Generate signals based on priority: OB > Trend > VWAP."""
        if len(candles) < 50:
            return None

        df = candles.copy()

        market_condition = self.detect_market_condition(df)
        self.current_mode = market_condition

        signal = self.ob_strategy.generate_signal(candles)
        if signal:
            logger.info(f"OB Strategy signal: {signal}")
            self.last_signal = signal
            self.entry_price = self.ob_strategy.entry_price
            self.stop_loss = self.ob_strategy.stop_loss
            self.take_profit = self.ob_strategy.take_profit
            return signal

        if market_condition in ["trending_up", "trending_down", "weak_trend"]:
            if self.trend_strategy:
                signal = self.trend_strategy.generate_signal(candles)
                if signal:
                    logger.info(f"Trend Strategy signal: {signal}")
                    self.last_signal = signal
                    self.entry_price = self.trend_strategy.entry_price
                    self.stop_loss = self.trend_strategy.stop_loss
                    self.take_profit = self.trend_strategy.take_profit
                    return signal

        elif market_condition == "sideways":
            if self.vwap_strategy:
                signal = self.vwap_strategy.generate_signal(candles)
                if signal:
                    logger.info(f"VWAP Strategy signal: {signal}")
                    self.last_signal = signal
                    self.entry_price = self.vwap_strategy.entry_price
                    self.stop_loss = self.vwap_strategy.stop_loss
                    self.take_profit = self.vwap_strategy.take_profit
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

            if hasattr(self.strategy, "generate_signals"):
                signal = self.strategy.generate_signals(current_df)
            else:
                signal = (
                    self.strategy.generate_signal(current_df)
                    if hasattr(self.strategy, "generate_signal")
                    else None
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

    def _execute_exit(self, idx: int, exit_price: float, reason: str, exit_time):
        position = self.positions[idx]

        if position["direction"] == "BUY":
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
        else:
            pnl = (position["entry_price"] - exit_price) * position["quantity"]

        pnl -= self.brokerage

        self.cash += exit_price * position["quantity"] + pnl

        self.trades[idx].update(
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
    "type": "Smart Money / Order Block",
    "indicators": ["Order Blocks", "RSI", "Volume", "Liquidity Sweep"],
    "entry": {
        "buy": "Bullish OB + liquidity sweep below + RSI divergence + volume",
        "sell": "Bearish OB + liquidity sweep above + RSI divergence + volume",
    },
    "exit": {
        "buy": "Opposite signal or SL/TP hit",
        "sell": "Opposite signal or SL/TP hit",
    },
    "filters": {
        "mitigation": "ignore mitigated OB",
        "volume": "Above 20-period average",
        "momentum": "RSI <30/>70 or divergence",
    },
    "risk_management": {
        "stop_loss": "below/above OB zone or 1.2×ATR",
        "take_profit": "2.0× Risk (RR 1:2)",
        "position_sizing": "Capital / Entry Price",
    },
}

"""
Master Strategy Engine

Unified trading system combining:
- Trend Strategy (EMA alignment + Supertrend)
- Breakout Strategy (Trendline + Structure)
- Momentum Strategy (RSI Divergence)
- Mean Reversion Strategy (VWAP)
- Smart Money Strategy (Order Blocks)

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
import logging

from .base_strategy import BaseStrategy
from ..indicators.supertrend import supertrend as calculate_supertrend
from ..indicators.trendline import calculate_trendline_channels, identify_pivots
from ..core.indicators import (
    calculate_rsi,
    detect_rsi_divergence,
    calculate_vwap_bands,
    calculate_atr,
    calculate_ema,
    calculate_volume_ma,
    is_volume_spike,
)
from ..core.market_condition import (
    detect_market_condition,
    detect_market_structure,
    is_trending_market,
    is_sideways_market,
)
from ..core.position_manager import create_managed_signal

logger = logging.getLogger(__name__)


class MasterStrategy(BaseStrategy):
    """
    Unified Master Strategy.

    Priority:
    1. Order Block (highest precision)
    2. Trend + Breakout (trending market)
    3. VWAP Mean Reversion (sideways market)
    """

    def __init__(
        self,
        capital: float = 25000.0,
        ema_periods: List[int] = None,
        atr_period: int = 10,
        supertrend_multiplier: float = 3.0,
        rsi_period: int = 14,
        volume_ma_period: int = 20,
        risk_reward_ratio: float = 2.0,
        atr_sl_multiplier: float = 1.5,
        enable_order_blocks: bool = True,
        enable_vwap: bool = True,
        enable_supertrend: bool = True,
    ):
        super().__init__(name="MasterStrategy", capital=capital)

        self.ema_periods = ema_periods or [20, 50, 100, 200]
        self.atr_period = atr_period
        self.supertrend_multiplier = supertrend_multiplier
        self.rsi_period = rsi_period
        self.volume_ma_period = volume_ma_period
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_sl_multiplier = atr_sl_multiplier

        self.enable_order_blocks = enable_order_blocks
        self.enable_vwap = enable_vwap
        self.enable_supertrend = enable_supertrend

        self.last_signal = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.position_config = None
        self.signal_reason = None
        self.confidence = "low"

        self.order_blocks: List[Dict] = []

    def calculate_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators."""
        df = candles.copy()

        for period in self.ema_periods:
            df[f"ema_{period}"] = calculate_ema(df["close"], period)

        df["atr"] = calculate_atr(df, self.atr_period)
        df["volume_ma"] = calculate_volume_ma(df, self.volume_ma_period)
        df["rsi"] = calculate_rsi(df["close"], self.rsi_period)

        vwap_df = calculate_vwap_bands(df)
        df["vwap"] = vwap_df["vwap"]
        df["vwap_upper_2"] = vwap_df["vwap_upper_2"]
        df["vwap_lower_2"] = vwap_df["vwap_lower_2"]

        pivot_highs, pivot_lows = identify_pivots(df, 5)
        df["is_pivot_high"] = pivot_highs
        df["is_pivot_low"] = pivot_lows

        trendline_df = calculate_trendline_channels(df, 14)
        df["trendline_upper"] = trendline_df["trendline_upper"]
        df["trendline_lower"] = trendline_df["trendline_lower"]

        supertrend_df = calculate_supertrend(
            df[["open", "high", "low", "close"]].copy(),
            period=self.atr_period,
            multiplier=self.supertrend_multiplier,
        )
        if not supertrend_df.empty:
            df["supertrend"] = supertrend_df["supertrend"]
            df["trend_direction"] = supertrend_df["trend_direction"]

        return df

    def detect_order_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """Detect order blocks."""
        if not self.enable_order_blocks:
            return []

        blocks = []
        volume_ma = df["volume_ma"].iloc[-1]
        current_volume = df["volume"].iloc[-1]

        if current_volume > volume_ma * 1.5:
            if len(df) > 5:
                future_move = df["close"].iloc[-1] - df["close"].iloc[-5]

                if future_move > 0 and df["close"].iloc[-1] < df["open"].iloc[-1]:
                    blocks.append(
                        {
                            "type": "bullish",
                            "high": df["high"].iloc[-1],
                            "low": df["low"].iloc[-1],
                            "volume": current_volume,
                        }
                    )
                elif future_move < 0 and df["close"].iloc[-1] > df["open"].iloc[-1]:
                    blocks.append(
                        {
                            "type": "bearish",
                            "high": df["high"].iloc[-1],
                            "low": df["low"].iloc[-1],
                            "volume": current_volume,
                        }
                    )

        return blocks

    def is_at_vwap_extreme(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Check if price at VWAP band extremes."""
        close = df["close"].iloc[-1]
        upper = df["vwap_upper_2"].iloc[-1]
        lower = df["vwap_lower_2"].iloc[-1]

        at_lower = not pd.isna(lower) and close <= lower
        at_upper = not pd.isna(upper) and close >= upper

        return at_lower, at_upper

    def check_trend_breakout(self, df: pd.DataFrame) -> Tuple[bool, bool]:
        """Check for trendline breakout."""
        if len(df) < 2:
            return False, False

        current = df.iloc[-1]
        prev = df.iloc[-2]

        upper = current.get("trendline_upper")
        lower = current.get("trendline_lower")

        prev_upper = prev.get("trendline_upper")
        prev_lower = prev.get("trendline_lower")

        breakout_up = False
        breakout_down = False

        if not pd.isna(upper) and not pd.isna(prev_upper):
            breakout_up = current["close"] > upper and prev["close"] <= prev_upper

        if not pd.isna(lower) and not pd.isna(prev_lower):
            breakout_down = current["close"] < lower and prev["close"] >= prev_lower

        return breakout_up, breakout_down

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        """Generate unified trading signal."""
        if len(candles) < 50:
            return None

        df = self.calculate_indicators(candles)

        if df.empty:
            return None

        market_condition = detect_market_condition(df)
        structure = detect_market_structure(df)

        current = df.iloc[-1]
        close = current["close"]
        atr = current["atr"]
        volume = current["volume"]
        volume_ma = current["volume_ma"]
        rsi = current["rsi"]

        has_volume = volume > volume_ma

        breakout_up, breakout_down = self.check_trend_breakout(df)

        rsi_div = detect_rsi_divergence(df["close"], df["rsi"], 5)

        trend_dir = current.get("trend_direction", 0)

        bullish_candle = close > current["open"]
        bearish_candle = close < current["open"]

        if self.enable_order_blocks:
            self.order_blocks = self.detect_order_blocks(df)

        if self.enable_order_blocks and self.order_blocks:
            for ob in self.order_blocks:
                in_bullish_ob = (
                    ob["type"] == "bullish" and ob["low"] <= close <= ob["high"]
                )
                in_bearish_ob = (
                    ob["type"] == "bearish" and ob["low"] <= close <= ob["high"]
                )

                if in_bullish_ob and has_volume:
                    if rsi_div["bullish"] or rsi < 35:
                        if bullish_candle:
                            self.last_signal = "BUY"
                            self.entry_price = close
                            self.stop_loss = ob["low"] - (self.atr_sl_multiplier * atr)
                            self.take_profit = close + (
                                self.risk_reward_ratio * self.atr_sl_multiplier * atr
                            )
                            self.signal_reason = "Order Block + RSI bullish"
                            self.confidence = "high"
                            self.position_config = create_managed_signal(
                                candles,
                                "BUY",
                                self.entry_price,
                                self.stop_loss,
                                capital=self.capital,
                                risk_per_trade=0.02,
                                tp1_ratio=1.0,
                                tp2_ratio=2.0,
                            )
                            logger.info(
                                f"BUY: Order Block + RSI - {self.signal_reason}"
                            )
                            return "BUY"

                if in_bearish_ob and has_volume:
                    if rsi_div["bearish"] or rsi > 65:
                        if bearish_candle:
                            self.last_signal = "SELL"
                            self.entry_price = close
                            self.stop_loss = ob["high"] + (self.atr_sl_multiplier * atr)
                            self.take_profit = close - (
                                self.risk_reward_ratio * self.atr_sl_multiplier * atr
                            )
                            self.signal_reason = "Order Block + RSI bearish"
                            self.confidence = "high"
                            self.position_config = create_managed_signal(
                                candles,
                                "SELL",
                                self.entry_price,
                                self.stop_loss,
                                capital=self.capital,
                                risk_per_trade=0.02,
                                tp1_ratio=1.0,
                                tp2_ratio=2.0,
                            )
                            logger.info(
                                f"SELL: Order Block + RSI - {self.signal_reason}"
                            )
                            return "SELL"

        if market_condition in ["trending_up", "trending_down"]:
            if breakout_up and bullish_candle:
                ema_aligned = market_condition == "trending_up"

                if (
                    ema_aligned
                    and trend_dir == 1
                    and structure == "hh_hl"
                    and has_volume
                ):
                    self.last_signal = "BUY"
                    self.entry_price = close
                    self.stop_loss = close - (self.atr_sl_multiplier * atr)
                    self.take_profit = close + (
                        self.risk_reward_ratio * self.atr_sl_multiplier * atr
                    )
                    self.signal_reason = "Trend breakout + EMA aligned + structure"
                    self.confidence = "high"
                    self.position_config = create_managed_signal(
                        candles,
                        "BUY",
                        self.entry_price,
                        self.stop_loss,
                        capital=self.capital,
                        risk_per_trade=0.02,
                        tp1_ratio=1.0,
                        tp2_ratio=2.0,
                    )
                    logger.info(f"BUY: Trend breakout - {self.signal_reason}")
                    return "BUY"

            if breakout_down and bearish_candle:
                ema_aligned = market_condition == "trending_down"

                if (
                    ema_aligned
                    and trend_dir == -1
                    and structure == "lh_ll"
                    and has_volume
                ):
                    self.last_signal = "SELL"
                    self.entry_price = close
                    self.stop_loss = close + (self.atr_sl_multiplier * atr)
                    self.take_profit = close - (
                        self.risk_reward_ratio * self.atr_sl_multiplier * atr
                    )
                    self.signal_reason = "Trend breakout + EMA aligned + structure"
                    self.confidence = "high"
                    self.position_config = create_managed_signal(
                        candles,
                        "SELL",
                        self.entry_price,
                        self.stop_loss,
                        capital=self.capital,
                        risk_per_trade=0.02,
                        tp1_ratio=1.0,
                        tp2_ratio=2.0,
                    )
                    logger.info(f"SELL: Trend breakout - {self.signal_reason}")
                    return "SELL"

        if self.enable_vwap and market_condition == "sideways":
            at_lower, at_upper = self.is_at_vwap_extreme(df)

            if at_lower and has_volume:
                if rsi < 35 or rsi_div["bullish"]:
                    if bullish_candle:
                        self.last_signal = "BUY"
                        self.entry_price = close
                        self.stop_loss = current["vwap_lower_2"] - (
                            self.atr_sl_multiplier * atr
                        )
                        self.take_profit = current["vwap"]
                        self.signal_reason = "VWAP lower band + RSI oversold"
                        self.confidence = "medium"
                        self.position_config = create_managed_signal(
                            candles,
                            "BUY",
                            self.entry_price,
                            self.stop_loss,
                            capital=self.capital,
                            risk_per_trade=0.02,
                            tp1_ratio=1.0,
                            tp2_ratio=1.5,
                        )
                        logger.info(f"BUY: VWAP mean reversion - {self.signal_reason}")
                        return "BUY"

            if at_upper and has_volume:
                if rsi > 65 or rsi_div["bearish"]:
                    if bearish_candle:
                        self.last_signal = "SELL"
                        self.entry_price = close
                        self.stop_loss = current["vwap_upper_2"] + (
                            self.atr_sl_multiplier * atr
                        )
                        self.take_profit = current["vwap"]
                        self.signal_reason = "VWAP upper band + RSI overbought"
                        self.confidence = "medium"
                        self.position_config = create_managed_signal(
                            candles,
                            "SELL",
                            self.entry_price,
                            self.stop_loss,
                            capital=self.capital,
                            risk_per_trade=0.02,
                            tp1_ratio=1.0,
                            tp2_ratio=1.5,
                        )
                        logger.info(f"SELL: VWAP mean reversion - {self.signal_reason}")
                        return "SELL"

        return None

    def get_risk_levels(self) -> Dict[str, Any]:
        """Get risk management levels."""
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
            "confidence": self.confidence,
            "reason": self.signal_reason,
            "position_config": self.position_config,
        }

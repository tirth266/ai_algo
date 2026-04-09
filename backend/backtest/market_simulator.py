"""
Realistic Indian Market Simulator
==================================

Replaces pure Gaussian noise with statistically accurate NSE/BSE market behaviour.

Market microstructure features implemented:
────────────────────────────────────────────
1.  Fat tails            – Student-t distribution (ν ≈ 3–5), not Normal
2.  Volatility clustering – GARCH(1,1) envelope so volatile periods cluster
3.  Gap opens            – Overnight and session gaps (random ±0.2–2 %)
4.  Circuit breakers     – Hard ±10 % intraday price limit per candle
5.  Trend / sideways phases – Regime switching via Markov two-state model
6.  NSE session mask     – Only 09:15–15:30 IST candles; skip weekends / holidays
7.  Intraday volume profile – Volume spikes at open and close (U-shaped)
8.  Tick size rounding   – Prices rounded to nearest ₹ 0.05

Symbol profiles match rough real-world characteristics:
    NIFTY50   ≈ index ~22 000, vol 0.8 %/day
    BANKNIFTY ≈ index ~47 000, vol 1.2 %/day
    RELIANCE  ≈ large-cap   ~2 900, vol 1.5 %/day
    INFY      ≈ large-cap   ~1 500, vol 1.4 %/day
    TATASTEEL ≈ cyclical     ~140,  vol 2.2 %/day

Usage::

    from backtest.market_simulator import IndianMarketSimulator

    sim = IndianMarketSimulator(symbol='NIFTY50', timeframe='5minute', seed=42)
    df  = sim.generate(start_date='2024-01-01', end_date='2024-06-30')
    print(df.head())          # standard OHLCV DataFrame
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

# ─── NSE trading calendar helpers ──────────────────────────────────────────────
# A minimal set of fixed NSE holidays (expand as needed)
_NSE_FIXED_HOLIDAYS_2024_2025 = {
    date(2024, 1, 22),  # Ram Mandir
    date(2024, 1, 26),  # Republic Day
    date(2024, 3, 25),  # Holi
    date(2024, 3, 29),  # Good Friday
    date(2024, 4, 14),  # Ambedkar Jayanti / Dr BR Ambedkar Jayanti
    date(2024, 4, 17),  # Ram Navami
    date(2024, 4, 21),  # Mahavir Jayanti
    date(2024, 5, 23),  # Buddha Purnima
    date(2024, 6, 17),  # Eid ul-Adha
    date(2024, 8, 15),  # Independence Day
    date(2024, 10, 2),  # Gandhi Jayanti
    date(2024, 10, 14), # Dussehra
    date(2024, 11, 1),  # Diwali Muhurat
    date(2024, 11, 15), # Gurunanak Jayanti
    date(2024, 12, 25), # Christmas
    date(2025, 1, 26),  # Republic Day
    date(2025, 3, 14),  # Holi
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 12),  # Buddha Purnima
    date(2025, 8, 15),  # Independence Day
    date(2025, 10, 2),  # Gandhi Jayanti
}


def _is_trading_day(d: date) -> bool:
    """Return True if *d* is a valid NSE trading day."""
    return d.weekday() < 5 and d not in _NSE_FIXED_HOLIDAYS_2024_2025


# ─── Symbol profiles ────────────────────────────────────────────────────────────

# Keys: symbol → (base_price, annual_vol_frac, t_df, tick_size)
# annual_vol_frac: annualised vol as a fraction (e.g. 0.18 = 18 %)
# t_df:            degrees-of-freedom for Student-t fat tails
_SYMBOL_PROFILES: dict[str, tuple[float, float, float, float]] = {
    "NIFTY50":    (22_500.0, 0.12, 4.0, 0.05),
    "NIFTY":      (22_500.0, 0.12, 4.0, 0.05),
    "BANKNIFTY":  (47_000.0, 0.18, 3.5, 0.05),
    "RELIANCE":   ( 2_900.0, 0.22, 4.5, 0.05),
    "INFY":       ( 1_500.0, 0.20, 4.5, 0.05),
    "TCS":        ( 4_000.0, 0.18, 4.5, 0.05),
    "HDFCBANK":   ( 1_700.0, 0.20, 4.0, 0.05),
    "SBIN":       (   800.0, 0.28, 3.5, 0.05),
    "TATASTEEL":  (   140.0, 0.35, 3.5, 0.05),
    "ICICIBANK":  ( 1_250.0, 0.22, 4.0, 0.05),
    "WIPRO":      (   500.0, 0.22, 4.5, 0.05),
    "ADANIENT":   ( 2_500.0, 0.45, 3.0, 0.05),
    # Generic fallback is computed from symbol hash
}

# Intraday U-shaped volume profile: 5-min block → weight factor
# 90 blocks × 5 min = 375 min = 6.25 h NSE session
_VOLUME_PROFILE_WEIGHTS = np.concatenate([
    np.linspace(2.5, 1.0, 18),   # first  90 min: open spike dies
    np.ones(54) * 0.7,            # middle 270 min: quiet
    np.linspace(0.7, 3.0, 18),   # last   90 min: close ramp-up
])  # shape (90,)


# ─── Main simulator class ───────────────────────────────────────────────────────

class IndianMarketSimulator:
    """
    Generates realistic NSE/BSE OHLCV candle data.

    Parameters
    ----------
    symbol : str
        Ticker symbol (case-insensitive).  Known symbols use calibrated
        parameters; unknown symbols get plausible defaults derived from
        the symbol hash.
    timeframe : str
        Candle width — one of ``'1minute'``, ``'5minute'``, ``'15minute'``,
        ``'30minute'``, ``'60minute'``, ``'1day'``.
    seed : int | None
        Random seed for reproducibility.  ``None`` → random each run.
    """

    _TIMEFRAME_MINUTES = {
        "1minute":  1,
        "5minute":  5,
        "15minute": 15,
        "30minute": 30,
        "60minute": 60,
        "1day":     375,   # treated as daily candles
    }

    # GARCH(1,1) default parameters (calibrated to NSE intraday)
    _GARCH_ALPHA = 0.10   # news / shock weight
    _GARCH_BETA  = 0.85   # persistence
    _GARCH_OMEGA_SCALE = 0.05  # fraction of long-run var

    # Circuit-breaker hard limit per candle
    _CIRCUIT_LIMIT = 0.10   # ±10 %

    # Regime definition: (trend_drift_per_day, sideways_vol_mul, switch_prob)
    _REGIME_TREND   = (0.0008,  1.0)   # (daily drift, vol multiplier)
    _REGIME_SIDEWAYS = (0.0,    0.6)   # lower vol in sideways
    _REGIME_SWITCH_PROB = 0.02         # prob of regime switch per candle

    def __init__(
        self,
        symbol:    str = "NIFTY50",
        timeframe: str = "5minute",
        seed:      Optional[int] = None,
    ):
        self.symbol    = symbol.upper()
        self.timeframe = timeframe
        self.rng       = np.random.default_rng(seed)

        mins_per_candle = self._TIMEFRAME_MINUTES.get(timeframe, 5)
        self.is_daily   = (timeframe == "1day")
        self.mins_per_candle = mins_per_candle

        # Load (or derive) symbol profile
        self._load_profile()

        # Annualised vol → per-candle vol
        # Convention: 252 trading days, 75 × 5-min candles/day
        candles_per_year = (252 * 375) / mins_per_candle
        self.candle_vol = self.annual_vol / np.sqrt(candles_per_year)

        logger.info(
            f"IndianMarketSimulator | {self.symbol} | {timeframe} | "
            f"base=₹{self.base_price:,.0f} | "
            f"vol={self.annual_vol*100:.1f}%/yr | "
            f"t-df={self.t_df:.1f}"
        )

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _load_profile(self):
        if self.symbol in _SYMBOL_PROFILES:
            self.base_price, self.annual_vol, self.t_df, self.tick = (
                _SYMBOL_PROFILES[self.symbol]
            )
        else:
            # Derive plausible defaults from symbol hash
            h = hash(self.symbol) % 10_000
            self.base_price = float(500 + h % 3_000)
            self.annual_vol = 0.15 + (h % 30) / 100.0   # 15–45 %
            self.t_df       = 4.0
            self.tick       = 0.05
            logger.info(
                f"Unknown symbol '{self.symbol}' — derived profile: "
                f"price=₹{self.base_price:.0f}, vol={self.annual_vol*100:.1f}%"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        start_date:  str | datetime,
        end_date:    str | datetime,
        start_price: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Generate a realistic OHLCV DataFrame.

        Parameters
        ----------
        start_date : str | datetime
            Simulation start (``'YYYY-MM-DD'`` or datetime object).
        end_date : str | datetime
            Simulation end (inclusive).
        start_price : float | None
            Opening price for the first candle.  Defaults to the symbol's
            calibrated base price.

        Returns
        -------
        pd.DataFrame
            Index: ``pandas.DatetimeIndex`` (IST timezone-aware)
            Columns: ``open``, ``high``, ``low``, ``close``, ``volume``
        """
        # Parse dates
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        price = float(start_price or self.base_price)

        # Build timestamp grid
        timestamps = self._build_timestamp_grid(start_date, end_date)
        if not timestamps:
            logger.warning("No trading timestamps in requested date range")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        n = len(timestamps)
        logger.info(f"Simulating {n} candles [{start_date.date()} → {end_date.date()}]")

        # ── Generate return series (GARCH + fat tails + regime) ──────────────
        returns = self._generate_returns(n)

        # ── Build OHLCV candles ───────────────────────────────────────────────
        rows = self._build_candles(returns, price, timestamps)

        df = pd.DataFrame(rows, index=pd.DatetimeIndex(timestamps))
        df.index.name = "timestamp"
        df = df.sort_index()

        logger.info(
            f"Generated {len(df)} candles | "
            f"price range ₹{df['low'].min():,.2f}–₹{df['high'].max():,.2f}"
        )
        return df

    # ── Internal generators ───────────────────────────────────────────────────

    def _build_timestamp_grid(
        self,
        start: datetime,
        end:   datetime,
    ) -> list[pd.Timestamp]:
        """Build IST-aware timestamps for every valid candle in the period."""
        tz = "Asia/Kolkata"
        freq = f"{self.mins_per_candle}T"

        if self.is_daily:
            # Daily: one candle per trading day at 15:30 IST
            stamps = []
            d = start.date()
            while d <= end.date():
                if _is_trading_day(d):
                    stamps.append(
                        pd.Timestamp(d.year, d.month, d.day, 15, 30, tz=tz)
                    )
                d += timedelta(days=1)
            return stamps

        # Intraday: candles from 09:15 to 15:30 IST on each trading day
        stamps = []
        session_start_h, session_start_m = 9, 15
        session_end_h,   session_end_m   = 15, 30

        d = start.date()
        while d <= end.date():
            if _is_trading_day(d):
                t = pd.Timestamp(
                    d.year, d.month, d.day,
                    session_start_h, session_start_m,
                    tz=tz,
                )
                end_ts = pd.Timestamp(
                    d.year, d.month, d.day,
                    session_end_h, session_end_m,
                    tz=tz,
                )
                while t <= end_ts:
                    stamps.append(t)
                    t += pd.Timedelta(minutes=self.mins_per_candle)
            d += timedelta(days=1)

        return stamps

    def _generate_returns(self, n: int) -> np.ndarray:
        """
        Generate *n* per-candle log-returns with:

        • GARCH(1,1) conditional variance
        • Student-t innovations (fat tails)
        • Regime switching (trend ↔ sideways via Markov chain)
        • Gap-open shocks between sessions
        """
        alpha = self._GARCH_ALPHA
        beta  = self._GARCH_BETA
        omega = (1 - alpha - beta) * (self.candle_vol ** 2)   # long-run var

        # Student-t innovations (mean-zero, unit-variance)
        t_innov = stats.t.rvs(df=self.t_df, size=n, random_state=self.rng)
        t_innov = t_innov / np.sqrt(self.t_df / (self.t_df - 2))  # unit-var

        # GARCH variance path
        h = np.zeros(n)
        h[0] = self.candle_vol ** 2
        for i in range(1, n):
            h[i] = omega + alpha * (returns_raw := self.rng.normal(0, np.sqrt(h[i-1]))) ** 2 * 0 + \
                   alpha * h[i-1] * t_innov[i-1] ** 2 + beta * h[i-1]
            # (the line above is GARCH: ε²_{t-1} = h_{t-1} × z²_{t-1}

        # Recompute cleanly (avoid side-effect lambda above)
        h[0] = self.candle_vol ** 2
        for i in range(1, n):
            eps2_prev = h[i - 1] * (t_innov[i - 1] ** 2)
            h[i] = omega + alpha * eps2_prev + beta * h[i - 1]
        h = np.maximum(h, 1e-12)   # safety floor

        sigma = np.sqrt(h)

        # ── Regime switching ──────────────────────────────────────────────────
        # Two regimes: TREND (state 0) and SIDEWAYS (state 1)
        trend_drift    = self._REGIME_TREND[0]   * (self.mins_per_candle / 375)
        sideways_drift = self._REGIME_SIDEWAYS[0] * (self.mins_per_candle / 375)
        switch_prob    = self._REGIME_SWITCH_PROB

        regime    = 0                 # start in trending
        drift_arr = np.zeros(n)
        vol_mul   = np.ones(n)

        for i in range(n):
            if regime == 0:   # trending
                drift_arr[i] = trend_drift
                vol_mul[i]   = self._REGIME_TREND[1]
                if self.rng.random() < switch_prob:
                    regime = 1
            else:             # sideways
                drift_arr[i] = sideways_drift
                vol_mul[i]   = self._REGIME_SIDEWAYS[1]
                if self.rng.random() < switch_prob:
                    regime = 0

        # ── Gap opens between sessions ────────────────────────────────────────
        # Every ~75 candles (for 5-min) marks an overnight gap
        candles_per_session = max(1, 375 // self.mins_per_candle)
        gap_shocks = np.zeros(n)
        for i in range(0, n, candles_per_session):
            if self.rng.random() < 0.60:   # 60 % of sessions have a gap
                # Gap magnitude: 0.05–1.5 % with t-distribution tails
                gap_sign = self.rng.choice([-1, 1])
                gap_mag  = abs(float(stats.t.rvs(df=4, random_state=self.rng))) * 0.003
                gap_mag  = np.clip(gap_mag, 0.0005, 0.015)
                gap_shocks[i] = gap_sign * gap_mag

        # ── Combine ───────────────────────────────────────────────────────────
        raw_returns = drift_arr + vol_mul * sigma * t_innov + gap_shocks

        # ── Circuit breaker: clip per-candle return to ±10 % ─────────────────
        raw_returns = np.clip(raw_returns, -self._CIRCUIT_LIMIT, self._CIRCUIT_LIMIT)

        return raw_returns

    def _build_candles(
        self,
        returns:    np.ndarray,
        start_px:   float,
        timestamps: list,
    ) -> list[dict]:
        """
        Convert log-return series to OHLCV dictionaries.

        Strategy:
        - Close is derived from prev-close × exp(return).
        - Open has a small independent noise  ±σ/3 relative to prev-close.
        - High and Low use intrabar range proportional to σ/√2.
        - Volume follows the intraday U-shaped profile.
        """
        rows    = []
        price   = start_px
        n       = len(returns)
        candles_per_session = max(1, 375 // self.mins_per_candle)

        # Precompute volume profile tiling
        if not self.is_daily:
            profile = np.tile(
                _VOLUME_PROFILE_WEIGHTS[:candles_per_session],
                (n // candles_per_session) + 2,
            )[:n]
        else:
            profile = np.ones(n)

        base_vol = 500_000 if self.symbol in ("NIFTY50", "BANKNIFTY", "NIFTY") else 200_000

        for i in range(n):
            ret   = float(returns[i])
            close = price * np.exp(ret)

            # Open: small gap from previous close
            open_noise = float(self.rng.normal(0, self.candle_vol / 3))
            open_px    = price * np.exp(open_noise)

            # Intrabar range: proportional to candle σ
            intrabar_range = abs(ret) + self.candle_vol * abs(float(self.rng.normal(0, 0.5)))
            half_range     = intrabar_range / 2.0

            high = max(open_px, close) * np.exp(abs(half_range))
            low  = min(open_px, close) * np.exp(-abs(half_range))

            # Enforce: low ≤ open,close ≤ high
            high = max(high, open_px, close)
            low  = min(low,  open_px, close)

            # Circuit breaker on OHLC relative to previous close
            high  = min(high,  price * (1 + self._CIRCUIT_LIMIT))
            low   = max(low,   price * (1 - self._CIRCUIT_LIMIT))
            close = np.clip(close, low, high)
            open_px = np.clip(open_px, low, high)

            # Round to tick size
            def _tick(v):
                return round(round(v / self.tick) * self.tick, 4)

            open_px = _tick(max(open_px, self.tick))
            high    = _tick(max(high,    self.tick))
            low     = _tick(max(low,     self.tick))
            close   = _tick(max(close,   self.tick))

            # Ensure integer OHLC relationships after rounding
            high  = max(high, open_px, close)
            low   = min(low,  open_px, close)

            # Volume
            vol_weight = float(profile[i]) if not self.is_daily else 1.0
            vol = int(
                base_vol
                * vol_weight
                * (1 + abs(ret) / self.candle_vol)   # spike on volatile candles
                * float(self.rng.lognormal(0, 0.3))
            )

            rows.append({
                "open":   open_px,
                "high":   high,
                "low":    low,
                "close":  close,
                "volume": max(vol, 1),
            })

            price = close  # next candle opens from this close

        return rows

    # ── Convenience ───────────────────────────────────────────────────────────

    @classmethod
    def available_symbols(cls) -> list[str]:
        """Return list of pre-calibrated Indian market symbols."""
        return sorted(_SYMBOL_PROFILES.keys())

    def describe(self) -> dict:
        """Return a summary of the simulator's configuration."""
        return {
            "symbol":         self.symbol,
            "timeframe":      self.timeframe,
            "base_price":     self.base_price,
            "annual_vol_pct": round(self.annual_vol * 100, 2),
            "t_df":           self.t_df,
            "tick_size":      self.tick,
            "circuit_limit":  f"±{self._CIRCUIT_LIMIT*100:.0f}%",
            "features": [
                "fat_tails_t_distribution",
                "garch_volatility_clustering",
                "gap_opens",
                "circuit_breakers",
                "regime_switching_trend_sideways",
                "nse_session_mask",
                "intraday_volume_profile",
                "tick_rounding",
            ],
        }


# ─── NSE CSV loader ─────────────────────────────────────────────────────────────

class NSEDataLoader:
    """
    Load real historical NSE/BSE candle data from CSV files.

    Expected CSV format (header flexible — auto-detected)::

        timestamp,open,high,low,close,volume
        2024-01-02 09:15:00,22126.95,22177.35,22098.70,22160.90,1234567

    All column name variants (Date, date, Datetime, OPEN, …) are accepted.
    The loader normalises them to lowercase ``open / high / low / close / volume``.

    Parameters
    ----------
    data_dir : str
        Directory that contains CSV files.  File naming convention:
        ``{SYMBOL}_{TIMEFRAME}.csv``  (e.g. ``NIFTY50_5minute.csv``).
    """

    # Column alias map: lowercase alias → canonical name
    _COL_ALIASES = {
        "date":      "timestamp",
        "datetime":  "timestamp",
        "time":      "timestamp",
        "Date":      "timestamp",
        "Datetime":  "timestamp",
        "o":         "open",
        "h":         "high",
        "l":         "low",
        "c":         "close",
        "vol":       "volume",
        "qty":       "volume",
    }

    def __init__(self, data_dir: str = "backtest/data"):
        from pathlib import Path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"NSEDataLoader pointing at {self.data_dir.resolve()}")

    def load(
        self,
        symbol:     str,
        timeframe:  str,
        start_date: Optional[str | datetime] = None,
        end_date:   Optional[str | datetime] = None,
        filepath:   Optional[str]            = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load real data from CSV.

        Parameters
        ----------
        symbol : str
            Instrument name (case-insensitive).
        timeframe : str
            Candle width — used to locate the file if *filepath* is None.
        start_date, end_date : str | datetime | None
            Filter the loaded data to this window.
        filepath : str | None
            Override the auto-generated file path.

        Returns
        -------
        pd.DataFrame | None
            Standard OHLCV DataFrame or ``None`` if the file is absent.
        """
        from pathlib import Path

        if filepath:
            csv_path = Path(filepath)
        else:
            csv_path = self.data_dir / f"{symbol.upper()}_{timeframe}.csv"

        if not csv_path.exists():
            logger.warning(f"CSV not found: {csv_path}")
            return None

        try:
            df = pd.read_csv(csv_path)
            df = self._normalise_columns(df)
            df = self._parse_index(df)
            df = self._clean(df)

            if start_date is not None:
                sd = pd.Timestamp(start_date)
                if df.index.tz is not None and sd.tz is None:
                    sd = sd.tz_localize(df.index.tz)
                df = df[df.index >= sd]

            if end_date is not None:
                ed = pd.Timestamp(end_date)
                if df.index.tz is not None and ed.tz is None:
                    ed = ed.tz_localize(df.index.tz)
                df = df[df.index <= ed]

            logger.info(
                f"Loaded {len(df)} rows of real {symbol} {timeframe} data "
                f"from {csv_path.name}"
            )
            return df

        except Exception as exc:
            logger.error(f"Error loading {csv_path}: {exc}", exc_info=True)
            return None

    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename variant column names to canonical lowercase."""
        df = df.rename(columns={k: v for k, v in self._COL_ALIASES.items() if k in df.columns})
        df.columns = [c.lower().strip() for c in df.columns]
        required = {"open", "high", "low", "close", "volume"}
        missing  = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns after normalisation: {missing}")
        return df

    def _parse_index(self, df: pd.DataFrame) -> pd.DataFrame:
        ts_col = next(
            (c for c in ["timestamp", "date", "datetime", "time"] if c in df.columns),
            None,
        )
        if ts_col:
            df[ts_col] = pd.to_datetime(df[ts_col], dayfirst=True)
            df.set_index(ts_col, inplace=True)
            df.index.name = "timestamp"
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            df.index.name = "timestamp"
        df.sort_index(inplace=True)
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df[~df.index.duplicated(keep="first")]
        df["volume"] = df["volume"].fillna(0).astype(int)
        # Enforce H ≥ O,C ≥ L after any coercion
        df["high"]  = df[["open", "high",  "close"]].max(axis=1)
        df["low"]   = df[["open", "low",   "close"]].min(axis=1)
        return df


# ─── Unified smart loader (replaces _generate_mock_data) ────────────────────────

class SmartDataLoader:
    """
    Priority-ordered data source:

    1. Real CSV files in *data_dir* (``{SYMBOL}_{TIMEFRAME}.csv``)
    2. Realistic simulation via :class:`IndianMarketSimulator`

    Dropped: pure Gaussian noise (the old ``_generate_mock_data``).

    Parameters
    ----------
    data_dir : str
        Directory to search for real CSV data.
    cache_dir : str
        Directory to cache generated / loaded data.
    """

    def __init__(
        self,
        data_dir:  str = "backtest/data",
        cache_dir: str = "backtest/cache",
    ):
        self.nse_loader = NSEDataLoader(data_dir)
        from pathlib import Path
        self.cache_dir  = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(
        self,
        symbol:     str,
        timeframe:  str,
        start_date: str | datetime,
        end_date:   str | datetime,
        seed:       Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Return the best available data for *symbol* / *timeframe*.

        Tries real CSV first; falls back to realistic simulation.
        """
        # 1. Try real data
        real = self.nse_loader.load(symbol, timeframe, start_date, end_date)
        if real is not None and len(real) >= 50:
            logger.info(f"Using REAL data for {symbol} ({len(real)} bars)")
            return real

        # 2. Realistic simulation
        logger.info(
            f"Real data unavailable — using IndianMarketSimulator for "
            f"{symbol} ({timeframe})"
        )
        sim = IndianMarketSimulator(symbol=symbol, timeframe=timeframe, seed=seed)
        df  = sim.generate(start_date=start_date, end_date=end_date)

        if df is not None and len(df) > 0:
            # Persist so next run uses the cache
            cache_file = self._cache_path(symbol, timeframe, start_date, end_date)
            try:
                df.to_pickle(cache_file)
                logger.info(f"Cached simulated data → {cache_file}")
            except Exception:
                pass

        return df

    def _cache_path(self, symbol, timeframe, start_date, end_date):
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y%m%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y%m%d")
        return self.cache_dir / f"{symbol}_{timeframe}_{start_date}_{end_date}_sim.pkl"


# ─── Quick-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("\n" + "=" * 68)
    print("  IndianMarketSimulator — Feature Verification")
    print("=" * 68)

    for sym in ["NIFTY50", "BANKNIFTY", "RELIANCE", "TATASTEEL"]:
        sim = IndianMarketSimulator(symbol=sym, timeframe="5minute", seed=0)
        df  = sim.generate("2024-01-02", "2024-03-31")

        # Basic stats
        log_rets = np.log(df["close"] / df["close"].shift(1)).dropna()
        kurt     = float(log_rets.kurtosis())
        ann_vol  = float(log_rets.std() * np.sqrt(252 * 75))
        gaps     = (df["open"] - df["close"].shift(1)).dropna()
        gap_pct  = float((gaps.abs() > 0.0005 * df["close"].mean()).mean() * 100)

        print(f"\n  {sym:12s}  bars={len(df):5d}  ann_vol={ann_vol*100:5.1f}%  "
              f"excess_kurt={kurt:.2f}  gap_sessions={gap_pct:.1f}%")
        print(f"   price ₹{df['close'].min():,.2f}–₹{df['close'].max():,.2f}")
        # Show session-open timestamps
        first_5 = df.index[:5].tolist()
        print(f"   first candles: {[str(t)[:19] for t in first_5]}")

    print("\n" + "=" * 68)
    print("  Available symbols:", IndianMarketSimulator.available_symbols())
    print("=" * 68 + "\n")
